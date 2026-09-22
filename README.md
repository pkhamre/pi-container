# Pi Container

Run Pi’s coding-agent CLI in a locked-down Docker or Podman container. The
current host directory is the only project directory mounted read-write.

## Prerequisites

- Docker or Podman
- GNU Make for build targets
- `curl` and `jq` for `make build-latest`

## Build and run

```sh
make build
mkdir -p ~/.pi-container/secrets
chmod 700 ~/.pi-container/secrets
printf '%s\n' 'your-token' > ~/.pi-container/secrets/anthropic_api_key
chmod 600 ~/.pi-container/secrets/anthropic_api_key
bin/pi-container
```

The default image is `pi-container:latest`. Add `bin/` to `PATH` to invoke
`pi-container` from any directory.

```sh
export PATH="$PWD/bin:$PATH"
pi-container --version
pi-container --print "list the files in this project"
PI_WORKSPACE=/path/to/project pi-container
```

All arguments other than the launcher options are passed directly to `pi`.
Pi’s own options include `--print`, `--mode json`, `--provider`, `--model`,
`--continue`, `--resume`, and `--offline`.

## Launcher options

| Option | Default | Meaning |
|---|---:|---|
| `--memory VALUE` | `4g` | Container memory limit |
| `--cpus VALUE` | `4` | Container CPU limit |
| `--host-access` | off | Add the engine host gateway; prints a warning |

Set `CONTAINER_ENGINE=docker` or `CONTAINER_ENGINE=podman`. Without it, Podman
is preferred, then Docker. `PI_WORKSPACE` overrides the current directory.

## Persistent state

The launcher stores Pi state below `~/.pi-container/state` and mounts it at
`/app/.pi`. With `HOME=/app`, Pi therefore uses its native paths, including:

- `~/.pi/agent/auth.json` — auth state
- `~/.pi/agent/settings.json` — settings
- `~/.pi/agent/sessions/` — session history
- `~/.pi/agent/extensions/`, `skills/`, `prompts/`, and `themes/`
- `~/.pi/agent/models-store.json`, `trust.json`, and `crashes.json`

The entire host home directory is not mounted.

## Secrets

Secrets are files in `~/.pi-container/secrets`, mounted read-only at
`/run/secrets`. Unsupported files are ignored. Secret files must be regular
files, preferably mode `600`; the directory should be mode `700`.

Most files expose their contents as the corresponding environment variable.
The complete current provider mapping is:

```text
<provider_env_lowercase> -> <PROVIDER_ENV>
```

The exact value-secret mapping is:

| Filename | Environment variable |
|---|---|
| `anthropic_api_key`, `anthropic_auth_token`, `anthropic_oauth_token` | `ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN`, `ANTHROPIC_OAUTH_TOKEN` |
| `ant_ling_api_key` | `ANT_LING_API_KEY` |
| `openai_api_key` | `OPENAI_API_KEY` |
| `azure_openai_api_key` | `AZURE_OPENAI_API_KEY` |
| `deepseek_api_key`, `nvidia_api_key`, `gemini_api_key` | `DEEPSEEK_API_KEY`, `NVIDIA_API_KEY`, `GEMINI_API_KEY` |
| `google_cloud_api_key` | `GOOGLE_CLOUD_API_KEY` |
| `mistral_api_key`, `groq_api_key`, `cerebras_api_key`, `xai_api_key` | matching uppercase names |
| `radius_api_key`, `openrouter_api_key`, `ai_gateway_api_key` | matching uppercase names |
| `zai_api_key`, `zai_coding_cn_api_key` | `ZAI_API_KEY`, `ZAI_CODING_CN_API_KEY` |
| `minimax_api_key`, `minimax_cn_api_key`, `moonshot_api_key` | matching uppercase names |
| `hf_token`, `fireworks_api_key`, `together_api_key`, `baseten_api_key` | matching uppercase names |
| `opencode_api_key`, `kimi_api_key`, `meta_api_key` | matching uppercase names |
| `cloudflare_api_key`, `cloudflare_account_id`, `cloudflare_gateway_id` | matching uppercase names |
| `qwen_token_plan_api_key`, `qwen_token_plan_cn_api_key` | matching uppercase names |
| `xiaomi_api_key`, `xiaomi_token_plan_cn_api_key`, `xiaomi_token_plan_ams_api_key`, `xiaomi_token_plan_sgp_api_key` | matching uppercase names |
| `copilot_github_token` | `COPILOT_GITHUB_TOKEN` |
| `aws_profile`, `aws_access_key_id`, `aws_secret_access_key`, `aws_session_token` | matching uppercase names |
| `aws_bearer_token_bedrock`, `aws_region`, `aws_default_region` | matching uppercase names |
| `aws_bedrock_skip_auth`, `aws_bedrock_force_http1`, `aws_bedrock_force_cache` | matching uppercase names |
| `aws_container_credentials_relative_uri`, `aws_container_credentials_full_uri` | matching uppercase names |

