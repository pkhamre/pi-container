#!/usr/bin/env python3
"""Load explicitly allowlisted secrets, then replace this process with pi."""

import os
import re
import sys
from pathlib import Path

SECRETS_DIR = Path("/run/secrets")

# Files whose contents are values. Names deliberately use a stable, documented
# lowercase spelling; arbitrary filenames never become environment variables.
VALUE_SECRETS = {
    "anthropic_api_key": "ANTHROPIC_API_KEY",
    "anthropic_auth_token": "ANTHROPIC_AUTH_TOKEN",
    "anthropic_oauth_token": "ANTHROPIC_OAUTH_TOKEN",
    "ant_ling_api_key": "ANT_LING_API_KEY",
    "openai_api_key": "OPENAI_API_KEY",
    "azure_openai_api_key": "AZURE_OPENAI_API_KEY",
    "azure_openai_base_url": "AZURE_OPENAI_BASE_URL",
    "azure_openai_resource_name": "AZURE_OPENAI_RESOURCE_NAME",
    "azure_openai_api_version": "AZURE_OPENAI_API_VERSION",
    "azure_openai_deployment_name_map": "AZURE_OPENAI_DEPLOYMENT_NAME_MAP",
    "deepseek_api_key": "DEEPSEEK_API_KEY",
    "nvidia_api_key": "NVIDIA_API_KEY",
    "gemini_api_key": "GEMINI_API_KEY",
    "google_cloud_api_key": "GOOGLE_CLOUD_API_KEY",
    "google_cloud_project": "GOOGLE_CLOUD_PROJECT",
    "gcloud_project": "GCLOUD_PROJECT",
    "google_cloud_location": "GOOGLE_CLOUD_LOCATION",
    "mistral_api_key": "MISTRAL_API_KEY",
    "groq_api_key": "GROQ_API_KEY",
    "cerebras_api_key": "CEREBRAS_API_KEY",
    "xai_api_key": "XAI_API_KEY",
    "radius_api_key": "RADIUS_API_KEY",
    "openrouter_api_key": "OPENROUTER_API_KEY",
    "ai_gateway_api_key": "AI_GATEWAY_API_KEY",
    "zai_api_key": "ZAI_API_KEY",
    "zai_coding_cn_api_key": "ZAI_CODING_CN_API_KEY",
    "minimax_api_key": "MINIMAX_API_KEY",
    "minimax_cn_api_key": "MINIMAX_CN_API_KEY",
    "moonshot_api_key": "MOONSHOT_API_KEY",
    "hf_token": "HF_TOKEN",
    "fireworks_api_key": "FIREWORKS_API_KEY",
    "together_api_key": "TOGETHER_API_KEY",
    "baseten_api_key": "BASETEN_API_KEY",
    "opencode_api_key": "OPENCODE_API_KEY",
    "kimi_api_key": "KIMI_API_KEY",
    "meta_api_key": "META_API_KEY",
    "cloudflare_api_key": "CLOUDFLARE_API_KEY",
    "cloudflare_account_id": "CLOUDFLARE_ACCOUNT_ID",
    "cloudflare_gateway_id": "CLOUDFLARE_GATEWAY_ID",
    "qwen_token_plan_api_key": "QWEN_TOKEN_PLAN_API_KEY",
    "qwen_token_plan_cn_api_key": "QWEN_TOKEN_PLAN_CN_API_KEY",
    "xiaomi_api_key": "XIAOMI_API_KEY",
    "xiaomi_token_plan_cn_api_key": "XIAOMI_TOKEN_PLAN_CN_API_KEY",
    "xiaomi_token_plan_ams_api_key": "XIAOMI_TOKEN_PLAN_AMS_API_KEY",
    "xiaomi_token_plan_sgp_api_key": "XIAOMI_TOKEN_PLAN_SGP_API_KEY",
    "copilot_github_token": "COPILOT_GITHUB_TOKEN",
    "aws_profile": "AWS_PROFILE",
    "aws_access_key_id": "AWS_ACCESS_KEY_ID",
    "aws_secret_access_key": "AWS_SECRET_ACCESS_KEY",
    "aws_session_token": "AWS_SESSION_TOKEN",
    "aws_bearer_token_bedrock": "AWS_BEARER_TOKEN_BEDROCK",
    "aws_region": "AWS_REGION",
    "aws_default_region": "AWS_DEFAULT_REGION",
    "aws_bedrock_skip_auth": "AWS_BEDROCK_SKIP_AUTH",
    "aws_bedrock_force_http1": "AWS_BEDROCK_FORCE_HTTP1",
    "aws_bedrock_force_cache": "AWS_BEDROCK_FORCE_CACHE",
    "aws_container_credentials_relative_uri": "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI",
    "aws_container_credentials_full_uri": "AWS_CONTAINER_CREDENTIALS_FULL_URI",
}

# Files containing credentials are mounted read-only and exposed by path, not
# by copying their contents into an environment value.
PATH_SECRETS = {
    "google_application_credentials": "GOOGLE_APPLICATION_CREDENTIALS",
    "aws_web_identity_token_file": "AWS_WEB_IDENTITY_TOKEN_FILE",
    "aws_shared_credentials_file": "AWS_SHARED_CREDENTIALS_FILE",
    "aws_config_file": "AWS_CONFIG_FILE",
}

ENVIRONMENT_NAME = re.compile(r"^[A-Z][A-Z0-9_]*$")


def load_secrets(secrets_dir: Path = SECRETS_DIR, environ: dict[str, str] | None = None) -> None:
    if not secrets_dir.is_dir():
        return
    environ = os.environ if environ is None else environ
    seen: set[str] = set()
    for entry in secrets_dir.iterdir():
        if entry.name not in VALUE_SECRETS and entry.name not in PATH_SECRETS:
            continue
        if entry.is_symlink() or not entry.is_file():
            raise RuntimeError(f"secret must be a regular file: {entry.name}")
        name = VALUE_SECRETS.get(entry.name) or PATH_SECRETS[entry.name]
        if not ENVIRONMENT_NAME.fullmatch(name) or name in seen:
            raise RuntimeError(f"invalid or duplicate secret: {entry.name}")
        seen.add(name)
        if entry.name in PATH_SECRETS:
            environ[name] = str(entry)
        else:
            environ[name] = entry.read_text(encoding="utf-8").rstrip("\r\n")


def bootstrap(args: list[str], execvp=os.execvp) -> None:
    load_secrets()
    execvp("pi", ["pi", *args])


if __name__ == "__main__":
    bootstrap(sys.argv[1:])
