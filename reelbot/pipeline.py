"""One full cycle: measure -> learn -> research -> then, per language: write -> voice -> render -> post."""
import shutil
from datetime import timedelta

from . import analyze, broll, learn, notify, render, render2d, render3d, research, script, store, voice
from .config import OUT, ROOT
from .instagram import Instagram


def posted_today():
    return learn.posted_today()


def make(cfg, plan, playbook=None):
    """Build one reel on disk. Returns the post record (not yet published)."""
    lang = next(l for l in cfg["content"]["languages"] if l["id"] == plan["language"])
    style = cfg["content"].get("style")
    s = script.write(cfg, plan, playbook or {})
    rid = f"{store.now().strftime('%Y%m%d-%H%M%S')}-{lang['id']}"
    work = OUT / f"{rid}-work"
    work.mkdir(parents=True, exist_ok=True)
    story = style in ("story3d", "explainer")
    clip = None if story else broll.fetch(cfg, s["scenes"][0].get("broll"), work / "broll.mp4")
    if clip:
        s["scenes"][0]["broll_path"] = str(clip)
    audio, speech, starts, total = voice.synthesize(cfg, lang, s["scenes"], work, pace=plan.get("pace", "calm"))
    engine = render2d if style == "explainer" else render3d if style == "story3d" else render
    video = engine.render(cfg, s, audio, speech, starts, total, OUT / f"{rid}.mp4")
    shutil.rmtree(work, ignore_errors=True)
    s["scenes"][0].pop("broll_path", None)
    for sc in s["scenes"]:
        sc.pop("_phrases", None)
    return {
        "id": rid, "created_at": store.iso(), "language": lang["id"], "topic": plan["topic"],
        "hook_style": plan["hook_style"], "format": plan["format"], "pace": plan.get("pace", "calm"), "distance": plan.get("distance"),
        "idea": (plan.get("idea") or {}).get("hook_en", ""), "plan_reason": plan["reason"],
        "title": s.get("title", ""), "hook": s["scenes"][0]["screen"], "seconds": round(total, 1),
        "script": s, "caption": s["caption"].strip() + "\n\n" + " ".join(s["hashtags"]),
        "video": video.name,
    }


def go_live_time(cfg, started):
    """The posting time this run is for: the first one in posting.times after the run started, if it is
    within 90 minutes (runs start about 70 minutes early so the reel is ready in time). A run started at any
    other time, or very late, posts as soon as its reel is ready."""
    from datetime import timedelta
    day = started.astimezone(store.IST)
    for t in cfg["posting"].get("times", []):
        h, m = map(int, t.split(":"))
        at = day.replace(hour=h, minute=m, second=0, microsecond=0)
        if at > day:
            return at if at - day <= timedelta(minutes=90) else None
    return None


def intended_start(started):
    """When this run was meant to start: a timed run's cron time (GitHub often starts them late), or the
    slot a backup trigger asked for (REELBOT_SLOT=11:00 means 'the reel that goes live at 11:00')."""
    import os
    from datetime import timedelta
    slot = os.environ.get("REELBOT_SLOT", "").strip()
    if slot:
        h, m = map(int, slot.split(":"))
        at = started.astimezone(store.IST).replace(hour=h, minute=m, second=0, microsecond=0)
        return at - timedelta(minutes=70)
    cron = os.environ.get("REELBOT_SCHEDULE", "").split()
    if len(cron) == 5 and cron[0].isdigit() and cron[1].isdigit():
        at = started.replace(hour=int(cron[1]), minute=int(cron[0]), second=0, microsecond=0)
        return at if at <= started else at - timedelta(days=1)
    return started


