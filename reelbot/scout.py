"""Daily: study what is working for other creators in the niche and turn it into things the bot can use.

1. Reads the latest public reels of the creator accounts we follow (official Business Discovery endpoint;
   hashtag search needs a Meta app review we do not have).
2. Ranks them by engagement per follower and picks the best new ones.
3. Listens to each one (speech to text with word timings) and looks at a few frames.
4. Asks Claude what makes each one work: the hook pattern, the structure, the format, the speaking pace.
5. Saves, for the generator:
   data/ideas.json        fresh angles for our own tools (new hooks, never copied lines)
   data/formats.json      story formats learned from other reels, tested like our own formats
   data/voice_style.json  how fast and with what pauses the best reels in the niche are spoken
   data/scout.json        which accounts work, which reels were already studied

Their videos and transcripts are only used inside the run and are never saved to the repo.
"""
import json
import re
import statistics
import subprocess
from pathlib import Path

import requests

from . import claude, store
from .config import OUT
from .instagram import IGError

PER_DAY = 6            # reels studied per run
MAX_ACCOUNTS = 30
MAX_FORMATS = 10
KEEP_IDEAS = 80


def accounts(cfg):
    state = store.read("scout", {})
    seed = cfg["research"].get("competitors", [])
    found = state.get("discovered", [])
    bad = {a for a, n in state.get("failures", {}).items() if n >= 3}
    return [a for a in dict.fromkeys(seed + found) if a not in bad][:MAX_ACCOUNTS]


def collect(cfg, ig, names, with_video=True):
    """Recent reels of each account, with engagement per 1,000 followers."""
    state = store.read("scout", {})
    fails = state.setdefault("failures", {})
    reels, ok = [], {}
    for name in names:
        try:
            followers, media = ig.discover(name, limit=20, with_video=with_video)
        except (IGError, KeyError) as e:
            fails[name] = fails.get(name, 0) + 1
            print(f"scout: @{name} not readable ({str(e)[:90]})")
            continue
        fails.pop(name, None)
        ok[name] = followers
        for m in media:
            if m.get("media_product_type") != "REELS":
                continue
            age_d = (store.now() - store.parse(m["timestamp"])).total_seconds() / 86400
            if age_d > 30:
                continue
            # likes + 3 x comments (+ views counted like 1 like per 20 views), per 1,000 followers
            eng = (m.get("like_count") or 0) + 3 * (m.get("comments_count") or 0) + (m.get("view_count") or 0) / 20
            per_k = 1000 * eng / max(followers, 1000)
            reels.append({"account": name, "followers": followers, "permalink": m.get("permalink", ""),
                          "caption": (m.get("caption") or "")[:600], "likes": m.get("like_count") or 0,
                          "comments": m.get("comments_count") or 0, "views": m.get("view_count") or 0,
                          "timestamp": m["timestamp"], "media_url": m.get("media_url"), "per_k": round(per_k, 1)})
    store.write("scout", state)
    return reels, ok


NICHE = re.compile(r"pdf|document|\bforms?\b|aadhaa?r|pan card|resume|\bcv\b|passport|photo size|photo resize|"
                   r"signature|\bscan|certificate|\bexams?\b|admit card|govt|sarkari|\bupload|marksheet|"
                   r"bank statement|excel|word file|compress|\bkb\b|cyber cafe|xerox|print")
USEFUL = re.compile(r"website|tool|\bapp\b|free|\bai\b|trick|hack|tips?\b|students?|useful|secret|nobody|stop")


def rank(r):
    """Reels about our kind of problem count three times, useful-tool reels one and a half; gadget launches less.
    Engagement is compared on a log scale so one viral video does not crowd out everything else."""
    import math
    cap = r["caption"].lower()
    weight = 3.0 if NICHE.search(cap) else 1.5 if USEFUL.search(cap) else 0.6
    return weight * math.log1p(r["per_k"])


