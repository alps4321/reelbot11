"""The feedback loop: score each posted reel, pick what to try next, write a playbook.

Every reel is tagged with a topic, a hook style and a format. Results are averaged
per tag and per language; the bot mostly repeats what scores best and sometimes
tests something new.
"""
import random
from collections import defaultdict

from . import claude, store

ARMS = ("topic", "hook_style", "format")


def score(post):
    at48 = [h for h in post.get("history", []) if h.get("hours") == 48]
    m = at48[0] if at48 else post.get("metrics")
    if not m:
        return None
    base = (m.get("views", 0) + 8 * m.get("shares", 0) + 6 * m.get("saved", 0)
            + 3 * m.get("comments", 0) + m.get("likes", 0))
    if m.get("avg_watch_s") and post.get("seconds"):  # reward reels people watch, not skip
        base *= 0.5 + min(1.0, m["avg_watch_s"] / post["seconds"])
    return round(base)


def of_language(lang):
    return [p for p in store.posts() if p.get("language") == lang]


def arm_stats(posts, key):
    sums, counts = defaultdict(float), defaultdict(int)
    for p in posts:
        s = score(p)
        if s is not None and p.get(key):
            sums[p[key]] += s
            counts[p[key]] += 1
    return {k: {"n": counts[k], "avg": round(sums[k] / counts[k], 1)} for k in counts}


def choose(options, stats, explore_rate, avoid=()):
    pool = [o for o in options if o not in avoid] or list(options)
    untried = [o for o in pool if o not in stats]
    if untried and (random.random() < max(explore_rate, 0.5) or len(untried) == len(pool)):
        return untried[0], "new test"                    # untried options are tested in config order
    if random.random() < explore_rate or not any(o in stats for o in pool):
        return random.choice(pool), "explore"
    best = max((o for o in pool if o in stats), key=lambda o: stats[o]["avg"])
    return best, "best so far"


def live(posts):
    return [p for p in posts if p.get("media_id")]


def next_plan(cfg, lang, slot=0, today=None):
    """Pick the tool, hook and format for the next reel.

    Week 1: a different tool every post, so each one gets a first result.
    From week 2: on the two "winner days" every post is about the best-scoring tool; on the other days
    one post goes to a proven tool (top 5, rotating) and one tests a tool that has had the fewest posts.
    """
    c, rate = cfg["content"], cfg["learning"]["explore_rate"]
    today = today or store.today()
    posts = live(store.posts())
    topics = [t["id"] for t in c["topics"]]
    counts = {t: 0 for t in topics}
    last_used = {}
    for p in posts:
        if p["topic"] in counts:
            counts[p["topic"]] += 1
            last_used[p["topic"]] = p["posted_at"]
    today_topics = {p["topic"] for p in posts if store.local_date(p["posted_at"]) == today}
    stats = arm_stats(posts, "topic")
    first = min((store.local_date(p["posted_at"]) for p in posts), default=today)
    week = (today - first).days // 7

    def fresh(pool):
        return [t for t in pool if t not in today_topics] or list(pool)

    def test_pick():
        pool = fresh(topics)
        return min(pool, key=lambda t: (counts[t], topics.index(t)))   # fewest posts first, then list order

    if week == 0 or not stats:
        topic, mode = test_pick(), "week 1: every tool gets a first try"
    else:
        ranked = sorted(stats, key=lambda t: -stats[t]["avg"])
        winner = ranked[0]
        if today.weekday() in cfg["posting"].get("winner_days", []):
            topic, mode = winner, f"winner day: {winner} has the best average score"
        else:
            want = ("engaging", "test", "engaging" if today.toordinal() % 2 == 0 else "test")[min(slot, 2)]
            proven = fresh([t for t in ranked[1:6]] or ranked[:1])
            if want == "engaging":
                topic = min(proven, key=lambda t: last_used.get(t, ""))    # the one not shown for longest
                mode = "proven tool (top 5, rotating)"
            else:
                topic, mode = test_pick(), "testing a less-tried tool"

    mine = of_language(lang)
    hook, why_h = choose(c["hook_styles"], arm_stats(mine, "hook_style"), rate)
    fmt, why_f = choose(c["formats"], arm_stats(mine, "format"), rate)
    return {"language": lang, "topic": topic, "hook_style": hook, "format": fmt,
            "reason": f"{mode}; hook: {why_h}; format: {why_f}"}


def update_playbook(cfg, lang):
    """Ask Claude to turn one language's results table into rules for the next scripts."""
    posts = [p for p in of_language(lang) if score(p) is not None]
    books = store.read("playbook", {})
    book = books.get(lang, {"measured": 0, "keep": [], "avoid": [], "next_tests": []})
    if (len(posts) < cfg["learning"]["min_posts_for_playbook"] or len(posts) == book.get("measured")
            or not claude.available(cfg)):
        return book
    rows = "\n".join(
        f"- score {score(p)} | topic {p['topic']} | hook style {p['hook_style']} | format {p.get('format')} | "
        f"{p.get('seconds', 0):.0f}s | hook: \"{p['hook']}\" | metrics {p['metrics']}"
        for p in sorted(posts, key=score, reverse=True)
    )
    try:
        out = claude.ask_json(
            cfg,
            "You analyse short-form video results for one Instagram account. Be concrete. "
            "Only draw conclusions the data supports; with few posts, say what is still unproven.",
            f"Results of our {lang} reels, best first (avg_watch_s is seconds watched on average):\n{rows}\n\n"
            'Return {"keep": [up to 5 rules that the best reels share], '
            '"avoid": [up to 5 things the weakest reels share], '
            '"next_tests": [up to 3 specific things to test next]}',
            max_tokens=900,
        )
    except Exception as e:  # keep the old playbook if the call fails
        print("playbook: skipped,", e)
        return book
    book = {"measured": len(posts), "updated": store.iso(), "keep": out.get("keep", []),
            "avoid": out.get("avoid", []), "next_tests": out.get("next_tests", [])}
    books[lang] = book
    store.write("playbook", books)
    print(f"playbook[{lang}]: updated from {len(posts)} measured reels")
    return book
