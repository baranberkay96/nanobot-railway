# nanobot v0.3 Always-On Personal AI Agent: Railway template spec

## Listing

| Field | Value |
|---|---|
| Name | **nanobot v0.3 Always-On Personal AI Agent** (as assigned; `v0.3` = major.minor of the pinned `v0.3.5`, upstream spells the name in lowercase) |
| Description | Lightweight AI agent that lives in your chat apps and runs 24/7. (64 chars, unchanged) |
| Category | AI/ML |
| Tags | nanobot, ai-agent, personal-assistant, telegram, discord, slack, whatsapp, llm |
| Icon | `https://cdn.jsdelivr.net/gh/HKUDS/nanobot@v0.3.5/images/nanobot_mark.svg` (upstream mark, pinned to the tag, HTTP 200 checked) |

The description is delivered as written:
- **Lives in your chat apps**: Telegram, Discord and Slack can be enabled from variables at deploy time; WhatsApp (QR login), Feishu, DingTalk, QQ, WeChat, WeCom, Mattermost and Email from WebUI Settings → Channels. Their SDKs are baked into the image, because upstream blocks package installs from remote (non-localhost) WebUI clients, which every Railway visitor is.
- **Runs 24/7**: `nanobot gateway` in the foreground with restart policy `ALWAYS`; heartbeat, cron and Dream memory consolidation run inside it. State lives on a volume.
- **Lightweight**: one service and no database; estimated 0.2-0.3 GB RAM idle (not yet measured in a container).

## Base market template

- **Base: `nanobot`** (`arjunkomath/nanobot-railway-template`, 111 deploys, 35 active, the market leader). Kept: one container, volume for all state, `/health`-style healthcheck, web-based setup instead of JSON editing, password-protected admin. Its repo has **no license**, so nothing was copied. It pins `nanobot-ai==0.1.4.post3` (a February 2026 release, many features behind v0.3.5), runs as root with `HOME=/data`, and wraps nanobot in a custom Starlette config dashboard that starts the gateway as a subprocess. Since v0.3, nanobot ships its own WebUI with chat, Settings (models, channels, pairing, automations) and an auth gate, so the wrapper is no longer needed.
- `nanobot-3` (`TheGreatAxios/nanobot-railway-template`, MIT, 29 deploys): the same wrapper approach with an unpinned PyPI install, a required user-typed `ADMIN_PASSWORD`, and **a raw TCP proxy instead of an HTTPS domain** (the admin password travels in clear text). Read only.
- `nanobot-4` (`codestorm-official/nanobot`, 26 deploys): HTTPS domain and `/data` volume, but `ADMIN_PASSWORD` and `ADMIN_USERNAME` default to empty and there is no healthcheck. Source not available locally; only the marketplace JSON was read.
- Upstream's own hosted one-click deploy (`render.yaml` + `render-config.json` in the repo) was the main reference: gateway + bundled WebUI as one web service, WebUI on 8765 protected by `tokenIssueSecret`, disk at `/home/nanobot/.nanobot`, healthcheck `/`.

## Pinned versions

| Service | Source | Version | Release date | Checked |
|---|---|---|---|---|
| nanobot | Built from `https://github.com/HKUDS/nanobot` tag `v0.3.5`, commit `1bb712d3488915ca4ed9ccc1a93067ff722f5ab9` (checked by the Dockerfile at build time) | v0.3.5 (latest release; PyPI `nanobot-ai 0.3.5` published the same day) | 2026-09-15 | 2026-10-13 |
| Build bases | `node:24-bookworm-slim` (WebUI build), `ghcr.io/astral-sh/uv:python3.12-bookworm-slim` (runtime), `debian:bookworm-slim` (git fetch) | upstream's choices | | 2026-10-13 |

There is **no official nanobot container image**. Upstream's deployment guide says official Docker usage means building from the repository and warns against third-party Docker Hub images, so the template builds the tag from source in `services/nanobot/Dockerfile` (repo `baranberkay96/nanobot-railway`, root directory `/services/nanobot`).

