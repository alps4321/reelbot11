"""Text to speech (one clip per scene, so visuals stay in sync) plus sound effects."""
import math
import re
import random
import subprocess
import sys
import wave
from array import array
from pathlib import Path

import requests

from .config import ROOT

RATE = 44100
VOICES = ROOT / "voices"


def _run(cmd, **kw):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **kw)


def _to_wav(src, dst):
    _run(["ffmpeg", "-y", "-i", str(src), "-ar", str(RATE), "-ac", "1", "-c:a", "pcm_s16le", str(dst)])


def _piper(cfg, lang, text, dst):
    name = lang["piper_voice"]
    VOICES.mkdir(exist_ok=True)
    if not (VOICES / f"{name}.onnx").exists():
        _run([sys.executable, "-m", "piper.download_voices", name, "--data-dir", str(VOICES)])
    raw = dst.with_suffix(".raw.wav")
    _run([sys.executable, "-m", "piper", "-m", name, "--data-dir", str(VOICES),
          "--length-scale", str(1.0 / float(cfg["voice"].get("speed", 1.0))), "-f", str(raw)],
         input=text.encode())
    _to_wav(raw, dst)
    raw.unlink()


KOKORO_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/"
_kokoro = None


def _kokoro_tts(cfg, lang, text, dst):
    """Kokoro: free open-source neural voices (Apache licence), runs on the machine itself."""
    global _kokoro
    import soundfile as sf
    from kokoro_onnx import Kokoro

    if _kokoro is None:
        folder = VOICES / "kokoro"
        folder.mkdir(parents=True, exist_ok=True)
        for name in ("kokoro-v1.0.onnx", "voices-v1.0.bin"):
            if not (folder / name).exists():
                with requests.get(KOKORO_URL + name, stream=True, timeout=600) as r:
                    r.raise_for_status()
                    with open(folder / name, "wb") as f:
                        for chunk in r.iter_content(1 << 20):
                            f.write(chunk)
        _kokoro = Kokoro(str(folder / "kokoro-v1.0.onnx"), str(folder / "voices-v1.0.bin"))
    samples, rate = _kokoro.create(text, voice=lang["kokoro_voice"], lang=lang.get("kokoro_lang", "en-us"),
                                   speed=float(cfg["voice"].get("speed", 1.0)))
    raw = dst.with_suffix(".raw.wav")
    sf.write(str(raw), samples, rate)
    _to_wav(raw, dst)
    raw.unlink()


def _voicemaker(cfg, lang, text, dst):
    """Voicemaker.in neural voices (Indian English and Hindi). Uses VOICEMAKER_API_KEY."""
    voice = lang["voicemaker_voice"]
    speed = int(round((float(cfg["voice"].get("speed", 1.0)) - 1) * 100))
    r = requests.post(
        "https://developer.voicemaker.in/api/v1/voice/convert",
        headers={"Authorization": f"Bearer {cfg['secrets']['voicemaker']}", "Content-Type": "application/json"},
        json={"Engine": "neural", "VoiceId": voice, "LanguageCode": voice.split("-", 1)[1][:5], "Text": text,
              "OutputFormat": "mp3", "SampleRate": "48000", "Effect": "default", "MasterVolume": "0",
              "MasterSpeed": str(speed), "MasterPitch": "0"}, timeout=120)
    body = r.json()
    if not body.get("success"):
        raise RuntimeError(f"Voicemaker: {str(body)[:200]}")
    mp3 = dst.with_suffix(".mp3")
    mp3.write_bytes(requests.get(body["path"], timeout=120).content)
    _to_wav(mp3, dst)
    mp3.unlink()
    return body.get("remainChars")


STYLES = {"angry": (1.0, 0.3), "panic": (0.9, 0.3), "happy": (0.8, 0.4), "quiet": (0.35, 0.5), "calm": (0.5, 0.5)}
SPEAKER_REFS = {"boss": "am_onyx", "jake": "am_michael", "narrator": "am_michael", "woman": "af_heart"}


