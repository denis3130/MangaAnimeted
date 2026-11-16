"""Motion manga — capitolo fornito dall'utente (14 tavole in demo/gachi/pages).
Niente voci: solo musica ed effetti sonori. I testi sono gia' nei balloon.
Uso: python3 gachi.py [stills|preview]"""
import math
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

D = Path(__file__).parent
PG = D / "gachi" / "pages"
OUT = D / "output"
W, H, FPS, SR = 1920, 1080, 30, 44100
UP = 2  # le tavole vengono ingrandite 2x (Lanczos + nitidezza) per zoom piu' puliti
FONT_I = "/usr/share/fonts/opentype/inter/Inter-SemiBoldItalic.otf"

# ------------------------------------------------------------------ regia
# vignette (x0,y0,x1,y1) in pixel della tavola originale, nell'ordine di lettura.
# tag: calm | hit | gun | run | title | big ; dur = secondi (default per tag)
P = {
    1: [((109, 177, 1191, 701), "calm", 4.0), ((108, 726, 1192, 1111), "calm", 3.8), ((108, 1135, 1193, 1707), "calm", 4.2)],
    2: [((0, 0, 1290, 921), "title", 6.5)],
    3: [((0, 120, 1225, 670), "calm", 3.2), ((145, 695, 1225, 1062), "calm", 4.0), ((595, 1098, 1225, 1840), "calm", 4.0),
        ((145, 1098, 580, 1330), "calm", 2.4), ((0, 1345, 590, 1842), "calm", 2.8)],
    4: [((65, 0, 1290, 570), "calm", 4.2), ((890, 600, 1290, 975), "calm", 2.4), ((530, 600, 885, 990), "calm", 3.4),
        ((65, 600, 515, 1005), "calm", 2.4), ((65, 990, 1290, 1430), "calm", 3.4), ((65, 1430, 1290, 1842), "truck", 3.4)],
    5: [((550, 0, 1230, 1842), "calm", 4.4), ((0, 130, 525, 540), "calm", 2.6), ((0, 560, 525, 885), "calm", 2.4),
        ((0, 895, 545, 1355), "clank", 2.8), ((0, 1355, 545, 1842), "calm", 2.6)],
    6: [((750, 115, 1145, 630), "tense", 2.8), ((65, 115, 710, 630), "tense", 3.2), ((65, 660, 1290, 1831), "tense", 5.0)],
    7: [((565, 0, 1229, 255), "hit", 1.8), ((500, 265, 1229, 925), "tense", 3.0), ((0, 0, 545, 925), "tense", 3.6),
        ((0, 925, 840, 1833), "tense", 3.6), ((860, 950, 1229, 1833), "tense", 2.4)],
    8: [((790, 115, 1140, 405), "hit", 1.8), ((65, 115, 760, 440), "tense", 2.8), ((65, 440, 1290, 1395), "tense", 5.0),
        ((65, 1400, 1290, 1836), "clank", 3.2)],
    9: [((60, 110, 640, 445), "tense", 2.6), ((60, 450, 640, 880), "tense", 2.6), ((655, 0, 1225, 915), "hit", 2.8),
        ((0, 920, 1225, 1825), "big", 3.6)],
    10: [((0, 0, 1290, 480), "hit", 2.8), ((555, 520, 1290, 980), "run", 2.2), ((65, 560, 635, 1440), "clank", 2.8),
         ((610, 1000, 1290, 1440), "run", 2.2), ((65, 1460, 1290, 1842), "run", 2.8)],
    11: [((735, 110, 1225, 465), "run", 2.0), ((150, 110, 715, 460), "gun", 2.4), ((0, 470, 1225, 1395), "big", 3.6),
         ((145, 1390, 1225, 1842), "hit", 2.4)],
    12: [((640, 0, 1290, 640), "run", 2.4), ((62, 120, 650, 640), "run", 2.2), ((62, 645, 1150, 1215), "gun", 3.4),
         ((850, 1240, 1290, 1842), "hit", 1.8), ((410, 1240, 835, 1842), "hit", 1.6), ((62, 1240, 400, 1842), "hit", 2.0)],
    13: [((580, 0, 1227, 540), "run", 2.6), ((0, 0, 560, 540), "calm", 2.4), ((0, 630, 1227, 1075), "run", 3.4),
         ((0, 1100, 720, 1730), "hit", 2.2), ((740, 1100, 1227, 1730), "tense", 2.8)],
    14: [((62, 0, 1290, 1135), "final", 5.0), ((62, 1145, 1290, 1830), "finalhit", 5.5)],
}
# sezioni musicali per tavola
MOOD = {1: "intro", 2: "title", 3: "intro", 4: "intro", 5: "intro", 6: "tense", 7: "tense", 8: "tense",
        9: "tense", 10: "action", 11: "action", 12: "action", 13: "action", 14: "final"}
