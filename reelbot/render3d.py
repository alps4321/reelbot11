"""Renders a low-poly 3D story reel.

A headless browser draws each 3D frame (studio/engine.js, three.js); Python adds
the hook title, labels and word-by-word captions, then ffmpeg encodes the video.
"""
import base64
import functools
import http.server
import io
import math
import os
import subprocess
import threading
from pathlib import Path

from PIL import Image, ImageDraw

from .config import ASSETS, ROOT
from .render import FPS, H, W, caption_chunks, font, norm, rgb, scene_word_times, wrap

CYAN = (120, 235, 255)


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def _serve():
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(_Quiet, directory=str(ROOT)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def _title(d, text, emphasis, accent, top=250, size=74, max_w=960):
    """Uppercase headline with a black outline, emphasis words in the accent colour."""
    fnt, hot = font("Bold", size), {norm(e) for e in emphasis}
    lines = wrap(text.upper().split(), fnt, max_w)
    for i, line in enumerate(lines[:4]):
        x, y = (W - fnt.getlength(" ".join(line))) / 2, top + i * int(size * 1.2)
        for w in line:
            fill = accent if norm(w) in hot or any(c.isdigit() for c in w) else (255, 255, 255)
            d.text((x, y), w, font=fnt, fill=fill, stroke_width=8, stroke_fill=(0, 0, 0))
            x += fnt.getlength(w + " ")
    return top + len(lines[:4]) * int(size * 1.2)


def add_mascot(scenes, storyboard):
    """Docu, the ilovedocuments.ai mascot, pops in on the answer shot and the closing shot of every reel,
    on whichever side the cast leaves free, so the page's own character is what people remember."""
    from .voice import reveal_shot
    for i in {reveal_shot(scenes), len(scenes) - 1} - {None}:
        shot = storyboard[i]
        cast = [a for a in shot.get("actors") or [] if not a.get("mascot")]
        mean = sum(a.get("x", 0) for a in cast) / len(cast) if cast else -1
        side = -1 if mean >= 0 else 1
        cast = sorted(cast[:2], key=lambda a: a.get("x", 0) * -side)     # nearest to Docu first
        for a, x in zip(cast, (-0.2, -1.05) if len(cast) == 2 else (-0.35,)):
            a["x"] = x * side                # make room: the cast moves to the other side
        shot["actors"] = cast + [{"mascot": True, "x": 0.85 * side, "z": 1.0, "look": "right" if side < 0 else "left"}]
        if len(cast) == 2 and shot.get("camera") not in ("wide", "orbit"):
            shot["camera"] = "wide"            # three on screen: pull back so nobody is cut off


def render(cfg, script, audio, speech, starts, total, out_path):
    from playwright.sync_api import sync_playwright

    b = cfg["brand"]
    accent = rgb(b["accent"])
    cap_font, label_font, brand_font, url_font = font("Bold", 64), font("Bold", 70), font("Medium", 34), font("Bold", 52)
    scenes = []
    for i, sc in enumerate(script["scenes"]):
        words = [w.upper() for w in sc["say"].split()]
        scenes.append({**sc, "start": starts[i], "end": starts[i + 1] if i + 1 < len(starts) else total,
                       "words": words, "times": scene_word_times(sc, words, starts[i], speech[i]),
                       "chunks": caption_chunks(words, max_words=3, max_chars=18)})
    storyboard = [{k: sc.get(k) for k in ("set", "actors", "props", "camera", "shake")} for sc in script["scenes"]]
    add_mascot(script["scenes"], storyboard)

    out_path = Path(out_path)
    cmd = ["ffmpeg", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-i", str(audio)]
    music = sorted((ASSETS / "music").glob("*.mp3"))
    if music:
        cmd += ["-stream_loop", "-1", "-i", str(music[0]), "-filter_complex",
                "[2:a]volume=0.10[m];[1:a][m]amix=inputs=2:duration=first:normalize=0[a]",
                "-map", "0:v", "-map", "[a]"]
    cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-t", f"{total:.2f}",
            "-movflags", "+faststart", str(out_path)]

    srv = _serve()
    chrome = next((p for p in ("/usr/bin/google-chrome", "/usr/bin/chromium") if os.path.exists(p)), None)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=chrome, args=[
            "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist", "--no-sandbox"])
        page = browser.new_page(viewport={"width": W, "height": H})
        page.goto(f"http://127.0.0.1:{srv.server_address[1]}/studio/index.html")
        page.wait_for_function("window.ready === true", timeout=30000)
        page.evaluate("s => window.load(s)", storyboard)

        ff = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        frames, cover_at = int(total * FPS), int(1.0 * FPS)
        for n in range(frames):
            t = n / FPS
            i = next((j for j, s in enumerate(scenes) if s["start"] <= t < s["end"]), len(scenes) - 1)
            sc = scenes[i]
            lt, span = t - sc["start"], max(0.1, sc["end"] - sc["start"])
            url = page.evaluate("([i, lt, k]) => window.frame(i, lt, k)", [i, lt, min(1.0, lt / span)])
            frame = Image.open(io.BytesIO(base64.b64decode(url.split(",", 1)[1]))).convert("RGB")
            d = ImageDraw.Draw(frame)

            d.rectangle((0, 0, int(W * t / total), 12), fill=accent)
            d.text((W / 2, 170), b["url"], font=brand_font, fill=(255, 255, 255), anchor="mm",
                   stroke_width=4, stroke_fill=(0, 0, 0))
            if sc["kind"] in ("hook", "cta"):
                has_panel = any(p.get("type") == "panel" for p in sc.get("props") or [])
                bottom = _title(d, sc["screen"], sc.get("emphasis", []), accent, size=54 if has_panel else 74)
                if sc["kind"] == "cta":
                    pulse = 1 + 0.035 * math.sin(t * 7)
                    uw, uh, cy = (url_font.getlength(b["url"]) + 110) * pulse, 120 * pulse, bottom + 90
                    d.rounded_rectangle(((W - uw) / 2, cy - uh / 2, (W + uw) / 2, cy + uh / 2), int(uh / 2),
                                        fill=accent, outline=(0, 0, 0), width=6)
                    d.text((W / 2, cy), b["url"], font=url_font, fill=rgb(b["background"]), anchor="mm")
            elif sc.get("label"):
                d.text((W / 2, 290), str(sc["label"]).upper()[:22], font=label_font, fill=CYAN, anchor="mm",
                       stroke_width=8, stroke_fill=(0, 0, 0))

            idx = next((j for j, (a, z) in enumerate(sc["times"]) if a <= t < z), None)
            if idx is not None:
                chunk = next(c for c in sc["chunks"] if idx in c)
                words = [sc["words"][j] for j in chunk]
                x, y = (W - cap_font.getlength(" ".join(words))) / 2, 1390
                for j, w in zip(chunk, words):
                    d.text((x, y), w, font=cap_font, anchor="lm", stroke_width=9, stroke_fill=(0, 0, 0),
                           fill=accent if j == idx else (255, 255, 255))
                    x += cap_font.getlength(w + " ")

            if n == cover_at:
                frame.save(out_path.with_suffix(".jpg"), quality=90)
            ff.stdin.write(frame.tobytes())
        ff.stdin.close()
        browser.close()
    srv.shutdown()
    if ff.wait() != 0:
        raise RuntimeError("ffmpeg failed to encode the reel")
    return out_path
