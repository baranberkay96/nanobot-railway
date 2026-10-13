# Deploy and Host nanobot with Railway

Run nanobot, the lightweight open-source personal AI agent from HKUDS, around the clock on Railway. It answers you in its own web chat and in Telegram, Discord, Slack, WhatsApp and other chat apps, remembers what matters on a persistent volume, and runs scheduled tasks while you are away.

## About Hosting nanobot

nanobot runs as a long-lived gateway: it keeps outbound connections to your chat apps, calls the LLM provider you choose, uses tools (shell, files, web search and fetch, cron) and stores sessions and memory under `~/.nanobot`. Self-hosting it needs a machine that never sleeps, durable storage, and a protected way to administer it. This community template builds nanobot v0.3.5 from the tagged upstream source, serves the bundled WebUI over HTTPS behind upstream's own password check, keeps config, sessions and memory on a Railway volume, and turns Railway variables into config so no JSON editing is needed.

## Common Use Cases

- A private assistant you message from Telegram, Discord, Slack or WhatsApp that remembers your preferences across conversations
- Scheduled briefings, reminders and recurring checks delivered to a chat, set up in plain language
- Research help: web search, reading pages and documents, summaries saved to the agent's workspace
- A small team helper in Slack or Discord, limited to approved people through pairing codes

## Dependencies for nanobot Hosting

- An API key for at least one LLM provider (OpenRouter, Anthropic, OpenAI, Gemini, DeepSeek, Groq or any other provider nanobot supports). It can be set as a variable or entered later in the WebUI.
- Optional bot credentials for the chat apps you want to use
- A Railway volume for `/home/nanobot/.nanobot` (included)

### Deployment Dependencies

- nanobot repository and releases: https://github.com/HKUDS/nanobot
- Deployment guide: https://github.com/HKUDS/nanobot/blob/v0.3.5/docs/deployment.md
- WebUI guide: https://github.com/HKUDS/nanobot/blob/v0.3.5/docs/webui.md
- Chat apps setup: https://github.com/HKUDS/nanobot/blob/v0.3.5/docs/chat-apps.md
- Providers and models: https://github.com/HKUDS/nanobot/blob/v0.3.5/docs/providers.md
- OpenRouter keys: https://openrouter.ai/keys
- Telegram BotFather: https://t.me/BotFather

### Implementation Details

| Service | Source | Purpose |
|---|---|---|
| nanobot | Dockerfile in `services/nanobot` (builds tag `v0.3.5`) | Gateway (agent loop, chat channels, cron, heartbeat, Dream memory consolidation) + WebUI on port 8765, healthcheck `/`, volume at `/home/nanobot/.nanobot` |

**First login**

1. Open the service's public URL. nanobot shows an "Authentication required" screen.
2. Paste the value of `NANOBOT_WEB_TOKEN` (Railway → nanobot → Variables) to sign in.
3. If you did not set an LLM key variable, open **Settings → Models**, add your provider key and pick a model. Otherwise check the active model there; the stock default is a premium Anthropic model.
4. Say hello in the web chat.
5. Connect chat apps in **Settings → Channels** (Telegram, Discord, Slack, WhatsApp via QR code, Feishu, DingTalk, QQ, WeChat, WeCom, Mattermost, Email and more; Email sends over SMTP, which Railway allows on the Pro plan only), or set `TELEGRAM_BOT_TOKEN`, `DISCORD_BOT_TOKEN` or `SLACK_BOT_TOKEN` + `SLACK_APP_TOKEN` and redeploy.
6. DM your bot. Unknown senders receive a pairing code; approve it in the WebUI (or type `/pairing approve {code}` in the web chat). Set `TELEGRAM_ALLOW_FROM` (or the Discord/Slack equivalent) to pre-approve IDs.

**Variables**: provider keys and channel tokens are stored in `config.json` only as `${VAR}` references, never in clear text. Removing a variable cleanly disables what it enabled. `LLM_MODEL` (with optional `LLM_PROVIDER`) overrides the WebUI model choice on every restart; leave it empty to manage models in the WebUI.

**Scaling**: nanobot is a single-writer process with file-based state. Keep one replica and let Railway scale the service vertically. Never run two gateways on one volume (duplicate bot polling).

**Pinning and upgrades**: the Dockerfile pins `UPSTREAM_TAG=v0.3.5` and checks `UPSTREAM_COMMIT`. To upgrade, set both to a newer release from https://github.com/HKUDS/nanobot/releases and redeploy; config and memory on the volume are kept. Read the release notes first.

**Security notes**: the WebUI can change models, keys and channels, so keep `NANOBOT_WEB_TOKEN` private and rotate it by changing the variable. Remote package installs stay disabled (`WEBUI_ALLOW_REMOTE_INSTALL=false`); common channel SDKs are already in the image. Upstream's bubblewrap shell sandbox needs privileges Railway does not grant, so the agent's shell runs unsandboxed as an unprivileged user, limited to its workspace by default.

**Optional OpenAI-compatible API**: WebUI Settings can start upstream's `/v1/chat/completions` API inside the same container. It listens on 127.0.0.1 by default; bind it to `0.0.0.0` with an API key there to call it from other services in the project at `http://nanobot.railway.internal:8900/v1`.

### Why Deploy nanobot on Railway?

An agent that lives in your chat apps is only useful if it is always online and never forgets. Railway keeps nanobot running with automatic restarts, a persistent volume, HTTPS, logs and SSH access, without a VPS to maintain. You pay for the small amount of RAM and CPU nanobot actually uses; LLM usage is billed by your provider.
