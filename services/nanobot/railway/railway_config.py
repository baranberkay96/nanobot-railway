"""Write the Railway-managed parts of nanobot's config.json before start.

Runs on every container start (as root, before upstream's entrypoint drops to
UID 1000). Only keys driven by Railway variables are touched; everything else
in config.json (models, presets, channels and settings changed in the WebUI)
is kept as is.

Secrets are never written in clear text: the config stores ``${VAR}``
references that nanobot resolves from the environment at startup. A reference
is only written while its variable is set, and removed again when the
variable is deleted, because nanobot refuses to start on an unset reference.
"""

from __future__ import annotations

import copy
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, NoReturn

# Railway variable -> providers.<name> in config.json (upstream provider keys).
PROVIDER_KEYS = {
    "OPENROUTER_API_KEY": "openrouter",
    "ANTHROPIC_API_KEY": "anthropic",
    "OPENAI_API_KEY": "openai",
    "GEMINI_API_KEY": "gemini",
    "DEEPSEEK_API_KEY": "deepseek",
    "GROQ_API_KEY": "groq",
}

# Channel name -> (config key -> token variable, allow-list variable).
TOKEN_CHANNELS: dict[str, tuple[dict[str, str], str]] = {
    "telegram": ({"token": "TELEGRAM_BOT_TOKEN"}, "TELEGRAM_ALLOW_FROM"),
    "discord": ({"token": "DISCORD_BOT_TOKEN"}, "DISCORD_ALLOW_FROM"),
    "slack": (
        {"botToken": "SLACK_BOT_TOKEN", "appToken": "SLACK_APP_TOKEN"},
        "SLACK_ALLOW_FROM",
    ),
}

# Applied only when config.json is created (upstream's hosted defaults from
# render-config.json); the WebUI owns these afterwards.
FIRST_BOOT_DEFAULTS: dict[str, Any] = {
    "tools": {
        "restrictToWorkspace": True,
        "webuiAllowRemotePackageInstall": False,
        "my": {"allowSet": False},
    },
}

WEB_TOKEN_VAR = "NANOBOT_WEB_TOKEN"
DEFAULT_PORT = 8765


def env(name: str) -> str:
    return os.environ.get(name, "").strip()


def ref(name: str) -> str:
    return "${" + name + "}"


def csv_list(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def fail(message: str) -> NoReturn:
    sys.exit(f"[railway] {message}")


def section(config: dict[str, Any], *path: str) -> dict[str, Any]:
    """Return a nested dict for writing, creating missing levels."""
    node = config
    for key in path:
        child = node.get(key)
        if not isinstance(child, dict):
            child = {}
            node[key] = child
        node = child
    return node


def lookup(config: dict[str, Any], *path: str) -> dict[str, Any] | None:
    """Return a nested dict if it already exists, without creating it."""
    node: Any = config
    for key in path:
        node = node.get(key) if isinstance(node, dict) else None
    return node if isinstance(node, dict) else None


def drop_stale_ref(target: dict[str, Any] | None, key: str, var: str) -> bool:
    """Remove ``target[key]`` if it still points at an unset variable."""
    if target is not None and target.get(key) == ref(var):
        target.pop(key)
        return True
    return False


def apply_web_ui(config: dict[str, Any]) -> None:
    if not env(WEB_TOKEN_VAR):
        fail(
            f"{WEB_TOKEN_VAR} is empty. It protects the public WebUI; set it to a "
            "long random value (the template generates one)."
        )
    port_raw = env("PORT") or str(DEFAULT_PORT)
    if not port_raw.isdigit():
        fail(f"PORT must be a number, got {port_raw!r}")
    section(config, "channels", "websocket").update(
        {
            "enabled": True,
            # asyncio servers on "::" are IPv6-only; Railway's edge proxy and
            # healthcheck connect over IPv4.
            "host": "0.0.0.0",
            "port": int(port_raw),
            "tokenIssueSecret": ref(WEB_TOKEN_VAR),
            "websocketRequiresToken": True,
        }
    )
    allow_install = env("WEBUI_ALLOW_REMOTE_INSTALL").lower()
    if allow_install in {"true", "false"}:
        section(config, "tools")["webuiAllowRemotePackageInstall"] = allow_install == "true"


def apply_providers(config: dict[str, Any]) -> list[str]:
    configured = []
    for var, name in PROVIDER_KEYS.items():
        if env(var):
            section(config, "providers", name)["apiKey"] = ref(var)
            configured.append(name)
        else:
            drop_stale_ref(lookup(config, "providers", name), "apiKey", var)
    return configured


def apply_model(config: dict[str, Any]) -> None:
    model = env("LLM_MODEL")
    if not model:
        return
    defaults = section(config, "agents", "defaults")
    defaults["model"] = model
    defaults["provider"] = env("LLM_PROVIDER") or "auto"
    # Upstream gives a selected preset precedence over defaults.model; the
    # variable is documented to win, so clear the preset selection.
    defaults.pop("modelPreset", None)


def apply_token_channel(config: dict[str, Any], name: str) -> bool:
    """Enable a channel from its token variables; disable it once they are removed."""
    tokens, allow_var = TOKEN_CHANNELS[name]
    if all(env(var) for var in tokens.values()):
        channel = section(config, "channels", name)
        channel.update({key: ref(var) for key, var in tokens.items()})
        channel["enabled"] = True
        allow = csv_list(env(allow_var))
        if allow:
            channel["allowFrom"] = allow
        if name == "slack":
            dm = section(channel, "dm")
            # Upstream's Slack DM policy defaults to "open" (any workspace
            # member). Use the allowlist so unknown senders get a pairing code.
            dm.setdefault("policy", "allowlist")
            if allow:
                dm["allowFrom"] = allow
        return True
    channel = lookup(config, "channels", name)
    dropped = [drop_stale_ref(channel, key, var) for key, var in tokens.items()]
    if channel is not None and any(dropped):
        channel["enabled"] = False
    return False


def load(path: Path) -> tuple[dict[str, Any], bool]:
    if not path.exists():
        return copy.deepcopy(FIRST_BOOT_DEFAULTS), True
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"cannot read {path}: {exc}. Fix or delete it via `railway ssh`.")
    if not isinstance(data, dict):
        fail(f"{path} must contain a JSON object")
    return data, False


def write_atomic(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".config.", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def clear_stale_process_state(data_dir: Path) -> None:
    """A fresh container has no running gateway/API; drop old PID records."""
    run_dir = data_dir / "run"
    if run_dir.is_dir():
        for item in run_dir.iterdir():
            if item.is_file():
                item.unlink(missing_ok=True)


def main() -> None:
    if len(sys.argv) != 2:
        fail("usage: railway_config.py <config.json>")
    path = Path(sys.argv[1])
    original, created = load(path)
    config = copy.deepcopy(original)
    apply_web_ui(config)
    providers = apply_providers(config)
    apply_model(config)
    channels = [name for name in TOKEN_CHANNELS if apply_token_channel(config, name)]
    changed = created or config != original
    if changed:
        write_atomic(path, config)
    clear_stale_process_state(path.parent)
    status = "created" if created else ("updated" if changed else "unchanged")
    print(
        f"[railway] config {status}: {path} | "
        f"LLM keys from variables: {', '.join(providers) or 'none'} | "
        f"channels from variables: {', '.join(channels) or 'none'}",
        flush=True,
    )
    if created and not providers:
        print(
            "[railway] no LLM key variable is set. Open the WebUI and add a provider "
            "in Settings > Models, or set a key variable such as OPENROUTER_API_KEY.",
            flush=True,
        )


if __name__ == "__main__":
    main()
