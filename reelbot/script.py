"""Writes the reel script (scenes, narration, visuals, caption) with Claude, then checks it."""
import re

from . import claude, research, scout, store

SYSTEM = """You write scripts for faceless Instagram Reels (9:16) for {name} ({url}): {tagline}.
Each reel is fast: a new visual every 2-3 seconds, big on-screen text, animated file/upload
graphics, voiceover with word-by-word captions. Viewers decide in the first second whether to skip.
Audience: {audience}
Tone: {tone}
You may only make these product claims: {facts}
Never invent statistics, prices, testimonials or official rules. Sizes used in visuals must be
realistic examples, not promises. Never copy wording from other creators' captions; they are shown
only so you can see which subjects and hooks get attention.
Language: {write_in}"""

FORMATS = {
    "problem_fix": "Show the painful moment (upload rejected), then the fix in 2-3 quick steps, then the result.",
    "three_mistakes": "Three mistakes people make with this task, one scene each, then the easy way.",
    "before_after": "Open on the before/after size reveal, then show how in 2 steps.",
    "myth_buster": "State a common wrong belief about this task, break it, show the right way.",
}

PROMPT = """Write one reel.

Topic: {topic}
Format: {format} - {format_help}
Hook style: {hook_style}  (question | problem | bold_claim | number | how_to)
Spoken length: {lo}-{hi} seconds, about {wlo}-{whi} spoken words in total.

What is working for other creators in this niche right now (studied by our scout; learn the pattern,
never copy their words):
{research}

What our own results have taught us so far:
keep: {keep}
avoid: {avoid}
test next: {tests}

Hooks we used recently (do not repeat them): {recent}

Rules:
- 6 to 8 scenes, each 2-4 seconds of speech. Scene 1 kind "hook". Middle scenes "step" or "point". Last scene "cta".
- The hook names the viewer's exact pain in the first second. No greeting, no "did you know".
- "screen": the big on-screen text, at most 6 words, no emoji, no hashtags.
- "voice": what is spoken in that scene, one short sentence. Numbers and units written the way they are said.
  {voice_rule}
- "emphasis": 1-2 words from "screen" to highlight.
- "visual": an animated graphic for the scene. Use one in at least 3 scenes. Options:
    {{"type": "error", "file": "photo.jpg", "size": "2.4 MB", "message": "File too large. Max 50 KB"}}
    {{"type": "size_drop", "file": "photo.jpg", "from": "2.4 MB", "to": "48 KB"}}
    {{"type": "success", "file": "photo.jpg", "size": "48 KB", "message": "Uploaded"}}
    {{"type": "none"}}
  Sizes are a number plus KB or MB. "message" is at most 5 words.
- "broll" (hook scene only): 2-3 English words describing a stock video for the background,
  for example "stressed student laptop".
- The cta scene's screen text is "{cta}".
- Caption: 2-3 short lines in the same language, a question to invite comments, then the site.
  At most {max_tags} hashtags.

Return:
{{"title": "...", "scenes": [{{"kind": "hook", "screen": "...", "voice": "...", {say_field}"emphasis": ["..."],
  "visual": {{"type": "error", "file": "...", "size": "...", "message": "..."}}, "broll": "..."}}],
 "caption": "...", "hashtags": ["#..."]}}"""

STORY_FORMATS = {
    "what_if": 'Open with "What if ...?" and play the idea out over time (labels like DAY 1, WEEK 2), '
               "with one named character who struggles, a small funny or warm twist near the end.",
    "deadline_story": "One named person, a ticking clock (labels are clock times), the upload fails, "
                      "the fix, success with seconds left.",
    "two_friends": "Two friends with the same task: one does it the hard way, one the easy way. Light humour.",
    "explainer": 'Answer one "Why does ...?" question about this task in plain steps, then show the fix.',
    "secret_answer": "Open on a question almost everyone has already asked themselves about this task. "
                     "Rule out two wrong guesses, then reveal the answer in the last third. Our best reel used this.",
    "boss_junior": "A boss loses his temper at a junior over a file problem; the junior fixes it in seconds; "
                   "the boss goes quiet and asks how. End on a punchline. English or Indian first names.",
}

