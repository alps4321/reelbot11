"""Chatterbox runner: reads a JSON job list [{text, out, ref, exaggeration, cfg}] and writes wav files."""
import json, sys, time
import torch, torchaudio as ta
from chatterbox.tts import ChatterboxTTS
torch.set_num_threads(2)
jobs = json.load(open(sys.argv[1]))
t = time.time(); model = ChatterboxTTS.from_pretrained(device="cpu"); print("loaded", round(time.time() - t), "s", flush=True)
for j in jobs:
    t = time.time()
    wav = model.generate(j["text"], audio_prompt_path=j.get("ref"), exaggeration=j.get("exaggeration", 0.5), cfg_weight=j.get("cfg", 0.5))
    ta.save(j["out"], wav, model.sr)
    print(j["out"], f"{wav.shape[-1] / model.sr:.1f}s audio in {time.time() - t:.0f}s", flush=True)
