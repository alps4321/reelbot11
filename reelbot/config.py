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
    apply_rotation(cfg)
    DATA.mkdir(exist_ok=True)
    OUT.mkdir(exist_ok=True)
    return cfg


def day_plan(cfg, day):
    """[(time, language)] for an India date: the round-the-clock test's plan on its days, else the usual slots."""
    import datetime as dt
    r = cfg["posting"].get("rotation") or {}
    if r.get("start") and r.get("days"):
        start = r["start"] if isinstance(r["start"], dt.date) else dt.date.fromisoformat(str(r["start"]))
        i = (day - start).days
        if 0 <= i < len(r["days"]):
            return [(t, lang) for t, lang in sorted(r["days"][i])]
    return list(zip(cfg["posting"]["times"], cfg["posting"]["slots"]))


def apply_rotation(cfg, day=None):
    """On a test day, swap in that day's posting times, languages and checked-answer slots (the Hinglish ones)."""
    import datetime as dt
    day = day or dt.datetime.now(dt.timezone(dt.timedelta(hours=5, minutes=30))).date()
    cfg["posting"].setdefault("base", {k: list(cfg["posting"][k]) for k in ("times", "slots", "proven_slots")})
    b = cfg["posting"]["base"]
    base = list(zip(b["times"], b["slots"]))
    plan = day_plan({"posting": {**cfg["posting"], "times": b["times"], "slots": b["slots"]}}, day)
    cfg["posting"]["testing_hours"] = plan != base
    if plan != base:
        cfg["posting"]["times"] = [t for t, _ in plan]
        cfg["posting"]["slots"] = [lang for _, lang in plan]
        cfg["posting"]["proven_slots"] = [t for t, lang in plan if lang == "hinglish"]
    return cfg