STORY_PROMPT = """Write one reel as a low-poly 3D animated short story (like the viral "What if" 3D story reels):
simple 3D characters act out a tiny story while a narrator tells it, with big captions.

Topic: {topic}
Story format: {format} - {format_help}
Hook style: {hook_style}
{idea}Spoken length: {lo}-{hi} seconds, about {wlo}-{whi} spoken words in total.

What is working for other creators in this niche right now (studied by our scout; learn the pattern,
never copy their words):
{research}

What our own results have taught us so far:
keep: {keep}
avoid: {avoid}
test next: {tests}

Hooks we used recently (do not repeat them): {recent}

Story rules:
- 6 to 8 shots, each ONE short spoken sentence (3 to 7 words). Keep the whole reel under 24 seconds. First shot kind "hook", last shot kind "cta",
  the rest "point". No scene-setting shots: every shot must change something.
- What our own reels have shown: a curiosity question over a character scene keeps people (skip rate under 40%);
  opening on an error card or anything that looks like an advert loses them (skip rate 57%). So shot 1 is a
  character in a situation with NO panel, and the hook line is a question or claim that cannot be answered
  without watching on. Most viewers leave between second 3 and 9, so by shot 3 raise the stakes or add a
  second hook ("but that is not the problem", "wait for the last step").
- Hold the real answer back until the last third, then show it clearly (size_drop, success or text panel).
- The hook is a question or a claim the viewer must see answered. It is spoken AND shown as "screen" text.
- Give the main character an Indian first name. Concrete details beat general statements
  (a time on the clock, a real file size, a specific form).
- The product appears as the turning point of the story, not as an advert. One mention of the site is enough.
- End by telling people to save it for their next form (saves are our strongest signal), and put a comment
  prompt in the caption.

Each shot has:
- "kind", "screen" (hook and cta only need it; at most 8 words; cta screen is "{cta}"), "emphasis" (1-2 words of screen)
- "voice": the narration as it is pronounced. {voice_rule}
  Write it the way a good storyteller SPEAKS, not the way text is read: short sentences, one idea each.
  Put "..." where the speaker would pause for effect: after the hook question, and right before the answer.
  At most one "..." per shot. Use contractions and everyday words. Never a list of features in one breath.
- "say": the same line as it should be written in the captions (Roman letters, numbers as digits, ilovedocuments.ai).
- "label": optional short time/place tag shown at the top, like "11:58 PM", "DAY 3", "NEXT MORNING".
- "set": one of park, sunset, night, bedroom, office, exam.
- "camera": one of wide, close, push_in, orbit, low, high. Vary it from shot to shot.
- "actors": 1 to 3 of {{"color": orange|blue|green|red|purple|yellow|teal|pink|grey, "pose": stand|walk|sit|type|sad|cheer|phone|point|panic|wave,
   "x": -1.3 to 1.3, "look": left|right|camera, "float": {{"text": "2.4 MB", "color": "#ff5a66"}} (optional text floating over the head)}}.
   Keep the same colour for the same character in every shot.
- "props": 0 or 1 of
   {{"type": "panel", "show": "error", "file": "photo.jpg", "size": "2.4 MB", "message": "Max size 50 KB"}}
   {{"type": "panel", "show": "size_drop", "file": "photo.jpg", "from": "2.4 MB", "to": "48 KB"}}
   {{"type": "panel", "show": "success", "file": "photo.jpg", "size": "48 KB", "message": "Uploaded"}}
   {{"type": "panel", "show": "text", "text": "MAX 50 KB"}}
   {{"type": "clock", "text": "11:58 PM"}}
   {{"type": "paper"}}
  Use a panel in at least 3 shots: it is how the viewer sees the problem and the fix.

Caption: 2-3 short lines in the same language, a comment prompt, then the site. At most {max_tags} hashtags.

Return:
{{"title": "...", "scenes": [{{"kind": "hook", "screen": "...", "emphasis": ["..."], "voice": "...", "say": "...",
  "label": null, "set": "night", "camera": "push_in", "actors": [{{"color": "orange", "pose": "type"}}], "props": []}}],
 "caption": "...", "hashtags": ["#..."]}}"""

