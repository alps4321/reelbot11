"""Telegram updates for the owner: a summary every 3 hours, a message when a reel goes live, and one when a run fails.

Setup (free): create a bot with @BotFather in Telegram, press Start in the new bot's chat, and save its token as the
GitHub secret TELEGRAM_BOT_TOKEN. The bot finds your chat by itself from that first message and remembers it
(GitHub Actions cache, so the chat number never appears in this public repo). TELEGRAM_CHAT_ID can set it directly.
"""
import html
import os
from datetime import timedelta
from pathlib import Path

import requests

from . import store

CHAT_FILE = Path(os.environ.get("TG_CHAT_FILE", Path.home() / ".cache" / "reelbot" / "tg_chat"))
API = "https://api.telegram.org/bot{token}/{method}"


def _api(cfg, method, **params):
    r = requests.post(API.format(token=cfg["secrets"]["telegram"], method=method), json=params, timeout=30)
    data = r.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram {method}: {data.get('description', r.status_code)}")
    return data["result"]


def _chat(cfg):
    if cfg["secrets"].get("telegram_chat"):
        return cfg["secrets"]["telegram_chat"]
    if CHAT_FILE.exists() and CHAT_FILE.read_text().strip():
        return CHAT_FILE.read_text().strip()
    updates = _api(cfg, "getUpdates", limit=100)
    chats = [u["message"]["chat"]["id"] for u in updates if u.get("message", {}).get("chat", {}).get("type") == "private"]
    if not chats:
        return None
    chat = str(chats[-1])
    if os.environ.get("GITHUB_ACTIONS") == "true":
        print(f"::add-mask::{chat}", flush=True)
    CHAT_FILE.parent.mkdir(parents=True, exist_ok=True)
    CHAT_FILE.write_text(chat)
    return chat


def send(cfg, text, silent=False):
    if not cfg["secrets"].get("telegram"):
        print("notify: Telegram is not set up (no TELEGRAM_BOT_TOKEN); this is what would be sent:\n" + text)
        return False
    try:
        chat = _chat(cfg)
        if not chat:
            print("notify: no chat yet. Open your bot in Telegram and press Start (or send it any message).")
            return False
        _api(cfg, "sendMessage", chat_id=chat, text=text[:4000], parse_mode="HTML",
             disable_web_page_preview=True, disable_notification=silent)
        print("notify: sent")
        return True
    except Exception as e:            # a message must never break posting
        print(f"notify: could not send ({str(e)[:150]})")
        return False


def e(x):
    return html.escape(str(x), quote=False)


def tool_name(cfg, topic):
    return next((t["tool"] for t in cfg["content"]["topics"] if t["id"] == topic), topic.replace("_", " ").title())


def label(cfg, post):
    """The tool's name, or the start of the hook for reels that are not about one tool."""
    if any(t["id"] == post.get("topic") for t in cfg["content"]["topics"]):
        return tool_name(cfg, post["topic"])
    hook = (post.get("hook") or post.get("caption") or "").split("\n")[0].strip()
    return (hook[:34] + "…") if len(hook) > 35 else hook or tool_name(cfg, post.get("topic", ""))


def posted(cfg, post):
    if not cfg.get("notify", {}).get("on_post", True):
        return
    send(cfg, f"✅ <b>New reel is live</b>\n{e(label(cfg, post))} · {e(post.get('language', '').title())}\n"
              f"Hook: {e(post.get('hook', ''))}\n{e(post.get('permalink', ''))}")


def failed(cfg, what, url=""):
    if not cfg.get("notify", {}).get("on_failure", True):
        return
    send(cfg, f"⚠️ <b>{e(what)} failed</b>\nI'll look at it, or open the details:\n{e(url)}")


def _fmt(n):
    return f"{n / 1000:.1f}K" if n >= 1000 else str(n)


def _failed_runs(since):
    """Failed GitHub Actions runs since `since` (needs GITHUB_TOKEN; skipped otherwise)."""
    token, repo = os.environ.get("GITHUB_TOKEN"), os.environ.get("GITHUB_REPOSITORY")
    if not (token and repo):
        return []
    try:
        r = requests.get(f"https://api.github.com/repos/{repo}/actions/runs", timeout=30,
                         headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
                         params={"per_page": 50, "created": f">={since:%Y-%m-%dT%H:%M:%SZ}"})
        return [(x["name"], x["html_url"]) for x in r.json().get("workflow_runs", []) if x.get("conclusion") == "failure"]
    except Exception:
        return []