def _listen(path, model):
    """Words with timings -> transcript, hook (first ~3 s) and how the speaker paces it."""
    wav = path.with_suffix(".wav")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(path), "-ar", "16000", "-ac", "1", str(wav)], check=True)
    import wave
    import numpy as np
    with wave.open(str(wav), "rb") as w:
        audio = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    segs, info = model.transcribe(audio, word_timestamps=True, vad_filter=True)
    words = [w for s in segs for w in (s.words or [])]
    if len(words) < 8:
        return None
    gaps = [b.start - a.end for a, b in zip(words, words[1:])]
    pauses = [g for g in gaps if g >= 0.25]
    spoken = (words[-1].end - words[0].start) - sum(g for g in gaps if g >= 0.6)
    return {"language": info.language, "transcript": " ".join(w.word.strip() for w in words),
            "hook": " ".join(w.word.strip() for w in words if w.start < words[0].start + 3.0),
            "first_word_at": round(float(words[0].start), 2), "seconds": round(float(words[-1].end), 1),
            "words_per_second": round(float(len(words) / max(spoken, 1)), 2),
            "pause_s": round(float(statistics.median(pauses)), 2) if pauses else 0.0,
            "pauses_per_10s": round(float(10 * len(pauses) / max(words[-1].end, 1)), 1)}


def _frames(path, out):
    """Six frames in one picture, so Claude can see the visual style."""
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(path), "-vf",
                    "fps=1/3,scale=240:-2,tile=6x1", "-frames:v", "1", str(out)], check=False)
    return out if out.exists() else None


SYSTEM = ("You study short-form video for a creator who promotes {name} ({url}), a free site with PDF and image "
          "tools for Indian students and job seekers. You explain precisely why reels work, and you turn what you "
          "learn into new ideas for our own reels. Never copy another creator's lines: learn the pattern, write new words.")

PROMPT = """These are the best-performing recent reels from creators in our niche, with what was said in them.
{frames_note}

{reels}

Our reels are narrated 3D low-poly animated stories (characters act out a tiny story, big captions, panels that
show files, errors, sizes and success). Our tools (id: name):
{tools}

Story formats we already use: {formats}

Return:
{{"reels": [{{"permalink": "...", "why_it_works": "one or two sentences", "hook_pattern": "the hook as a reusable pattern, e.g. 'Stop paying X for these N things'",
  "structure": ["beat 1", "beat 2", "..."], "visual_style": "what the viewer sees", "speaking_style": "pace, pauses, tone",
  "format_name": "snake_case name", "format_description": "how to tell a story of OUR 3D kind in this format, in one or two sentences, written as an instruction"}}],
 "ideas": [{{"tool": "one of our tool ids", "format": "a format name (ours or one from above)", "hook_en": "a new English hook for our reel",
   "hook_hinglish": "the same hook in casual Hinglish, Roman letters", "angle": "one line: the story", "from": "permalink that inspired it"}}],
 "voice_notes": "what the best speakers here do with pace, pauses and emphasis, in two sentences"}}

Give 4 to 8 ideas, spread over different tools, most promising first. A format_name that is really one of ours should use our name.
Our account cannot send DMs or links in replies, so never build an idea or format on "comment a word and I'll send
the link" or any other promise we cannot keep. Our call to action is: save this for your next form, the site name is on screen.
A format is a way of telling the story, not a call to action."""


