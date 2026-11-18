"""Simulates three weeks of the bot (3 reels a day) with a fake Instagram, fake Claude and a fake clock.

Checks: week 1 tests a different tool every post; from week 2 the winner days go to the best tool and
other days mix proven and new tools; results are read and the report is written. No network, no keys.
Run:  python tests/simulate.py
"""
import random
import sys
import tempfile
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from reelbot import analyze, claude, config, instagram, learn, pipeline, render, render2d, render3d, script, store

tmp = Path(tempfile.mkdtemp())
store.DATA = analyze.DATA = tmp
pipeline.OUT = tmp
cfg = config.load()
cfg["secrets"].update(anthropic="fake", ig_user_id="1", ig_token="t")
cfg["posting"]["dry_run"] = False
cfg["voice"]["provider"] = "none"
random.seed(7)

GOOD = "pdf_to_word"                     # the fake audience loves this tool
clock = [datetime(2026, 11, 16, 7, 0, tzinfo=timezone.utc)]   # a Monday
store.now = lambda: clock[0]
published, current = {}, [None]


class FakeIG(instagram.Instagram):
    base = "https://graph.facebook.com/v25.0"

    def _call(self, method, path, **params):
        return {"data": []}

    def hashtag_top(self, tag, limit=25):
        return []

    def publish_reel(self, video_path, caption, **kw):
        mid = f"m{len(published) + 1}"
        published[mid] = current[0]
        return mid, f"https://instagram.com/reel/{mid}"

    def insights(self, media_id):
        v = int((9000 if published[media_id] == GOOD else 800) * random.uniform(0.7, 1.3))
        return {"views": v, "reach": int(v * .8), "likes": v // 20, "comments": v // 200,
                "shares": v // 100, "saved": v // 80, "ig_reels_avg_watch_time": 7400}


def fake_claude(cfg, system, prompt, max_tokens=2000):
    if "Results of our" in prompt:
        return {"keep": ["x"], "avoid": ["y"], "next_tests": ["z"]}
    lang = cfg["content"]["languages"][1 if "Devanagari" in prompt else 0]
    s = script._offline_story(cfg, "t", lang)
    kinds = ["phone_upload", "split_flap", "counter", "file_shrink", "steps", "privacy", "spotlight", "browser"]
    for i, sc in enumerate(s["scenes"]):       # explainer reels: one drawing per shot, the site only at the end
        sc["scene"] = {"type": kinds[i % len(kinds)]}
        sc["say"] = sc["voice"] = f"A useful thing number {i}" if i < len(s["scenes"]) - 1 else "Save this, ilovedocuments.ai"
    return s


real_plan = learn.next_plan


def plan(cfg, lang, slot=0, today=None):
    p = real_plan(cfg, lang, slot, today)
    current[0] = p["topic"]
    return p


claude.ask_json = fake_claude
render.render = render2d.render = render3d.render = lambda cfg, s, a, sp, st, total, out: (Path(out).write_bytes(b"x"), Path(out))[1]
pipeline.Instagram = FakeIG
learn.next_plan = plan

for day in range(21):
    for hour in (7, 13, 15):             # the three scheduled runs (UTC)
        clock[0] = datetime(2026, 11, 16, hour, 30, tzinfo=timezone.utc) + timedelta(days=day)
        pipeline.run(cfg)

posts = [p for p in store.posts() if p.get("media_id")]
by_day = {}
for p in posts:
    by_day.setdefault(store.local_date(p["posted_at"]), []).append(p["topic"])
assert len(posts) == 63, len(posts)
assert all(len(v) == 3 for v in by_day.values()), "three reels every day"
start = min(by_day)
winner_days = [d for d in by_day if d.weekday() in cfg["posting"]["winner_days"] and d >= start + timedelta(days=7)]
assert all(len(set(v)) == 3 for d, v in by_day.items() if d not in winner_days), "no tool twice on a normal day"
week1 = [p["topic"] for p in posts[:21]]
assert len(set(week1)) == 21, "week 1 tests 21 different tools"
assert sum(1 for p in posts if p.get("metrics")) >= 55
assert winner_days and all(set(by_day[d]) == {GOOD} for d in winner_days), "winner days go to the best tool"
later = Counter(p["topic"] for p in posts[21:])
print("week 1 tools:", len(set(week1)), "| weeks 2-3 most used:", later.most_common(4))
print("winner days:", [(str(d), by_day[d]) for d in winner_days])
assert later[GOOD] == max(later.values()), "the winning tool gets the most posts after week 1"
assert len(later) >= 12, "new tools keep being tested after week 1"
assert (tmp / "report.md").exists()
print("SIMULATION OK")
