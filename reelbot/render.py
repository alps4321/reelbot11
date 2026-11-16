"""Draws the reel frame by frame with Pillow and encodes it with ffmpeg.

Each scene has: big text that pops in word by word, an optional animated card
(upload error, file size dropping, upload success), optional stock video behind
the hook, and word-by-word captions. Everything stays inside Instagram's safe
area so the app's buttons never cover text.
"""
import math
import re
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .config import ASSETS
from .script import size_kb

W, H, FPS = 1080, 1920, 30
FONTS = ASSETS / "fonts"
RED, GREEN, INK, GREY = (226, 61, 72), (30, 170, 100), (20, 26, 40), (120, 128, 145)
CARD = (110, 430, 970, 850)


def font(weight, size):
    return ImageFont.truetype(str(FONTS / f"Poppins-{weight}.ttf"), size)


def rgb(hex_):
    hex_ = hex_.lstrip("#")
    return tuple(int(hex_[i:i + 2], 16) for i in (0, 2, 4))


def ease(x):
    x = max(0.0, min(1.0, x))
    return 1 - (1 - x) ** 3


def lerp(a, b, k):
    return tuple(int(a[i] + (b[i] - a[i]) * k) for i in range(3))


def norm(word):
    return re.sub(r"[^\w.]", "", word).lower().strip(".")


def fmt_size(kb):
    return f"{kb / 1024:.1f} MB" if kb >= 1000 else f"{kb:.0f} KB"


def background(c1, c2):
    grad = Image.linear_gradient("L").resize((W, H))
    return Image.composite(Image.new("RGB", (W, H), c2), Image.new("RGB", (W, H), c1), grad)