def _study(cfg, studied, frames):
    tools = "\n".join(f"- {t['id']}: {t['tool']}" for t in cfg["content"]["topics"])
    known = list(dict.fromkeys(cfg["content"]["formats"] + list(store.read("formats", {}).get("learned", {}))))
    blocks = []
    for i, r in enumerate(studied, 1):
        a = r["audio"]
        blocks.append(
            f"REEL {i}: {r['permalink']} by @{r['account']} ({r['followers']} followers): {r['likes']} likes, "
            f"{r['comments']} comments{', ' + str(r['views']) + ' views' if r['views'] else ''}, "
            f"engagement {r['per_k']} per 1,000 followers\nCaption: {r['caption'][:300]}\n"
            + (f"Spoken ({a['language']}, {a['seconds']} s, {a['words_per_second']} words/s, pauses of {a['pause_s']} s, "
               f"{a['pauses_per_10s']} pauses per 10 s, first word at {a['first_word_at']} s):\n{a['transcript'][:1400]}"
               if a else "(no speech or video not available)")
            + (f"\nFrames: {r['frames']}" if r.get("frames") else ""))
    note = ("Each reel's six frames (one every 3 seconds) are in the image file named after 'Frames:'. "
            "Open them with the Read tool to see the visual style." if frames else "")
    b = cfg["brand"]
    return claude.ask_json(cfg, SYSTEM.format(name=b["name"], url=b["url"]),
                           PROMPT.format(frames_note=note, reels="\n\n".join(blocks), tools=tools,
                                         formats=", ".join(known)),
                           max_tokens=4000, read_files=frames and not cfg["secrets"]["anthropic"])


