"""Renders an explainer reel: flat hand-drawn illustration style (studio/explainer.js) with a headline that
builds word by word, one animated scene per sentence, a soft music bed under the voice."""
import base64
import functools
import http.server
import math
import os
import subprocess
import threading
import wave
from array import array
from pathlib import Path

from .config import ASSETS, ROOT
from .render import FPS, H, W, scene_word_times

MUSIC = ASSETS / "music" / "explainer" / "bed.mp3"
MUSIC_DB = -17.1          # mean level of the bed (tools/make_music.py)
UNDER_VOICE_DB = 9        # the bed ends up about 12 dB under the voice, like the reference reel


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def _serve():
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(_Quiet, directory=str(ROOT)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def _mean_db(path):
    with wave.open(str(path)) as w:
        a = array("h", w.readframes(w.getnframes()))
    if not a:
        return -20.0
    voiced = [x for x in a if abs(x) > 300] or list(a)
    rms = math.sqrt(sum(x * x for x in voiced[::7]) / max(1, len(voiced[::7]))) / 32768
    return 20 * math.log10(max(rms, 1e-6))


def reel_data(cfg, script, speech, starts, total):
    shots = []
    for i, sc in enumerate(script["scenes"]):
        words = sc["say"].split()
        times = scene_word_times(sc, words, starts[i], speech[i])
        shots.append({"start": starts[i], "end": starts[i + 1] if i + 1 < len(starts) else total,
                      "tag": sc.get("tag"), "meter": sc.get("meter"), "accent": sc.get("accent", []),
                      "scene": sc.get("scene") or {"type": "stamp", "word": "FREE"},
                      "words": [{"w": w, "t0": a} for w, (a, _) in zip(words, times)]})
    return {"shots": shots, "url": cfg["brand"]["url"]}


def render(cfg, script, audio, speech, starts, total, out_path):
    from playwright.sync_api import sync_playwright

    out_path = Path(out_path)
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "image2pipe", "-framerate", str(FPS), "-c:v", "mjpeg", "-i", "-", "-i", str(audio)]
    if MUSIC.exists():
        vol = 10 ** ((_mean_db(audio) - UNDER_VOICE_DB - MUSIC_DB) / 20)
        cmd += ["-stream_loop", "-1", "-i", str(MUSIC), "-filter_complex",
                f"[2:a]volume={vol:.3f},afade=t=out:st={max(0.0, total - 1.2):.2f}:d=1.2[m];"
                f"[1:a][m]amix=inputs=2:duration=first:normalize=0[a]", "-map", "0:v", "-map", "[a]"]
    cmd += ["-vf", f"scale={W}:{H}", "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-t", f"{total:.2f}", "-movflags", "+faststart", str(out_path)]

    reel = reel_data(cfg, script, speech, starts, total)
    srv = _serve()
    chrome = next((p for p in ("/usr/bin/google-chrome", "/usr/bin/chromium") if os.path.exists(p)), None)
    errors = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=chrome, args=["--no-sandbox"])
        page = browser.new_page(viewport={"width": W, "height": H})
        page.on("console", lambda m: errors.append(m.text) if "error" in m.text.lower() else None)
        page.goto(f"http://127.0.0.1:{srv.server_address[1]}/studio/explainer.html")
        page.wait_for_function("window.ready === true", timeout=30000)
        page.evaluate("r => window.load(r)", reel)
        ff = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        cover_at = int(1.2 * FPS)
        for n in range(int(total * FPS)):
            jpg = base64.b64decode(page.evaluate("t => window.frame(t)", n / FPS).split(",", 1)[1])
            if n == cover_at:
                out_path.with_suffix(".jpg").write_bytes(jpg)
            ff.stdin.write(jpg)
        ff.stdin.close()
        browser.close()
    srv.shutdown()
    if ff.wait() != 0:
        raise RuntimeError("ffmpeg failed to encode the reel: " + ff.stderr.read().decode()[-400:])
    if errors:
        print("render2d: scene warnings:", "; ".join(errors[:5]))
    return out_path
