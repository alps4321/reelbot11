"""Animated cheat-sheet reels ("5 ways" style).

Learned from a reference reel: show the finished result first, number the items with a progress marker,
fill a cheat-sheet table one row per item (the thing people save), switch background colour per section,
give every item its own small animation, and highlight captions word by word.
"""
import math
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .config import ASSETS
from .render import FPS, H, W, caption_chunks, ease, scene_word_times

FONTS = ASSETS / "fonts"
SERIF_ITALIC = "/usr/share/fonts/truetype/google-fonts/Lora-Italic-Variable.ttf"
MAGENTA, GREEN, RED, INK, GREY = (214, 22, 139), (30, 170, 100), (226, 61, 72), (24, 22, 32), (150, 146, 160)
THEMES = {
    "light": {"bg": (247, 238, 241), "glow": (244, 170, 210), "text": INK, "soft": (120, 110, 125)},
    "magenta": {"bg": (205, 18, 132), "glow": (246, 110, 190), "text": (255, 255, 255), "soft": (255, 220, 240)},
    "dark": {"bg": (24, 9, 30), "glow": (150, 20, 110), "text": (255, 255, 255), "soft": (200, 170, 200)},
}


ARROW_FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def arrow(d, x, y, size, color):
    try:
        f = ImageFont.truetype(ARROW_FONT, size)
    except OSError:
        f = F("Bold", size)
    d.text((x, y), "\u2192", font=f, fill=color, anchor="mm")


def F(weight, size):
    return ImageFont.truetype(str(FONTS / f"Poppins-{weight}.ttf"), size)


def serif(size):
    try:
        return ImageFont.truetype(SERIF_ITALIC, size)
    except OSError:
        return ImageFont.truetype(str(FONTS / "Poppins-Medium.ttf"), size)


def background(theme):
    t = THEMES[theme]
    img = Image.new("RGB", (W, H), t["bg"])
    glow = Image.new("L", (W, H), 0)
    ImageDraw.Draw(glow).ellipse((W * 0.15, H * 0.12, W * 0.85, H * 0.5), fill=120)
    glow = glow.filter(ImageFilter.GaussianBlur(160))
    img.paste(Image.new("RGB", (W, H), t["glow"]), (0, 0), glow)
    return img


def rr(d, box, r, **kw):
    d.rounded_rectangle([int(v) for v in box], int(r), **kw)


def mix(a, b, k):
    return tuple(int(a[i] + (b[i] - a[i]) * k) for i in range(3))


def check(d, cx, cy, s, color, width=10):
    d.line((cx - s, cy, cx - s * 0.3, cy + s * 0.7, cx + s, cy - s * 0.7), fill=color, width=width, joint="curve")


def cross(d, cx, cy, s, color, width=10):
    d.line((cx - s, cy - s, cx + s, cy + s), fill=color, width=width)
    d.line((cx - s, cy + s, cx + s, cy - s), fill=color, width=width)


def pop(lt, at, dur=0.25):
    """0..1 with a small overshoot, for things that pop in at time `at`."""
    x = (lt - at) / dur
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    return min(1.08, ease(x) * 1.08)


# ---------------------------------------------------------------- title
def draw_title(d, tokens, lt, color, top=210):
    """tokens: list of lines, each a list of (word, accent). Words appear one by one."""
    n = 0
    y = top
    for line in tokens:
        fonts = [serif(96) if acc else (ImageFont.truetype(ARROW_FONT, 72) if w == "\u2192" else F("Medium", 84))
                 for w, acc in line]
        widths = [f.getlength(w) for (w, _), f in zip(line, fonts)]
        gap = 22
        x = (W - (sum(widths) + gap * (len(line) - 1))) / 2
        for (word, acc), f, wd in zip(line, fonts, widths):
            k = ease((lt - 0.05 - n * 0.08) / 0.22)
            if k > 0:
                c = MAGENTA if acc and color == INK else ((255, 230, 245) if acc else color)
                dy = 16 if word == "\u2192" else 0
                d.text((x, y + dy + (1 - k) * 24), word, font=f, fill=mix(THEMES_BG_CACHE["bg"], c, k))
            x += wd + gap
            n += 1
        y += 108
    return y