def _save(cfg, studied, result):
    topics = {t["id"] for t in cfg["content"]["topics"]}
    ours = set(cfg["content"]["formats"])
    fm = store.read("formats", {"learned": {}})
    for r in result.get("reels", []):
        name = re.sub(r"[^a-z0-9_]", "", (r.get("format_name") or "").lower().replace(" ", "_"))[:30]
        if name and name not in ours and name not in fm["learned"] and r.get("format_description"):
            fm["learned"][name] = {"description": r["format_description"][:400], "from": r.get("permalink", ""),
                                   "hook_pattern": r.get("hook_pattern", "")[:160], "added": store.iso()}
            print(f"scout: learned a new format: {name}")
    if len(fm["learned"]) > MAX_FORMATS:      # keep the newest; older untested ones make room
        fm["learned"] = dict(sorted(fm["learned"].items(), key=lambda kv: kv[1]["added"])[-MAX_FORMATS:])
    store.write("formats", fm)

    ideas = store.read("ideas", [])
    for i in result.get("ideas", []):
        if i.get("tool") in topics and i.get("hook_en"):
            ideas.append({**{k: str(i.get(k, ""))[:240] for k in ("tool", "format", "hook_en", "hook_hinglish", "angle", "from")},
                          "added": store.iso(), "used": 0})
    store.write("ideas", ideas[-KEEP_IDEAS:])

    notes = store.read("insights", [])
    notes += [{"at": store.iso(), "permalink": r.get("permalink"), "why": r.get("why_it_works", "")[:300],
               "hook_pattern": r.get("hook_pattern", "")[:160], "structure": r.get("structure", [])[:8],
               "visual": r.get("visual_style", "")[:200], "speaking": r.get("speaking_style", "")[:200]}
              for r in result.get("reels", [])]
    store.write("insights", notes[-60:])

    vs = store.read("voice_style", {"samples": []})
    vs["samples"] = (vs["samples"] + [{"wps": r["audio"]["words_per_second"], "pause_s": r["audio"]["pause_s"],
                                       "lang": r["audio"]["language"], "per_k": r["per_k"]}
                                      for r in studied if r.get("audio")])[-40:]
    if vs["samples"]:
        top = sorted(vs["samples"], key=lambda s: -s["per_k"])[: max(5, len(vs["samples"]) // 2)]   # the better half
        vs["words_per_second"] = round(statistics.median(s["wps"] for s in top), 2)
        vs["pause_s"] = round(statistics.median(s["pause_s"] for s in top if s["pause_s"]) if any(s["pause_s"] for s in top) else 0.3, 2)
    if result.get("voice_notes"):
        vs["notes"] = result["voice_notes"][:400]
    vs["updated"] = store.iso()
    store.write("voice_style", vs)
    return fm, ideas, vs


def run(cfg, ig, probe=False):
    if not ig.ready:
        print("scout: no Instagram credentials")
        return
    names = accounts(cfg) if not probe else list(dict.fromkeys(accounts(cfg) + cfg["research"].get("candidates", [])))
    reels, ok = collect(cfg, ig, names)
    print(f"scout: {len(ok)} of {len(names)} accounts readable; {len(reels)} reels from the last 30 days; "
          f"{sum(1 for r in reels if r['media_url'])} with a video link")
    if probe:
        for n, f in ok.items():
            mine = [r for r in reels if r["account"] == n]
            print(f"  @{n}: {f} followers, {len(mine)} recent reels, best {max([r['per_k'] for r in mine], default=0)} per 1k")
        return
    state = store.read("scout", {})
    seen = set(state.get("seen", []))
    fresh, per_account = [], {}
    for r in sorted((r for r in reels if r["permalink"] not in seen), key=lambda r: (bool(r["media_url"]), rank(r)),
                    reverse=True):
        if per_account.get(r["account"], 0) < 2 and len(fresh) < PER_DAY:     # spread over creators
            fresh.append(r)
            per_account[r["account"]] = per_account.get(r["account"], 0) + 1
    if not fresh:
        print("scout: nothing new to study")
        return

    from faster_whisper import WhisperModel
    model = WhisperModel("small", device="cpu", compute_type="int8")
    work = OUT / "scout"
    work.mkdir(parents=True, exist_ok=True)
    studied = []
    for i, r in enumerate(fresh):
        r["audio"] = None
        if r.get("media_url"):
            try:
                vid = work / f"r{i}.mp4"
                with requests.get(r["media_url"], timeout=120, stream=True) as resp:
                    resp.raise_for_status()
                    with open(vid, "wb") as f:
                        for chunk in resp.iter_content(1 << 20):
                            f.write(chunk)
                r["audio"] = _listen(vid, model)
                fr = _frames(vid, work / f"r{i}.jpg")
                r["frames"] = str(fr.relative_to(OUT.parent)) if fr else None
            except Exception as e:
                print(f"scout: could not study {r['permalink']}: {str(e)[:120]}")
        studied.append(r)
        a = r["audio"]
        print(f"scout: @{r['account']} {r['per_k']}/1k " + (f"{a['words_per_second']} w/s, pauses {a['pause_s']} s, hook: {a['hook'][:70]}" if a else "(caption only)"))

    frames = any(r.get("frames") for r in studied)
    try:
        result = _study(cfg, studied, frames)
    except claude.ClaudeError as e:
        if not frames:
            raise
        print(f"scout: study with frames failed ({e}); trying without")
        for r in studied:
            r["frames"] = None
        result = _study(cfg, studied, False)
    fm, ideas, vs = _save(cfg, studied, result)
    state["seen"] = (state.get("seen", []) + [r["permalink"] for r in studied])[-500:]
    state["accounts"] = ok
    state["updated"] = store.iso()
    # creators tagged in the best captions are often in the same niche: try them next time
    tagged = {m.lower() for r in studied for m in re.findall(r"@([A-Za-z0-9_.]{3,30})", r["caption"])}
    state["discovered"] = list(dict.fromkeys(state.get("discovered", []) + sorted(tagged - set(ok))))[:40]
    store.write("scout", state)
    for f in work.glob("*"):
        f.unlink()
    print(f"scout: studied {len(studied)} reels; {len(result.get('ideas', []))} new ideas; "
          f"{len(fm['learned'])} learned formats; niche pace {vs.get('words_per_second')} words/s, pauses {vs.get('pause_s')} s")


def digest(limit=6):
    """Short notes on what works in the niche, for the script prompt."""
    notes = store.read("insights", [])[-limit:]
    lines = [f"- {n['why']} Hook pattern: \"{n['hook_pattern']}\". Beats: {' > '.join(n['structure'][:6])}."
             for n in reversed(notes) if n.get("why")]
    vs = store.read("voice_style", {})
    if vs.get("notes"):
        lines.append(f"- How the best ones speak: {vs['notes']}")
    return "\n".join(lines)
