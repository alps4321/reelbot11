"""Reads each posted reel's results at 24h, 72h and 7 days, and writes the report."""
from . import learn, store
from .config import DATA
from .instagram import IGError


def collect(cfg, ig):
    if not ig.ready:
        return 0
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