def _chatterbox_batch(cfg, lang, scenes, workdir):
    """Chatterbox (free, open source, MIT): expressive speech with an emotion dial.

    Each speaker's voice colour comes from a short reference clip that Kokoro generates,
    so no real person's voice is copied. Slow on CPU (about 12x the audio length).
    """
    import json
    import os

    refs = VOICES / "refs"
    refs.mkdir(parents=True, exist_ok=True)
    jobs = []
    for i, sc in enumerate(scenes):
        speaker = sc.get("speaker", "narrator")
        ref = refs / f"{speaker}.wav"
        if not ref.exists():
            _kokoro_tts(cfg, {"kokoro_voice": SPEAKER_REFS.get(speaker, "am_michael"), "kokoro_lang": "en-us"},
                        "Honestly, I did not expect that to work. But here we are, and it only took a few seconds. "
                        "Let me show you exactly what I did, step by step.", ref)
        ex, cfgw = STYLES.get(sc.get("style", "calm"), STYLES["calm"])
        jobs.append({"text": sc["voice"], "out": str(workdir / f"cb{i}.wav"), "ref": str(ref),
                     "exaggeration": ex, "cfg": cfgw})
    job_file = workdir / "jobs.json"
    job_file.write_text(json.dumps(jobs))
    py = os.environ.get("CHATTERBOX_PYTHON", sys.executable)
    _run([py, str(Path(__file__).with_name("cb_tts.py")), str(job_file)])
    for i in range(len(scenes)):
        _to_wav(workdir / f"cb{i}.wav", workdir / f"scene{i}.wav")


PAUSE = {"?": 0.50, "!": 0.34, ".": 0.34, "।": 0.34, "…": 0.48}   # seconds of silence after a phrase

# Speaking paces the bot tests and learns from, like hooks and formats.
#   pause: share of the pauses above that is kept; gap: silence between shots;
#   tempo: how far toward the niche's speaking speed (learned by the scout) the voice is sped up.
PACES = {
    "calm":    {"pause": 1.00, "gap": 0.30, "tempo": 0.0},
    "natural": {"pause": 0.80, "gap": 0.24, "tempo": 0.5},
    "brisk":   {"pause": 0.62, "gap": 0.18, "tempo": 1.0},
}
DEFAULT_NICHE_WPS = 3.2         # words per second of a typical explainer reel until the scout measures the niche


def phrases(text):
    """Split a spoken line where a good speaker would breathe: sentence ends and '...' beats."""
    text = text.replace("...", "…")
    parts = [p.strip() for p in re.split(r"(?<=[।.?!…])\s+", text.strip()) if p.strip(" ।.?!…")]
    return parts or [text]


def _trim(src, dst):
    """Cut the silence the voice model leaves at both ends, so pauses are exactly the ones we choose."""
    cut = "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.03"
    _run(["ffmpeg", "-y", "-i", str(src), "-af", f"{cut},areverse,{cut},areverse",
          "-ar", str(RATE), "-ac", "1", "-c:a", "pcm_s16le", str(dst)])


def _omnivoice_batch(cfg, lang, scenes, workdir, pause_scale=1.0):
    """OmniVoice (open source): every phrase is spoken in the voice of one reference clip.

    Pacing is done the way a trained speaker does it: one phrase per breath, a real pause
    after each sentence, a longer one after a question or before the answer.
    """
    import json
    import os

    v = cfg["voice"]
    ref = ROOT / lang.get("omnivoice_ref", v["omnivoice_ref"])
    jobs, plan = [], []
    for i, sc in enumerate(scenes):
        parts = phrases(sc["voice"])
        plan.append(parts)
        for k, part in enumerate(parts):
            jobs.append({"text": part.rstrip("…").strip() or part, "out": str(workdir / f"ov{i}_{k}.wav"),
                         "ref": str(ref), "ref_text": v["omnivoice_ref_text"], "speed": float(v.get("speed", 1.0)),
                         "steps": int(v.get("omnivoice_steps", 32))})
    job_file = workdir / "ov_jobs.json"
    job_file.write_text(json.dumps(jobs, ensure_ascii=False))
    py = os.environ.get("OMNIVOICE_PYTHON", sys.executable)
    subprocess.run([py, str(Path(__file__).with_name("ov_tts.py")), str(job_file)], check=True,
                   stdout=subprocess.DEVNULL)
    for i, parts in enumerate(plan):
        track, marks = array("h"), []
        for k, part in enumerate(parts):
            clean = workdir / f"ov{i}_{k}_t.wav"
            _trim(workdir / f"ov{i}_{k}.wav", clean)
            samples = _read(clean)
            marks.append((len(track) / RATE, len(samples) / RATE))
            track.extend(samples)
            if k < len(parts) - 1:
                track.extend(array("h", bytes(2 * int(RATE * pause_scale * PAUSE.get(part[-1], 0.3)))))
        with wave.open(str(workdir / f"scene{i}.wav"), "wb") as out:
            out.setnchannels(1), out.setsampwidth(2), out.setframerate(RATE)
            out.writeframes(track.tobytes())
        scenes[i]["_phrases"] = marks           # (offset, length) of each phrase, for caption timing


