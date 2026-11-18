"""Start whatever is due. Runs after every stats check (every 5 minutes when GitHub's timer is on time).

GitHub's own schedules are best-effort and on this account they are often dropped. So every time any check
runs, it looks at the clock and at today's runs and starts what should have started but did not:
  - the reel run for each time in posting.times (70 minutes ahead, or late but still today)
  - the Telegram summary at each notify.digest_hours
  - the daily scout
Each one is started at most once per window, and the reel run itself skips a slot that is already live,
so a late GitHub timer and this catch-up can never post the same reel twice.
"""
import os
from datetime import timedelta, timezone

import requests

from . import learn, store

REEL, SUMMARY, SCOUT = "ReelBot", "Telegram summary", "Reel scout"


def _gh(method, path, **kw):
    token, repo = os.environ.get("GITHUB_TOKEN"), os.environ.get("GITHUB_REPOSITORY")
    if not (token and repo):
        raise RuntimeError("no GITHUB_TOKEN")
    r = requests.request(method, f"https://api.github.com/repos/{repo}/{path}", timeout=30,
                         headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}, **kw)
    r.raise_for_status()
    return r.json() if r.content else {}


def _start(workflow, inputs=None):
    _gh("POST", f"actions/workflows/{workflow}/dispatches", json={"ref": "main", "inputs": inputs or {}})


def _at(now, hhmm):
    h, m = map(int, hhmm.split(":"))
    return now.replace(hour=h, minute=m, second=0, microsecond=0)


def plan(cfg, now, runs, posted):
    """What to start now. `runs`: [(name, created_at as datetime)], `posted`: reels live today."""
    todo = []

    def started_since(name, since):
        return any(n == name and t >= since for n, t in runs)

    times = cfg["posting"].get("times", [])
    for i, hhmm in enumerate(times):
        live = _at(now, hhmm)
        if live - timedelta(minutes=70) <= now <= live + timedelta(minutes=40) and posted <= i \
                and not started_since(REEL, live - timedelta(minutes=80)):
            todo.append(("reelbot.yml", {"slot": hhmm}, f"the {hhmm} reel"))
            break                                   # one reel run at a time
    for h in cfg.get("notify", {}).get("digest_hours", []):
        at = now.replace(hour=h, minute=3, second=0, microsecond=0)
        if at <= now <= at + timedelta(minutes=50) and not started_since(SUMMARY, at - timedelta(minutes=5)):
            todo.append(("notify.yml", {}, f"the {h}:00 summary"))
    scout_at = _at(now, "09:11")
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if scout_at <= now <= scout_at + timedelta(hours=4) and not started_since(SCOUT, day_start):
        todo.append(("scout.yml", {"probe": "false"}, "the daily scout"))
    return todo


def run(cfg):
    now = store.now().astimezone(store.IST)
    day_start_utc = now.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)
    try:
        data = _gh("GET", "actions/runs", params={"per_page": 100, "created": f">={day_start_utc:%Y-%m-%dT%H:%M:%SZ}"})
    except Exception as e:
        print(f"due: cannot read today's runs ({str(e)[:100]})")
        return
    runs = [(r["name"], store.parse(r["created_at"]).astimezone(store.IST)) for r in data.get("workflow_runs", [])]
    for workflow, inputs, what in plan(cfg, now, runs, learn.posted_today()):
        try:
            _start(workflow, inputs)
            print(f"due: started {what} (it had not started on time)")
        except Exception as e:
            print(f"due: could not start {what}: {str(e)[:120]}")
