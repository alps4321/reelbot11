"""OmniVoice runner: reads a JSON job list [{text, out, ref, ref_text}] and writes 24 kHz wav files.

Every line is spoken in the voice of the reference clip, so the narrator sounds the same in every reel.
"""
import json
import sys
import time

import soundfile as sf
import torch
from omnivoice import OmniVoice
from omnivoice.models.omnivoice import OmniVoiceGenerationConfig

torch.set_num_threads(max(2, torch.get_num_threads()))
jobs = json.load(open(sys.argv[1]))
t = time.time()
model = OmniVoice.from_pretrained("k2-fsa/OmniVoice", device_map="cpu", dtype=torch.float32)
print("voice model loaded in", round(time.time() - t), "s", flush=True)
for j in jobs:
    t = time.time()
    audio = model.generate(text=j["text"], ref_audio=j["ref"], ref_text=j["ref_text"], speed=j.get("speed"),
                           generation_config=OmniVoiceGenerationConfig(num_step=j.get("steps", 32)))
    sf.write(j["out"], audio[0], 24000)
    print(j["out"].rsplit("/", 1)[-1], f"{len(audio[0]) / 24000:.1f}s audio in {time.time() - t:.0f}s", flush=True)