def post_queued(cfg, ig, item_path, go_live_at=None):
    """Post a reel that was made outside the daily generator (queue/<name>.json + its video)."""
    import json
    item = json.loads(item_path.read_text())
    video = ROOT / item["video"]
    media_id, link = ig.publish_reel(video, item["caption"], share_to_feed=cfg["posting"]["share_to_feed"],
                                     ai_label=cfg["posting"]["label_ai_generated"], go_live_at=go_live_at)
    post = {"id": item_path.stem, "created_at": store.iso(), "posted_at": store.iso(), "media_id": media_id,
            "permalink": link, "checked": [], "language": item.get("language", "english"),
            "topic": item.get("topic", "general"), "hook_style": item.get("hook_style", "manual"),
            "format": item.get("format", "manual"), "hook": item.get("hook", ""), "seconds": item.get("seconds", 0),
            "caption": item["caption"], "queued": True}
    posts = store.posts()
    posts.append(post)
    store.save_posts(posts)
    video.unlink()
    item_path.unlink()
    print(f"[queue] posted {item_path.stem}: {link}")
    notify.posted(cfg, post)


def run(cfg):
    if not cfg["posting"]["enabled"]:
        print("posting.enabled is false: nothing to do")
        return
    started = store.now()
    target = go_live_time(cfg, intended_start(started))
    if target:
        print(f"this run is for the {target:%H:%M} reel")
    ig = Instagram(cfg)
    dry = cfg["posting"]["dry_run"]
    if not dry and not ig.ready:
        raise SystemExit("IG_USER_ID / IG_ACCESS_TOKEN missing. Set them, or use DRY_RUN=1.")

    analyze.collect(cfg, ig)                 # 1. read results of earlier reels
    if research.stale(cfg):                  # 2. refresh what works in the niche
        research.refresh(cfg, ig)

    queue = ROOT / "queue"
    if (queue / "HOLD").exists():                      # a reel is being made by hand; do not post another
        print("queue/HOLD is set: not posting this run")
        analyze.report(cfg)
        return
    ready = sorted(queue.glob("*.json")) if queue.exists() else []
    if ready and not dry:                              # a finished reel was dropped in the queue: post it first
        post_queued(cfg, ig, ready[0], target)
        analyze.report(cfg)
        return

    slots = cfg["posting"]["slots"]
    done = posted_today()
    times = cfg["posting"].get("times", [])
    taken = learn.slots_taken()
    at = f"{target:%H:%M}" if target else ""
    if not dry:
        why = None
        if target and store.now() > target + timedelta(hours=2):
            why = f"the {target:%Y-%m-%d %H:%M} slot was missed by more than 2 hours (GitHub started this run late)"
        elif at and at in taken:
            why = f"the {at} reel is already live"
        elif not at and times and all(t in taken for t in times):
            why = f"all {len(times)} reels for today are posted"
        elif done >= len(slots) + 1:
            why = f"{done} reels are already live today, the daily maximum"
        if why:
            print(f"{why}: nothing to post")
            analyze.report(cfg)
            return
    # each time keeps its language (11:00 Hinglish, 1:00 pm English, 7:00 pm Hinglish), even after a missed slot
    slot = times.index(at) if at in times and times.index(at) < len(slots) else min(done, len(slots) - 1)
    lang = slots[slot]
    failures = []
    try:
        playbook = learn.update_playbook(cfg, lang)       # 3. turn results into rules
        plan = learn.next_plan(cfg, lang, slot)           # 4. pick tool, hook, format
        print("plan:", plan)
        post = make(cfg, plan, playbook)                  # 5-7. script, voice, video
        print(f"[{lang}] made {post['video']} ({post['seconds']}s): {post['hook']}")
        if dry:
            post["dry_run"] = True
        else:                                             # 8. publish
            media_id, link = ig.publish_reel(
                OUT / post["video"], post["caption"],
                share_to_feed=cfg["posting"]["share_to_feed"],
                ai_label=cfg["posting"]["label_ai_generated"], go_live_at=target)
            post.update(media_id=media_id, permalink=link, posted_at=store.iso(), checked=[], slot=at or None)
            print(f"[{lang}] posted: {link}")
            learn.mark_idea_used(plan.get("idea"))
            notify.posted(cfg, post)
        posts = store.posts()
        posts.append(post)
        store.save_posts(posts)
    except Exception as e:
        failures.append(f"{lang}: {e}")
        print(f"[{lang}] FAILED: {e}")
    analyze.report(cfg)
    if failures:
        raise SystemExit("; ".join(failures))