THEMES_BG_CACHE = {"bg": (247, 238, 241)}


# ---------------------------------------------------------------- top marker
def draw_marker(d, index, total, theme):
    t = THEMES[theme]
    if index <= 0:
        return
    label = f"WAY {index}"
    f = F("Bold", 26)
    w = f.getlength(label) + 36
    fill = (255, 255, 255) if theme == "magenta" else MAGENTA
    txt = MAGENTA if theme == "magenta" else (255, 255, 255)
    rr(d, ((W - w) / 2, 118, (W + w) / 2, 160), 21, fill=fill)
    d.text((W / 2, 139), label, font=f, fill=txt, anchor="mm")
    seg, gap = 34, 10
    x0 = (W - (total * seg + (total - 1) * gap)) / 2
    for i in range(total):
        c = fill if i < index else mix(t["bg"], t["text"], 0.25)
        d.rounded_rectangle((x0 + i * (seg + gap), 176, x0 + i * (seg + gap) + seg, 182), 3, fill=c)


# ---------------------------------------------------------------- table
def draw_table(d, rows, filled, current, alpha_bg=None, top=1000, compact=False):
    """rows: [(problem, use)], filled: list of (show_problem 0..1, show_use 0..1)."""
    x0, x1 = 90, W - 90
    rh = 62 if not compact else 58
    h = 70 + rh * len(rows) + 20
    rr(d, (x0 + 6, top + 10, x1 + 6, top + h + 10), 26, fill=(0, 0, 0) if alpha_bg is None else alpha_bg)
    rr(d, (x0, top, x1, top + h), 26, fill=(255, 255, 255))
    head = F("Bold", 22)
    split = x0 + 400
    d.text((x0 + 28, top + 38), "IF YOU NEED", font=head, fill=GREY, anchor="lm")
    d.text((split + 20, top + 38), "USE (FREE)", font=head, fill=GREY, anchor="lm")
    d.line((x0 + 20, top + 64, x1 - 20, top + 64), fill=(236, 230, 236), width=2)
    body = F("Medium", 30)
    for i, (prob, use) in enumerate(rows):
        y = top + 70 + i * rh
        sp, su = filled[i] if i < len(filled) else (0, 0)
        if i == current and sp > 0:
            rr(d, (x0 + 12, y + 4, x1 - 12, y + rh - 4), 14, fill=(253, 232, 243))
        if sp > 0:
            rr(d, (x0 + 22, y + 12, x0 + 22 + body.getlength(prob) + 24, y + rh - 12), 12,
               fill=mix((255, 255, 255), (250, 214, 233), sp))
            d.text((x0 + 34, y + rh / 2), prob, font=body, fill=mix((255, 255, 255), INK, sp), anchor="lm")
        if su > 0:
            f = body
            while f.getlength(use) > x1 - split - 60 and f.size > 20:
                f = F("Medium", f.size - 2)
            rr(d, (split + 12, y + 12, split + 12 + f.getlength(use) + 24, y + rh - 12), 12,
               fill=mix((255, 255, 255), (214, 244, 225), su))
            d.text((split + 24, y + rh / 2), use, font=f, fill=mix((255, 255, 255), (18, 110, 60), su), anchor="lm")


# ---------------------------------------------------------------- illustrations (centre area y 420..900)
def card(d, box, fill=(255, 255, 255)):
    x0, y0, x1, y1 = box
    rr(d, (x0 + 6, y0 + 12, x1 + 6, y1 + 12), 34, fill=(0, 0, 0, 40) if False else mix(fill, (0, 0, 0), 0.18))
    rr(d, box, 34, fill=fill)


