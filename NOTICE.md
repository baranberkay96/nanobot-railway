# NOTICE: nanobot template

## Software deployed

| Component | Source | License | How it is used |
|---|---|---|---|
| nanobot | https://github.com/HKUDS/nanobot, tag `v0.3.5` (commit `1bb712d3488915ca4ed9ccc1a93067ff722f5ab9`) | MIT, Copyright (c) 2025-present Xubin Ren and the nanobot contributors | Built from the tagged source at image build time (`services/nanobot/Dockerfile` clones the tag and verifies the commit). Upstream's `entrypoint.sh` is used unchanged from that checkout. Bundled third-party components are listed in upstream's `THIRD_PARTY_NOTICES.md`, which is installed with the package. |
| Chat channel SDKs | PyPI packages declared in upstream's channel manifests (`python-telegram-bot`, `discord.py`, `slack-sdk`, `neonize`, `lark-oapi`, ...) | Their respective licenses | Installed at build time by upstream's `scripts/install_channel_dependencies.py`. |

nanobot and HKUDS are names of their respective owners. This is a community template and is not affiliated with or endorsed by the nanobot authors.

## Adapted upstream material (MIT)

- `services/nanobot/Dockerfile`: the WebUI build stage and runtime stage follow upstream's `Dockerfile` at `v0.3.5` (base images `node:24-bookworm-slim` and `ghcr.io/astral-sh/uv:python3.12-bookworm-slim`, venv layout, non-root UID 1000, metadata-first dependency layer). Changes: source fetched from the release tag with a commit check, `api` extra and more chat channels preinstalled, Railway wrapper as entrypoint, build args renamed so they cannot collide with the `NANOBOT_*` settings prefix.
- `services/nanobot/railway/railway_config.py`: the first-boot tool defaults (`restrictToWorkspace`, `webuiAllowRemotePackageInstall: false`, `my.allowSet: false`) and the `${NANOBOT_WEB_TOKEN}` WebUI secret mirror upstream's `render-config.json` / `render.yaml` (upstream's own hosted one-click deploy). The script itself was written for this template.

MIT License text: https://github.com/HKUDS/nanobot/blob/v0.3.5/LICENSE

## Upstream files checked (tag `v0.3.5`, released 2026-09-15, checked 2026-10-13)

- `Dockerfile`, `entrypoint.sh`, `docker-compose.yml`, `docker-compose.bwrap.yml`, `render.yaml`, `render-config.json`, `pyproject.toml`
- `docs/deployment.md` (Docker, Render, bind/auth requirements, bwrap capabilities), `docs/webui.md` (LAN/remote access, remote package installs), `docs/chat-apps.md` (channel fields, pairing), `docs/providers.md`, `docs/openai-api.md`, `docs/memory.md`
- `nanobot/config/schema.py`, `nanobot/config/loader.py` (`${VAR}` resolution, `NANOBOT_` env prefix), `nanobot/channels/websocket/runtime.py`, `nanobot/webui/ws_http.py`, `nanobot/webui/gateway_endpoint.py` (auth on `/webui/bootstrap`, `/api/*`, WebSocket), `nanobot/webui/settings_routes.py` (local-only actions), `nanobot/cli/commands.py` (`serve`), `nanobot/channels/*/manifest.py`

## Market templates and repositories reviewed (ideas only, nothing copied)

| Template / repo | License | Use |
|---|---|---|
| `nanobot` / `arjunkomath/nanobot-railway-template` | none (all rights reserved) | Read for approach (custom config dashboard around nanobot 0.1.4, `/data` volume, basic auth). No files or text copied. |
| `nanobot-3` / `TheGreatAxios/nanobot-railway-template` | MIT, Copyright 2026 Sawyer Cutler | Read only (fork of the same approach, unpinned, TCP proxy). Nothing copied. |
| `nanobot-4` / `codestorm-official/nanobot` | not available locally | Only the marketplace JSON and readme were read. Nothing copied. |

All template files (TEMPLATE.md, template.json, README.md, this NOTICE, the Railway wrapper scripts) were written for this package.
