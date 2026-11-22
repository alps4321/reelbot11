"""Merge two copies of data/posts.json so a save clash never loses a record.

Two runs can overlap: one posts a reel and saves its full record, while another run that started a
moment earlier sees the same reel on Instagram, imports it as a "manual" post and saves after it.
A plain git rebase then keeps only one side. This merges by reel instead:
  - every record from both copies is kept (matched by media_id, or id when there is no media id);
  - when both copies have the same reel, the bot's own record beats a "manual" import of it;
  - the reading history (checked / metrics / history) comes from whichever copy has read it more.

Usage: python -m reelbot.mergeposts REMOTE_COPY LOCAL_COPY   (writes the merge into LOCAL_COPY)
"""
import json
import sys
from pathlib import Path

READINGS = ("checked", "metrics", "history")


def _key(r):
    return r.get("media_id") or r.get("id")


def _reads(r):
    """How far this copy has read the reel: number of checkpoints, readings, and the latest reading."""
    hist = r.get("history") or []
    last = max((h.get("at") or "" for h in hist if isinstance(h, dict)), default="")
    return len(r.get("checked") or []), len(hist), last


def pick(a, b):
    """Return the better of two records for the same reel (on a full tie, b: the local copy)."""
    if bool(a.get("manual")) != bool(b.get("manual")):
        base, other = (b, a) if a.get("manual") else (a, b)
    else:
        base, other = (a, b) if _reads(a) > _reads(b) else (b, a)
    out = dict(base)
    if _reads(other) > _reads(base):
        for k in READINGS:
            if k in other:
                out[k] = other[k]
    return out


def merge(remote, local):
    seen = {}
    for r in list(remote) + list(local):
        k = _key(r)
        seen[k] = pick(seen[k], r) if k in seen else r
    return sorted(seen.values(), key=lambda r: r.get("posted_at") or r.get("created_at") or "")


def main(remote_path, local_path):
    rp, lp = Path(remote_path), Path(local_path)
    remote = json.loads(rp.read_text()) if rp.exists() and rp.stat().st_size else []
    local = json.loads(lp.read_text()) if lp.exists() else []
    merged = merge(remote, local)
    lp.write_text(json.dumps(merged, indent=2, ensure_ascii=False))
    print(f"mergeposts: {len(remote)} remote + {len(local)} local -> {len(merged)} records")


if __name__ == "__main__":
    main(*sys.argv[1:3])
