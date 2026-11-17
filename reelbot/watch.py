"""Every 5 minutes: read the latest numbers of every reel on the account and keep a timeline per reel.

The timelines live on the separate `stats` branch (checked out at stats-data/), so this job never edits the
files the posting runs write, and the two can never collide.

How often a reel is read depends on its age, to stay far below Meta's rate limits:
  first 2 days  -> every run (about every 5 minutes)
  2 to 7 days   -> hourly
  7 to 30 days  -> daily
  older         -> no longer read
"""
import json
import os
from pathlib import Path

from . import store
from .config import ROOT
from .instagram import IGError

STATS = Path(os.environ.get("STATS_DIR", ROOT / "stats-data"))
KEYS = ("views", "reach", "likes", "comments", "shares", "saved", "watch_s")
STOP_AT = 75           # % of a Meta rate limit; above this the run stops reading


def reel_file(media_id):
    return STATS / "reels" / f"{media_id}.json"


def timeline(media_id):
    f = reel_file(media_id)
    return json.loads(f.read_text()) if f.exists() else None


def _due(age_h, last):
    if age_h > 24 * 30:
        return False
    if last is None or age_h < 48:
        return True
    since = (store.now() - store.parse(last["t"])).total_seconds() / 3600
    return since >= (0.9 if age_h < 24 * 7 else 23)


def _sample(ig, media_id, age_h):
    m = ig.insights(media_id)
    if not m:
        return None
    watch = m.get("ig_reels_avg_watch_time")
    return {"t": store.iso(), "h": round(age_h, 2), "views": m.get("views", 0), "reach": m.get("reach", 0),
            "likes": m.get("likes", 0), "comments": m.get("comments", 0), "shares": m.get("shares", 0),
            "saved": m.get("saved", 0), "watch_s": round(watch / 1000, 1) if watch else 0}


def run(cfg, ig):
    if not ig.ready:
        print("watch: no Instagram credentials")
        return 0
    (STATS / "reels").mkdir(parents=True, exist_ok=True)
    media = ig._call("GET", f"{ig.uid}/media", fields="id,caption,media_product_type,timestamp,permalink",
                     limit=50).get("data", [])
    reels = [m for m in media if m.get("media_product_type") == "REELS"]
    read = changed = 0
    for m in reels:
        if ig.last_usage >= STOP_AT:
            print(f"watch: Meta rate limit at {ig.last_usage}%, stopping this run early")
            break
        age_h = (store.now() - store.parse(m["timestamp"])).total_seconds() / 3600
        tl = timeline(m["id"]) or {"media_id": m["id"], "posted_at": m["timestamp"], "permalink": m.get("permalink", ""),
                                   "hook": (m.get("caption") or "").split("\n")[0][:80], "samples": []}
        last = tl["samples"][-1] if tl["samples"] else None
        if not _due(age_h, last):
            continue
        try:
            s = _sample(ig, m["id"], age_h)
        except IGError as e:
            print(f"watch: {m['id']} failed: {e}")
            continue
        read += 1
        if not s:
            continue
        same = last and all(last.get(k) == s[k] for k in KEYS)
        stale = last and (store.now() - store.parse(last["t"])).total_seconds() >= 3600
        if not same or stale:
            tl["samples"].append(s)
            reel_file(m["id"]).write_text(json.dumps(tl, separators=(",", ":"), ensure_ascii=False))
            changed += 1
    _summary(reels)
    print(f"watch: {len(reels)} reels on the account, read {read}, {changed} changed, rate limit use {ig.last_usage}%")
    return changed


def growth(tl, hours=1.0):
    """Views gained in the last `hours`, from the timeline."""
    s = tl["samples"]
    if len(s) < 2:
        return 0
    end = store.parse(s[-1]["t"])
    before = [x for x in s if (end - store.parse(x["t"])).total_seconds() >= hours * 3600]
    return s[-1]["views"] - (before[-1]["views"] if before else s[0]["views"])


def _summary(reels):
    """A table anyone can read on GitHub (the stats branch front page)."""
    rows = []
    for m in reels:
        tl = timeline(m["id"])
        if not tl or not tl["samples"]:
            continue
        s = tl["samples"][-1]
        rows.append((m["timestamp"], f"| {store.local_date(m['timestamp'])} | {tl['hook'][:50].replace('|', '/')} | "
                                     f"{s['views']} | +{growth(tl)} | {s['watch_s']} | {s['likes']} | {s['comments']} | "
                                     f"{s['shares']} | {s['saved']} | [open]({tl['permalink']}) |"))
    rows.sort(reverse=True)
    lines = ["# Live reel stats", "", f"Updated {store.now().astimezone(store.IST).strftime('%d %b %Y, %I:%M %p')} India time "
             "(refreshed about every 5 minutes)", "",
             "| posted | hook | views | views last hour | avg watch s | likes | comments | shares | saves | link |",
             "|---|---|---|---|---|---|---|---|---|---|"] + [r for _, r in rows]
    (STATS / "README.md").write_text("\n".join(lines) + "\n")