def digest(cfg):
    """The every-3-hours summary: how the reels are doing and whether anything needs the owner."""
    from . import learn, watch

    now = store.now().astimezone(store.IST)
    posts = [p for p in learn.live(store.posts())]
    times = cfg["posting"].get("times", [])
    done = learn.posted_today()
    lines = [f"📊 <b>ReelBot</b> · {now:%I:%M %p}".replace(" 0", " ")]

    nxt = ""
    if done < len(times):
        upcoming = [t for t in times if t > f"{now:%H:%M}"]
        if upcoming:
            lang = cfg["posting"]["slots"][min(done, len(cfg["posting"]["slots"]) - 1)]
            try:
                topic = learn.next_plan(cfg, lang, done)["topic"]
                nxt = f" · next {upcoming[0]}: {e(tool_name(cfg, topic))} ({lang.title()})"
            except Exception:
                nxt = f" · next {upcoming[0]} ({lang.title()})"
    lines.append(f"Today: {done} of {len(times)} posted{nxt}")

    rows, gained, latest_t, best = [], 0, None, None
    for p in sorted(posts, key=lambda p: p["posted_at"], reverse=True):
        tl = watch.timeline(p["media_id"])
        s = tl["samples"][-1] if tl and tl["samples"] else None
        if s:
            g = watch.growth(tl, 3)
            gained += g
            t = store.parse(s["t"])
            latest_t = max(latest_t, t) if latest_t else t
            views, watch_s, shares, saves = s["views"], s["watch_s"], s["shares"], s["saved"]
        else:
            m = p.get("metrics", {})
            g, views, watch_s, shares, saves = 0, m.get("views", 0), m.get("avg_watch_s", 0), m.get("shares", 0), m.get("saved", 0)
        if not best or views > best[0]:
            best = (views, p)
        age_d = (store.now() - store.parse(p["posted_at"])).total_seconds() / 86400
        if age_d <= 3 and len(rows) < 5:
            secs = f"/{p['seconds']:.0f}s" if p.get("seconds") else "s"
            rows.append(f"• <b>{e(label(cfg, p))}</b> ({p.get('language', '')[:2].upper()}): "
                        f"{_fmt(views)} views (+{_fmt(g)}), watch {watch_s}{secs}, {shares} shares, {saves} saves "
                        f"<a href=\"{e(p.get('permalink', ''))}\">open</a>")
    lines.append(f"Last 3 hours: +{_fmt(gained)} views")
    if rows:
        lines += ["", "<b>Recent reels</b>"] + rows
    if best and best[0]:
        lines.append(f"\n🏆 Best so far: {e(label(cfg, best[1]))} · {_fmt(best[0])} views")

    needs = []
    for name, url in _failed_runs(store.now() - timedelta(hours=3, minutes=10)):
        needs.append(f"⚠️ {e(name)} failed: {e(url)}")
    if latest_t and store.now() - latest_t > timedelta(minutes=45):
        needs.append(f"⚠️ The 5-minute stats have not updated since {latest_t.astimezone(store.IST):%I:%M %p}")
    for i, t in enumerate(times):
        h, m = map(int, t.split(":"))
        due = now.replace(hour=h, minute=m, second=0, microsecond=0) + timedelta(minutes=30)
        if now > due and done <= i:
            needs.append(f"⚠️ The {t} reel has not gone live")
            break
    learned = [k for k, v in store.read("formats", {}).get("learned", {}).items()
               if store.now() - store.parse(v["added"]) < timedelta(hours=24)]
    ideas = [i for i in store.read("ideas", []) if not i.get("used")]
    lines.append("")
    lines += needs or ["✅ Nothing needed from you"]
    lines.append(f"🔎 Scout: {len(ideas)} fresh ideas waiting" + (f"; new formats in the last day: {', '.join(x.replace('_', ' ') for x in learned)}" if learned else ""))

    tip = _tip(cfg, "\n".join(lines))
    if tip:
        lines.append(f"\n💡 {e(tip)}")
    quiet = now.hour >= 23 or now.hour < 8
    return send(cfg, "\n".join(lines), silent=quiet)


def _tip(cfg, summary):
    """One practical takeaway from Claude; skipped quietly if Claude is not available."""
    try:
        from . import claude
        out = claude.ask_json(cfg, "You coach a small Instagram account promoting a free PDF/image tools site in India.",
                              "From this status, give ONE short practical takeaway (max 25 words) about what is working "
                              "or what to change. If there is too little data, say what to watch next. "
                              f'Return {{"tip": "..."}}\n\n{summary}', max_tokens=200)
        return str(out.get("tip", ""))[:220]
    except Exception as ex:
        print(f"notify: no tip ({str(ex)[:80]})")
        return ""