def _azure(cfg, lang, text, dst):
    """Microsoft Azure Speech neural voices (free tier: 0.5M characters a month)."""
    from xml.sax.saxutils import escape

    sec, voice = cfg["secrets"], lang["azure_voice"]
    rate = int(round((float(cfg["voice"].get("speed", 1.0)) - 1) * 100))
    ssml = (f"<speak version='1.0' xml:lang='{voice[:5]}'><voice name='{voice}'>"
            f"<prosody rate='{rate:+d}%'>{escape(text)}</prosody></voice></speak>")
    r = requests.post(
        f"https://{sec['azure_region']}.tts.speech.microsoft.com/cognitiveservices/v1",
        headers={"Ocp-Apim-Subscription-Key": sec["azure_key"], "Content-Type": "application/ssml+xml",
                 "X-Microsoft-OutputFormat": "riff-44100hz-16bit-mono-pcm", "User-Agent": "reelbot"},
        data=ssml.encode("utf-8"), timeout=120)
    r.raise_for_status()
    raw = dst.with_suffix(".raw.wav")
    raw.write_bytes(r.content)
    _to_wav(raw, dst)
    raw.unlink()


def _elevenlabs(cfg, lang, text, dst):
    r = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{lang['elevenlabs_voice_id']}",
        params={"output_format": "mp3_44100_128"},
        headers={"xi-api-key": cfg["secrets"]["elevenlabs"]},
        json={"text": text, "model_id": "eleven_multilingual_v2"}, timeout=120)
    r.raise_for_status()
    mp3 = dst.with_suffix(".mp3")
    mp3.write_bytes(r.content)
    _to_wav(mp3, dst)
    mp3.unlink()


def _read(path):
    with wave.open(str(path), "rb") as w:
        return array("h", w.readframes(w.getnframes()))


# ---- sound effects, synthesised so there is nothing to license -------------
def _sfx(name):
    rnd, out = random.Random(1), array("h")
    if name == "whoosh":
        n, low = int(RATE * 0.28), 0.0
        for i in range(n):
            x = i / n
            low += (0.05 + 0.3 * x) * (rnd.uniform(-1, 1) - low)
            out.append(int(9000 * low * math.sin(math.pi * x) ** 2))
    elif name == "pop":
        n = int(RATE * 0.09)
        for i in range(n):
            x = i / n
            out.append(int(7000 * math.sin(2 * math.pi * (700 - 380 * x) * i / RATE) * (1 - x) ** 2))
    elif name == "ding":
        n = int(RATE * 0.6)
        for i in range(n):
            t = i / RATE
            out.append(int(4500 * math.exp(-6 * t) * (math.sin(2 * math.pi * 1320 * t)
                                                      + 0.5 * math.sin(2 * math.pi * 1980 * t))))
    elif name == "buzz":
        n = int(RATE * 0.26)
        for i in range(n):
            t = i / RATE
            sq = 1 if math.sin(2 * math.pi * 140 * t) > 0 else -1
            out.append(int(3800 * sq * (1 if (t % 0.13) < 0.1 else 0)))
    elif name == "thud":              # a stamp landing
        n = int(RATE * 0.22)
        for i in range(n):
            t = i / RATE
            out.append(int(11000 * math.sin(2 * math.pi * (70 + 90 * math.exp(-t * 40)) * t) * math.exp(-t * 18)
                           + 2500 * rnd.uniform(-1, 1) * math.exp(-t * 90)))
    return out