Upgrade: set `UPSTREAM_TAG` and `UPSTREAM_COMMIT` in the Dockerfile to a newer release (`gh api repos/HKUDS/nanobot/commits/<tag> --jq .sha`) and redeploy. The volume keeps config, sessions and memory.

## Architecture

```
 Telegram / Discord / Slack / WhatsApp / ...  ◄── outbound bot connections (no inbound ports)
                         ▲
   ┌─────────────────────┴───────────────────────────────────────────┐
   │ nanobot (built from v0.3.5)                                       │
   │  railway-entrypoint.sh  (Railway init is PID 1)                   │
   │   1. railway_config.py: variables → config.json (refs, not values)│
   │   2. upstream entrypoint.sh: chown volume, setpriv → UID 1000     │
   │   3. nanobot gateway --config ~/.nanobot/config.json              │
   │       ├─ agent loop, tools, cron, heartbeat, Dream memory          │
   │       ├─ chat channels                                              │
   │       ├─ WebSocket channel + WebUI  0.0.0.0:8765  (public)         │
   │       └─ gateway /health            127.0.0.1:18790 (internal)     │
   │  volume /home/nanobot/.nanobot = config.json, sessions/, webui/,  │
   │         cron/, workspace/ (memory, SOUL.md, USER.md, skills)       │
   └─────────────────────┬───────────────────────────────────────────┘
                         │ HTTPS/WSS (Railway edge) → :8765, healthcheck GET /
                  WebUI login with NANOBOT_WEB_TOKEN
```

One service. No database: nanobot keeps state in files (JSONL sessions, Markdown memory with a Git history).

### Why not a second `nanobot-api` service (upstream compose has one)

Upstream's `docker-compose.yml` runs `nanobot serve` (OpenAI-compatible API, port 8900) next to the gateway, sharing one bind-mounted directory. On Railway a volume cannot be shared, so the API service would be a second agent with its own memory that sees only keys set as variables, never keys entered in the WebUI. It also **exits at startup when no LLM key is configured** (verified with a native run of `nanobot serve` v0.3.5: `Error: No provider is configured for model 'anthropic/claude-opus-4-5'`), so a keyless deploy would crash-loop and show a failed service. Instead the image includes the `api` extra, and WebUI Settings can start the same API as a managed child process of the gateway, sharing its config, keys and workspace. It is reachable from other services at `http://nanobot.railway.internal:8900/v1` once bound to `0.0.0.0` with an API key in that settings page.

### bubblewrap sandbox decision

`docker-compose.bwrap.yml` gives the container `CAP_SYS_ADMIN` and unconfined seccomp/AppArmor so bubblewrap can create namespaces. Railway runs unprivileged containers without these, so `tools.exec.sandbox` stays at upstream's default (empty = no bwrap). Upstream documents that bwrap then exits with `clone3: Operation not permitted`; this was **not re-checked locally** because Docker was unavailable during packaging (see Verification results). Mitigations kept: the agent runs as UID 1000 (never root), `tools.restrictToWorkspace: true` on first boot, shell commands get upstream's minimal environment, and secrets are stored as `${VAR}` references so `config.json` holds no clear-text keys.

## Services

### nanobot