def glow(color, size=1100):
    layer = Image.new("L", (size, size), 0)
    ImageDraw.Draw(layer).ellipse((size * .2, size * .2, size * .8, size * .8), fill=70)
    return Image.new("RGB", (size, size), color), layer.filter(ImageFilter.GaussianBlur(size // 7))


def wrap(words, fnt, max_w):
    lines, cur = [], []
    for w in words:
        if cur and fnt.getlength(" ".join(cur + [w])) > max_w:
            lines.append(cur)
            cur = []
        cur.append(w)
    if cur:
        lines.append(cur)
    return lines


def text_frames(text, emphasis, colors, start_size, max_lines, max_w=920):
    """One image per word count, so the text can pop in word by word."""
    words, hot, size = text.split(), {norm(e) for e in emphasis}, start_size
    while True:
        fnt = font("Bold", size)
        lines = wrap(words, fnt, max_w)
        if (len(lines) <= max_lines and all(fnt.getlength(" ".join(l)) <= max_w for l in lines)) or size <= 54:
            break
        size -= 6
    lh, space, placed = int(size * 1.16), fnt.getlength(" "), []
    for i, line in enumerate(lines):
        x = (W - fnt.getlength(" ".join(line))) / 2
        for w in line:
            placed.append((x, i * lh, w, norm(w) in hot or any(ch.isdigit() for ch in w)))
            x += fnt.getlength(w) + space
    frames, img = [], Image.new("RGBA", (W, lh * len(lines) + 30), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for x, y, w, is_hot in placed:
        d.text((x + 4, y + 6), w, font=fnt, fill=(0, 0, 0, 150))
        d.text((x, y), w, font=fnt, fill=colors["accent"] if is_hot else colors["text"])
        frames.append(img.copy())
    return frames


def chip(label, colors):
    fnt = font("Bold", 42)
    w = int(fnt.getlength(label)) + 60
    img = Image.new("RGBA", (w, 78), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, w - 1, 77), 39, fill=colors["accent"])
    d.text((w / 2, 39), label, font=fnt, fill=colors["bg"], anchor="mm")
    return img


def caption_chunks(words, max_words=3, max_chars=20):
    chunks, cur = [], []
    for i, w in enumerate(words):
        if cur and (len(cur) >= max_words or len(" ".join(words[j] for j in cur) + " " + w) > max_chars):
            chunks.append(cur)
            cur = []
        cur.append(i)
        if w[-1:] in ".?!," and len(cur) >= 2:
            chunks.append(cur)
            cur = []
    if cur:
        chunks.append(cur)
    return chunks


def word_times(words, start, speech):
    weights = [len(w) + 2 for w in words]
    total, t, out = sum(weights), start, []
    for wt in weights:
        dur = speech * wt / total
        out.append((t, t + dur))
        t += dur
    return out


class Clip:
    """Reads a stock video as 1080x1920 frames, looping if it is short."""

    def __init__(self, path):
        self.proc = subprocess.Popen(
            ["ffmpeg", "-v", "error", "-stream_loop", "-1", "-i", str(path), "-an", "-vf",
             f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS}",
             "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
        self.black, self.last = Image.new("RGB", (W, H)), None

    def frame(self):
        data = self.proc.stdout.read(W * H * 3)
        if len(data) == W * H * 3:
            self.last = Image.blend(Image.frombytes("RGB", (W, H), data), self.black, 0.58)
        return self.last

    def close(self):
        self.proc.kill()


def draw_card(d, v, lt, f):
    """Animated white card: a file row, then an error, a shrinking size bar, or a success banner."""
    dy = int((1 - ease(lt / 0.25)) * 140)
    dx = 0
    if v["type"] == "error" and 0.3 <= lt <= 0.8:
        dx = int(16 * math.sin(lt * 55) * (1 - (lt - 0.3) / 0.5))
    x0, y0, x1, y1 = CARD[0] + dx, CARD[1] + dy, CARD[2] + dx, CARD[3] + dy
    d.rounded_rectangle((x0 + 6, y0 + 12, x1 + 6, y1 + 12), 48, fill=(0, 0, 0))
    d.rounded_rectangle((x0, y0, x1, y1), 48, fill=(255, 255, 255))

    ext = (v["file"].rsplit(".", 1)[-1] if "." in v["file"] else "file").upper()[:4]
    d.rounded_rectangle((x0 + 44, y0 + 44, x0 + 140, y0 + 140), 22, fill=(52, 104, 232))
    d.text((x0 + 92, y0 + 92), ext, font=f["ext"], fill=(255, 255, 255), anchor="mm")
    d.text((x0 + 168, y0 + 92), v["file"], font=f["file"], fill=INK, anchor="lm")
    d.line((x0 + 44, y0 + 184, x1 - 44, y0 + 184), fill=(228, 231, 238), width=3)

    if v["type"] == "size_drop":
        a, b = size_kb(v["from"]), size_kb(v["to"])
        p = ease((lt - 0.35) / 0.9)
        now = a + (b - a) * p
        color = lerp(RED, GREEN, p)
        d.text((x1 - 44, y0 + 92), fmt_size(now), font=f["size"], fill=color, anchor="rm")
        d.rounded_rectangle((x0 + 44, y0 + 232, x1 - 44, y0 + 286), 27, fill=(228, 231, 238))
        width = (x1 - x0 - 88) * max(0.07, now / a)
        d.rounded_rectangle((x0 + 44, y0 + 232, x0 + 44 + width, y0 + 286), 27, fill=color)
        d.text((x0 + 44, y0 + 346), v["from"], font=f["file"], fill=GREY, anchor="lm")
        if p >= 1:
            d.text((x1 - 44, y0 + 346), f"{100 * (1 - b / a):.0f}% smaller", font=f["size"], fill=GREEN, anchor="rm")
        return
    bad = v["type"] == "error"
    color = RED if bad else GREEN
    d.text((x1 - 44, y0 + 92), v["size"], font=f["size"], fill=color, anchor="rm")
    if lt >= 0.3:
        d.rounded_rectangle((x0 + 44, y0 + 226, x1 - 44, y1 - 48), 30, fill=color)
        cx, cy = x0 + 110, (y0 + 226 + y1 - 48) // 2
        if bad:
            d.line((cx - 20, cy - 20, cx + 20, cy + 20), fill=(255, 255, 255), width=10)
            d.line((cx - 20, cy + 20, cx + 20, cy - 20), fill=(255, 255, 255), width=10)
        else:
            d.line((cx - 24, cy, cx - 6, cy + 18, cx + 26, cy - 20), fill=(255, 255, 255), width=10, joint="curve")
        d.text((cx + 52, cy), v["message"], font=f["msg"], fill=(255, 255, 255), anchor="lm")


def render(cfg, script, audio, speech, starts, total, out_path):
    b = cfg["brand"]
    colors = {"bg": rgb(b["background"]), "bg2": rgb(b["background2"]),
              "accent": rgb(b["accent"]), "text": rgb(b["text"])}
    bg = background(colors["bg"], colors["bg2"])
    glow_img, glow_mask = glow((40, 90, 200))
    cap_font, brand_font, url_font = font("Bold", 62), font("Medium", 38), font("Bold", 52)
    card_fonts = {"ext": font("Bold", 30), "file": font("Medium", 42), "size": font("Bold", 46),
                  "msg": font("Bold", 40)}

    scenes, step_no = [], 0
    for i, sc in enumerate(script["scenes"]):
        end = starts[i + 1] if i + 1 < len(starts) else total
        words, label, v = sc["say"].split(), None, sc.get("visual")
        if sc["kind"] == "step":
            step_no += 1
            label = f"STEP {step_no}"
        scenes.append({
            "kind": sc["kind"], "start": starts[i], "end": end, "visual": v,
            "frames": text_frames(sc["screen"], sc["emphasis"], colors, 100 if v else 124, 3 if v else 4),
            "center": 1050 if v else 800,
            "chip": chip(label, colors) if label and not v else None,
            "clip": Clip(sc["broll_path"]) if sc.get("broll_path") else None,
            "words": words, "times": word_times(words, starts[i], speech[i]),
            "chunks": caption_chunks(words),
        })

    out_path = Path(out_path)
    cmd = ["ffmpeg", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-i", str(audio)]
    music = sorted((ASSETS / "music").glob("*.mp3"))
    if music:  # optional background track you have the rights to use
        cmd += ["-stream_loop", "-1", "-i", str(music[0]), "-filter_complex",
                "[2:a]volume=0.08[m];[1:a][m]amix=inputs=2:duration=first:normalize=0[a]",
                "-map", "0:v", "-map", "[a]"]
    cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-t", f"{total:.2f}",
            "-movflags", "+faststart", str(out_path)]
    ff = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    frames, cover_at = int(total * FPS), int(1.0 * FPS)
    for n in range(frames):
        t = n / FPS
        sc = next((s for s in scenes if s["start"] <= t < s["end"]), scenes[-1])
        lt = t - sc["start"]
        frame = sc["clip"].frame() if sc["clip"] else None
        if frame is None:
            frame = bg.copy()
            frame.paste(glow_img, (int(W / 2 - 550 + 260 * math.sin(t * 0.5)),
                                   int(760 - 550 + 320 * math.cos(t * 0.37))), glow_mask)
        else:
            frame = frame.copy()
        d = ImageDraw.Draw(frame)

        # progress bar and brand pill
        d.rectangle((0, 0, int(W * t / total), 12), fill=colors["accent"])
        bw = brand_font.getlength(b["name"]) + 86
        d.rounded_rectangle(((W - bw) / 2, 196, (W + bw) / 2, 268), 36, fill=(255, 255, 255))
        d.ellipse(((W - bw) / 2 + 22, 222, (W - bw) / 2 + 42, 242), fill=colors["accent"])
        d.text(((W - bw) / 2 + 58, 232), b["name"], font=brand_font, fill=colors["bg"], anchor="lm")

        if sc["visual"]:
            draw_card(d, sc["visual"], lt, card_fonts)

        # scene text: words pop in one after another, the block slides up
        shown = min(len(sc["frames"]), 1 + int(max(0, lt - 0.04) / 0.07))
        block = sc["frames"][shown - 1]
        top = int(sc["center"] - block.height / 2 + (1 - ease(lt / 0.22)) * 46)
        if sc["chip"]:
            frame.paste(sc["chip"], ((W - sc["chip"].width) // 2, top - 120), sc["chip"])
        frame.paste(block, (0, top), block)

        if sc["kind"] == "cta":  # site address as a pulsing button
            pulse = 1 + 0.035 * math.sin(t * 7)
            uw, uh = (url_font.getlength(b["url"]) + 110) * pulse, 120 * pulse
            cy = top + block.height + 120
            d.rounded_rectangle(((W - uw) / 2, cy - uh / 2, (W + uw) / 2, cy + uh / 2), int(uh / 2),
                                fill=colors["accent"])
            d.text((W / 2, cy), b["url"], font=url_font, fill=colors["bg"], anchor="mm")

        # captions: current chunk, current word highlighted
        idx = next((i for i, (a, z) in enumerate(sc["times"]) if a <= t < z), None)
        if idx is not None:
            chunk = next(c for c in sc["chunks"] if idx in c)
            words = [sc["words"][i] for i in chunk]
            line_w = cap_font.getlength(" ".join(words))
            x, y = (W - line_w) / 2, 1340
            d.rounded_rectangle((x - 34, y - 58, x + line_w + 34, y + 58), 30, fill=(0, 0, 0))
            for i, w in zip(chunk, words):
                d.text((x, y), w, font=cap_font, anchor="lm",
                       fill=colors["accent"] if i == idx else colors["text"])
                x += cap_font.getlength(w + " ")

        if n == cover_at:
            frame.save(out_path.with_suffix(".jpg"), quality=90)
        ff.stdin.write(frame.tobytes())
    ff.stdin.close()
    for sc in scenes:
        if sc["clip"]:
            sc["clip"].close()
    if ff.wait() != 0:
        raise RuntimeError("ffmpeg failed to encode the reel")
    return out_path
