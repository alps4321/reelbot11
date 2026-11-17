"""Reads each posted reel's results at 24h, 72h and 7 days, and writes the report."""
from . import learn, store
from .config import DATA
from .instagram import IGError


GUESS = [("aadhaar", "password", "unlock_aadhaar"), ("aadhaar", "print", "id_card_print"), ("too large", "", "resize_photo_kb"),
         ("50 kb", "", "resize_photo_kb"), ("passport", "", "passport_photo"), ("merge", "", "merge_pdf")]
HINDI = ("kya", "hai", "ka ", "ke ", "ki ", "kar", "mein", "nahi", "lo", "karo")


def import_existing(cfg, ig):
    """Add reels that are on the account but not in our records (posted by hand), so they are tracked too."""
    posts = store.posts()
    known = {p.get("media_id") for p in posts}
    try:
        media = ig._call("GET", f"{ig.uid}/media", fields="id,caption,media_product_type,timestamp,permalink",
                         limit=50).get("data", [])
    except Exception as e:
        print("import: skipped,", e)
        return
    added = 0
    for m in media:
        if m["id"] in known or m.get("media_product_type") != "REELS":
            continue
        cap = (m.get("caption") or "").lower()
        topic = next((t for a, b, t in GUESS if a in cap and b in cap), "general")
        posts.append({"id": f"manual-{m['id']}", "created_at": m["timestamp"], "posted_at": m["timestamp"],
                      "media_id": m["id"], "permalink": m.get("permalink", ""), "manual": True,
                      "language": "hinglish" if sum(w in cap for w in HINDI) >= 2 else "english",
                      "topic": topic, "hook_style": "manual", "format": "manual", "seconds": 0,
                      "hook": (m.get("caption") or "").split("\n")[0][:60], "caption": m.get("caption", ""), "checked": []})
        added += 1
    if added:
        posts.sort(key=lambda p: p.get("posted_at") or p["created_at"])
        store.save_posts(posts)
        print(f"import: added {added} reels posted outside the bot")


def collect(cfg, ig):
    if not ig.ready:
        return 0
    import_existing(cfg, ig)
    posts, done = store.posts(), 0
    for p in posts:
        if not p.get("media_id"):
            continue
        age_h = (store.now() - store.parse(p["posted_at"])).total_seconds() / 3600
        due = [h for h in cfg["learning"]["check_hours"] if age_h >= h and h not in p.get("checked", [])]
        if not due:
            continue
        try:
            m = ig.insights(p["media_id"])
        except IGError as e:
            print(f"analyze: {p['id']} failed: {e}")
            continue
        if not m:
            continue
        if "ig_reels_avg_watch_time" in m:  # API returns milliseconds
            m["avg_watch_s"] = round(m.pop("ig_reels_avg_watch_time") / 1000, 1)
        m.pop("ig_reels_video_view_total_time", None)
        p["metrics"] = m
        p.setdefault("history", []).append({"at": store.iso(), "hours": max(due), **m})
        p["checked"] = sorted(set(p.get("checked", [])) | set(due))
        done += 1
    store.save_posts(posts)
    print(f"analyze: updated {done} reels")
    return done


def report(cfg):
    posts = store.posts()
    book = store.read("playbook", {})
    lines = ["# ReelBot report", "", f"Updated {store.iso()}", "",
             f"Reels made: {len(posts)}. Posted: {sum(1 for p in posts if p.get('media_id'))}. "
             f"Measured: {sum(1 for p in posts if p.get('metrics'))}.", ""]

    for lang in [l["id"] for l in cfg["content"]["languages"]]:
        mine = learn.of_language(lang)
        for key in learn.ARMS:
            stats = learn.arm_stats(mine, key)
            if stats:
                lines += [f"## {lang}: results by {key.replace('_', ' ')}", "",
                          "| " + key + " | reels | avg score |", "|---|---|---|"]
                lines += [f"| {k} | {v['n']} | {v['avg']} |"
                          for k, v in sorted(stats.items(), key=lambda kv: -kv[1]["avg"])]
                lines.append("")
        b = book.get(lang, {})
        if b.get("keep") or b.get("avoid"):
            lines += [f"## {lang}: what the bot has learned", ""]
            for name in ("keep", "avoid", "next_tests"):
                lines += [f"**{name.replace('_', ' ').title()}**", ""] + [f"- {x}" for x in b.get(name, [])] + [""]

    lines += ["## Reels", "", "| date | lang | topic | format | hook | views | watch s | likes | comments | shares | saves | score | link |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for p in reversed(posts):
        m = p.get("metrics") or {}
        g = lambda k: m.get(k, "")
        link = f"[open]({p['permalink']})" if p.get("permalink") else ("dry run" if p.get("dry_run") else "")
        lines.append(f"| {p['created_at'][:10]} | {p.get('language', '')} | {p['topic']} | {p.get('format', '')} | "
                     f"{p['hook']} | {g('views')} | {g('avg_watch_s')} | "
                     f"{g('likes')} | {g('comments')} | {g('shares')} | {g('saved')} | "
                     f"{learn.score(p) or ''} | {link} |")
    (DATA / "report.md").write_text("\n".join(lines) + "\n")