EXPLAINER_PROMPT = """Write one reel as a flat, hand-drawn animated explainer (cream paper, coral and black drawings).
Every sentence is one shot: the sentence builds on screen word by word as a big headline while a drawing
animates under it. It must feel like a smart friend telling you about a find: confident, quick, concrete.

Topic: {topic}
Hook style: {hook_style}
{idea}Spoken length: 22-28 seconds, about 65-85 spoken words in total, 8 or 9 shots.

What is working for other creators in this niche right now (studied by our scout; learn the pattern,
never copy their words):
{research}

What our own results have taught us so far:
keep: {keep}
avoid: {avoid}

Hooks we used recently (do not repeat them): {recent}

The structure (it comes from a reel that performed very well; follow it):
1. HOOK (shot 1, kind "hook"): one bold, specific line that makes the viewer stay. A surprising claim or the exact
   pain ("Your form just rejected a 2 MB PDF?"). No greeting, no brand name yet.
2. REVEAL (shot 2): name the fix: the site ilovedocuments.ai and the tool.
3. PROOF NUMBER (shot 3): one concrete true number ("45 free tools. No sign-up.").
4. BREAKDOWN (2-3 shots): exactly what happens for THIS topic, with real-looking details (file names, sizes, steps).
5. TRUST (1 shot): why it is safe or easy (it runs in your browser, files are not uploaded, works on the phone).
6. PAYOFF (1 shot, the second-to-last): an identity line that makes the viewer feel powerful
   ("You just became your own cyber cafe."). Use the "spotlight" scene.
7. CTA (last shot, kind "cta"): tell them to save it for their next form. Never ask them to comment for a link or a DM:
   we cannot send links. Use the "cta" scene.

Writing rules:
- Each "say" is one spoken sentence of 4 to 12 words. Short words. Contractions. Speak like a person, not an ad.
- Numbers as digits in "say". Never state another business's price as a fact.
- "accent": 1 or 2 words copied exactly from "say" (with their punctuation) that carry the meaning; they are shown in
  coral italic. Numbers are highlighted automatically.
- "tag": a 1-3 word lowercase section label shown at the top left (like "upload error", "the fix", "how").
- "meter": optional small counter shown at the top right, e.g. {{"label": "SIZE", "value": "180 KB"}} or {{"label": "PRICE", "value": "Rs 0"}}.
- "voice": the narration as it is pronounced. {voice_rule} Put "..." where the speaker pauses for effect (at most
  one per shot; use it after the hook and right before the payoff). The voice engine stumbles on some words: write
  "water mark" and "sign up" as two words, and keep brand and tool names simple.
- "say": the same line in Roman letters for the headline (ilovedocuments.ai written like that).
- "scene": one drawing per shot, from this list (use at least 6 different ones; params in brackets):
  phone_upload {{"state": "error"|"success", "file": "marksheet.pdf", "size": "2.4 MB", "text": "File too large. Max 200 KB", "title": "Exam form"}}
  file_shrink {{"file": "resume.pdf", "from": "2.4 MB", "to": "180 KB"}}
  stamp {{"word": "FREE", "on": "big text on the card", "label": "small label", "sub": "optional line"}}
  counter {{"value": 45, "label": "free tools", "badge": "NO SIGN-UP"}}
  tool_grid {{"highlight": "the tool name", "count": 45}}
  steps {{"items": ["Upload", "Pick 200 KB", "Download"]}}   (2 or 3 items, 1-2 words each)
  browser {{"url": "ilovedocuments.ai", "button": "the tool name"}}
  before_after {{"before": "2.4 MB", "after": "180 KB", "before_label": "REJECTED", "after_label": "ACCEPTED"}}
  cyber_cafe {{"price": "Paid", "text": "per page", "free": "FREE"}}
  privacy {{"text": "Never uploaded"}}
  deadline {{"time": "11:59 PM", "text": "TODAY"}}
  id_card {{"title": "Exam form", "name": "Riya Sharma", "sub": "photo 35 x 45 mm"}}
  split_flap {{"word": "ILOVEDOCS", "sub": "ilovedocuments.ai"}}   (word max 12 letters)
  convert {{"from": "PDF", "to": "WORD", "text": "Fully editable"}}
  photo_cutout {{"text": "Background removed"}}
  spotlight {{"title": "2-12 letters, the identity, e.g. CYBER CAFE"}}
  cta {{"keyword": "SAVE", "line": "// free · no sign-up · no watermark"}}

Caption: 2-3 short lines in the same language as the reel, a question that invites a comment, then the site.
At most {max_tags} hashtags.

Return:
{{"title": "...", "scenes": [{{"kind": "hook", "say": "...", "voice": "...", "accent": ["..."], "tag": "...",
  "meter": {{"label": "...", "value": "..."}}, "scene": {{"type": "phone_upload", "state": "error", "file": "...", "size": "...", "text": "..."}}}}],
 "caption": "...", "hashtags": ["#..."]}}"""

