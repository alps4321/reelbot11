"""Simulates 30 days of the loop with a fake Instagram and fake Claude (no network).

Checks that results are read, scores change the next plan, and the report is written.
Run:  python tests/simulate.py
"""
import random
import sys
import tempfile
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from reelbot import analyze, claude, config, instagram, learn, pipeline, render, render3d, script, store

tmp = Path(tempfile.mkdtemp())
store.DATA = analyze.DATA = tmp
pipeline.OUT = tmp
cfg = config.load()
cfg["secrets"].update(anthropic="fake", ig_user_id="1", ig_token="t")
cfg["posting"].update(dry_run=False, per_language_per_day=1)
cfg["voice"]["provider"] = "none"
random.seed(7)

GOOD_TOPIC = "resize_photo_kb"   # the fake audience loves this topic
published = {}
current_topic = [None]


class FakeIG(instagram.Instagram):
    def hashtag_top(self, tag, limit=25):
        return [{"media_product_type": "REELS", "caption": f"viral {tag} tip", "like_count": 900,
                 "comments_count": 40, "permalink": f"https://ig/{tag}", "timestamp": "2026-11-01"}]

    def publish_reel(self, video_path, caption, **kw):
        mid = f"m{len(published) + 1}"
        published[mid] = current_topic[0]
        return mid, f"https://instagram.com/reel/{mid}"

    def insights(self, media_id):
        base = 9000 if published[media_id] == GOOD_TOPIC else 800
        v = int(base * random.uniform(0.7, 1.3))
        return {"views": v, "reach": int(v * .8), "likes": v // 20, "comments": v // 200,
                "shares": v // 100, "saved": v // 80, "ig_reels_avg_watch_time": 7400}


def fake_claude(cfg, system, prompt, max_tokens=2000):
    if "Results of our" in prompt:
        return {"keep": ["photo size topics"], "avoid": ["vague hooks"], "next_tests": ["shorter hooks"]}
    lang = cfg["content"]["languages"][1 if "Devanagari" in prompt else 0]
    s = script._offline_story(cfg, "t", lang)
    s["scenes"][0]["screen"] = f"Hook {random.randint(1000, 9999)}?"
    return s


def fake_render(cfg, s, audio, speech, starts, total, out):
    Path(out).write_bytes(b"x")
    return Path(out)


real_plan = learn.next_plan


def plan(cfg, lang):
    p = real_plan(cfg, lang)
    current_topic[0] = p["topic"]
    return p


claude.ask_json = fake_claude
render.render = render3d.render = fake_render
pipeline.Instagram = FakeIG
learn.next_plan = plan

for day in range(30):
    pipeline.run(cfg)
    posts = store.posts()          # move the clock: age every post by one day
    for p in posts:
        for k in ("posted_at", "created_at"):
            p[k] = store.iso(store.parse(p[k]) - timedelta(days=1))
    store.save_posts(posts)

posts = store.posts()
assert len(posts) == 60 and all(p["media_id"] for p in posts)
measured = [p for p in posts if p.get("metrics")]
assert len(measured) >= 56, len(measured)
assert {p["language"] for p in posts} == {"english", "hinglish"}
assert all(p["metrics"]["avg_watch_s"] == 7.4 for p in measured)
assert store.read("playbook", {})["hinglish"]["keep"] == ["photo size topics"]
early = sum(p["topic"] == GOOD_TOPIC for p in posts[:24])
late = sum(p["topic"] == GOOD_TOPIC for p in posts[36:])
print(f"good topic used {early}x in first 24 posts, {late}x in last 24 posts")
assert late > early, "bot did not shift toward the winning topic"
assert (tmp / "report.md").exists()
print((tmp / "report.md").read_text()[:1300])
print("SIMULATION OK")