# Explainer reels: sounds placed on the animation's own beats (seconds after the shot starts; studio/explainer.js).
def explainer_sfx(scene, dur=9.0):
    p, kind = scene or {}, (scene or {}).get("type")

    def seq(n, first, base):          # same timing rule as seq() in studio/explainer.js
        return min(base, max(0.12, (dur - first - 0.3) / max(1, n)))
    table = {
        "phone_upload": [("buzz" if p.get("state") != "success" else "ding", 0.6)],
        "file_shrink": [("ding", 1.45)], "stamp": [("thud", 0.52)], "counter": [("ding", 1.0)],
        "tool_grid": [("pop", 0.95)], "browser": [("pop", 1.3)], "before_after": [("buzz", 0.35), ("ding", 0.95)],
        "cyber_cafe": [("pop", 1.0)], "privacy": [("ding", 0.8)], "deadline": [("buzz", 0.55)],
        "id_card": [("thud", 0.35)], "spotlight": [("ding", 0.6)], "cta": [("pop", 0.85)],
        "convert": [("pop", 0.85)], "photo_cutout": [("ding", 1.15)],
        "steps": [("pop", 0.15 + i * seq(n, 0.15, 0.5)) for n in [min(3, len(p.get("items") or [1, 2, 3]))] for i in range(n)],
        "split_flap": [("ding", 0.2 + min(12, len(str(p.get("word", "ILOVEDOCS")))) * 0.07)],
        "news": [("pop", 0.5)], "search": [("pop", 1.0)], "chart": [("ding", 1.2)],
        "versus": [("thud", 0.6), ("ding", 0.9)], "big_text": [("thud", 0.3)], "person": [("pop", 0.55)],
        "bulb": [("ding", 0.5)], "money": [("pop", 0.8)], "notification": [("ding", 0.45)], "warning": [("buzz", 0.3)],
        "chat": [("pop", 0.25 + i * seq(n, 0.25, 0.55)) for n in [min(4, len(p.get("messages") or [1, 2]))] for i in range(n)],
        "checklist": [("pop", 0.35 + i * seq(n, 0.35, 0.45)) for n in [min(4, len(p.get("items") or [1, 2, 3]))] for i in range(n)],
        "timeline": [("pop", 0.25 + i * seq(n, 0.25, 0.45)) for n in [min(4, len(p.get("items") or [1, 2, 3]))] for i in range(n)],
    }
    return table.get(kind, [])


def _mix(track, clip, at):
    start = max(0, int(at * RATE))
    for i, v in enumerate(clip):
        j = start + i
        if j >= len(track):
            break
        track[j] = max(-32768, min(32767, track[j] + v))