EXPLAINER_SCENES = {"phone_upload", "file_shrink", "stamp", "counter", "tool_grid", "steps", "browser", "before_after",
                    "cyber_cafe", "privacy", "deadline", "id_card", "split_flap", "convert", "photo_cutout",
                    "spotlight", "cta"}


def _clean_explainer(sc, last):
    scene = sc.get("scene") if isinstance(sc.get("scene"), dict) else {}
    kind = scene.get("type")
    if last:
        scene = {**scene, "type": "cta"} if kind != "cta" else scene
    elif kind not in EXPLAINER_SCENES or kind == "cta":
        scene = {"type": "stamp", "word": "FREE", "on": (sc.get("say") or "")[:24]}
    sc["scene"] = {k: (v[:3] if isinstance(v, list) else v) for k, v in scene.items() if v is not None}
    sc["accent"] = [str(a) for a in (sc.get("accent") or [])][:2]
    sc["tag"] = str(sc.get("tag") or "").lower()[:24]
    m = sc.get("meter")
    sc["meter"] = {"label": str(m.get("label", ""))[:12].upper(), "value": str(m.get("value", ""))[:10]} if isinstance(m, dict) else None
    sc["screen"] = (sc.get("say") or sc.get("voice") or "").replace("...", " ")[:60]


SETS = {"park", "sunset", "night", "bedroom", "office", "exam"}
CAMERAS = {"wide", "close", "push_in", "orbit", "low", "high"}
POSES = {"yell", "talk", "stand", "walk", "sit", "type", "sad", "cheer", "phone", "point", "panic", "wave"}


def _clean_shot(sc):
    """Make a 3D shot safe for the renderer: unknown values fall back to defaults."""
    sc["set"] = sc.get("set") if sc.get("set") in SETS else "park"
    sc["camera"] = sc.get("camera") if sc.get("camera") in CAMERAS else "wide"
    actors = []
    for a in (sc.get("actors") or [])[:3]:
        if not isinstance(a, dict):
            continue
        try:
            x = max(-1.5, min(1.5, float(a.get("x", 0))))
        except (TypeError, ValueError):
            x = 0.0
        actor = {"color": str(a.get("color", "orange")), "pose": a.get("pose") if a.get("pose") in POSES else "stand",
                 "x": x}
        if a.get("look") in ("left", "right", "camera"):
            actor["look"] = a["look"]
        if a.get("tie"):
            actor["tie"] = True
        if a.get("screen") == "error":
            actor["screen"] = "error"
        f = a.get("float")
        if isinstance(f, dict) and f.get("text"):
            actor["float"] = {"text": str(f["text"])[:10], "color": str(f.get("color", "#ffffff"))[:9]}
        actors.append(actor)
    sc["actors"] = actors or [{"color": "orange", "pose": "stand", "x": 0.0}]
    props = []
    for p in (sc.get("props") or [])[:1]:
        if not isinstance(p, dict):
            continue
        if p.get("type") == "panel":
            if p.get("show") == "text" and p.get("text"):
                props.append({"type": "panel", "show": "text", "text": str(p["text"])[:24]})
            else:
                v = _clean_visual({**p, "type": p.get("show")})
                if v:
                    props.append({**v, "type": "panel", "show": v["type"]})
        elif p.get("type") == "clock":
            props.append({"type": "clock", "text": str(p.get("text", ""))[:9]})
        elif p.get("type") == "paper":
            props.append({"type": "paper"})
    sc["props"] = props
    sc["label"] = str(sc["label"])[:22] if sc.get("label") else None
    return sc


