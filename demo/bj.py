"""Motion manga su tavole vere: "Give My Regards to Black Jack" (ブラックジャックによろしく) di Shuho Sato,
opera libera per l'uso secondario per volontà dell'autore (credito obbligatorio: titolo + autore).

Pipeline: ritaglio vignette automatico -> camera virtuale (pan/zoom/rotazione/shake) -> luci ed effetti
-> voci neurali gratuite (edge-tts) -> musica ed effetti sonori sintetizzati -> sottotitoli -> MP4.
Uso:  python3 bj.py [stills|preview]"""
import json
import math
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

from panels import detect

D = Path(__file__).parent
HI = D / "bj" / "hi"
AUD = D / "bj" / "audio"
AUD.mkdir(parents=True, exist_ok=True)
OUT = D / "output"
W, H, FPS, SR = 1920, 1080, 30, 44100
FONT_B = "/usr/share/fonts/opentype/inter/Inter-Bold.otf"
FONT_I = "/usr/share/fonts/opentype/inter/Inter-SemiBoldItalic.otf"
FONT_JP = "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf"
VOICE_ON = False  # niente voci parlanti: solo musica ed effetti
XF = 0.4  # durata dissolvenza incrociata tra le inquadrature

# ------------------------------------------------------------------ voci
NARR, RADIO = "it-IT-DiegoNeural", "it-IT-GiuseppeMultilingualNeural"
VOICES = {
    "n1": (NARR, "-12%", "Questa... è la notte di questo paese.", "narr"),
    "n2": (NARR, "-6%", "Un'indagine sui settantanove ospedali universitari del Giappone rivela che solo due su dieci "
                        "vietano agli specializzandi i turni esterni. E l'ottanta per cento di chi li fa... "
                        "si è trovato a visitare da solo.", "narr"),
    "n3": (NARR, "-6%", "E oltre il novanta per cento di loro... lo fa con la paura di sbagliare.", "narr"),
    "r1": (RADIO, "+4%", "Incidente stradale. Maschio, sui vent'anni. Traumi e contusioni, possibili fratture multiple.", "radio"),
    "r2": (RADIO, "+4%", "Livello trenta. Respiro ventiquattro, polso centoventi.", "radio"),
    "r3": (RADIO, "+10%", "Centrale, fate presto! Siamo pronti a partire!", "shout"),
    "n4": (NARR, "-10%", "E quella notte, in ospedale... di guardia c'era solo lui.", "narr"),
}
FX = {
    "narr": "aresample=44100,highpass=f=70,aecho=0.8:0.5:40|75:0.12|0.08,volume=1.3",
    "radio": "aresample=44100,highpass=f=350,lowpass=f=3200,acompressor=threshold=0.1:ratio=8,"
             "volume=2.2,acrusher=bits=10:mix=0.25",
    "shout": "aresample=44100,highpass=f=250,lowpass=f=4500,acompressor=threshold=0.1:ratio=6,volume=2.0",
}


def read_wav(p):
    with wave.open(str(p)) as w:
        return np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768


def voice(key):
    out = AUD / f"{key}.wav"
    if not out.exists():
        v, rate, text, fx = VOICES[key]
        mp3 = AUD / f"{key}.mp3"
        subprocess.run(["edge-tts", "--voice", v, f"--rate={rate}", "--text", text, "--write-media", str(mp3)],
                       check=True, capture_output=True)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp3), "-af", FX[fx], "-ac", "1", str(out)],
                       check=True)
    return read_wav(out)


VO = {k: voice(k) for k in VOICES}
VLEN = {k: len(v) / SR for k, v in VO.items()}