def synthesize(cfg, lang, scenes, workdir, gap=None, tail=1.0, pace="calm"):
    """Returns (audio_path, [speech seconds per scene], [scene start times], total seconds)."""
    p = PACES.get(pace or "calm", PACES["calm"])
    gap = p["gap"] if gap is None else gap
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    provider = lang.get("provider") or cfg["voice"]["provider"]   # a language can pick its own engine
    if provider == "elevenlabs" and not (cfg["secrets"]["elevenlabs"] and lang.get("elevenlabs_voice_id")):
        provider = "kokoro"
    if provider == "voicemaker" and not (cfg["secrets"]["voicemaker"] and lang.get("voicemaker_voice")):
        provider = "kokoro"
    if provider == "azure" and not (cfg["secrets"]["azure_key"] and lang.get("azure_voice")):
        provider = "kokoro"
    if provider == "kokoro" and not lang.get("kokoro_voice"):
        provider = "piper"

    if provider == "chatterbox":
        _chatterbox_batch(cfg, lang, scenes, workdir)
    if provider == "omnivoice":
        try:
            _omnivoice_batch(cfg, lang, scenes, workdir, pause_scale=p["pause"])
        except Exception as e:          # never lose a day's post over the voice engine
            provider = "kokoro" if lang["id"] == "english" else "piper"
            print(f"voice: OmniVoice failed ({e}); falling back to {provider}")
            for sc in scenes:
                sc.pop("_phrases", None)

    track, speech, starts, t = array("h"), [], [], 0.0
    for i, sc in enumerate(scenes):
        clip = workdir / f"scene{i}.wav"
        if provider in ("chatterbox", "omnivoice"):
            pass
        elif provider == "elevenlabs":
            _elevenlabs(cfg, lang, sc["voice"], clip)
        elif provider == "voicemaker":
            _voicemaker(cfg, lang, sc["voice"], clip)
        elif provider == "azure":
            _azure(cfg, lang, sc["voice"], clip)
        elif provider == "kokoro":
            _kokoro_tts(cfg, {**lang, "kokoro_voice": sc.get("kokoro_voice") or lang["kokoro_voice"]}, sc["voice"], clip)
        elif provider == "piper":
            _piper(cfg, lang, sc["voice"], clip)
        samples = _read(clip) if provider != "none" else array(
            "h", bytes(2 * int(RATE * max(1.4, len(sc["say"].split()) / 2.8))))
        dur = len(samples) / RATE
        ends = sc["voice"].rstrip()[-1:]
        pad = tail if i == len(scenes) - 1 else (gap + 0.18 if ends in "?…" else gap)
        starts.append(t)
        speech.append(dur)
        track.extend(samples)
        track.extend(array("h", bytes(2 * int(RATE * pad))))
        t += dur + pad

    if cfg["voice"].get("sound_effects"):
        bank = {n: _sfx(n) for n in ("whoosh", "pop", "ding", "buzz", "thud")}
        for i, sc in enumerate(scenes):
            if i:
                _mix(track, bank["whoosh"], starts[i] - 0.12)
            if sc.get("scene"):
                dur = starts[i + 1] - starts[i] if i + 1 < len(starts) else 9.0
                for name, offset in explainer_sfx(sc["scene"], dur):
                    if offset < dur:
                        _mix(track, bank[name], starts[i] + offset)
                continue
            panel = next((p for p in sc.get("props") or [] if p.get("type") == "panel"), {})
            kind = (sc.get("visual") or {}).get("type") or panel.get("show")
            if kind == "error":
                _mix(track, bank["buzz"], starts[i] + 0.3)
            elif kind == "success":
                _mix(track, bank["ding"], starts[i] + 0.3)
            elif kind == "size_drop":
                _mix(track, bank["ding"], starts[i] + min(1.3, speech[i] * 0.8))
            elif sc["kind"] == "cta":
                _mix(track, bank["pop"], starts[i] + 0.05)

    full = workdir / "voice.wav"
    with wave.open(str(full), "wb") as out:
        out.setnchannels(1), out.setsampwidth(2), out.setframerate(RATE)
        out.writeframes(track.tobytes())
    total = len(track) / RATE

    tempo = _tempo(scenes, speech, p["tempo"])
    if tempo > 1.01:                 # speed up without changing the pitch, then move every timing with it
        fast = workdir / "voice_fast.wav"
        _run(["ffmpeg", "-y", "-i", str(full), "-af", f"atempo={tempo:.3f}", "-ar", str(RATE), "-ac", "1",
              "-c:a", "pcm_s16le", str(fast)])
        speech, starts, total = [x / tempo for x in speech], [x / tempo for x in starts], total / tempo
        for sc in scenes:
            if sc.get("_phrases"):
                sc["_phrases"] = [(o / tempo, l / tempo) for o, l in sc["_phrases"]]
        full = fast
    print(f"voice: pace {pace}, tempo {tempo:.2f}, {total:.1f} s")
    return full, speech, starts, total


def _tempo(scenes, speech, share):
    """How much to speed up: `share` of the way from our speed to the niche's (learned by the scout)."""
    if share <= 0:
        return 1.0
    from . import store
    target = store.read("voice_style", {}).get("words_per_second") or DEFAULT_NICHE_WPS
    words = sum(len((sc.get("say") or sc.get("voice") or "").split()) for sc in scenes)
    ours = words / max(sum(speech), 1)
    want = ours + share * (target - ours)
    return max(1.0, min(1.18, want / max(ours, 0.5)))      # never slower than recorded, never chipmunk
