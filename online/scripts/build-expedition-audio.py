"""Render original Capsule charge/blast accents; requires ffmpeg for OGG encoding."""
import math
from pathlib import Path
import random
import struct
import subprocess
import tempfile
import wave

RATE = 48000
output = Path(__file__).resolve().parents[2] / 'viz/dist/assets/audio'
rng = random.Random(20260919)

charge = []
phase = 0.0
noise = 0.0
for i in range(round(1.6 * RATE)):
    t = i / RATE
    u = t / 1.6
    phase += math.tau * (170 + 650 * u * u) / RATE
    noise += .18 * (rng.uniform(-1, 1) - noise)
    tone = math.sin(phase) + .3 * math.sin(phase * 2) + .14 * math.sin(phase * 3)
    pulse = .8 + .2 * math.sin(math.tau * (3 * t + 5 * t * t))
    envelope = min(1, t / .025) * min(1, (1.6 - t) / .035) * (.32 + .68 * u)
    charge.append(envelope * (.28 * tone * pulse + .16 * noise))

blast = []
low = 0.0
body = 0.0
phase = 0.0
for i in range(round(1.8 * RATE)):
    t = i / RATE
    noise = rng.uniform(-1, 1)
    low += .025 * (noise - low)
    body += .24 * (noise - body)
    phase += math.tau * (52 + 95 * math.exp(-t * 15)) / RATE
    attack = min(1, t / .004)
    crack = .6 * noise * math.exp(-t * 48)
    boom = .52 * math.sin(phase) * math.exp(-t * 6)
    debris = (1.5 * low + .6 * body) * math.exp(-t * 3.4)
    blast.append(attack * (crack + boom + debris) * min(1, (1.8 - t) / .12))

with tempfile.TemporaryDirectory(prefix='atlas-expedition-audio-') as directory:
    for name, samples in [('expedition-charge', charge), ('expedition-launch-blast', blast)]:
        # Leave headroom for the existing flight cue and effects compressor.
        scale = .78 / max(abs(value) for value in samples)
        pcm = b''.join(struct.pack('<h', round(value * scale * 32767)) for value in samples)
        wav = Path(directory) / (name + '.wav')
        with wave.open(str(wav), 'wb') as stream:
            stream.setparams((1, 2, RATE, 0, 'NONE', 'not compressed'))
            stream.writeframes(pcm)
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(wav),
                        '-c:a', 'libvorbis', '-q:a', '5', str(output / (name + '.ogg'))], check=True)
        print(name)
