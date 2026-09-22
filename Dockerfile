# syntax=docker/dockerfile:1

FROM debian:13-slim@sha256:d7e12182ce18b85b93007c1dedf31f2d29e01ccf3182cc4017c709b6259bc132 AS builder-tools

ARG USER_UID=1000
ARG USER_GID=1000
ARG NODE_MAJOR=24
ARG PI_VERSION=0.86.1

ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY
ARG http_proxy
ARG https_proxy
ARG no_proxy
ENV DEBIAN_FRONTEND=noninteractive
ENV NPM_CONFIG_CAFILE=/etc/ssl/certs/ca-certificates.crt

RUN export http_proxy="${http_proxy:-${HTTP_PROXY:-}}" https_proxy="${https_proxy:-${HTTPS_PROXY:-}}" no_proxy="${no_proxy:-${NO_PROXY:-}}"; \
    apt-get update && apt-get install --no-install-recommends -y \
      bash ca-certificates curl fd-find git gnupg jq openssl python3 ripgrep \
    && rm -rf /var/lib/apt/lists/*

RUN export http_proxy="${http_proxy:-${HTTP_PROXY:-}}" https_proxy="${https_proxy:-${HTTPS_PROXY:-}}" no_proxy="${no_proxy:-${NO_PROXY:-}}"; \
    mkdir -p /etc/apt/keyrings && \
    curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key -o /tmp/nodesource-repo.gpg.key && \
    test "$(gpg --show-keys --with-colons --fingerprint /tmp/nodesource-repo.gpg.key | awk -F: '$1 == "fpr" { print $10; exit }')" = "6F71F525282841EEDAF851B42F59B5F99B1BE0B4" && \
    gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg /tmp/nodesource-repo.gpg.key && \
    rm -f /tmp/nodesource-repo.gpg.key && \
    echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_${NODE_MAJOR}.x nodistro main" > /etc/apt/sources.list.d/nodesource.list && \
    apt-get update && apt-get install --no-install-recommends -y nodejs && \
    rm -rf /var/lib/apt/lists/*

RUN export http_proxy="${http_proxy:-${HTTP_PROXY:-}}" https_proxy="${https_proxy:-${HTTPS_PROXY:-}}" no_proxy="${no_proxy:-${NO_PROXY:-}}"; \
    npm install --global --no-audit --no-fund npm@12.0.2 \
      @earendil-works/pi-coding-agent@"${PI_VERSION}" \
    && PI_ROOT="$(npm root --global)" \
    && ln -sf "${PI_ROOT}/@earendil-works/pi-coding-agent/dist/bundle/cli.js" /usr/local/bin/pi \
    && chmod 0755 "${PI_ROOT}/@earendil-works/pi-coding-agent/dist/bundle/cli.js"

RUN node --version && npm --version && pi --version && bash --version | head -n 1

RUN ln -sf "$(command -v fdfind)" /usr/local/bin/fd

COPY scripts/collect-runtime-deps.sh /usr/local/bin/collect-runtime-deps.sh
RUN chmod 0755 /usr/local/bin/collect-runtime-deps.sh

FROM builder-tools AS collector

ARG USER_UID=1000
ARG USER_GID=1000

RUN mkdir -p /opt/runtime-rootfs && \
    /usr/local/bin/collect-runtime-deps.sh /opt/runtime-rootfs \
      pi node npm npx bash python3 git rg fdfind \
      /usr/lib/git-core/git-remote-http /usr/lib/git-core/git-remote-https \
      mkdir find grep cat head tail sed awk ls cp mv rm chmod wc sort cut env date \
      dirname basename readlink pwd sh

RUN cd /opt/runtime-rootfs && \
    for dir in bin sbin lib lib64; do \
      if [ -d "${dir}" ] && [ ! -L "${dir}" ]; then \
        mkdir -p "usr/${dir}"; cp -a "${dir}"/. "usr/${dir}"/ 2>/dev/null || true; rm -rf "${dir}"; \
      fi; \
    done

RUN mkdir -p /opt/runtime-rootfs/app/.pi /opt/runtime-rootfs/app/.cache /opt/runtime-rootfs/workspace /opt/runtime-rootfs/run/secrets && \
    chown -R "${USER_UID}:${USER_GID}" /opt/runtime-rootfs/app /opt/runtime-rootfs/workspace && \
    printf 'pi:x:%s:%s:Pi User:/app:/bin/bash\n' "${USER_UID}" "${USER_GID}" >> /opt/runtime-rootfs/etc/passwd && \
    printf 'pi:x:%s:\n' "${USER_GID}" >> /opt/runtime-rootfs/etc/group

FROM gcr.io/distroless/base-debian13@sha256:9ef50bca108839d5986e4d84b7f7b2d79024c9293b7c35b162c6c55485bd5868 AS final

ARG USER_UID=1000
ARG USER_GID=1000
WORKDIR /workspace

ENV HOME=/app
ENV PATH=/usr/local/bin:/usr/bin:/bin
ENV PI_CODING_AGENT_DIR=/app/.pi/agent
ENV NPM_CONFIG_CAFILE=/etc/ssl/certs/ca-certificates.crt
ENV NPM_CONFIG_CACHE=/tmp/.npm

COPY --from=collector /opt/runtime-rootfs/ /
COPY --chmod=0755 bootstrap.py /usr/local/bin/bootstrap.py

USER ${USER_UID}:${USER_GID}
ENTRYPOINT ["/usr/bin/python3", "/usr/local/bin/bootstrap.py"]