Additional provider configuration filenames are mapped directly:

```text
azure_openai_base_url             AZURE_OPENAI_BASE_URL
azure_openai_resource_name        AZURE_OPENAI_RESOURCE_NAME
azure_openai_api_version          AZURE_OPENAI_API_VERSION
azure_openai_deployment_name_map  AZURE_OPENAI_DEPLOYMENT_NAME_MAP
google_cloud_project              GOOGLE_CLOUD_PROJECT
google_cloud_location             GOOGLE_CLOUD_LOCATION
aws_region                        AWS_REGION
```

File credentials remain file-backed and are never copied into an environment
value:

```text
google_application_credentials -> GOOGLE_APPLICATION_CREDENTIALS=/run/secrets/google_application_credentials
aws_web_identity_token_file    -> AWS_WEB_IDENTITY_TOKEN_FILE=/run/secrets/aws_web_identity_token_file
aws_shared_credentials_file    -> AWS_SHARED_CREDENTIALS_FILE=/run/secrets/aws_shared_credentials_file
aws_config_file                -> AWS_CONFIG_FILE=/run/secrets/aws_config_file
custom_ca_certificate          -> NODE_EXTRA_CA_CERTS=/run/secrets/custom_ca_certificate
```

Place a PEM-encoded CA certificate (or bundle) in
`~/.pi-container/secrets/custom_ca_certificate`. Node.js-based clients in the
container will trust it in addition to the system CA certificates. The file is
mounted read-only and is not copied into the image. Restart the container after
changing it.

OAuth login can be performed interactively with `pi` and persists under the
same state mount. Do not put secrets on the command line.

## Security model

The launcher uses a read-only root filesystem, an executable `/tmp` tmpfs,
all Linux capabilities dropped, `no-new-privileges`, resource limits, a
configurable non-root UID/GID, and SELinux-compatible `:Z` bind mounts.
Secrets are read-only and are not baked into image layers. `--host-access`
weakens network isolation; use it only when needed and protect host services.

Pi’s shell tool runs inside this container. The image includes Bash, `/bin/sh`,
Git, ripgrep, fd, Node, npm, and required POSIX utilities. The final image has
no OS package manager or compiler. Pi package installs that require native
compilation are therefore not supported.

Pi prefers Bash on Unix, so this image intentionally includes Bash; this is a
meaningful deviation from the reference OpenCode image’s dash-only runtime.

## Docker and Podman

Rootless Podman receives `--userns=keep-id` when the engine reports rootless
operation. Rootful Podman does not receive that option. Docker receives the
Docker host gateway alias when `--host-access` is enabled; Podman receives the
Podman alias.

## Build targets

```sh
make build
make build-builder-tools
make build-latest
make shell
make test
make smoke
make clean
make prune-cache
```

Override the verified package version with:

```sh
make build PI_VERSION=0.86.1
docker build --build-arg PI_VERSION=0.86.1 -t pi-container:latest .
```

The default is the exact published version `0.86.1`. Pi currently requires
Node `>=22.19.0`; the image uses Node 24.

## Troubleshooting

- Check the selected engine with `CONTAINER_ENGINE=docker` or `podman`.
- Check state and secret permissions under `~/.pi-container`.
- Use `make shell` for builder-stage debugging; the production image has no
  Bash entry shell or package manager access beyond Pi’s own npm operations.
- Use `pi --offline --version` or `pi --offline --list-models` to validate
  startup without provider credentials.
- If a provider needs a file credential, use the documented path-secret name;
  do not pass a host path that is not mounted into the container.