OVERVIEW = 1.6  # secondi di "tavola intera" all'inizio di ogni pagina
XF = 0.3

# ------------------------------------------------------------------ timeline
SHOTS = [dict(kind="intro", dur=2.0)]
for n in sorted(P):
    if n != 2:
        SHOTS.append(dict(kind="page", page=n, dur=OVERVIEW, mood=MOOD[n]))
    for k, (box, tag, dur) in enumerate(P[n]):
        SHOTS.append(dict(kind="panel", page=n, box=box, tag=tag, dur=dur, idx=k, mood=MOOD[n]))
SHOTS.append(dict(kind="end", dur=4.0, cut=True))
t = 0.0
for s in SHOTS:
    s["start"] = t
    t += s["dur"]
TOTAL = t

# ------------------------------------------------------------------ immagini
_pages, _bgs = {}, {}


def page(n):
    if n not in _pages:
        im = Image.open(PG / f"{n:02d}.jpg").convert("RGB")
        im = im.resize((im.width * UP, im.height * UP), Image.LANCZOS)
        im = im.filter(ImageFilter.UnsharpMask(radius=2, percent=70, threshold=2))
        _pages[n] = im
    return _pages[n]


def page_bg(n):
    """Sfondo per le vignette piccole: tavola sfocata e scurita."""
    if n not in _bgs:
        im = page(n)
        s = max(W / im.width, H / im.height)
        bg = im.resize((int(im.width * s) + 1, int(im.height * s) + 1), Image.BILINEAR)
        bg = bg.crop(((bg.width - W) // 2, (bg.height - H) // 2, (bg.width - W) // 2 + W, (bg.height - H) // 2 + H))
        bg = bg.filter(ImageFilter.GaussianBlur(28))
        _bgs[n] = np.asarray(bg, np.float32) * 0.35
    return _bgs[n]


def ease(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def lerp(a, b, x):
    return a + (b - a) * x


yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
VIG = (1 - np.clip((np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2) - 0.75) / 0.7, 0, 1) ** 1.5 * 0.5)[..., None]
GRAIN = [np.random.default_rng(i).normal(0, 5, (H // 2, W // 2, 1)).repeat(2, 0).repeat(2, 1).astype(np.float32) for i in range(5)]
SHADOW = None


def shake(lt, t0, dur, amp, seed):
    if not (t0 <= lt < t0 + dur):
        return 0.0, 0.0
    k = (1 - (lt - t0) / dur) ** 2
    r = np.random.default_rng(int(lt * 60) + seed * 7)
    return r.uniform(-amp, amp) * k, r.uniform(-amp, amp) * k


def cam_for(s):
    """Movimento di camera automatico in base a forma della vignetta e tag."""
    x0, y0, x1, y1 = s["box"]
    w, h = x1 - x0, y1 - y0
    tag, k = s["tag"], s["idx"]
    if tag == "title":
        return (0.0, 0.5, 1.0), (1.0, 0.5, 1.12)
    if tag in ("hit", "big", "finalhit"):
        return (0.5, 0.5, 1.0), (0.5, 0.5, 1.18)
    if tag == "run":
        return (0.85, 0.5, 1.12), (0.15, 0.5, 1.12)
    if h / w > 1.0:  # vignetta alta: panoramica dall'alto in basso
        return (0.5, 0.05, 1.0), (0.5, 0.95, 1.06)
    if w / h > 2.0:  # vignetta larga: da destra a sinistra (lettura manga)
        return (0.9, 0.5, 1.05), (0.1, 0.5, 1.05)
    return ((0.5, 0.5, 1.0), (0.5, 0.45, 1.12)) if k % 2 == 0 else ((0.5, 0.45, 1.14), (0.5, 0.5, 1.02))


def render_panel(s, lt):
    im = page(s["page"])
    x0, y0, x1, y1 = [v * UP for v in s["box"]]
    pw, ph = x1 - x0, y1 - y0
    a, b = cam_for(s)
    x = ease(lt / s["dur"]) if s["tag"] not in ("hit", "big", "finalhit") else 1 - (1 - min(lt / s["dur"], 1)) ** 3
    fx, fy, z = [lerp(a[j], b[j], x) for j in range(3)]
    tag = s["tag"]
    ox, oy = 0.0, 0.0
    if tag in ("hit", "finalhit"):
        ox, oy = shake(lt, 0.0, 0.6, 26, s["idx"])
    elif tag == "big":
        ox, oy = shake(lt, 0.0, 1.0, 40, s["idx"])
    elif tag == "gun":
        for g in (0.3, 0.55, 0.8, 1.3, 1.5):
            dx, dy = shake(lt, g, 0.18, 18, int(g * 10))
            ox += dx; oy += dy
    elif tag == "run":
        oy += math.sin(lt * 22) * 4
    elif tag == "truck":
        ox, oy = math.sin(lt * 40) * 2, math.sin(lt * 33) * 2
    cover = max(W / pw, H / ph)
    asp = pw / ph
    full = tag in ("title", "big", "hit", "finalhit", "final") and 1.15 <= asp <= 2.7 and cover * UP <= 2.4
    if ph / pw > 1.55:
        # vignetta molto alta: scorre dall'alto in basso, larga meta' schermo
        arr = page_bg(s["page"]).copy()
        fit = min(W * 0.55 / pw, 1.6 / UP)
        nw, nh = int(pw * fit), int(ph * fit)
        crop = np.asarray(im.crop((x0, y0, x1, y1)).resize((nw, nh), Image.BICUBIC), np.float32)
        top = int((nh - H * 0.92) * x) if nh > H * 0.92 else 0
        px, py = (W - nw) // 2, int(H * 0.04)
        vis = crop[top:top + int(H * 0.92)]
        arr[py:py + vis.shape[0], px:px + nw] = vis
    elif full:
        # vignetta abbastanza grande: riempie lo schermo
        sc = cover * z
        vw, vh = W / sc, H / sc
        cx = x0 + vw / 2 + (pw - vw) * fx if pw > vw else x0 + pw / 2
        cy = y0 + vh / 2 + (ph - vh) * fy if ph > vh else y0 + ph / 2
        box = (cx - vw / 2 + ox / sc, cy - vh / 2 + oy / sc, cx + vw / 2 + ox / sc, cy + vh / 2 + oy / sc)
        arr = np.asarray(im.transform((W, H), Image.EXTENT, box, Image.BICUBIC), np.float32)
    else:
        # vignetta piccola: incorniciata sopra la tavola sfocata (niente sgranatura)
        arr = page_bg(s["page"]).copy()
        fit = min(W * 0.86 / pw, H * 0.86 / ph) * (0.96 + 0.06 * x if tag not in ("hit", "big") else z * 0.95)
        nw, nh = int(pw * fit), int(ph * fit)
        crop = im.crop((x0, y0, x1, y1)).resize((nw, nh), Image.BICUBIC)
        px = int((W - nw) / 2 + ox + (0.5 - fx) * 30)
        py = int((H - nh) / 2 + oy)
        sh = 14
        X0, Y0 = max(px + sh, 0), max(py + sh, 0)
        X1, Y1 = min(px + nw + sh, W), min(py + nh + sh, H)
        arr[Y0:Y1, X0:X1] *= 0.45  # ombra
        X0, Y0, X1, Y1 = max(px, 0), max(py, 0), min(px + nw, W), min(py + nh, H)
        c = np.asarray(crop, np.float32)
        arr[Y0:Y1, X0:X1] = c[Y0 - py:Y1 - py, X0 - px:X1 - px]
    # flash d'impatto
    if tag in ("hit", "big", "finalhit") and lt < 0.12:
        arr = arr + 200 * (1 - lt / 0.12)
    if tag == "gun":
        for g in (0.3, 0.55, 0.8, 1.3, 1.5):
            if g <= lt < g + 0.06:
                arr = arr * 0.6 + 140
    if tag == "title" and lt < 0.15:
        arr = arr * 0 + 255 * (1 - lt / 0.15) + arr * (lt / 0.15)
    return arr


def render_page(s, lt):
    """Tavola intera, leggera discesa: da' il contesto prima di entrare nelle vignette."""
    im = page(s["page"])
    arr = page_bg(s["page"]).copy()
    fit = H * 0.94 / im.height * (1.0 + 0.03 * ease(lt / s["dur"]))
    nw, nh = int(im.width * fit), int(im.height * fit)
    pg = np.asarray(im.resize((nw, nh), Image.BILINEAR), np.float32)
    px, py = (W - nw) // 2, (H - nh) // 2
    arr[max(py, 0):max(py, 0) + min(nh, H), px:px + nw] = pg[max(-py, 0):max(-py, 0) + min(nh, H)]
    return arr


def card(lt, dur, lines):
    im = Image.new("RGB", (W, H), (0, 0, 0))
    d = ImageDraw.Draw(im)
    a = ease(lt / 0.6) * (1 - ease((lt - dur + 0.7) / 0.7))
    y = H / 2 - 40 * (len(lines) - 1)
    for txt, size in lines:
        v = int(255 * a)
        d.text((W / 2, y), txt, font=ImageFont.truetype(FONT_I, size), anchor="mm", fill=(v, v, v))
        y += size + 30
    return np.asarray(im, np.float32)


def render(i, lt):
    s = SHOTS[i]
    if s["kind"] == "intro":
        return card(lt, s["dur"], [("Capitolo 1", 70)])
    if s["kind"] == "end":
        return card(lt, s["dur"], [("Continua...", 80)])
    if s["kind"] == "page":
        return render_page(s, lt)
    return render_panel(s, lt)


def frame(t):
    i = next((k for k, s in enumerate(SHOTS) if s["start"] <= t < s["start"] + s["dur"]), len(SHOTS) - 1)
    s = SHOTS[i]
    lt = t - s["start"]
    arr = render(i, lt)
    if i > 0 and lt < XF and not s.get("cut") and s.get("tag") not in ("hit", "big", "finalhit", "title"):
        prev = render(i - 1, SHOTS[i - 1]["dur"] + lt)
        a = ease(lt / XF)
        arr = prev * (1 - a) + arr * a
    arr = arr * VIG + GRAIN[int(t * FPS) % len(GRAIN)]
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


# ------------------------------------------------------------------ audio (sintetizzato, gratis)
rng = np.random.default_rng(1)


def T(x):
    return int(x * SR)


def lp(x, k):
    return np.convolve(x, np.ones(k) / k, mode="same").astype(np.float32)


def env(n, a, r):
    e = np.ones(n, np.float32)
    a, r = int(a * SR), int(r * SR)
    if a: e[:a] = np.linspace(0, 1, a)
    if r: e[-r:] *= np.linspace(1, 0, r)
    return e


def piano(f, dur, decay=1.3):
    tt = np.arange(T(dur)) / SR
    x = sum(np.sin(2 * np.pi * f * h * tt) * (0.55 ** (h - 1)) for h in range(1, 6))
    return (x * np.exp(-tt * decay) * (1 - np.exp(-tt * 300))).astype(np.float32)


def saw_pad(f, dur, det=(0.996, 1.0, 1.004)):
    tt = np.arange(T(dur)) / SR
    x = sum(2 * ((tt * f * d) % 1) - 1 for d in det).astype(np.float32)
    return lp(lp(x, 25), 25)


def kick():
    tt = np.arange(T(0.45)) / SR
    return (np.sin(2 * np.pi * 120 * np.exp(-tt * 18) * tt * 4) * np.exp(-tt * 9)).astype(np.float32)


def snare():
    tt = np.arange(T(0.25)) / SR
    return (rng.standard_normal(len(tt)) * np.exp(-tt * 22) * 0.6 + np.sin(2 * np.pi * 190 * tt) * np.exp(-tt * 30)).astype(np.float32)


def hat():
    tt = np.arange(T(0.06)) / SR
    x = rng.standard_normal(len(tt)).astype(np.float32)
    return (x - lp(x, 4)) * np.exp(-tt * 70).astype(np.float32)


def boom(dur=2.0, f=45):
    tt = np.arange(T(dur)) / SR
    b = np.sin(2 * np.pi * f * tt * np.exp(-tt * 0.8)) * np.exp(-tt * 2.2)
    n = lp(rng.standard_normal(len(tt)).astype(np.float32), 5) * np.exp(-tt * 6)
    return (b + n * 0.7).astype(np.float32)


def gunshot():
    tt = np.arange(T(0.6)) / SR
    crack = rng.standard_normal(len(tt)) * np.exp(-tt * 45)
    body = np.sin(2 * np.pi * 70 * tt) * np.exp(-tt * 14)
    tail = lp(rng.standard_normal(len(tt)).astype(np.float32), 20) * np.exp(-tt * 5) * 0.6
    return (crack + body + tail).astype(np.float32)


def whoosh(dur=0.5):
    n = T(dur)
    x = rng.standard_normal(n).astype(np.float32)
    out = np.zeros(n, np.float32)
    for i, k in enumerate(np.linspace(30, 3, 8).astype(int)):
        seg = slice(i * n // 8, (i + 1) * n // 8)
        out[seg] = lp(x, k)[seg]
    return out * np.hanning(n).astype(np.float32)


def clank():
    tt = np.arange(T(0.7)) / SR
    x = sum(np.sin(2 * np.pi * f * tt) * np.exp(-tt * d) for f, d in ((523, 9), (1187, 12), (1873, 16), (2971, 20)))
    return (x * 0.5 + rng.standard_normal(len(tt)) * np.exp(-tt * 80) * 0.6).astype(np.float32)


def steps(dur, rate=6.5):
    out = np.zeros(T(dur), np.float32)
    k = 0.0
    while k < dur - 0.1:
        st = hat() * 3 + kick()[: T(0.06)] * 0.4
        s0 = T(k); out[s0:s0 + len(st)] += st[: len(out) - s0]
        k += 1 / rate
    return out


def rumble(dur):
    x = lp(lp(rng.standard_normal(T(dur)).astype(np.float32), 60), 60) * 8
    return x * env(len(x), 0.4, 0.6)


def build_audio():
    mix = np.zeros(T(TOTAL) + SR * 3, np.float32)

    def add(sig, at, g=1.0):
        s0 = T(at); e = min(len(mix), s0 + len(sig))
        if e > s0: mix[s0:e] += sig[: e - s0] * g

    # intervalli per mood
    spans = {}
    for s in SHOTS:
        m = s.get("mood")
        if m:
            a, b = spans.get(m, (1e9, 0))
            spans[m] = (min(a, s["start"]), max(b, s["start"] + s["dur"]))
    # --- intro: piano misterioso (Re minore) + pad
    a, b = spans["intro"][0] - 2.0, spans["intro"][1]
    a = max(a, 0)
    notes = [293.7, 349.2, 440, 349.2, 261.6, 329.6, 392, 329.6, 233.1, 293.7, 349.2, 293.7, 220, 277.2, 329.6, 277.2]
    k, tt = 0, a + 0.3
    while tt < b - 1:
        if not (spans["title"][0] - 0.3 <= tt < spans["title"][1] - 0.5):
            add(piano(notes[k % 16], 2.5), tt, 0.08)
            if k % 4 == 0:
                add(piano(notes[k % 16] / 2, 3.5, 0.9), tt, 0.07)
        tt += 0.62; k += 1
    pad = saw_pad(73.4, b - a) * env(T(b - a), 3, 1.5)
    add(pad, a, 0.035)
    # --- title: colpo + accordo epico
    ta, tb = spans["title"]
    add(boom(3.0, 40), ta, 0.9)
    for f in (73.4, 110, 146.8, 174.6, 220, 293.7):
        add(saw_pad(f, tb - ta + 0.5) * env(T(tb - ta + 0.5), 0.05, 2.0), ta, 0.03)
    tt = ta
    while tt < tb - 0.6:
        add(kick(), tt, 0.5); tt += 0.5
    # --- tense: bordone dissonante + battito che accelera
    a, b = spans["tense"]
    n = T(b - a)
    dr = (saw_pad(55, b - a) + 0.6 * saw_pad(58.3, b - a)) * np.linspace(0.3, 1, n).astype(np.float32) * env(n, 2, 0.2)
    add(dr, a, 0.05)
    tt, gap = a, 0.95
    while tt < b - 0.3:
        add(kick(), tt, 0.35); add(kick(), tt + 0.18, 0.2)
        tt += gap; gap = max(0.55, gap * 0.985)
    # --- action: batteria 150 bpm + basso ostinato
    a, b = spans["action"]
    a -= 0.0
    beat = 60 / 150
    tt, k = spans["tense"][1] - 0.0, 0
    bass = [73.4, 73.4, 87.3, 73.4, 65.4, 65.4, 77.8, 82.4]
    while tt < b - 0.2:
        if k % 2 == 0: add(kick(), tt, 0.55)
        if k % 4 == 2: add(snare(), tt, 0.35)
        add(hat(), tt + beat / 2, 0.25); add(hat(), tt, 0.15)
        bn = saw_pad(bass[(k // 2) % 8], beat * 0.95) * env(T(beat * 0.95), 0.005, 0.08)
        add(bn, tt, 0.09)
        if k % 16 == 0:
            add(saw_pad(bass[(k // 2) % 8] * 4, beat * 8) * env(T(beat * 8), 0.3, 1.0), tt, 0.02)
        tt += beat; k += 1
    # --- final: silenzio, poi colpo e accordo cupo che resta
    a, b = spans["final"]
    mix[T(a - 0.2):T(a)] *= np.linspace(1, 0.2, T(a) - T(a - 0.2))
    for f in (73.4, 110, 146.8, 174.6):
        add(piano(f, 6.0, 0.5), a + 0.1, 0.06)
    # effetti per inquadratura
    for s in SHOTS:
        tag, st, du = s.get("tag"), s["start"], s["dur"]
        if tag == "hit":
            add(boom(1.0, 60), st, 0.5); add(whoosh(0.3), st - 0.25, 0.4)
        elif tag == "big":
            add(boom(2.2, 42), st, 0.9); add(whoosh(0.6), st - 0.5, 0.6)
        elif tag == "finalhit":
            add(boom(3.0, 38), st, 0.9)
            for f in (36.7, 55, 73.4):
                add(saw_pad(f, du + 4) * env(T(du + 4), 0.05, 4), st, 0.05)
        elif tag == "gun":
            for g in (0.3, 0.55, 0.8, 1.3, 1.5):
                add(gunshot(), st + g, 0.45)
        elif tag == "run":
            add(steps(du), st, 0.25); add(whoosh(0.45), st + 0.1, 0.35)
        elif tag == "clank":
            for g in (0.3, 0.9, 1.5):
                add(clank(), st + g, 0.12)
        elif tag == "truck":
            add(rumble(du + 0.5), st - 0.2, 0.5)
        elif tag == "title":
            add(whoosh(0.8), st - 0.7, 0.6)
    # fine: silenzio sul nero
    e0 = SHOTS[-1]["start"]
    mix[T(e0) + T(1.5):] *= 0
    mix[T(e0):T(e0) + T(1.5)] *= np.linspace(1, 0, T(1.5))
    mix = mix[: T(TOTAL)]
    mix = np.tanh(mix * 1.3) / np.tanh(1.3)
    mix = mix / np.max(np.abs(mix)) * 0.92
    p = D / "gachi" / "mix.wav"
    with wave.open(str(p), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((mix * 32767).astype(np.int16).tobytes())
    return p


def main(mode):
    print(f"durata {TOTAL:.1f}s, {len(SHOTS)} inquadrature")
    if mode == "stills":
        ims = []
        for s in SHOTS:
            ims.append(frame(s["start"] + s["dur"] * 0.6).resize((384, 216)))
        cols = 10
        sheet = Image.new("RGB", (384 * cols, 216 * ((len(ims) + cols - 1) // cols)))
        for k, im in enumerate(ims):
            sheet.paste(im, ((k % cols) * 384, (k // cols) * 216))
        sheet.save(OUT / "gachi_sheet.png")
        return
    wav = build_audio()
    fps = 10 if mode == "preview" else FPS
    out = OUT / ("gachi_preview.mp4" if mode == "preview" else "gachi_cap1.mp4")
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                          "-r", str(fps), "-i", "-", "-i", str(wav), "-c:v", "libx264", "-preset", "medium", "-crf", "20",
                          "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart",
                          str(out)], stdin=subprocess.PIPE)
    n = int(TOTAL * fps)
    for i in range(n):
        p.stdin.write(frame(i / fps).tobytes())
        if i % 300 == 0:
            print(f"{i}/{n}", flush=True)
    p.stdin.close(); p.wait()
    print("scritto", out)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "")
