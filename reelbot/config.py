"""Loads config.yaml and secrets from the environment (or a local .env file)."""
import os
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = ROOT / "out"
ASSETS = ROOT / "assets"
_MASKED = []


def _load_dotenv():
    env = ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def load():
    _load_dotenv()
    cfg = yaml.safe_load((ROOT / "config.yaml").read_text())
    cfg["secrets"] = {
        "anthropic": os.environ.get("ANTHROPIC_API_KEY", ""),
        "claude_oauth": os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", ""),
        "pexels": os.environ.get("PEXELS_API_KEY", ""),
        "voicemaker": os.environ.get("VOICEMAKER_API_KEY", ""),
        "azure_key": os.environ.get("AZURE_SPEECH_KEY", ""),
        "azure_region": os.environ.get("AZURE_SPEECH_REGION", "centralindia"),
        "ig_user_id": os.environ.get("IG_USER_ID", ""),
        "ig_token": os.environ.get("IG_ACCESS_TOKEN", ""),
        "elevenlabs": os.environ.get("ELEVENLABS_API_KEY", ""),
        "graph_version": os.environ.get("GRAPH_VERSION", "v25.0"),
        "telegram": os.environ.get("TELEGRAM_BOT_TOKEN", ""),
        "telegram_chat": os.environ.get("TELEGRAM_CHAT_ID", ""),
    }
    sec = cfg["secrets"]
    os.environ["CLAUDE_TOKEN_RAW_LEN"] = str(len(sec["claude_oauth"]))
    for k in ("anthropic", "claude_oauth", "ig_token", "telegram", "telegram_chat"):
        sec[k] = "".join(sec[k].split())   # copying from a terminal can leave line breaks inside a key
    if sec["claude_oauth"].startswith("sk-ant-api"):       # an API key pasted into the token slot still works
        sec["anthropic"], sec["claude_oauth"] = sec["anthropic"] or sec["claude_oauth"], ""
    os.environ["CLAUDE_CODE_OAUTH_TOKEN"] = sec["claude_oauth"]
    if os.environ.get("GITHUB_ACTIONS") == "true" and not _MASKED:
        # The repo is public, so run logs are too. GitHub hides each secret as it was pasted; tell it to hide the
        # cleaned-up copies as well, in case cleaning changed them.
        for k, v in sec.items():
            if v and k not in ("azure_region", "graph_version", "ig_user_id"):
                print(f"::add-mask::{v}", flush=True)
        _MASKED.append(True)
    if os.environ.get("DRY_RUN", "").lower() in ("1", "true", "yes"):
        cfg["posting"]["dry_run"] = True
    DATA.mkdir(exist_ok=True)
    OUT.mkdir(exist_ok=True)
    return cfg
