"""One full cycle: measure -> learn -> research -> then, per language: write -> voice -> render -> post."""
import shutil

from . import analyze, broll, learn, render, render3d, research, script, store, voice
from .config import OUT
from .instagram import Instagram


def posted_today(lang):
    today = store.now().date()
    return sum(1 for p in learn.of_language(lang)
               if p.get("media_id") and store.parse(p["posted_at"]).date() == today)


def make(cfg, plan, playbook=None):
    """Build one reel on disk. Returns the post record (not yet published)."""
    lang = next(l for l in cfg["content"]["languages"] if l["id"] == plan["language"])
    s = script.write(cfg, plan, playbook or {})
    rid = f"{store.now().strftime('%Y%m%d-%H%M%S')}-{lang['id']}"
    work = OUT / f"{rid}-work"
    work.mkdir(parents=True, exist_ok=True)
    story = cfg["content"].get("style") == "story3d"
    clip = None if story else broll.fetch(cfg, s["scenes"][0].get("broll"), work / "broll.mp4")
    if clip:
        s["scenes"][0]["broll_path"] = str(clip)
    audio, speech, starts, total = voice.synthesize(cfg, lang, s["scenes"], work)
    engine = render3d if story else render
    video = engine.render(cfg, s, audio, speech, starts, total, OUT / f"{rid}.mp4")
    shutil.rmtree(work, ignore_errors=True)
    s["scenes"][0].pop("broll_path", None)
    return {
        "id": rid, "created_at": store.iso(), "language": lang["id"], "topic": plan["topic"],
        "hook_style": plan["hook_style"], "format": plan["format"], "plan_reason": plan["reason"],
        "title": s.get("title", ""), "hook": s["scenes"][0]["screen"], "seconds": round(total, 1),
        "script": s, "caption": s["caption"].strip() + "\n\n" + " ".join(s["hashtags"]),
        "video": video.name,
    }


def run(cfg):
    if not cfg["posting"]["enabled"]:
        print("posting.enabled is false: nothing to do")
        return
    ig = Instagram(cfg)
    dry = cfg["posting"]["dry_run"]
    if not dry and not ig.ready:
        raise SystemExit("IG_USER_ID / IG_ACCESS_TOKEN missing. Set them, or use DRY_RUN=1.")

    analyze.collect(cfg, ig)                 # 1. read results of earlier reels
    if research.stale(cfg):                  # 2. refresh what works in the niche
        research.refresh(cfg, ig)

    failures = []
    for lang in [l["id"] for l in cfg["content"]["languages"]]:
        try:
            playbook = learn.update_playbook(cfg, lang)   # 3. turn results into rules
            if not dry and posted_today(lang) >= cfg["posting"]["per_language_per_day"]:
                print(f"[{lang}] daily limit reached")
                continue
            plan = learn.next_plan(cfg, lang)             # 4. pick topic, hook, format
            print("plan:", plan)
            post = make(cfg, plan, playbook)              # 5-7. script, voice, video
            print(f"[{lang}] made {post['video']} ({post['seconds']}s): {post['hook']}")
            if dry:
                post["dry_run"] = True
            else:                                         # 8. publish
                media_id, link = ig.publish_reel(
                    OUT / post["video"], post["caption"],
                    share_to_feed=cfg["posting"]["share_to_feed"],
                    ai_label=cfg["posting"]["label_ai_generated"])
                post.update(media_id=media_id, permalink=link, posted_at=store.iso(), checked=[])
                print(f"[{lang}] posted: {link}")
            posts = store.posts()
            posts.append(post)
            store.save_posts(posts)
        except Exception as e:  # one language failing must not block the other
            failures.append(f"{lang}: {e}")
            print(f"[{lang}] FAILED: {e}")
    analyze.report(cfg)
    if failures:
        raise SystemExit("; ".join(failures))
