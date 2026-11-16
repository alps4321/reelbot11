"""Tiny JSON file store. State lives in data/ so it can be committed to the repo."""
import json
from datetime import datetime, timezone

from .config import DATA


def now():
    return datetime.now(timezone.utc)


def iso(dt=None):
    return (dt or now()).isoformat(timespec="seconds")


def parse(ts):
    return datetime.fromisoformat(ts)


def read(name, default):
    p = DATA / f"{name}.json"
    if not p.exists():
        return default
    return json.loads(p.read_text())


def write(name, value):
    p = DATA / f"{name}.json"
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(value, indent=2, ensure_ascii=False))
    tmp.replace(p)


def posts():
    return read("posts", [])


def save_posts(items):
    write("posts", items)
