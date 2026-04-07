import json
import os
from pathlib import Path
from typing import Optional

CONFIG_DIR = Path.home() / ".fisique"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULTS = {
    "device_ip": "",
    "device_port": 4370,
    "device_password": 0,
    "web_app_url": "",
    "api_key": "",
    "ep_active_members":     "/functions/v1/bridge-active-members",
    "ep_all_members":        "/functions/v1/bridge-all-members",
    "ep_confirm_enrollment": "/functions/v1/bridge-confirm-enrollment",
    "ep_access_log":         "/functions/v1/bridge-access-log",
    "ep_member_lookup":      "/functions/v1/bridge-member-lookup",
    "sync_hour": 2,          # 2 AM nightly sync
    "agent_port": 7474,      # local port bridge listens on
    "wipe_preserve_uid": 999,
    "log_level": "INFO",
}


def load() -> dict:
    if not CONFIG_FILE.exists():
        return dict(DEFAULTS)
    with open(CONFIG_FILE) as f:
        data = json.load(f)
    return {**DEFAULTS, **data}


def save(cfg: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)
    # Restrict permissions on non-Windows (contains API key)
    if os.name != "nt":
        CONFIG_FILE.chmod(0o600)


def get(key: str):
    return load().get(key, DEFAULTS.get(key))


def set_key(key: str, value) -> None:
    cfg = load()
    cfg[key] = value
    save(cfg)


def is_configured() -> bool:
    cfg = load()
    return bool(cfg.get("device_ip") and cfg.get("web_app_url") and cfg.get("api_key"))