SIZE = re.compile(r"^\s*([\d.]+)\s*(KB|MB)\s*$", re.I)


class ScriptError(ValueError):
    pass


def size_kb(text):
    m = SIZE.match(str(text or ""))
    if not m:
        return None
    return float(m.group(1)) * (1024 if m.group(2).upper() == "MB" else 1)


def _clean_visual(v):
    """Keep a visual only if it has everything the renderer needs."""
    if not isinstance(v, dict):
        return None
    t = v.get("type")
    v["file"] = str(v.get("file") or "document.pdf")[:22]
    v["message"] = str(v.get("message") or "")[:34]
    if t == "size_drop" and size_kb(v.get("from")) and size_kb(v.get("to")):
        return v
    if t in ("error", "success") and v["message"]:   # size is optional (e.g. a password error)
        v["size"] = v["size"] if size_kb(v.get("size")) else ""
        return v
    return None


def validate(cfg, s, lang):
    story = cfg["content"].get("style") == "story3d"
    explainer = cfg["content"].get("style") == "explainer"
    scenes = s.get("scenes") or []
    if not 4 <= len(scenes) <= 12:
        raise ScriptError(f"needs 4-12 scenes, got {len(scenes)}")
    if explainer:
        scenes[0]["kind"], scenes[-1]["kind"] = "hook", "cta"
        for sc in scenes[1:-1]:
            sc["kind"] = "point"
    if scenes[0].get("kind") != "hook" or scenes[-1].get("kind") != "cta":
        raise ScriptError("must start with a hook and end with a cta")
    for i, sc in enumerate(scenes):
        if explainer:
            _clean_explainer(sc, i == len(scenes) - 1)
            if len(sc["screen"]) > 60:
                sc["screen"] = sc["screen"][:60]
        elif story:
            _clean_shot(sc)
            sc["screen"] = sc.get("screen") or sc.get("label") or ""
            if sc["kind"] in ("hook", "cta") and not sc["screen"]:
                raise ScriptError("hook and cta need screen text")
        if not sc.get("voice") or (not story and not explainer and not sc.get("screen")):
            raise ScriptError("every scene needs screen text and voice")
        if len(sc["screen"]) > 60 and not explainer:
            raise ScriptError(f"screen text too long: {sc['screen']}")
        if lang.get("tts_script") and not sc.get("say"):
            raise ScriptError('every scene needs "say" (the spoken line in Roman letters)')
        sc["say"] = " ".join((sc.get("say") or sc["voice"]).replace("...", " ").replace("…", " ").split())
        sc.setdefault("emphasis", [])
        sc["visual"] = None if (story or explainer) else _clean_visual(sc.get("visual"))
    if explainer:
        kinds = {sc["scene"]["type"] for sc in scenes}
        if len(kinds) < 5:
            raise ScriptError(f"use at least 6 different scenes, got {sorted(kinds)}")
        long = [sc["say"] for sc in scenes if len(sc["say"].split()) > 16]
        if long:
            raise ScriptError(f"sentences too long for the headline (max 12 words): {long[0]}")
    words = sum(len(sc["say"].split()) for sc in scenes)
    if not 30 <= words <= 150:
        raise ScriptError(f"voiceover is {words} words, outside 30-150")
    if not s.get("caption"):
        raise ScriptError("caption missing")
    tags = [t if t.startswith("#") else f"#{t}" for t in s.get("hashtags", [])]
    s["hashtags"] = tags[: cfg["content"]["max_hashtags"]]
    return s