# ------------------------------------------------------------------ inquadrature
# cam: (fx, fy, zoom, rot°) inizio -> fine; fx/fy = centro normalizzato nella vignetta, zoom 1 = riempie lo schermo
SHOTS = [
    dict(kind="title", dur=4.5),
    dict(page=34, panel=0, dur=4.0 + VLEN["n1"] + VLEN["n2"] + 0.4, cam=[(0.5, 0.0, 1.0, 0), (0.45, 1.0, 1.12, 0)],
         vo=[("n1", 0.8), ("n2", 1.0 + VLEN["n1"] + 1.1)], light=None),
    dict(page=35, panel=0, dur=VLEN["n3"] + 2.6, cam=[(0.5, 0.75, 1.25, -1.5), (0.5, 0.25, 1.05, 0.5)],
         vo=[("n3", 0.6)]),
    dict(page=36, panel=0, dur=5.0, cut=True, cam=[(0.45, 0.62, 1.0, 2), (0.42, 0.66, 1.3, 0)], flash=0.0,
         shake=(0.0, 1.2, 40)),
    dict(page=37, panel=0, dur=4.0, cam=[(0.5, 0.45, 1.15, -3), (0.5, 0.55, 1.4, -1)], shake=(0.0, 0.8, 14)),
    dict(page=38, panel=0, dur=5.2, cam=[(0.5, 0.25, 1.35, -4), (0.5, 0.6, 1.05, 3)],
         light=[(0.5, 0.35), (0.38, 0.55)]),
    dict(page=38, panel=1, dur=VLEN["r1"] + 1.2, cam=[(0.5, 0.15, 1.05, 0), (0.5, 0.75, 1.15, 0)],
         vo=[("r1", 0.4)], light=[(0.45, 0.3)]),
    dict(page=38, panel=2, dur=VLEN["r2"] + 1.0, cam=[(0.5, 0.25, 1.05, 0), (0.5, 0.7, 1.2, 0)], vo=[("r2", 0.3)]),
    dict(page=38, panel=3, dur=VLEN["r3"] + 1.6, cam=[(0.55, 0.45, 1.0, 0), (0.55, 0.55, 1.35, 0)],
         vo=[("r3", 0.3)], shake=(0.3, 2.0, 6)),
    dict(page=39, panel=0, dur=4.0, cam=[(0.5, 0.2, 1.0, 0), (0.5, 0.55, 1.2, 0)], light=[(0.6, 0.62)]),
    dict(page=39, panel=1, dur=VLEN["n4"] + 1.8, cam=[(0.4, 0.4, 1.0, 0), (0.45, 0.45, 1.25, 0)], vo=[("n4", 0.6)]),
    dict(page=39, panel=2, dur=3.6, cam=[(0.15, 0.5, 1.0, 0), (0.85, 0.5, 1.0, 0)], light=[(0.5, 0.45)]),
    dict(page=39, panel=3, dur=3.2, cam=[(0.4, 0.5, 1.0, 0), (0.6, 0.5, 1.1, 0)], ring=True),
    dict(page=39, panel=4, dur=4.4, cam=[(0.45, 0.45, 1.0, 0), (0.3, 0.22, 1.75, 0)], ring=True, end_black=True),
    dict(kind="end", dur=5.0, cut=True),
]
t = 0.0
for s in SHOTS:
    s["start"] = t
    t += s["dur"]
TOTAL = t

# ------------------------------------------------------------------ immagini
_pages, _boxes = {}, {}


def page(n):
    if n not in _pages:
        im = Image.open(HI / f"p{n:03d}-{n:03d}.png").convert("L")
        _pages[n] = im
        _boxes[n] = detect(HI / f"p{n:03d}-{n:03d}.png")
    return _pages[n], _boxes[n]