def file_icon(d, x, y, label, color):
    rr(d, (x, y, x + 96, y + 96), 22, fill=color)
    d.text((x + 48, y + 48), label, font=F("Bold", 28), fill=(255, 255, 255), anchor="mm")


def ill_compress(d, lt, ans):
    k = ease((lt - ans) / 1.0)
    a, b = 4.8 * 1024, 180
    now = a + (b - a) * k
    col = mix(RED, GREEN, k)
    card(d, (150, 470, 930, 820))
    file_icon(d, 190, 510, "PDF", (52, 104, 232))
    d.text((310, 558), "form.pdf", font=F("Medium", 40), fill=INK, anchor="lm")
    txt = f"{now / 1024:.1f} MB" if now >= 1000 else f"{now:.0f} KB"
    d.text((890, 558), txt, font=F("Bold", 44), fill=col, anchor="rm")
    rr(d, (190, 650, 890, 700), 25, fill=(236, 232, 238))
    rr(d, (190, 650, 190 + 700 * max(0.07, now / a), 700), 25, fill=col)
    if k >= 1:
        d.text((540, 760), "Under the form's limit", font=F("Bold", 36), fill=GREEN, anchor="mm")
    elif lt > 0.5:
        d.text((540, 760), "Too large to upload", font=F("Bold", 36), fill=RED, anchor="mm")


def photo_tile(d, x, y, s):
    rr(d, (x, y, x + s, y + s), 16, fill=(255, 255, 255))
    rr(d, (x + 8, y + 8, x + s - 8, y + s - 8), 10, fill=(210, 230, 250))
    d.polygon([(x + 14, y + s - 14), (x + s * 0.42, y + s * 0.45), (x + s * 0.65, y + s - 14)], fill=(90, 170, 120))
    d.ellipse((x + s * 0.62, y + s * 0.2, x + s * 0.8, y + s * 0.38), fill=(250, 200, 80))