| Setting | Value |
|---|---|
| Source | repo `baranberkay96/nanobot-railway`, root `/services/nanobot` (Dockerfile) |
| Start | image ENTRYPOINT `railway-entrypoint.sh`, CMD `gateway` (no start command override) |
| Healthcheck | `GET /` on `PORT=8765` (the WebUI shell served by the WebSocket channel; only answers once the gateway and channel are up; upstream's Render blueprint uses the same path), timeout 300 s |
| Public domain | yes, target port 8765 (WebUI, WebSocket upgrade on `/`) |
| TCP proxy | none |
| Volume | `/home/nanobot/.nanobot` (upstream's data dir; same path as upstream's Render disk) |
| Restart policy | `ALWAYS` (always-on agent; a clean exit must also restart) |
| Replicas | 1 (single writer; two gateways would double-poll bots) |

What the wrapper does on every start (`railway/railway_config.py`):

| Variable(s) | config.json effect |
|---|---|
| `NANOBOT_WEB_TOKEN` (required to be non-empty, generated) | `channels.websocket`: `enabled`, `host 0.0.0.0` (asyncio `::` would be IPv6-only), `port $PORT`, `tokenIssueSecret "${NANOBOT_WEB_TOKEN}"`, `websocketRequiresToken true` |
| `OPENROUTER_API_KEY`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`, `DEEPSEEK_API_KEY`, `GROQ_API_KEY` | `providers.<name>.apiKey = "${VAR}"` while set; the reference is removed when the variable is deleted (upstream refuses to start on an unset reference; verified natively) |
| `LLM_MODEL`, `LLM_PROVIDER` | if `LLM_MODEL` is set: `agents.defaults.model/provider`, and the WebUI preset selection is cleared so the variable wins |
| `TELEGRAM_BOT_TOKEN` (+ `TELEGRAM_ALLOW_FROM`) | `channels.telegram` enabled with a token reference; allow list if given, otherwise pairing |
| `DISCORD_BOT_TOKEN` (+ `DISCORD_ALLOW_FROM`) | `channels.discord`, same pattern |
| `SLACK_BOT_TOKEN` + `SLACK_APP_TOKEN` (+ `SLACK_ALLOW_FROM`) | `channels.slack` (Socket Mode); `dm.policy: allowlist` so unknown DM senders get a pairing code (upstream default is open to the whole workspace) |
| `WEBUI_ALLOW_REMOTE_INSTALL` | `tools.webuiAllowRemotePackageInstall` |
| first boot only | `tools.restrictToWorkspace: true`, `webuiAllowRemotePackageInstall: false`, `my.allowSet: false` (upstream's hosted defaults) |
| always | deletes stale `run/` process records (defensive: a fresh container has no running gateway or API process; upstream also checks the PID start time, so a collision is unlikely) |

Everything else in `config.json` (models, presets, other channels, tools, MCP servers) belongs to the WebUI and is never overwritten. Channels configured in the WebUI with literal tokens are left alone.

Variables (all have descriptions in `template.json`; **none is required at deploy**):

| Variable | Default | Notes |
|---|---|---|
| `PORT` | `8765` | Railway healthcheck port (Rule 8.1) = WebSocket channel port = domain target port |
| `NANOBOT_WEB_TOKEN` | `${{secret(32)}}` | WebUI password. Upstream's own variable name from `render.yaml` |
| `OPENROUTER_API_KEY` … `GROQ_API_KEY` | empty | Optional. Without any, the gateway still boots and the WebUI walks through provider setup |
| `LLM_MODEL`, `LLM_PROVIDER` | empty | Optional hard override of the model |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_ALLOW_FROM` | empty | Optional |
| `DISCORD_BOT_TOKEN`, `DISCORD_ALLOW_FROM` | empty | Optional |
| `SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN`, `SLACK_ALLOW_FROM` | empty | Optional, Socket Mode needs both tokens |
| `TZ` | `UTC` | nanobot's auto timezone reads it (cron, reminders) |
| `WEBUI_ALLOW_REMOTE_INSTALL` | `false` | Upstream secure default |
| `RAILWAY_DEPLOYMENT_DRAINING_SECONDS` | `30` | Lets running turns finish before redeploys |

Why no LLM key is required: upstream's gateway starts with an "unconfigured provider" runtime when the WebUI is enabled, so first-time provider setup can happen in Settings → Models (verified with a native run of the v0.3.5 wheel and the generated config: gateway up, WebUI served, no key set; not yet in the container). Variables are offered for people who prefer to configure at deploy time.

Not set on purpose: `NANOBOT_*` settings variables other than the WebUI token (nanobot's pydantic settings only read them when no `config.json` exists, which is never the case here); upstream's build arg `NANOBOT_CHANNELS` (renamed `PRELOAD_CHANNELS` so a Railway variable can never collide with the settings prefix); `allowFrom: ["*"]` (would let anyone who finds the bot spend your LLM budget).

## First login

1. Open the public URL → "Authentication required" → paste `NANOBOT_WEB_TOKEN`.
2. Settings → Models: add a provider key (unless set as a variable) and choose the model. The stock default is `anthropic/claude-opus-4-5`, which is expensive; choose deliberately.
3. Chat in the WebUI to confirm the model works.
4. Settings → Channels: connect chat apps (WhatsApp shows a QR code to scan). Restart from the WebUI if it asks.
5. DM the bot; approve the pairing code in the WebUI or with `/pairing approve {code}`.

## Improvements over market templates

1. **Current release, pinned and verified**: v0.3.5 built from the release tag with a commit check (market: 0.1.4.post3 from February 2026, or unpinned latest).
2. **Upstream's own WebUI and auth gate** (chat, models, channels, pairing, automations, sessions) instead of custom config wrappers; secret generated with `secret(32)` (market: empty default password, or a user-typed one sent over a raw TCP proxy).
3. **HTTPS + WSS** through a Railway domain; no TCP proxy.
4. **Non-root runtime**: upstream entrypoint chowns the volume and drops to UID 1000 (market templates run as root).
5. **Healthcheck** on `/` with `PORT` set (two of three market templates have none).
6. **No secrets in clear text on disk**: keys and tokens live in Railway variables and are referenced as `${VAR}`; deleting a variable cleanly disables the feature instead of crash-looping.
7. **Works with zero required inputs**; optional variables for six LLM providers and Telegram/Discord/Slack, with pairing-by-default access control (Slack DM allowlist instead of upstream's open default).
8. **Chat SDKs preinstalled** (Telegram, Discord, Slack, WhatsApp, Feishu, DingTalk, QQ, WeCom, WeChat) because remote package installs are blocked by upstream.
9. **Restart `ALWAYS`** and graceful draining for an always-on agent, plus defensive cleanup of old process records on the volume.
10. **Channel setup panels in the WebUI**: the v0.3.5 upstream Dockerfile does not copy `nanobot/channels/*/webui` into its WebUI build stage, so a Docker-built v0.3.5 WebUI lacks the per-channel setup panels (the PyPI wheel has them). The fix upstream made on main (commit `30e43aec82`, #6179) is backported.
11. **OpenAI-compatible API available on demand**: the `api` extra (aiohttp, not a core dependency in v0.3.5) is preinstalled, so WebUI Settings can start the API without a remote package install.

## Resource estimate

Railway prices: RAM $10/GB-month, vCPU $20/vCPU-month, volume $0.15/GB-month.

| Service | Idle RAM / CPU | Typical RAM / CPU | Notes |
|---|---|---|---|
| nanobot | ~0.25 GB / 0.01 vCPU | 0.4-0.6 GB / 0.05-0.1 vCPU | Peaks during long tool runs, subagents (up to 4 by default) and document parsing |
| Volume | 0.1 GB | 0.5-1 GB | Sessions, WebUI transcripts, memory, media from chats |

Estimated monthly cost: **idle ≈ $3**, **typical ≈ $5-8**. LLM usage is billed by your provider.

Minimum plan: **Trial** can run it (well under 1 GB RAM), but Trial credit runs out; **Hobby** is the realistic plan for 24/7 use. Email channel replies need outbound SMTP, which Railway allows on **Pro** only.

## Verification results (local, 2026-10-13)

Docker on the packaging machine froze (host disk full) before the build reached the daemon, and packaging continued without Docker on instruction. **The Dockerfile has not been built and the container has not been run.** What was checked instead:

| Check | How | Result |
|---|---|---|
| `docker build --platform linux/amd64 services/nanobot` | Docker | **not run (unverified)**: the build client never got a daemon response and was abandoned |
| `docker run --init` with template variables, healthcheck, privilege drop, volume chown | Docker | **not run (unverified)** |
| Tag `v0.3.5` → commit `1bb712d3488915ca4ed9ccc1a93067ff722f5ab9` | `git clone --depth 1 --branch v0.3.5`, `gh api` | matches |
| Base images exist | registry API | `node:24-bookworm-slim`, `debian:bookworm-slim`, `ghcr.io/astral-sh/uv:python3.12-bookworm-slim` all 200 |
| Python deps for the image resolve on linux/amd64 | `uv pip compile --python-platform x86_64-manylinux_2_28 --python-version 3.12` with `nanobot-ai[api]==0.3.5` + the nine preloaded channel manifests | resolves (363 pins; neonize has a manylinux2014 x86_64 wheel) |
| `railway_config.py` | local runs: first boot, variables added/removed, idempotent rerun, bad `PORT`, missing `NANOBOT_WEB_TOKEN` | all behave as specified; config written 0600; stale `run/` files removed |
| Gateway with the generated config, **no LLM key** | native macOS run of the PyPI `nanobot-ai==0.3.5` wheel (same release, not the container) | boots in ~3 s; `GET /` 200 `text/html`; `/webui/bootstrap` 401 without the token, 200 with it; `/api/sessions` 401; WebSocket upgrade 401 without a token, connects with an issued token; loopback `/health` reports `ready: true, websocket: running` |
| Railway-style proxy headers | `Host: demo.up.railway.app`, `X-Forwarded-Proto: https` on `/webui/bootstrap` | `ws_url` = `wss://demo.up.railway.app/` |
| Variables added on restart | `OPENROUTER_API_KEY` + fake `TELEGRAM_BOT_TOKEN` | references written; Telegram channel starts, fake token rejected by Telegram, gateway keeps serving |
| Variables removed on restart | same config, variables unset | raw upstream refuses (`Found 2 missing environment variable reference(s)`); after `railway_config.py` the references are gone, Telegram disabled, gateway healthy |
| `nanobot serve` without a key | native run | exits: `Error: No provider is configured for model 'anthropic/claude-opus-4-5'` (reason for no separate API service); also needs aiohttp (`api` extra) |
| bubblewrap without `SYS_ADMIN` | Docker | **not run (unverified)**; upstream docs describe the failure |
| RAM/CPU figures | | **estimates**, not measured in a container |

## Verification checklist

- [ ] Build logs show the git clone of `v0.3.5` and the commit check passing; image builds without errors.
- [ ] Deploy logs: `[railway] config created …`, `[entrypoint] dropping privileges to nanobot via setpriv`, `WebSocket server listening on ws://0.0.0.0:8765/`; healthcheck `/` passes.
- [ ] `GET https://{domain}/` returns the WebUI; `GET /webui/bootstrap` without the token returns 401; login with `NANOBOT_WEB_TOKEN` works and the chat connects over WSS.
- [ ] With no key variables: WebUI offers provider setup; after adding a key, a chat reply arrives.
- [ ] Telegram (or another channel): bot replies after pairing approval; an unknown user only gets a pairing code.
- [ ] Persistence: tell the agent a fact, redeploy, ask again; a cron reminder created before the redeploy still fires.
- [ ] Delete a key or token variable and redeploy: service stays healthy (reference removed, channel disabled).
- [ ] `railway ssh`: `ps -o user,cmd -C python` shows the gateway running as `nanobot`, `cat ~/.nanobot/config.json` shows `${…}` references only.

## Open questions

- **The image has never been built.** The first Railway build is the first build of this Dockerfile. Most likely failure points: `npm ci`/`npm run build` with the backported channel panels, and the batch of channel SDK installs (each failing channel fails the build on purpose; drop it from `PRELOAD_CHANNELS` if needed). Expect a 5-10 minute first build.
- Railway deploy itself not tested (task scope: local only). WebSocket upgrade through Railway's edge is standard, and the bootstrap derives `wss://{host}/` from `Host` + `X-Forwarded-Proto` (checked locally with those headers).
- WhatsApp (neonize) login was not exercised end to end; it needs a phone to scan the QR code.
- Railway's per-domain target ports could expose the optional API (port 8900) publicly through a second domain; not verified, so the template documents private-network use only.
- Running the shell tool without bubblewrap means a prompt-injected agent could read the gateway process environment (`/proc/<pid>/environ`, same UID), which contains the LLM keys. This is upstream's documented trade-off without the sandbox; keep pairing on and only approve people you trust.