def ease(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def lerp(a, b, x):
    return a + (b - a) * x


def camera_view(n, panel, fx, fy, z, rot, ox=0.0, oy=0.0):
    im, boxes = page(n)
    x0, y0, x1, y1 = [float(v) for v in boxes[panel]]
    pw, ph = x1 - x0, y1 - y0
    # zoom 1 = "cover": la vignetta riempie lo schermo senza bordi
    s = max(W / pw, H / ph) * z
    vw, vh = W / s, H / s
    # il centro resta dentro la vignetta (niente bordi bianchi)
    cx = x0 + vw / 2 + (pw - vw) * fx if pw > vw else x0 + pw / 2
    cy = y0 + vh / 2 + (ph - vh) * fy if ph > vh else y0 + ph / 2
    cx += ox / s
    cy += oy / s
    a = math.radians(rot)
    ca, sa = math.cos(a), math.sin(a)
    # margine extra quando si ruota, per non mostrare gli angoli
    k = 1.0 + abs(math.sin(a)) * 0.9
    hw, hh = vw / 2 / k, vh / 2 / k

    def P(dx, dy):
        return (cx + dx * ca - dy * sa, cy + dx * sa + dy * ca)

    quad = (*P(-hw, -hh), *P(-hw, hh), *P(hw, hh), *P(hw, -hh))
    return im.transform((W, H), Image.QUAD, quad, Image.BICUBIC, fillcolor=0)


def shake_off(lt, spec, seed):
    if not spec:
        return 0, 0
    t0, dur, amp = spec
    if not (t0 <= lt < t0 + dur):
        return 0, 0
    k = (1 - (lt - t0) / dur) ** 2
    r = np.random.default_rng(int(lt * 60) + seed)
    return r.uniform(-amp, amp) * k, r.uniform(-amp, amp) * k


yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)


def blob(px, py, rad):
    d = ((xx - px) ** 2 + (yy - py) ** 2) / (rad ** 2)
    return np.exp(-d)


