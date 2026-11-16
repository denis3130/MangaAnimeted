"""Audio della demo, tutto gratis e offline:
voci con Piper TTS, musica ed effetti sonori sintetizzati con numpy.
Produce audio/mix.wav e audio/lines.json (tempi dei sottotitoli)."""
import json
import subprocess
import wave
from pathlib import Path
import numpy as np

D = Path(__file__).parent
A = D / "audio"
A.mkdir(exist_ok=True)
VOICES = Path("/tmp/claude-0/-home-user-MangaAnimeted/27c93ac4-f722-5215-875d-c055171a77eb/scratchpad/voices")
SR = 44100
TOTAL = 31.0
rng = np.random.default_rng(0)

# (start, voce, testo, effetto)
LINES = [
    (1.2, "it_IT-riccardo-x_low", "La città di Kaien cadde in una sola notte.", "narr"),
    (7.6, "it_IT-paola-medium", "Ti ho trovato... finalmente.", None),
    (15.6, "it_IT-riccardo-x_low", "Piccola umana... sarai la mia cena.", "monster"),
    (19.4, "it_IT-paola-medium", "Questa volta... finisce qui!", None),
]


def read_wav(p):
    with wave.open(str(p)) as w:
        x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
        return x, w.getframerate()


def tts(i, voice, text, fx):
    raw = A / f"line{i}_raw.wav"
    out = A / f"line{i}.wav"
    subprocess.run(["python3", "-m", "piper", "-m", str(VOICES / f"{voice}.onnx"), "-f", str(raw)],
                   input=text.encode(), check=True, capture_output=True)
    af = {
        "narr": "aresample=44100,aecho=0.8:0.6:60:0.15,volume=1.1",
        "monster": "asetrate=16000*0.72,aresample=44100,atempo=1.1,aecho=0.8:0.8:90|160:0.4|0.25,"
                   "lowshelf=g=8:f=150,volume=1.6",
        None: "aresample=44100,volume=1.2",
    }[fx]
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(raw), "-af", af, "-ac", "1", str(out)], check=True)
    x, sr = read_wav(out)
    return x


def t(sec):
    return int(sec * SR)


mix = np.zeros(t(TOTAL) + SR, np.float32)


def add(sig, at, gain=1.0):
    s = t(at)
    e = min(len(mix), s + len(sig))
    mix[s:e] += sig[: e - s] * gain


def env(n, a, r):
    e = np.ones(n, np.float32)
    a, r = int(a * SR), int(r * SR)
    if a: e[:a] = np.linspace(0, 1, a)
    if r: e[-r:] *= np.linspace(1, 0, r)
    return e


def lowpass(x, k):
    return np.convolve(x, np.ones(k) / k, mode="same").astype(np.float32)


def tone(f, dur, kind="saw"):
    tt = np.arange(t(dur)) / SR
    if kind == "sine":
        return np.sin(2 * np.pi * f * tt).astype(np.float32)
    return (2 * ((tt * f) % 1) - 1).astype(np.float32)


# --- musica: drone cupo + pad, tamburi dalla Bestia in poi ---
drone = (tone(55, 23.5) + 0.6 * tone(55 * 1.5, 23.5) + 0.4 * tone(41.2, 23.5, "sine"))
drone = lowpass(drone, 40) * env(len(drone), 2.0, 0.05)
drone *= np.linspace(0.5, 1.0, len(drone))
add(drone, 0, 0.18)
for k, f in enumerate([220, 261.6, 196]):  # pad malinconico
    p = lowpass(tone(f, 11.5) + tone(f * 1.005, 11.5), 60) * env(t(11.5), 2.5, 2.5)
    add(p, 0.5, 0.035)


def drum(dur=0.6, f0=90):
    n = t(dur)
    tt = np.arange(n) / SR
    body = np.sin(2 * np.pi * f0 * np.exp(-tt * 6) * tt * 3) * np.exp(-tt * 7)
    hit = rng.standard_normal(n) * np.exp(-tt * 40) * 0.3
    return (body + hit).astype(np.float32)


bpm_t = 12.0
beat = 60 / 100
while bpm_t < 23.4:
    add(drum(), bpm_t, 0.5)
    if bpm_t > 16:
        add(drum(0.3, 140), bpm_t + beat / 2, 0.3)
    if bpm_t > 19:
        add(drum(0.2, 180), bpm_t + beat / 4, 0.25)
        add(drum(0.2, 180), bpm_t + 3 * beat / 4, 0.25)
    bpm_t += beat
# finale: pad in maggiore dopo il colpo
for f in [130.8, 164.8, 196, 261.6]:
    p = lowpass(tone(f, 6) + tone(f * 1.004, 6), 50) * env(t(6), 1.0, 3)
    add(p, 25.0, 0.04)

# --- effetti sonori ---
rain = lowpass(rng.standard_normal(t(7.2)).astype(np.float32), 6) * env(t(7.2), 0.8, 0.6)
add(rain, 0, 0.12)
for k in range(3):  # tuono lontano
    th = lowpass(rng.standard_normal(t(2.5)).astype(np.float32), 300) * env(t(2.5), 0.05, 2.2)
    add(th * 6, 3.0 + k * 0.08, 0.5)

roar_n = t(3.0)
tt = np.arange(roar_n) / SR
roar = (lowpass(rng.standard_normal(roar_n).astype(np.float32), 25) * 3
        + 0.5 * np.sin(2 * np.pi * (70 - 25 * tt) * tt) * (1 + 0.5 * np.sin(2 * np.pi * 23 * tt)))
roar = (roar * env(roar_n, 0.15, 1.2)).astype(np.float32)
add(roar, 12.7, 0.6)


def whoosh(dur):
    n = t(dur)
    x = rng.standard_normal(n).astype(np.float32)
    out = np.zeros(n, np.float32)
    for i, k in enumerate(np.linspace(40, 3, 8).astype(int)):
        seg = slice(i * n // 8, (i + 1) * n // 8)
        out[seg] = lowpass(x, k)[seg]
    return out * np.hanning(n).astype(np.float32)


add(whoosh(0.9), 18.9, 0.8)
add(whoosh(0.5), 23.1, 1.0)
boom = drum(2.5, 55) * 1.5
add(boom, 23.5, 1.0)
crack = rng.standard_normal(t(0.4)).astype(np.float32) * np.exp(-np.arange(t(0.4)) / SR * 15)
add(crack, 23.5, 0.6)
# silenzio dopo il colpo: ducking della musica
mix[t(23.55):t(25.0)] *= np.linspace(0.6, 1, t(25.0) - t(23.55))

# --- voci ---
timings = []
for i, (start, voice, text, fx) in enumerate(LINES):
    x = tts(i, voice, text, fx)
    mix[t(start):t(start) + len(x)] *= 0.55  # abbassa musica sotto la voce
    add(x, start, 1.0)
    timings.append({"start": start, "end": start + len(x) / SR, "text": text,
                    "who": {"narr": "", "monster": "BESTIA", None: "REN"}[fx]})

mix = mix[: t(TOTAL)]
mix = np.tanh(mix * 1.3) / np.tanh(1.3)
mix = mix / np.max(np.abs(mix)) * 0.9
with wave.open(str(A / "mix.wav"), "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((mix * 32767).astype(np.int16).tobytes())
(A / "lines.json").write_text(json.dumps(timings, ensure_ascii=False, indent=1))
print(json.dumps(timings, ensure_ascii=False, indent=1))
