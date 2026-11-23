"""Build the data files for the ReelBot control-room dashboard.

Reads the bot's own records (data/*.json, config.yaml), the 5-minute stats timelines (stats branch,
checked out at STATS_DIR) and a list of recent GitHub Actions runs (RUNS_JSON, saved from the API),
and writes one JSON file per dashboard source into OUT_DIR. Nothing here talks to Instagram.

Usage: python tools/dashboard_data.py STATS_DIR RUNS_JSON OUT_DIR
"""
import glob
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from reelbot import config, learn, store  # noqa: E402

IST = timezone(timedelta(hours=5, minutes=30))
STYLE_SWITCH = datetime(2026, 11, 18, 18, 22, tzinfo=timezone.utc)   # flat explainer style went live
FORMAT_NAMES = {
    "secret_answer": "Question + checked answer", "story": "Short story", "discovery": "Discovery",
    "myth_buster": "Myth buster", "did_you_know": "Did you know", "three_things": "Three things",
    "versus": "Versus", "mistake": "Common mistake", "behind_the_scenes": "Behind the scenes",
    "what_if": "What if", "same_task_before_after": "Before / after", "cheat_sheet": "Cheat sheet",
    "manual": "Posted by hand",
}


def t(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00").replace("+0000", "+00:00"))


def ist(dt, fmt="%d %b, %I:%M %p"):
    return dt.astimezone(IST).strftime(fmt).replace(" 0", " ").lstrip("0")


def pretty(s):
    return FORMAT_NAMES.get(s or "", (s or "").replace("_", " ").capitalize())


def style_of(p, posted):
    if p.get("manual"):
        return "Posted by hand"
    if posted >= STYLE_SWITCH:
        return "Flat explainer"
    if posted.astimezone(IST).date() == datetime(2026, 11, 18).date():
        return "3D story"
    return "Early bot style"


def tracking(age_h, last_t, now):
    if age_h > 24 * 30:
        return "Stopped (over 30 days)"
    if age_h < 48:
        return "Every check (under 2 days old)"
    if age_h < 24 * 7:
        return "Hourly (2-7 days old)"
    return "Daily (7-30 days old)"


def reels(stats_dir, now, excluded):
    posts = {p.get("media_id"): p for p in store.posts() if p.get("media_id")}
    rows = []
    for f in glob.glob(f"{stats_dir}/reels/*.json"):
        d = json.load(open(f))
        s = d.get("samples") or []
        if not s:
            continue
        p = posts.get(d["media_id"], {})
        posted = t(d["posted_at"])
        last = s[-1]
        age_h = (now - posted).total_seconds() / 3600

        def views_at(hours_ago):
            cut = t(last["t"]) - timedelta(hours=hours_ago)
            prev = [x for x in s if t(x["t"]) <= cut]
            return prev[-1]["views"] if prev else 0
        at24 = [x for x in s if x["h"] <= 26]
        sc = learn.score(p) if p else None
        if d["media_id"] in excluded:
            learning = "No: you left it out"
        elif sc is None:
            learning = "Not yet (needs 24h of data)"
        else:
            learning = "Yes"
        a = p.get("answer")
        rows.append({
            "media_id": d["media_id"],
            "reel": (p.get("permalink") or d.get("permalink") or "").rstrip("/").rsplit("/", 1)[-1],
            "posted": ist(posted), "posted_at": posted.isoformat(), "slot": p.get("slot") or "",
            "language": (p.get("language") or "").capitalize(), "style": style_of(p, posted),
            "format": pretty(p.get("format")), "answer": (a.get("id") if isinstance(a, dict) else a) or "",
            "tool": p.get("topic") or "", "hook": (d.get("hook") or p.get("hook") or "")[:90],
            "views": last["views"], "views_24h": at24[-1]["views"] if at24 and age_h >= 24 else None,
            "watch_s": last.get("watch_s"), "likes": last["likes"], "comments": last["comments"],
            "shares": last["shares"], "saves": last["saved"], "reach": last.get("reach"),
            "gain_3h": last["views"] - views_at(3), "gain_24h": last["views"] - views_at(24),
            "age_h": round(age_h, 1), "tracking": tracking(age_h, last["t"], now),
            "last_read": ist(t(last["t"])), "in_learning": learning, "score": sc,
            "link": p.get("permalink") or d.get("permalink") or "",
            "scout_idea": ((p.get("idea") or {}).get("hook_en", "") if isinstance(p.get("idea"), dict)
                           else (p.get("idea") or ""))[:120],
        })
    rows.sort(key=lambda r: r["posted_at"], reverse=True)
    return rows


JOB = {"ReelBot": "Make and post a reel", "Stats watch": "Read Instagram stats",
       "Telegram summary": "Telegram summary", "Reel scout": "Study competitor reels"}


def runs(path, now, posts):
    out = []
    raw = json.load(open(path))
    # each bot post belongs to the one reel run that finished soonest after it went live
    owner = {}
    for p in posts:
        if not p.get("media_id") or p.get("manual") is True:
            continue
        at = t(p["posted_at"])
        cands = [r for r in raw if r["name"] == "ReelBot" and t(r["created_at"]) <= at <= t(r["updated_at"])]
        if cands:
            owner[min(cands, key=lambda r: t(r["updated_at"]) - at)["id"]] = p
    for r in raw:
        created = t(r["created_at"])
        if now - created > timedelta(hours=72):
            continue
        detail = ""
        if r["name"] == "ReelBot":
            hit = [owner[r["id"]]] if r["id"] in owner else []
            if hit:
                detail = f"Posted {hit[0].get('permalink', '')}"
            elif r["conclusion"] == "success":
                detail = "Posted nothing: its slot was missed or already posted"
            elif r["conclusion"] == "failure":
                detail = "Failed (see the run log)"
        out.append({
            "started": ist(created), "started_at": created.isoformat(), "job": JOB.get(r["name"], r["name"]),
            "started_by": "GitHub's timer" if r["event"] == "schedule" else "A catch-up check",
            "result": {"success": "Done", "failure": "Failed", "cancelled": "Cancelled", None: "Running"}.get(
                r["conclusion"], r["conclusion"] or r["status"]),
            "detail": detail, "run": r["html_url"],
        })
    return out


def jobs(run_rows, now):
    spec = [("Read Instagram stats", "Every 5 minutes", 288), ("Make and post a reel", "11:00, 13:00, 19:00 IST", 3),
            ("Telegram summary", "Every 3 hours (8 am-11 pm)", 6), ("Study competitor reels", "Once a day", 1)]
    rows = []
    for name, target, per_day in spec:
        mine = [r for r in run_rows if r["job"] == name]
        day = [r for r in mine if now - t(r["started_at"]) <= timedelta(hours=24)]
        last = mine[0] if mine else None
        if name == "Make and post a reel":
            posted = sum(r["detail"].startswith("Posted http") for r in day)
            note = f"{posted} posted; {sum('Posted nothing' in r['detail'] for r in day)} extra timer runs posted nothing; {sum(r['result'] == 'Failed' for r in day)} failed"
        else:
            note = f"{len(day)} runs (target {per_day})"
        rows.append({"job": name, "target": target, "target_per_day": per_day, "ran_24h": len(day), "note": note,
                     "on_timer_24h": sum(r["started_by"] == "GitHub's timer" for r in day),
                     "last_run": last["started"] if last else "", "last_result": last["result"] if last else ""})
    return rows


def schedule(cfg, now):
    times, langs = cfg["posting"]["times"], cfg["posting"]["slots"]
    proven = cfg["posting"].get("proven_slots", [])
    posts = [p for p in store.posts() if p.get("media_id")]
    rows, today = [], now.astimezone(IST).date()
    answers_cfg = cfg["content"].get("answers") or []
    used = {}
    for p in posts:
        a = p.get("answer")
        a = a.get("id") if isinstance(a, dict) else a
        if a:
            used[a] = used.get(a, 0) + 1
    day_tools = {}
    for p in posts:
        day_tools.setdefault(store.local_date(p["posted_at"]), set()).add(p.get("topic"))

    def rotate(day):
        fresh = [a for a in answers_cfg if a["tool"] not in day_tools.get(day, set())]
        if not fresh:
            return None
        a = min(fresh, key=lambda a: (used.get(a["id"], 0), answers_cfg.index(a)))
        used[a["id"]] = used.get(a["id"], 0) + 1
        day_tools.setdefault(day, set()).add(a["tool"])
        return a
    for day in (today, today + timedelta(days=1)):
        for i, (hhmm, lang) in enumerate(zip(times, langs)):
            when = datetime.combine(day, datetime.strptime(hhmm, "%H:%M").time(), IST)
            done = next((p for p in posts if p.get("slot") == hhmm and store.local_date(p["posted_at"]) == day), None)
            if done:
                a = done.get("answer")
                rows.append({"when": ist(when), "when_at": when.isoformat(), "slot": hhmm, "language": lang.capitalize(),
                             "plan": pretty(done.get("format")), "answer": (a.get("id") if isinstance(a, dict) else a) or "",
                             "tool": done.get("topic", ""), "status": "Posted", "link": done.get("permalink", "")})
                continue
            plan = ("Question + checked answer" if hhmm in proven else "Rotating format test")
            ans = rotate(day) if hhmm in proven and when > now else None
            rows.append({"when": ist(when), "when_at": when.isoformat(), "slot": hhmm, "language": lang.capitalize(), "plan": plan,
                         "answer": ans["id"] if ans else "",
                         "tool": ans["tool"] if ans else "", "status": "Next" if when > now and not any(
                             r["status"] == "Next" for r in rows) else ("Waiting" if when > now else "Missed"),
                         "link": ""})
    return rows


def answers(cfg, reel_rows):
    used, best, watch = {}, {}, {}
    for r in reel_rows:
        if r["answer"]:
            used[r["answer"]] = used.get(r["answer"], 0) + 1
            best[r["answer"]] = max(best.get(r["answer"], 0), r["views"])
            watch.setdefault(r["answer"], []).append(r["watch_s"] or 0)
    nxt = learn.pick_answer(cfg)
    return [{"id": a["id"], "question": a.get("question", ""), "answer": a.get("answer", ""), "tool": a["tool"],
             "times_used": used.get(a["id"], 0), "best_views": best.get(a["id"]),
             "avg_watch_s": round(sum(watch[a["id"]]) / len(watch[a["id"]]), 1) if a["id"] in watch else None,
             "next_up": "Yes" if nxt and nxt["id"] == a["id"] else "", "source": a.get("source", "")}
            for a in cfg["content"].get("answers", [])]


def competitors():
    ins = store.read("insights", [])
    rows = [{"added": ist(t(i["at"]), "%d %b"), "added_at": i["at"], "link": i["permalink"], "why": i["why"],
             "hook_pattern": i.get("hook_pattern", ""), "structure": " → ".join(i.get("structure") or []),
             "visual": i.get("visual", ""), "speaking": i.get("speaking", "")} for i in ins]
    rows.sort(key=lambda r: r["added_at"], reverse=True)
    fm = store.read("formats", {}).get("learned", {})
    formats = sorted(({"format": k.replace("_", " ").capitalize(), "description": v.get("description", ""),
                       "hook_pattern": v.get("hook_pattern", ""), "added": ist(t(v["added"]), "%d %b") if v.get("added") else "",
                       "added_at": v.get("added", ""), "link": v.get("from", "")} for k, v in fm.items()),
                     key=lambda r: r["added_at"], reverse=True)
    sc = store.read("scout", {})
    accts = [{"account": "@" + k, "followers": v, "status": "Studied daily"} for k, v in sc.get("accounts", {}).items()]
    accts += [{"account": "@" + k, "followers": None, "status": "Can't be read (Instagram refuses)"}
              for k in sc.get("failures", {})]
    accts.sort(key=lambda r: -(r["followers"] or 0))
    ideas = [{"tool": i["tool"], "format": i["format"].replace("_", " ").capitalize(), "hook_hinglish": i.get("hook_hinglish", ""),
              "hook_en": i.get("hook_en", ""), "used": "Used" if i.get("used") else "Waiting",
              "added": ist(t(i["added"]), "%d %b") if i.get("added") else "", "added_at": i.get("added", ""),
              "link": i.get("from", "")} for i in store.read("ideas", [])]
    ideas.sort(key=lambda r: r["added_at"], reverse=True)
    v = store.read("voice_style", {})
    voice = [{"finding": v.get("notes", ""), "words_per_second": float(v.get("words_per_second") or 0),
              "pause_s": float(v.get("pause_s") or 0), "samples": len(v.get("samples", [])),
              "updated": ist(t(v["updated"])) if v.get("updated") else ""}]
    return rows, formats, accts, ideas, voice


NICHE = __import__("re").compile(r"pdf|document|form|aadhaa?r|pan card|resume|passport|photo|signature|exam|govt|sarkari")


def scout_views():
    """What the scout sees: competitor reels with their real view counts, and what it did each day."""
    r = store.read("research", {})
    seen = sorted(r.get("items", []), key=lambda x: -x.get("views", 0))
    top = [{"account": x["source"], "views": x.get("views", 0), "likes": x.get("likes", 0),
            "caption": (x.get("caption") or "").split("\n")[0][:90], "link": x["permalink"],
            "our_niche": "Yes" if NICHE.search((x.get("caption") or "").lower()) else "No"} for x in seen]
    days = {}
    for i in store.read("insights", []):
        days.setdefault(i["at"][:10], {}).setdefault("studied", 0)
        days[i["at"][:10]]["studied"] += 1
    for i in store.read("ideas", []):
        if i.get("added"):
            days.setdefault(i["added"][:10], {}).setdefault("ideas", 0)
            days[i["added"][:10]]["ideas"] += 1
    for v in store.read("formats", {}).get("learned", {}).values():
        if v.get("added"):
            days.setdefault(v["added"][:10], {}).setdefault("formats", 0)
            days[v["added"][:10]]["formats"] += 1
    log = [{"day": datetime.strptime(d, "%Y-%m-%d").strftime("%d %b"), "date": d, "studied": v.get("studied", 0),
            "ideas": v.get("ideas", 0), "formats": v.get("formats", 0)} for d, v in sorted(days.items())]
    return top, log


def stages(job_rows, run_rows, posts, cfg):
    by = {r["job"]: r for r in job_rows}
    pb = store.read("playbook", {})
    upd = max((b.get("updated", "") for b in pb.values()), default="")
    last_post = max((p for p in posts if p.get("media_id")), key=lambda p: p["posted_at"], default=None)
    sc = store.read("scout", {})
    def st(job):
        r = by.get(job, {})
        return r.get("last_run", ""), ("ok" if r.get("last_result") == "Done" else "bad" if r.get("last_result") == "Failed" else "warn")
    rows = []
    t1, s1 = st("Study competitor reels")
    rows.append({"order": 1, "stage": "Scout", "what": "Studies competitor reels", "last": t1, "state": s1,
                 "detail": f"{len(sc.get('seen', []))} reels studied from {len(sc.get('accounts', {}))} accounts"})
    t2, s2 = st("Make and post a reel")
    rows.append({"order": 2, "stage": "Create", "what": "Writes the script, voices and renders the reel", "last": t2, "state": s2,
                 "detail": by.get("Make and post a reel", {}).get("note", "")})
    rows.append({"order": 3, "stage": "Post", "what": "Publishes to @ilovedocumentss", "last": ist(t(last_post["posted_at"])) if last_post else "",
                 "state": "ok" if last_post else "warn", "detail": (last_post or {}).get("permalink", "")})
    t4, s4 = st("Read Instagram stats")
    rows.append({"order": 4, "stage": "Watch", "what": "Reads every reel's numbers", "last": t4,
                 "state": "warn" if by.get("Read Instagram stats", {}).get("ran_24h", 0) < 48 else s4,
                 "detail": by.get("Read Instagram stats", {}).get("note", "")})
    rows.append({"order": 5, "stage": "Learn", "what": "Rewrites its rules from results", "last": ist(t(upd)) if upd else "",
                 "state": "ok" if upd else "warn", "detail": f"{max((b.get('measured', 0) for b in pb.values()), default=0)} reels measured"})
    t6, s6 = st("Telegram summary")
    rows.append({"order": 6, "stage": "Report", "what": "Sends you a Telegram summary", "last": t6, "state": s6,
                 "detail": by.get("Telegram summary", {}).get("note", "")})
    return rows


def playbook():
    rows = []
    for lang, b in store.read("playbook", {}).items():
        for kind, key in (("Keep doing", "keep"), ("Avoid", "avoid"), ("Test next", "next_tests")):
            for i, text in enumerate(b.get(key, [])):
                rows.append({"id": f"{lang}-{key}-{i}", "language": lang.capitalize(), "kind": kind, "text": text,
                             "measured": b.get("measured"), "updated": ist(t(b["updated"]), "%d %b") if b.get("updated") else ""})
    return rows


def main(stats_dir, runs_json, out_dir):
    now = datetime.now(timezone.utc)
    cfg = config.load()
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    excluded = set(store.read("exclude", []))
    reel_rows = reels(stats_dir, now, excluded)
    run_rows = runs(runs_json, now, store.posts())
    ins, fmts, accts, ideas, voice = competitors()
    seen_top, scout_log = scout_views()
    files = {"reels": reel_rows, "runs": run_rows, "jobs": (job_rows := jobs(run_rows, now)), "schedule": schedule(cfg, now),
             "answers": answers(cfg, reel_rows), "insights": ins[:30], "formats": fmts, "accounts": accts,
             "ideas": ideas[:60], "voice": voice, "playbook": playbook(),
             "seen": seen_top, "scoutlog": scout_log, "stages": stages(job_rows, run_rows, store.posts(), cfg),
             "snapshot": [{"built": ist(now), "built_at": now.isoformat(), "reels": len(reel_rows)}]}
    notes = json.load(open(ROOT / "tools" / "dashboard_notes.json"))
    files.update({k: v for k, v in notes.items() if not k.startswith("_")})
    for name, rows in files.items():
        (out / f"{name}.json").write_text(json.dumps(rows, ensure_ascii=False, indent=0))
    print({k: len(v) for k, v in files.items()})


if __name__ == "__main__":
    main(*sys.argv[1:4])
