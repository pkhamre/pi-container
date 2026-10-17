# Pi Container

Run Pi’s coding-agent CLI in a locked-down Docker or Podman container. The
current host directory is the only project directory mounted read-write.

## Prerequisites

- Docker or Podman
- GNU Make for build targets
- `curl` and Python 3 for `make build-latest`

## Build and run

```sh
make build
bin/pi-container
# Inside Pi, run /login to authenticate.
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
| `--pids-limit VALUE` | `256` | Maximum container processes/threads; positive integer |
| `--kubeconfig FILE` | none | Explicitly mount this kubeconfig read-only |

Set `CONTAINER_ENGINE=docker` or `CONTAINER_ENGINE=podman`. Without it, Podman
is preferred, then Docker. `PI_WORKSPACE` overrides the current directory.
`PIDS_LIMIT` overrides the default process limit; `--pids-limit` takes precedence.
Place launcher options before Pi arguments. Increase the process limit for large
parallel builds, for example `pi-container --pids-limit 512 --version`.

## Persistent state

The launcher stores Pi state below `~/.pi-container/state` and mounts it at
`/app/.pi`. With `HOME=/app`, Pi therefore uses its native paths, including:

- `~/.pi/agent/auth.json` — auth state
- `~/.pi/agent/settings.json` — settings
- `~/.pi/agent/sessions/` — session history
- `~/.pi/agent/extensions/`, `skills/`, `prompts/`, and `themes/`
- `~/.pi/agent/models-store.json`, `trust.json`, and `crashes.json`

The entire host home directory is not mounted. Kubeconfig is **not mounted by
default**, even when `~/.kube/config` or the host `KUBECONFIG` variable exists.
To expose Kubernetes credentials explicitly:

```sh
pi-container --kubeconfig "$HOME/.kube/config"
pi-container --kubeconfig ./cluster-config.yaml --version
```

The supplied file must exist and be readable. Relative paths are resolved from
the current host directory; paths containing colons or commas are rejected.
The file is mounted read-only at `/run/kubeconfig`, and the container receives
`KUBECONFIG=/run/kubeconfig`. Only that file is mounted: external certificate/key
files and host credential helper programs referenced by it are not included.
Read-only access still allows Pi to read and use its credentials. The image
includes `kubectl`, `helm`, and `skopeo`.

## Authentication

Run `/login` inside Pi to authenticate. Authentication persists in the existing
`~/.pi-container/state` mount. This state contains credentials and must be treated
as sensitive; commands running inside the container can access it.

The launcher no longer creates or mounts a secrets directory, and bootstrap no
longer loads credentials from files into environment variables. Existing host
secret directories are left untouched but are not used. Runtime secret-file CA
injection is also removed; the optional build-time `custom-ca.crt` input remains.
Do not put credentials on the command line.

## Security model

The launcher uses a read-only root filesystem, an executable `/tmp` tmpfs,
all Linux capabilities dropped, `no-new-privileges`, resource limits, a
configurable non-root UID/GID, and SELinux-compatible `:Z` bind mounts.
The launcher limits processes/threads to 256 by default and disables core dumps.
The launcher and container bootstrap use `umask 077`, so normally created files
are private (`600`) and directories are private (`700`). Existing files are not
retroactively changed, and applications can explicitly choose other permissions.
Production builds reject UID 0, and the normal container entrypoint refuses to
start Pi as UID 0, including a `--user 0` override. Run builds as a non-root host
user or explicitly supply a positive `USER_UID`. Overriding the entrypoint bypasses
the bootstrap checks; these checks do not constrain the container engine owner.
The `--host-access` option has been removed. The launcher adds no host gateway
mapping, but this does not block access to host IP addresses or private networks.
Outbound traffic still uses the container engine's default networking; no egress
firewall is configured by this launcher.

Pi’s shell tool runs inside this container. The image includes Bash, `/bin/sh`,
Git, ripgrep, fd, Node, npm, and required POSIX utilities. The final image has
no OS package manager or compiler. Pi package installs that require native
compilation are therefore not supported.

Pi prefers Bash on Unix, so this image intentionally includes Bash; this is a
meaningful deviation from the reference OpenCode image’s dash-only runtime.

## Docker and Podman

Rootless Podman receives `--userns=keep-id` when the engine reports rootless
operation. Rootful Podman does not receive that option.

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

Override the verified package, Node major, or npm version with:

```sh
make build PI_VERSION=1.3.0 NODE_MAJOR=24 NPM_VERSION=12.2.0
docker build --build-arg PI_VERSION=1.3.0 --build-arg NODE_MAJOR=24 --build-arg NPM_VERSION=12.2.0 -t pi-container:latest .
```

The default is the exact published Pi version `1.3.0`, Node 24 LTS, and npm
`12.2.0`. Builds install the latest available Node 24.x release from NodeSource.
Pi currently requires Node `>=22.19.0`.

Helm archives are verified against architecture-specific SHA-256 values pinned
in `Dockerfile` before extraction. Changing Helm's version requires updating the
reviewed checksums too. The Docker build context allows only the Dockerfile,
bootstrap, dependency collector, and optional `custom-ca.crt`; keep that CA input
a public certificate bundle, never a private key.

`make build-latest` queries the npm registry for the `latest` release of
`@earendil-works/pi-coding-agent`, then builds `pi-container:latest` with that
exact Pi version instead of the pinned default (or a supplied `PI_VERSION`).
It leaves the Node and npm version settings unchanged. If the version lookup
fails, the build stops rather than falling back to the pinned Pi version.

## Troubleshooting

- Check the selected engine with `CONTAINER_ENGINE=docker` or `podman`.
- Check state permissions under `~/.pi-container` and authenticate with `/login`.
- Use `make shell` for builder-stage debugging; the production image has no
  Bash entry shell or package manager access beyond Pi’s own npm operations.
- Use `pi --offline --version` or `pi --offline --list-models` to validate
  startup without provider credentials.
