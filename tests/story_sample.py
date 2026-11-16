"""Renders the built-in sample 3D story (no keys needed):  python tests/story_sample.py [english|hinglish]"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from reelbot import config, render3d, script, voice

cfg = config.load()
cfg["posting"]["dry_run"] = True
lang_id = sys.argv[1] if len(sys.argv) > 1 else "english"
lang = next(l for l in cfg["content"]["languages"] if l["id"] == lang_id)
s = script.validate(cfg, script._offline_story(cfg, "sample", lang), lang)
work = config.OUT / "story-work"
audio, speech, starts, total = voice.synthesize(cfg, lang, s["scenes"], work)
out = render3d.render(cfg, s, audio, speech, starts, total, config.OUT / f"story-{lang_id}.mp4")
print(out, f"{total:.1f}s")
