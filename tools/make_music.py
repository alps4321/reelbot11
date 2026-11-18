"""Builds the explainer reels' music bed from scratch (nothing to license): soft lo-fi chords, a plucked
arpeggio, a light kick and shaker at 96 BPM. Run once: python tools/make_music.py"""
import subprocess
import wave
from pathlib import Path

import numpy as np

SR, BPM, BARS = 44100, 96, 16
beat = 60 / BPM
n = int(SR * beat * 4 * BARS)
t = np.arange(n) / SR
out = np.zeros(n)
rng = np.random.default_rng(7)
mid = lambda m: 440 * 2 ** ((m - 69) / 12)
CHORDS = [[53, 57, 60, 64], [52, 55, 59, 62], [50, 53, 57, 60], [48, 52, 55, 59]]   # Fmaj7 Em7 Dm7 Cmaj7


def note(freq, start, dur, amp, kind="keys"):
    a, b = int(start * SR), min(n, int((start + dur + 1.2) * SR))
    tt = np.arange(b - a) / SR
    if kind == "keys":   # warm electric piano: a few harmonics, soft attack, slow decay, light tremolo
        w = np.sin(2 * np.pi * freq * tt) + 0.35 * np.sin(4 * np.pi * freq * tt) + 0.08 * np.sin(6 * np.pi * freq * tt)
        env = (1 - np.exp(-tt * 40)) * np.exp(-tt * 1.1) * (1 + 0.08 * np.sin(2 * np.pi * 5 * tt))
    elif kind == "pluck":
        w = np.sin(2 * np.pi * freq * tt) + 0.2 * np.sin(2 * np.pi * 2 * freq * tt)
        env = np.exp(-tt * 7)
    else:                # sub bass
        w = np.sin(2 * np.pi * freq * tt)
        env = (1 - np.exp(-tt * 30)) * np.exp(-tt * 0.9)
    out[a:b] += amp * w * env


for bar in range(BARS):
    ch = CHORDS[(bar // 2) % 4]
    t0 = bar * 4 * beat
    if bar % 2 == 0:
        for m in ch:
            note(mid(m), t0, 4 * beat * 2, 0.10, "keys")
        note(mid(ch[0] - 12), t0, 4 * beat * 2, 0.22, "bass")
    for k, step in enumerate([0, 1.5, 2, 3, 3.5]):                     # gentle arpeggio
        note(mid(ch[(k + bar) % 4] + 12), t0 + step * beat, 0.4, 0.05, "pluck")
    for b in (0, 2):                                                    # soft kick
        a = int((t0 + b * beat) * SR); tt = np.arange(int(0.25 * SR)) / SR
        out[a:a + len(tt)] += 0.35 * np.sin(2 * np.pi * (55 + 70 * np.exp(-tt * 30)) * tt) * np.exp(-tt * 14)
    for e in range(8):                                                  # shaker on eighths
        a = int((t0 + e * beat / 2) * SR); m = int(0.06 * SR)
        noise = rng.standard_normal(m) * np.exp(-np.arange(m) / SR * 60)
        out[a:a + m] += (0.03 if e % 2 else 0.018) * np.diff(np.concatenate([[0], noise]))

k = int(0.004 * SR); out = np.convolve(out, np.ones(k) / k, mode="same")   # take the edge off
out /= np.max(np.abs(out)) * 1.05
fade = int(1.5 * SR); out[:fade] *= np.linspace(0, 1, fade); out[-fade:] *= np.linspace(1, 0, fade)
dst = Path(__file__).resolve().parent.parent / "assets" / "music" / "explainer"
dst.mkdir(parents=True, exist_ok=True)
with wave.open(str(dst / "bed.wav"), "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((out * 32767).astype(np.int16).tobytes())
subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(dst / "bed.wav"), "-b:a", "128k", str(dst / "bed.mp3")], check=True)
(dst / "bed.wav").unlink()
print("music bed:", dst / "bed.mp3", f"{n / SR:.1f} s")
