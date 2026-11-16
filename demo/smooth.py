"""Stile "lettura continua": le tavole sono affiancate (da destra a sinistra, come un manga) e la camera
scorre senza stacchi da una vignetta all'altra e da una pagina alla successiva.
Uso: python3 smooth.py 9 10 11   (pagine da includere)"""
import math
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

import gachi as g
from fx_test import Debris

D = Path(__file__).parent
SCR = Path("/tmp/claude-0/-home-user-MangaAnimeted/27c93ac4-f722-5215-875d-c055171a77eb/scratchpad")
W, H, FPS = 1280, 720, 30
UP = 2
GAP = 140
ACTION = {"hit", "big", "gun", "run", "finalhit"}

pages = [int(a) for a in sys.argv[1:]] or [9, 10, 11]

# --- striscia di pagine, da destra a sinistra
imgs = []
for n in pages:
    im = cv2.cvtColor(cv2.imread(str(g.PG / f"{n:02d}.jpg")), cv2.COLOR_BGR2RGB)
    im = cv2.resize(im, (im.shape[1] * UP, im.shape[0] * UP), interpolation=cv2.INTER_LANCZOS4)
    blur = cv2.GaussianBlur(im, (0, 0), 1.2)
    im = cv2.addWeighted(im, 1.5, blur, -0.5, 0)
    imgs.append(im)
PH = max(i.shape[0] for i in imgs)
SW = sum(i.shape[1] for i in imgs) + GAP * (len(imgs) + 1)
strip = np.full((PH + 2 * GAP, SW, 3), 18, np.uint8)
offs = {}
x = SW - GAP
for n, im in zip(pages, imgs):
    x -= im.shape[1]
    strip[GAP:GAP + im.shape[0], x:x + im.shape[1]] = im
    offs[n] = (x, GAP)
    x -= GAP

# --- percorso della camera: un fotogramma-chiave per vignetta
keys = []
for n in pages:
    ox, oy = offs[n]
    for (x0, y0, x1, y1), tag, dur in g.P[n]:
        cx, cy = ox + (x0 + x1) / 2 * UP, oy + (y0 + y1) / 2 * UP
        pw, ph = (x1 - x0) * UP, (y1 - y0) * UP
        w = max(pw, ph * W / H) * 1.1
        keys.append(dict(cx=cx, cy=cy, w=w, tag=tag, hold=dur * 0.85, page=n))
# tempi: ogni vignetta = transizione in ingresso + sosta
t = 0.0
for k, kf in enumerate(keys):
    tr = 0.0 if k == 0 else (0.35 if kf["tag"] in ACTION else 0.8)
    if k > 0 and kf["page"] != keys[k - 1]["page"]:
        tr = 1.1  # cambio pagina: scivolata piu' lunga
    kf["t_in"], kf["t0"] = t, t + tr
    t += tr + kf["hold"]
TOTAL = t + 0.5