def _offline(cfg, topic_title, lang):
    """Fixed sample used only for dry runs without Claude. Never posted."""
    c = cfg["content"]
    if lang.get("tts_script"):
        rows = [
            ("hook", "Photo upload nahi ho raha?", "फोटो अपलोड नहीं हो रहा?", "Photo upload nahi ho raha?",
             ["upload"], {"type": "error", "file": "photo.jpg", "size": "2.4 MB", "message": "File too large. Max 50 KB"}),
            ("point", "Form ko chahiye 50 KB", "फॉर्म को चाहिए सिर्फ पचास के बी।", "Form ko chahiye sirf pachaas KB.",
             ["50", "KB"], None),
            ("step", "ilovedocuments.ai kholo", "आई लव डॉक्यूमेंट्स डॉट ए आई खोलो। साइन अप नहीं चाहिए।",
             "I love documents dot A I kholo. Sign up nahi chahiye.", ["ilovedocuments.ai"], None),
            ("step", "Photo daalo, size chuno", "फोटो डालो और साइज़ चुनो।", "Photo daalo aur size chuno.",
             ["size"], {"type": "size_drop", "file": "photo.jpg", "from": "2.4 MB", "to": "48 KB"}),
            ("point", "Photo phone se bahar nahi jaati", "फोटो आपके फोन से बाहर नहीं जाती।",
             "Photo aapke phone se bahar nahi jaati.", ["nahi"], None),
            ("step", "Ab upload karo", "अब फॉर्म में अपलोड करो। हो गया।", "Ab form mein upload karo. Ho gaya.",
             ["upload"], {"type": "success", "file": "photo.jpg", "size": "48 KB", "message": "Uploaded"}),
            ("cta", c["cta"], "बिल्कुल फ्री। अगले फॉर्म के लिए सेव कर लो।", "Bilkul free. Agle form ke liye save kar lo.",
             ["Free."], None),
        ]
    else:
        rows = [
            ("hook", "Photo upload rejected again?", "Your form rejected your photo again?", None,
             ["rejected"], {"type": "error", "file": "photo.jpg", "size": "2.4 MB", "message": "File too large. Max 50 KB"}),
            ("point", "The form wants 50 KB", "The form wants fifty K B. Your photo is fifty times bigger.", None,
             ["50", "KB"], None),
            ("step", "Open ilovedocuments.ai", "Open I love documents dot A I. No sign up.", None,
             ["ilovedocuments.ai"], None),
            ("step", "Add photo, pick the size", "Add your photo and pick the size.", None,
             ["size"], {"type": "size_drop", "file": "photo.jpg", "from": "2.4 MB", "to": "48 KB"}),
            ("point", "Photo never leaves your phone", "It runs in your browser, so the photo is never uploaded.", None,
             ["never"], None),
            ("step", "Upload it. Done.", "Now upload it to the form. Done.", None,
             ["Done."], {"type": "success", "file": "photo.jpg", "size": "48 KB", "message": "Uploaded"}),
            ("cta", c["cta"], "It is free. Save this for your next form.", None, ["Free."], None),
        ]
    scenes = [{"kind": k, "screen": sc, "voice": v, "say": say, "emphasis": e, "visual": vis}
              for k, sc, v, say, e, vis in rows]
    scenes[0]["broll"] = "stressed student laptop"
    return {"title": topic_title, "scenes": scenes,
            "caption": f"{topic_title}.\nWhich form gave you the most trouble?\n{cfg['brand']['url']}",
            "hashtags": c["hashtags"]}


EN_SAY = {
    "File too large. The form wants fifty K B.": "File too large. The form wants 50 KB.",
    "No app. No sign up. He opens I love documents dot A I.": "No app. No sign-up. He opens ilovedocuments.ai",
    "Two point four M B becomes forty eight K B. In seconds.": "2.4 MB becomes 48 KB. In seconds.",
}