VIG = 1 - np.clip((np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2) - 0.7) / 0.8, 0, 1) ** 1.5 * 0.55
GRAIN = [np.random.default_rng(i).normal(0, 7, (H // 2, W // 2)).repeat(2, 0).repeat(2, 1).astype(np.float32)
         for i in range(5)]


def render_shot(i, lt):
    s = SHOTS[i]
    if s.get("kind") == "title":
        return title_card(lt, s["dur"])
    if s.get("kind") == "end":
        return end_card(lt, s["dur"])
    x = ease(lt / s["dur"])
    (a, b) = s["cam"]
    fx, fy, z, rot = [lerp(a[j], b[j], x) for j in range(4)]
    ox, oy = shake_off(lt, s.get("shake"), i)
    if s.get("ring"):  # vibrazione a ogni squillo del telefono
        ph = lt % 1.4
        if ph < 0.8:
            ox += math.sin(lt * 90) * 5
    im = camera_view(s["page"], s["panel"], fx, fy, z, rot, ox, oy)
    arr = np.asarray(im, np.float32)
    if s.get("light"):  # lampeggianti: luce pulsante alternata
        for k, (lx, ly) in enumerate(s["light"]):
            pulse = max(0.0, math.sin((lt * 2 * math.pi * 1.6) + k * math.pi)) ** 3
            arr = arr + blob(lx * W, ly * H, 380) * 120 * pulse
    if "flash" in s and lt < 0.35:
        arr = arr + 255 * (1 - lt / 0.35)
    if s.get("end_black"):
        arr = arr * (1 - ease((lt - (s["dur"] - 0.25)) / 0.25))
    return arr


def title_card(lt, dur):
    im = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(im)
    a = int(255 * ease(lt / 1.0) * (1 - ease((lt - dur + 0.8) / 0.8)))
    d.text((W / 2, H / 2 - 40), "GIVE MY REGARDS TO BLACK JACK", font=ImageFont.truetype(FONT_B, 72), anchor="mm", fill=a)
    d.text((W / 2, H / 2 + 50), "ブラックジャックによろしく　佐藤秀峰", font=ImageFont.truetype(FONT_JP, 46), anchor="mm",
           fill=int(a * 0.75))
    d.text((W / 2, H / 2 + 130), "Capitolo 1 — La notte dello specializzando", font=ImageFont.truetype(FONT_I, 40),
           anchor="mm", fill=int(a * 0.6))
    return np.asarray(im, np.float32)


def end_card(lt, dur):
    im = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(im)
    a = int(255 * ease((lt - 0.4) / 1.0) * (1 - ease((lt - dur + 0.9) / 0.9)))
    d.text((W / 2, H / 2 - 30), "Continua...", font=ImageFont.truetype(FONT_I, 80), anchor="mm", fill=a)
    d.text((W / 2, H / 2 + 70), "Opera originale: ブラックジャックによろしく　佐藤秀峰  (Shuho Sato)",
           font=ImageFont.truetype(FONT_JP, 34), anchor="mm", fill=int(a * 0.6))
    return np.asarray(im, np.float32)


SUBS = []
for s in SHOTS:
    for key, off in s.get("vo", []):
        txt = VOICES[key][2]
        st = s["start"] + off
        SUBS.append((st, st + VLEN[key], txt, VOICES[key][3] != "narr"))


def wrap(text, font, maxw, d):
    words, lines, cur = text.split(), [], ""
    for w_ in words:
        tryl = (cur + " " + w_).strip()
        if d.textlength(tryl, font=font) > maxw and cur:
            lines.append(cur); cur = w_
        else:
            cur = tryl
    lines.append(cur)
    return lines


def subtitles(im, t):
    for st, en, txt, radio in SUBS:
        if st - 0.05 <= t <= en + 0.4:
            d = ImageDraw.Draw(im)
            f = ImageFont.truetype(FONT_I if radio else FONT_B, 46)
            lines = wrap(txt, f, W * 0.78, d)
            y = H - 70 - (len(lines) - 1) * 58
            for ln in lines:
                d.text((W / 2, y), ln, font=f, anchor="mm", fill=(255, 255, 255), stroke_width=5, stroke_fill=(0, 0, 0))
                y += 58
    return im


def frame(t):
    i = next(k for k, s in enumerate(SHOTS) if s["start"] <= t < s["start"] + s["dur"]) if t < TOTAL else len(SHOTS) - 1
    s = SHOTS[i]
    lt = t - s["start"]
    arr = render_shot(i, lt)
    if i > 0 and lt < XF and not s.get("cut") and not SHOTS[i - 1].get("end_black"):
        prev = render_shot(i - 1, SHOTS[i - 1]["dur"] + lt)
        a = ease(lt / XF)
        arr = prev * (1 - a) + arr * a
    arr = arr * VIG + GRAIN[int(t * FPS) % len(GRAIN)]
    rgb = np.clip(arr, 0, 255).astype(np.uint8)
    # tono leggermente freddo (notte)
    im = Image.merge("RGB", [Image.fromarray(np.clip(rgb * c, 0, 255).astype(np.uint8)) for c in (0.94, 0.97, 1.02)])
    return subtitles(im, t)


# ------------------------------------------------------------------ audio
rng = np.random.default_rng(0)


def T(x):
    return int(x * SR)


def lowpass(x, k):
    return np.convolve(x, np.ones(k) / k, mode="same").astype(np.float32)


def env(n, a, r):
    e = np.ones(n, np.float32)
    a, r = int(a * SR), int(r * SR)
    if a: e[:a] = np.linspace(0, 1, a)
    if r: e[-r:] *= np.linspace(1, 0, r)
    return e


def piano(f, dur, vel=1.0):
    n = T(dur)
    tt = np.arange(n) / SR
    x = sum(np.sin(2 * np.pi * f * h * tt) * (0.6 ** (h - 1)) for h in range(1, 6))
    x *= np.exp(-tt * 1.4) * (1 - np.exp(-tt * 400))
    return (x * vel).astype(np.float32)


def build_audio():
    mix = np.zeros(T(TOTAL) + SR * 2, np.float32)

    def add(sig, at, g=1.0):
        s0 = T(at); e = min(len(mix), s0 + len(sig))
        if e > s0: mix[s0:e] += sig[: e - s0] * g

    st = {k: s["start"] for k, s in enumerate(SHOTS)}
    # 1) piano malinconico + bordone notturno: titolo -> pagina 35
    end_mel = st[3]
    chords = [(220, 261.6, 329.6), (174.6, 220, 261.6), (130.8, 196, 261.6), (196, 246.9, 293.7)]  # Am F C G
    tt = 0.3; k = 0
    while tt < end_mel - 1.5:
        ch = chords[(k // 4) % 4]
        add(piano(ch[k % 3] * (2 if k % 4 == 3 else 1), 3.0), tt, 0.09)
        if k % 4 == 0:
            add(piano(ch[0] / 2, 4.0), tt, 0.08)
        tt += 0.75; k += 1
    hum = lowpass(rng.standard_normal(T(end_mel)).astype(np.float32), 120) * env(T(end_mel), 2, 0.6) * 4
    add(hum, 0, 0.12)  # brusio della città
    # 2) schianto: silenzio di colpo, poi impatto
    c = st[3]
    mix[T(c - 0.6):T(c)] *= np.linspace(1, 0, T(c) - T(c - 0.6))
    boom_t = np.arange(T(2.5)) / SR
    boom = np.sin(2 * np.pi * 48 * boom_t * np.exp(-boom_t * 1.5)) * np.exp(-boom_t * 2.5)
    crash = lowpass(rng.standard_normal(T(1.8)).astype(np.float32), 3) * np.exp(-np.arange(T(1.8)) / SR * 4)
    add(boom.astype(np.float32), c, 0.9); add(crash, c, 0.7)
    for _ in range(40):  # vetri
        f = rng.uniform(2500, 7000); d0 = rng.uniform(0.05, 1.2)
        n = T(0.25); tt_ = np.arange(n) / SR
        add((np.sin(2 * np.pi * f * tt_) * np.exp(-tt_ * 25)).astype(np.float32), c + d0, 0.05)
    # 3) acufene dopo l'impatto
    tin = np.sin(2 * np.pi * 3800 * np.arange(T(5)) / SR).astype(np.float32) * env(T(5), 0.6, 3.5)
    add(tin, c + 0.8, 0.025)
    # 4) sirena (bitonale) da pagina 38 fino alla fine di pagina 39 pannello 3, + battito/tensione
    s0, s1 = st[5] - 0.5, st[12]
    n = T(s1 - s0); tt_ = np.arange(n) / SR
    f = np.where((tt_ % 1.3) < 0.65, 960, 770)
    ph = np.cumsum(2 * np.pi * f / SR)
    siren = np.sign(np.sin(ph)) * 0.3 + np.sin(ph) * 0.7
    vol = np.interp(tt_ + s0, [s0, st[5] + 1, st[6], st[9], st[11], st[11] + 2.5, s1],
                    [0, 0.5, 0.25, 0.15, 0.5, 0.8, 0.0])
    siren = lowpass(siren.astype(np.float32), 6) * vol
    add(siren, s0, 0.16)
    # pulsazione cupa crescente
    bt = st[5]
    while bt < st[13] + SHOTS[13]["dur"] - 0.4:
        n = T(0.5); tt_ = np.arange(n) / SR
        add((np.sin(2 * np.pi * 52 * tt_) * np.exp(-tt_ * 9)).astype(np.float32), bt, 0.45)
        bt += 0.9 if bt < st[11] else 0.6 if bt < st[13] else 0.42
    # statico radio sotto le voci radio
    for key in ("r1", "r2"):
        for s in SHOTS:
            for kk, off in s.get("vo", []):
                if kk == key:
                    at = s["start"] + off
                    nz = lowpass(rng.standard_normal(T(VLEN[key] + 0.4)).astype(np.float32), 2)
                    add(nz * env(len(nz), 0.05, 0.1), at - 0.2, 0.025)
                    beep = np.sin(2 * np.pi * 1400 * np.arange(T(0.12)) / SR).astype(np.float32)
                    add(beep, at - 0.25, 0.08); add(beep, at + VLEN[key] + 0.05, 0.08)
    # 5) telefono che squilla (プルルル)
    for k in (12, 13):
        r0 = st[k]
        while r0 < st[k] + SHOTS[k]["dur"] - 0.3:
            n = T(0.8); tt_ = np.arange(n) / SR
            ring = (np.sin(2 * np.pi * 420 * tt_) + np.sin(2 * np.pi * 480 * tt_)) * (np.sin(2 * np.pi * 18 * tt_) > 0)
            add(lowpass(ring.astype(np.float32), 3) * env(n, 0.01, 0.05), r0, 0.13)
            r0 += 1.4
    # 6) finale: silenzio netto sul nero, poi accordo
    e0 = st[14]
    mix[T(e0):T(e0) + T(0.05)] *= np.linspace(1, 0, T(0.05))
    mix[T(e0) + T(0.05):] = 0
    for f in (110, 220, 261.6, 329.6):
        add(piano(f, 4.5, 1.0), e0 + 0.6, 0.09)
    # tappeto di tensione (archi sintetici) dallo schianto al finale, in crescendo
    a0, a1 = st[4], st[14]
    n = T(a1 - a0); tt_ = np.arange(n) / SR
    pad = np.zeros(n, np.float32)
    for f0, g in ((55, 1.0), (82.4, 0.6), (110, 0.5), (116.5, 0.25)):  # cluster cupo con semitono dissonante
        for det in (0.997, 1.0, 1.003):
            f = f0 * det * (1 + 0.06 * (tt_ / tt_[-1]))  # sale lentamente di intonazione
            pad += g * (2 * ((np.cumsum(f) / SR) % 1) - 1).astype(np.float32)
    pad = lowpass(lowpass(pad, 30), 30) * np.linspace(0.15, 1.0, n).astype(np.float32) * env(n, 2.0, 0.05)
    add(pad, a0, 0.05)
    # ostinato di piano grave nella parte dell'ambulanza
    bt = st[6]
    while bt < st[13]:
        add(piano(110, 1.2), bt, 0.07); add(piano(116.5, 1.2), bt + 0.3, 0.05)
        bt += 0.6
    if not VOICE_ON:
        SUBS_ONLY = True
    # voci, con ducking
    for s in (SHOTS if VOICE_ON else []):
        for key, off in s.get("vo", []):
            at = s["start"] + off
            v = VO[key]
            a0, a1 = T(at - 0.15), T(at) + len(v) + T(0.2)
            mix[a0:a1] *= 0.5
            add(v, at, 1.0)
    mix = mix[: T(TOTAL)]
    mix = np.tanh(mix * 1.2) / np.tanh(1.2)
    mix = mix / np.max(np.abs(mix)) * 0.92
    p = AUD / "mix.wav"
    with wave.open(str(p), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((mix * 32767).astype(np.int16).tobytes())
    return p


def render(preview=False):
    wav = build_audio()
    out = OUT / ("bj_preview.mp4" if preview else "blackjack_demo.mp4")
    fps = 10 if preview else FPS
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                          "-r", str(fps), "-i", "-", "-i", str(wav), "-c:v", "libx264", "-preset", "medium", "-crf", "21",
                          "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart",
                          str(out)], stdin=subprocess.PIPE)
    n = int(TOTAL * fps)
    for i in range(n):
        p.stdin.write(frame(i / fps).tobytes())
        if i % 150 == 0:
            print(f"{i}/{n}", flush=True)
    p.stdin.close(); p.wait()
    print("scritto", out, f"{TOTAL:.1f}s")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    print(f"durata totale {TOTAL:.1f}s")
    if mode == "stills":
        for k, s in enumerate(SHOTS):
            for frac in (0.15, 0.85):
                frame(s["start"] + s["dur"] * frac).resize((640, 360)).save(OUT / f"bj_{k:02d}_{int(frac*100)}.png")
    else:
        render(preview=mode == "preview")
