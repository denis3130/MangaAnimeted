"""Ritaglio automatico delle vignette (XY-cut sui bordi bianchi).
Ordine di lettura giapponese: righe dall'alto in basso, nella riga da destra a sinistra."""
import sys
from pathlib import Path
import numpy as np
from PIL import Image


def _bands(profile, thr, min_gap):
    """Intervalli 'pieni' separati da gap bianchi lunghi almeno min_gap."""
    full = profile > thr
    segs, start, gap = [], None, 0
    for i, f in enumerate(full):
        if f:
            if start is None:
                start = i
            gap = 0
            end = i
        elif start is not None:
            gap += 1
            if gap >= min_gap:
                segs.append((start, end + 1)); start = None
    if start is not None:
        segs.append((start, end + 1))
    return segs


def detect(path, min_size=0.12):
    im = Image.open(path).convert("L")
    g = np.asarray(im).astype(np.int16)
    # colore di sfondo stimato dal bordo pagina (bianco, grigio acquerello, ecc.)
    border = np.concatenate([g[:8].ravel(), g[-8:].ravel(), g[:, :8].ravel(), g[:, -8:].ravel()])
    bg = int(np.median(border))
    a = np.abs(g - bg) > (20 if bg > 230 else 45)
    H, W = a.shape
    gap = 2
    out = []

    def cut(x0, y0, x1, y1, depth, horizontal):
        sub = a[y0:y1, x0:x1]
        prof = sub.mean(axis=1 if horizontal else 0)
        segs = _bands(prof, 0.02, gap)
        segs = [s for s in segs if s[1] - s[0] > (H if horizontal else W) * 0.03]
        # unisci segmenti troppo stretti (falsi tagli dentro una vignetta)
        lim = (H if horizontal else W) * 0.14
        merged = []
        for s in segs:
            if merged and (s[1] - s[0] < lim or merged[-1][1] - merged[-1][0] < lim):
                merged[-1] = (merged[-1][0], s[1])
            else:
                merged.append(s)
        segs = merged
        if len(segs) <= 1 and depth > 0:
            # nessun taglio in questa direzione: rifila e termina
            if segs:
                s = segs[0]
                if horizontal: y0, y1 = y0 + s[0], y0 + s[1]
                else: x0, x1 = x0 + s[0], x0 + s[1]
            ys = np.where(a[y0:y1, x0:x1].mean(axis=1) > 0.004)[0]
            xs = np.where(a[y0:y1, x0:x1].mean(axis=0) > 0.004)[0]
            if len(xs) and len(ys):
                out.append((x0 + xs[0], y0 + ys[0], x0 + xs[-1] + 1, y0 + ys[-1] + 1))
            return
        if not segs:
            return
        if not horizontal:
            segs = segs[::-1]  # destra -> sinistra
        for s in segs:
            if horizontal:
                cut(x0, y0 + s[0], x1, y0 + s[1], depth + 1, False)
            else:
                cut(x0 + s[0], y0, x0 + s[1], y1, depth + 1, True)

    cut(0, 0, W, H, 0, True)
    out = [b for b in out if (b[2] - b[0]) > W * min_size and (b[3] - b[1]) > H * 0.05]
    return out


if __name__ == "__main__":
    from PIL import ImageDraw
    for p in sys.argv[1:]:
        boxes = detect(p)
        print(Path(p).name, boxes)
        im = Image.open(p).convert("RGB")
        d = ImageDraw.Draw(im)
        for i, b in enumerate(boxes):
            d.rectangle(b, outline=(255, 0, 0), width=12)
            d.text((b[0] + 30, b[1] + 30), str(i + 1), fill=(255, 0, 0), font_size=150)
        im.thumbnail((700, 1000))
        im.save(Path(p).with_suffix(".boxes.jpg"))