def _offline_story(cfg, topic_title, lang):
    """Fixed 3D story sample for dry runs without Claude. Never posted."""
    hi = bool(lang.get("tts_script"))
    A = lambda pose, **k: {"color": "orange", "pose": pose, **k}
    rows = [
        ("hook", "night", "push_in", None, [A("type", screen="error")], [],
         "What if your form closed in 2 minutes?", ["2", "minutes?"],
         "What if your exam form closed in two minutes?",
         "क्या हो अगर आपका एग्ज़ाम फॉर्म दो मिनट में बंद हो जाए?", "Kya ho agar aapka exam form do minute mein band ho jaye?"),
        ("point", "bedroom", "wide", "11:58 PM", [A("type", screen="error")],
         [{"type": "panel", "show": "error", "file": "photo.jpg", "size": "2.4 MB", "message": "Max size 50 KB"}],
         "Rejected", [], "Rohan uploads his photo. Rejected.",
         "रोहन ने फोटो अपलोड की। रिजेक्ट।", "Rohan ne photo upload ki. Reject."),
        ("point", "bedroom", "close", "11:58 PM", [A("panic")],
         [{"type": "panel", "show": "text", "text": "MAX 50 KB"}],
         "Max 50 KB", [], "File too large. The form wants fifty K B.",
         "फाइल बहुत बड़ी है। फॉर्म को पचास के बी चाहिए।", "File bahut badi hai. Form ko pachaas KB chahiye."),
        ("step", "bedroom", "push_in", "11:59 PM", [A("phone")], [],
         "Opens ilovedocuments.ai", [], "No app. No sign up. He opens I love documents dot A I.",
         "ना ऐप, ना साइन अप। उसने आई लव डॉक्यूमेंट्स डॉट ए आई खोला।", "Na app, na sign up. Usne I love documents dot A I khola."),
        ("step", "bedroom", "wide", "11:59 PM", [A("phone")],
         [{"type": "panel", "show": "size_drop", "file": "photo.jpg", "from": "2.4 MB", "to": "48 KB"}],
         "2.4 MB to 48 KB", [], "Two point four M B becomes forty eight K B. In seconds.",
         "दो पॉइंट चार एम बी बन गया अड़तालीस के बी। कुछ ही सेकंड में।", "2.4 MB ban gaya 48 KB. Kuch hi second mein."),
        ("point", "bedroom", "low", "12:00 AM", [A("cheer")],
         [{"type": "panel", "show": "success", "file": "photo.jpg", "size": "48 KB", "message": "Uploaded"}],
         "Uploaded", [], "Uploaded. With one second left.",
         "अपलोड हो गया। सिर्फ एक सेकंड बाकी था।", "Upload ho gaya. Sirf ek second baaki tha."),
        ("point", "park", "wide", "NEXT MORNING",
         [A("walk", x=-1.3, look="right"), {"color": "blue", "pose": "sad", "x": 1.0, "float": {"text": "2.4 MB", "color": "#ff5a66"}}], [],
         "Only Kevin struggled", [], "Rohan slept fine. Only Kevin is still stuck.",
         "रोहन आराम से सोया। बस केविन अभी भी अटका है।", "Rohan aaram se soya. Bas Kevin abhi bhi atka hai."),
        ("cta", "sunset", "orbit", None, [A("wave", x=-0.6), {"color": "blue", "pose": "cheer", "x": 0.7}], [],
         "Send this to your Kevin", ["Kevin"], "It is free. Send this to the friend who waits till the last day.",
         "बिल्कुल फ्री है। उस दोस्त को भेजो जो आखिरी दिन तक रुकता है।", "Bilkul free hai. Us dost ko bhejo jo aakhri din tak rukta hai."),
    ]
    scenes = [{"kind": k, "set": st, "camera": cam, "label": lab, "actors": actors, "props": props, "screen": screen,
               "emphasis": emph, "voice": v_hi if hi else v_en, "say": say_hi if hi else EN_SAY.get(v_en)}
              for k, st, cam, lab, actors, props, screen, emph, v_en, v_hi, say_hi in rows]
    return {"title": topic_title, "scenes": scenes,
            "caption": "Tag the friend who fills forms at 11:58 PM.\nComment FORM and I will send the link.\n"
                       + cfg["brand"]["url"], "hashtags": cfg["content"]["hashtags"]}


