# nanobot gateway + bundled WebUI for Railway.
#
# There is no official nanobot image ("official Docker usage currently means
# building from this repository", docs/deployment.md). This file rebuilds the
# upstream Dockerfile of the pinned release tag from source, preinstalls the
# common chat-channel SDKs and adds a small Railway wrapper (railway/).
#
# Upgrade: change UPSTREAM_TAG and UPSTREAM_COMMIT together (the commit the tag
# points to: gh api repos/HKUDS/nanobot/commits/<tag> --jq .sha).

ARG UPSTREAM_TAG=v0.3.5
ARG UPSTREAM_COMMIT=1bb712d3488915ca4ed9ccc1a93067ff722f5ab9

# --- 1. Fetch the tagged source and verify the commit -----------------------
FROM debian:bookworm-slim AS source
ARG UPSTREAM_TAG
ARG UPSTREAM_COMMIT
RUN apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates git && \
    rm -rf /var/lib/apt/lists/*
RUN git clone --depth 1 --branch "$UPSTREAM_TAG" https://github.com/HKUDS/nanobot.git /src && \
    test "$(git -C /src rev-parse HEAD)" = "$UPSTREAM_COMMIT" && \
    rm -rf /src/.git

# --- 2. Build the WebUI bundle (same as upstream's webui-builder stage) ----
FROM node:24-bookworm-slim AS webui-builder
WORKDIR /app/webui
COPY --from=source /src/webui/package.json /src/webui/package-lock.json ./
RUN npm ci
COPY --from=source /src/webui/ ./
COPY --from=source /src/packages/client-events/ /app/packages/client-events/
# Channel setup panels (Settings -> Channels) are bundled from
# nanobot/channels/*/webui via import.meta.glob. The v0.3.5 Dockerfile does not
# copy them, so its WebUI ships without them; upstream main added this line in
# commit 30e43aec82 (#6179). Backported here.
COPY --from=source /src/nanobot/channels/ /app/nanobot/channels/
RUN mkdir -p /app/nanobot/web && npm run build

# --- 3. Runtime (mirrors upstream's v0.3.5 runtime stage) -------------------
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates git bubblewrap openssh-client libmagic1 && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
ENV VIRTUAL_ENV=/app/.venv
ENV PATH="/app/.venv/bin:$PATH"
RUN uv venv --seed "$VIRTUAL_ENV"

# Dependency layer first (metadata-only install, as upstream does). The "api"
# extra (aiohttp) lets WebUI Settings start the OpenAI-compatible API without
# a remote package install. Upstream calls this ARG NANOBOT_EXTRAS.
ARG PYTHON_EXTRAS=api
COPY --from=source /src/pyproject.toml /src/README.md /src/LICENSE /src/THIRD_PARTY_NOTICES.md /src/hatch_build.py ./
RUN mkdir -p nanobot && touch nanobot/__init__.py && \
    if [ -n "$PYTHON_EXTRAS" ]; then target=".[${PYTHON_EXTRAS}]"; else target="."; fi && \
    NANOBOT_SKIP_WEBUI_BUILD=1 uv pip install --python "$VIRTUAL_ENV/bin/python" --no-cache "$target" && \
    rm -rf nanobot

COPY --from=source /src/nanobot/ nanobot/
COPY --from=source /src/scripts/install_channel_dependencies.py scripts/
COPY --from=webui-builder /app/nanobot/web/dist/ nanobot/web/dist/
RUN NANOBOT_SKIP_WEBUI_BUILD=1 uv pip install --python "$VIRTUAL_ENV/bin/python" --no-cache .

# Chat-channel SDKs baked into the image. A Railway WebUI is always a "remote"
# client, and upstream blocks package installs from remote browsers by default,
# so channels enabled later in Settings -> Channels must already be installed.
# Matrix is left out (its e2e extra needs native libolm). Microsoft Teams is left
# out because it needs its own public webhook port (3978), which this single-
# domain service does not expose. Email, Mattermost and Signal need no SDK.
# Named PRELOAD_CHANNELS (not upstream's NANOBOT_CHANNELS) so a Railway variable
# can never collide with nanobot's NANOBOT_* settings prefix.
ARG PRELOAD_CHANNELS=telegram,discord,slack,whatsapp,feishu,dingtalk,qq,wecom,weixin
RUN for channel in $(printf '%s' "$PRELOAD_CHANNELS" | tr ',' ' '); do \
        python -m scripts.install_channel_dependencies "$channel"; \
    done

# Upstream entrypoint (unchanged): chowns the data dir, drops to UID 1000 via
# setpriv and refuses to run as root.
COPY --from=source /src/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN sed -i 's/\r$//' /usr/local/bin/entrypoint.sh && chmod +x /usr/local/bin/entrypoint.sh

RUN useradd -m -u 1000 -s /bin/bash nanobot && \
    mkdir -p /home/nanobot/.nanobot && \
    chown -R nanobot:nanobot /home/nanobot /app/.venv

# Railway wrapper: writes the deploy-managed parts of config.json from
# variables, then hands over to the upstream entrypoint.
COPY --chmod=0755 railway/railway-entrypoint.sh /usr/local/bin/railway-entrypoint.sh
COPY --chmod=0644 railway/railway_config.py /app/railway/railway_config.py

USER root
ENV HOME=/home/nanobot
ENV PYTHONUNBUFFERED=1 PYTHONFAULTHANDLER=1

# 8765 = WebSocket channel + WebUI (public). 18790 = gateway health (loopback).
EXPOSE 8765

ENTRYPOINT ["/usr/local/bin/railway-entrypoint.sh"]
CMD ["gateway"]
