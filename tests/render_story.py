"""Renders a story file:  python tests/render_story.py stories/<name>.json [english|hinglish]"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from reelbot import config, render3d, script, voice

cfg = config.load()
path = Path(sys.argv[1])
lang_id = sys.argv[2] if len(sys.argv) > 2 else "english"
lang = dict(next(l for l in cfg["content"]["languages"] if l["id"] == lang_id))
if len(sys.argv) > 3:
    lang["provider"] = sys.argv[3]   # e.g. chatterbox
story = json.loads(path.read_text())
hindi = bool(lang.get("tts_script"))
caption_en = story.pop("caption_en", None)
if not hindi and caption_en:
    story["caption"] = caption_en
for sc in story["scenes"]:  # a story file can carry both languages
    hi_voice, hi_say, hi_screen = sc.pop("voice_hi", None), sc.pop("say_hi", None), sc.pop("screen_hi", None)
    if hindi and hi_voice:
        sc["voice"], sc["say"] = hi_voice, hi_say
    if hindi and hi_screen:
        sc["screen"] = hi_screen
s = script.validate(cfg, story, lang)
audio, speech, starts, total = voice.synthesize(cfg, lang, s["scenes"], config.OUT / f"{path.stem}-work")
out = render3d.render(cfg, s, audio, speech, starts, total, config.OUT / f"{path.stem}-{lang_id}.mp4")
(config.OUT / f"{path.stem}-{lang_id}.txt").write_text(s["caption"] + "\n\n" + " ".join(s["hashtags"]) + "\n")
print(out, f"{total:.1f}s")