def format_help(name):
    learned = {k: v["description"] + (f' A hook that worked in this format: "{v["hook_pattern"]}".' if v.get("hook_pattern") else "")
               for k, v in store.read("formats", {}).get("learned", {}).items()}
    return {**FORMATS, **STORY_FORMATS, **learned}.get(name, "")


def idea_text(idea, lang):
    """A fresh angle the scout found for this tool. A starting point, not a script."""
    if not idea:
        return ""
    hook = idea.get("hook_hinglish") if lang.get("tts_script") and idea.get("hook_hinglish") else idea.get("hook_en")
    return (f"Idea to build on (from studying a top reel in the niche; make it fit the story format, improve it if you can): "
            f'hook "{hook}"; story: {idea.get("angle", "")}\n')


def write(cfg, plan, playbook):
    c, b = cfg["content"], cfg["brand"]
    lang = next(l for l in c["languages"] if l["id"] == plan["language"])
    topic = next(t for t in c["topics"] if t["id"] == plan["topic"])
    topic_title = f"{topic['title']} (the site's tool for this is called \"{topic.get('tool', topic['title'])}\")"
    story = c.get("style") == "story3d"
    explainer = c.get("style") == "explainer"
    if not claude.available(cfg):
        if not cfg["posting"]["dry_run"]:
            raise ScriptError("No Claude credentials: refusing to post a template script")
        return validate(cfg, (_offline_story if story else _offline)(cfg, topic_title, lang), lang)

    lo, hi = c["target_seconds"]
    if lang.get("tts_script"):
        voice_rule = (f'Write "voice" in {lang["tts_script"]} script for the voice engine (English words '
                      f'transliterated, the site as "आई लव डॉक्यूमेंट्स डॉट ए आई"). Keep it how friends actually talk: short, '
                      f'casual, mostly Hindi grammar with everyday English words, never formal or textbook Hindi. Write "say" as the same '
                      f'line in Roman letters for the captions.')
        say_field = '"say": "...", '
    else:
        voice_rule, say_field = 'Say the site as "I love documents dot A I" and spell out numbers and units.', ""
    system = SYSTEM.format(name=b["name"], url=b["url"], tagline=b["tagline"],
                           audience=c["audience"].strip(), tone=c["voice_and_tone"],
                           facts="; ".join(c["facts"]), write_in=lang["write_in"].strip())
    prompt = (EXPLAINER_PROMPT if explainer else STORY_PROMPT if story else PROMPT).format(
        topic=topic_title, format=plan["format"],
        format_help=format_help(plan["format"]), idea=idea_text(plan.get("idea"), lang),
        hook_style=plan["hook_style"], lo=lo, hi=hi, wlo=int(lo * 2.0), whi=int(hi * 2.0),   # the narrator pauses, so fewer words fit
        research="\n".join(x for x in (scout.digest(), research.digest()) if x) or "(no research data yet)",
        keep=playbook.get("keep") or "nothing proven yet",
        avoid=playbook.get("avoid") or "nothing proven yet",
        tests=playbook.get("next_tests") or "none",
        recent=[p["hook"] for p in store.posts()[-10:]] or "none",
        voice_rule=voice_rule, say_field=say_field, cta=c["cta"], max_tags=c["max_hashtags"],
    )
    last = None
    for _ in range(3):  # retry when a draft fails the checks
        try:
            return validate(cfg, claude.ask_json(cfg, system, prompt), lang)
        except (ScriptError, claude.ClaudeError, ValueError) as e:
            last = e
            prompt += f"\n\nYour previous draft was rejected: {e}. Fix it."
    raise ScriptError(f"no valid script after 3 tries: {last}")