def ill_jpg(d, lt, ans):
    k = ease((lt - ans) / 0.8)
    target = (700, 600)
    for i in range(4):
        sx, sy = 200 + (i % 2) * 150, 500 + (i // 2) * 150
        x = sx + (target[0] - sx) * k
        y = sy + (target[1] - sy) * k
        s = 130 * (1 - 0.6 * k)
        if k < 0.98:
            photo_tile(d, x, y, s)
    if lt > 0.3:
        arrow(d, 560, 650, 90, (255, 255, 255) if k < 1 else GREEN)
    p = pop(lt, ans + 0.5)
    if p > 0:
        x0, y0 = 660, 500
        rr(d, (x0, y0, x0 + 200 * p, y0 + 260 * p), 22, fill=(255, 255, 255))
        if p >= 1:
            file_icon(d, x0 + 52, y0 + 40, "PDF", (226, 61, 72))
            d.text((x0 + 100, y0 + 190), "1 file", font=F("Bold", 34), fill=INK, anchor="mm")
            check(d, x0 + 190, y0 - 6, 18, GREEN, 9)


def ill_aadhaar(d, lt, ans, mid):
    card(d, (150, 470, 930, 840))
    d.text((190, 520), "aadhaar.pdf is protected", font=F("Medium", 34), fill=INK, anchor="lm")
    rr(d, (190, 570, 890, 670), 20, outline=(210, 200, 215), width=4, fill=(250, 248, 251))
    unlocked = lt >= ans + 1.4
    lx, ly = 225, 620
    lock = GREEN if unlocked else RED
    rr(d, (lx - 22, ly - 6, lx + 22, ly + 30), 8, fill=lock)
    d.arc((lx - 16, ly - 34 - (10 if unlocked else 0), lx + 16, ly + 2 - (10 if unlocked else 0)), 180, 360, fill=lock, width=7)
    if lt < ans:
        d.text((280, 620), "• • • • • • • •", font=F("Bold", 40), fill=GREY, anchor="lm")
        if lt > mid:
            d.text((190, 730), "Not the OTP. Not the Aadhaar number.", font=F("Medium", 30), fill=RED, anchor="lm")
    else:
        typed = "RAHU1998"
        n = min(len(typed), int((lt - ans) / 0.13) + 1)
        x = 280
        for i, ch in enumerate(typed[:n]):
            c = MAGENTA if i < 4 else GREEN
            d.text((x, 620), ch, font=F("Bold", 46), fill=c, anchor="lm")
            x += F("Bold", 46).getlength(ch) + 4
        d.text((190, 725), "RAHUL", font=F("Bold", 32), fill=MAGENTA, anchor="lm")
        d.text((340, 725), "= first 4 letters, CAPITALS", font=F("Medium", 28), fill=INK, anchor="lm")
        d.text((190, 785), "1998", font=F("Bold", 32), fill=GREEN, anchor="lm")
        d.text((340, 785), "= year of birth", font=F("Medium", 28), fill=INK, anchor="lm")


def tile(d, cx, cy, label, state, k):
    s = 1 if k >= 1 else max(0.0, k)
    if s <= 0:
        return
    w, h = 250 * s, 170 * s
    fill = (255, 255, 255) if state != "yes" else (230, 250, 238)
    rr(d, (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2), 26 * s, fill=fill,
       outline=GREEN if state == "yes" else None, width=6)
    if s >= 1:
        f = F("Bold", 38)
        d.text((cx, cy), label, font=f, fill=INK if state != "no" else GREY, anchor="mm")
        if state == "no":
            d.ellipse((cx + w / 2 - 34, cy - h / 2 - 22, cx + w / 2 + 14, cy - h / 2 + 26), fill=RED)
            cross(d, cx + w / 2 - 10, cy - h / 2 + 2, 10, (255, 255, 255), 6)
        if state == "yes":
            d.ellipse((cx + w / 2 - 34, cy - h / 2 - 22, cx + w / 2 + 14, cy - h / 2 + 26), fill=GREEN)
            check(d, cx + w / 2 - 10, cy - h / 2 + 4, 11, (255, 255, 255), 6)


def ill_sign(d, lt, ans, mid):
    tile(d, 240, 650, "Print", "no" if lt > mid else "", pop(lt, 0.4))
    tile(d, 540, 650, "Scan", "no" if lt > mid + 0.3 else "", pop(lt, 0.7))
    tile(d, 840, 650, "Sign PDF", "yes", pop(lt, ans))
    if lt > ans + 0.6:
        f = F("Medium", 30)
        d.text((540, 800), "on your phone", font=f, fill=GREEN, anchor="mm")


def ill_bank(d, lt, ans):
    card(d, (170, 500, 440, 800))
    for i in range(6):
        d.line((210, 560 + i * 36, 400 - (i % 3) * 30, 560 + i * 36), fill=(200, 196, 206), width=10)
    d.text((305, 530), "statement.pdf", font=F("Medium", 22), fill=GREY, anchor="mm")
    k = ease((lt - ans) / 0.6)
    if lt > 0.4:
        arrow(d, 540, 650, 90, (255, 255, 255) if k < 1 else GREEN)
    if k > 0:
        x0, y0 = 640, 500
        rr(d, (x0, y0, x0 + 270, y0 + 300), 26, fill=(255, 255, 255))
        cols, rows_ = 3, 6
        for r in range(rows_):
            for c in range(cols):
                if (r * cols + c) / (rows_ * cols) <= k:
                    fill = (30, 140, 80) if r == 0 else (214, 244, 225)
                    rr(d, (x0 + 20 + c * 80, y0 + 20 + r * 44, x0 + 92 + c * 80, y0 + 56 + r * 44), 6, fill=fill)
        if k >= 1:
            check(d, x0 + 262, y0 - 4, 18, GREEN, 9)


def ill_best(d, lt):
    chips = [("Free", 0.3), ("No sign-up", 0.7), ("Never uploaded", 1.1)]
    for i, (label, at) in enumerate(chips):
        p = pop(lt, at)
        if p <= 0:
            continue
        f = F("Bold", 44)
        w = (f.getlength(label) + 130) * p
        cy = 520 + i * 125
        rr(d, (540 - w / 2, cy - 48 * p, 540 + w / 2, cy + 48 * p), 48 * p, fill=(255, 255, 255))
        if p >= 1:
            d.ellipse((540 - w / 2 + 22, cy - 26, 540 - w / 2 + 74, cy + 26), fill=GREEN)
            check(d, 540 - w / 2 + 48, cy + 2, 13, (255, 255, 255), 6)
            d.text((540 - w / 2 + 92, cy), label, font=f, fill=INK, anchor="lm")


def bookmark(d, cx, cy, s, color):
    d.polygon([(cx - s, cy - s * 1.2), (cx + s, cy - s * 1.2), (cx + s, cy + s * 1.2), (cx, cy + s * 0.5),
               (cx - s, cy + s * 1.2)], fill=color)


# ---------------------------------------------------------------- captions
def draw_captions(d, sc, t, theme):
    idx = next((j for j, (a, z) in enumerate(sc["times"]) if a <= t < z), None)
    if idx is None:
        return
    chunk = next(c for c in sc["chunks"] if idx in c)
    words = [sc["words"][j] for j in chunk]
    f = F("Bold", 52)
    gap = 18
    widths = [f.getlength(w) + 28 for w in words]
    x = (W - (sum(widths) + gap * (len(words) - 1))) / 2
    y = 1505
    base = INK if theme == "light" else (255, 255, 255)
    for j, w, wd in zip(chunk, words, widths):
        if j == idx:
            box = MAGENTA if theme != "magenta" else (255, 255, 255)
            rr(d, (x, y - 40, x + wd, y + 40), 14, fill=box)
            d.text((x + wd / 2, y), w, font=f, fill=(255, 255, 255) if theme != "magenta" else MAGENTA, anchor="mm")
        else:
            d.text((x + wd / 2, y), w, font=f, fill=base, anchor="mm")
        x += wd + gap


# ---------------------------------------------------------------- main
def render(cfg, plan, scenes, audio, speech, starts, total, out_path):
    """plan: dict with 'titles' (per scene tokens), 'themes', 'rows', 'kinds' (illustration per scene)."""
    bgs = {k: background(k) for k in THEMES}
    rows = plan["rows"]
    prepared = []
    for i, sc in enumerate(scenes):
        end = starts[i + 1] if i + 1 < len(starts) else total
        words = sc["say"].split()
        marks = sc.get("_phrases") or [(0.0, speech[i])]
        prepared.append({
            "start": starts[i], "end": end, "theme": plan["themes"][i], "title": plan["titles"][i],
            "ill": plan["kinds"][i], "item": plan["items"][i],
            "ans": marks[-1][0], "mid": marks[-2][0] if len(marks) > 1 else 0.0,
            "words": words, "times": scene_word_times(sc, words, starts[i], speech[i]),
            "chunks": caption_chunks(words, max_words=3, max_chars=20),
        })
    n_items = max(p["item"] for p in prepared)
    item_scene = {p["item"]: p for p in prepared if p["item"] > 0}

    out_path = Path(out_path)
    cmd = ["ffmpeg", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-i", str(audio), "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-t", f"{total:.2f}", "-movflags", "+faststart",
           str(out_path)]
    ff = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    site = F("Medium", 26)
    for n in range(int(total * FPS)):
        t = n / FPS
        i = next((j for j, p in enumerate(prepared) if p["start"] <= t < p["end"]), len(prepared) - 1)
        sc = prepared[i]
        lt = t - sc["start"]
        frame = bgs[sc["theme"]].copy()
        if i > 0 and lt < 0.25 and prepared[i - 1]["theme"] != sc["theme"]:      # colour change between sections
            frame = Image.blend(bgs[prepared[i - 1]["theme"]], frame, ease(lt / 0.25))
        THEMES_BG_CACHE["bg"] = THEMES[sc["theme"]]["bg"]
        d = ImageDraw.Draw(frame)
        theme = THEMES[sc["theme"]]
        d.text((W / 2, 70), "ilovedocuments.ai", font=site, fill=theme["soft"], anchor="mm")
        draw_marker(d, sc["item"], n_items, sc["theme"])
        draw_title(d, sc["title"], lt, theme["text"], top=215 if sc["item"] else 240)

        k = sc["ill"]
        if k == "compress":
            ill_compress(d, lt, sc["ans"])
        elif k == "jpg":
            ill_jpg(d, lt, sc["ans"])
        elif k == "aadhaar":
            ill_aadhaar(d, lt, sc["ans"], sc["mid"])
        elif k == "sign":
            ill_sign(d, lt, sc["ans"], sc["mid"])
        elif k == "bank":
            ill_bank(d, lt, sc["ans"])
        elif k == "best":
            ill_best(d, lt)

        # the cheat sheet: complete and faded at the start (result first), then filled row by row
        if k == "hook":
            filled = [(1, 1)] * len(rows)
            ghost = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            draw_table(ImageDraw.Draw(ghost), rows, filled, -1, alpha_bg=(0, 0, 0, 0), top=660)
            a = ghost.getchannel("A").point(lambda v: int(v * (0.35 + 0.25 * ease(lt / 0.6))))
            ghost.putalpha(a)
            frame.paste(ghost, (0, 0), ghost)
            d = ImageDraw.Draw(frame)
        elif k == "cta":
            draw_table(d, rows, [(1, 1)] * len(rows), -1, top=470)
            p = pop(lt, 0.3)
            if p > 0:
                bookmark(d, W - 160, 380, 30 * p, (255, 255, 255))
            if lt > 0.9:
                f = F("Bold", 44)
                w = f.getlength("ilovedocuments.ai") + 80
                rr(d, ((W - w) / 2, 1200, (W + w) / 2, 1290), 45, fill=(255, 255, 255))
                d.text((W / 2, 1245), "ilovedocuments.ai", font=f, fill=MAGENTA, anchor="mm")
            if lt > 0.6:
                badge = Image.new("RGBA", (560, 100), (0, 0, 0, 0))
                bd = ImageDraw.Draw(badge)
                rr(bd, (0, 0, 559, 99), 18, fill=(255, 236, 246))
                bd.text((280, 50), "FOR YOUR NEXT FORM", font=F("Bold", 40), fill=MAGENTA, anchor="mm")
                badge = badge.rotate(4, expand=True, resample=Image.BICUBIC)
                frame.paste(badge, ((W - badge.width) // 2, 1010), badge)
                d = ImageDraw.Draw(frame)
        else:
            filled = []
            for r in range(1, len(rows) + 1):
                rs = item_scene.get(r)
                if rs is None or t < rs["start"]:
                    filled.append((0, 0))
                else:
                    filled.append((ease((t - rs["start"] - 0.2) / 0.3), ease((t - rs["start"] - rs["ans"]) / 0.3)))
            draw_table(d, rows, filled, sc["item"] - 1, top=990)

        draw_captions(d, sc, t, sc["theme"])
        d.rectangle((0, 0, int(W * t / total), 8), fill=MAGENTA if sc["theme"] != "magenta" else (255, 255, 255))
        if n == int(1.2 * FPS):
            frame.save(out_path.with_suffix(".jpg"), quality=90)
        ff.stdin.write(frame.tobytes())
    ff.stdin.close()
    if ff.wait() != 0:
        raise RuntimeError("ffmpeg failed")
    return out_path