def ease(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def cam_at(tt):
    for k, kf in enumerate(keys):
        if tt < kf["t0"]:  # in transizione da k-1 a k
            a = keys[k - 1]
            u = ease((tt - kf["t_in"]) / (kf["t0"] - kf["t_in"]))
            pa = 1 - 0.06  # posizione finale della spinta lenta di a
            wa = a["w"] * pa
            cx = a["cx"] + (kf["cx"] - a["cx"]) * u
            cy = a["cy"] + (kf["cy"] - a["cy"]) * u
            w = math.exp(math.log(wa) + (math.log(kf["w"]) - math.log(wa)) * u)
            if kf["page"] != a["page"]:  # allontanati un po' a meta' del passaggio di pagina
                w *= 1 + 0.35 * math.sin(math.pi * u)
            return cx, cy, w, k, -1.0
        if tt < kf["t0"] + kf["hold"] or k == len(keys) - 1:
            lt = tt - kf["t0"]
            return kf["cx"], kf["cy"], kf["w"] * (1 - 0.06 * ease(lt / kf["hold"])), k, lt
    return keys[-1]["cx"], keys[-1]["cy"], keys[-1]["w"], len(keys) - 1, 0


def view(cx, cy, w):
    s = W / w
    M = np.float32([[s, 0, W / 2 - cx * s], [0, s, H / 2 - cy * s]])
    return cv2.warpAffine(strip, M, (W, H), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_CONSTANT,
                          borderValue=(18, 18, 18)).astype(np.float32)


DEB = {}


def frame(tt):
    cx, cy, w, k, lt = cam_at(tt)
    kf = keys[k]
    tag = kf["tag"]
    if lt < 0:  # transizione: mosso (media di sotto-fotogrammi)
        acc = np.zeros((H, W, 3), np.float32)
        for j in range(4):
            c = cam_at(tt - j / FPS / 4 * (2.5 if tag in ACTION else 1.2))
            acc += view(c[0], c[1], c[2])
        img = acc / 4
    else:
        r = np.random.default_rng(int(tt * 1000))
        amp = {"hit": 18, "big": 26, "finalhit": 20}.get(tag, 0) * max(0, 1 - lt / 0.6) ** 2
        if tag == "gun":
            amp = 10 * max([max(0, 1 - abs(lt - gt) / 0.15) for gt in (0.3, 0.55, 0.8, 1.3, 1.5)])
        cx += r.uniform(-amp, amp) * w / W; cy += r.uniform(-amp, amp) * w / W
        img = view(cx, cy, w)
        if tag in ("hit", "big", "finalhit"):
            if lt < 0.06:
                img = 255 - img
            elif lt < 0.14:
                img = img * 0.4 + 150
            d = DEB.setdefault(k, Debris(40 if tag == "big" else 22, W * 0.5, H * 0.45, k))
            img = np.ascontiguousarray(img)
            d.draw(img, lt * 0.6)
        if tag == "gun":
            for gt in (0.3, 0.55, 0.8, 1.3, 1.5):
                if gt <= lt < gt + 0.05:
                    img = img * 0.6 + 110
    if tt > TOTAL - 0.6:
        img = img * max(0, (TOTAL - tt) / 0.6)
    return np.clip(img, 0, 255).astype(np.uint8)


def audio(out):
    m, s = SCR / "music", SCR / "sfx"
    first_action = next((kf["t0"] for kf in keys if kf["tag"] in ("hit", "big")), TOTAL / 3)
    cues = []
    for kf in keys:
        if kf["tag"] == "big":
            cues += [("1338", kf["t0"], 1.0), ("2150", kf["t0"], 0.9)]
        elif kf["tag"] == "hit":
            cues += [("2150", kf["t0"], 0.8), ("2047", kf["t0"] + 0.03, 0.6)]
        elif kf["tag"] == "gun":
            cues += [("1659", kf["t0"] + gt, 0.7) for gt in (0.3, 0.55, 0.8, 1.3, 1.5)]
        elif kf["tag"] == "run":
            cues += [("1485", kf["t_in"], 0.5)]
        if kf["t0"] - kf["t_in"] >= 1.0:
            cues += [("1491", kf["t_in"], 0.45)]  # fruscio del cambio pagina
    inp = ["-t", str(first_action + 0.5), "-i", str(m / "Darkest_Child.mp3"),
           "-ss", "4", "-t", str(TOTAL - first_action + 0.5), "-i", str(m / "Volatile_Reaction.mp3")]
    f = [f"[0:a]volume=0.7,afade=t=in:d=1,afade=t=out:st={first_action-0.3}:d=0.5[a0]",
         f"[1:a]volume=0.6,adelay={int((first_action-0.1)*1000)}:all=1,afade=t=out:st={TOTAL-1}:d=1[a1]"]
    for i, (n, at, v) in enumerate(cues, 2):
        inp += ["-i", str(s / f"{n}.mp3")]
        f.append(f"[{i}:a]volume={v},adelay={int(at*1000)}:all=1[s{i}]")
    f.append("[a0][a1]" + "".join(f"[s{i}]" for i in range(2, len(cues) + 2)) +
             f"amix=inputs={len(cues)+2}:normalize=0,alimiter=limit=0.95,atrim=0:{TOTAL}[o]")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *inp, "-filter_complex", ";".join(f), "-map", "[o]",
                    "-ac", "2", "-ar", "44100", str(out)], check=True)


if __name__ == "__main__":
    wav = SCR / "smooth.wav"
    audio(wav)
    out = D / "output" / f"smooth_{'-'.join(map(str, pages))}.mp4"
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                          "-r", str(FPS), "-i", "-", "-i", str(wav), "-c:v", "libx264", "-profile:v", "main", "-crf", "22",
                          "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart",
                          str(out)], stdin=subprocess.PIPE)
    for i in range(int(TOTAL * FPS)):
        p.stdin.write(frame(i / FPS).tobytes())
    p.stdin.close(); p.wait()
    print("scritto", out, f"{TOTAL:.1f}s")
