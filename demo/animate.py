"""Compositore "motion manga": camera, parallasse, effetti, sottotitoli.
Legge layers/*.png e audio/, scrive output/demo.mp4."""
import json
import math
import subprocess
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops

D = Path(__file__).parent
L = D / "layers"
W, H, FPS = 1920, 1080, 30
TOTAL = 31.0
FONT = "/usr/share/fonts/opentype/inter/Inter-ExtraBold.otf"
FONT_I = "/usr/share/fonts/opentype/inter/Inter-SemiBoldItalic.otf"

_cache = {}


def img(name):
    if name not in _cache:
        _cache[name] = Image.open(L / f"{name}.png").convert("RGBA")
    return _cache[name]


def ease(x):
    x = min(max(x, 0), 1)
    return x * x * (3 - 2 * x)


def lerp(a, b, x):
    return a + (b - a) * x


def view(layer, cx, cy, z, depth, ox=0, oy=0, scale_extra=1.0):
    """Ritaglia il livello per una camera (cx,cy,z) espressa in coordinate della vignetta.
    depth<1 = lontano (si muove meno), >1 = vicino (si muove di piu')."""
    im = img(layer)
    pw, ph = im.size
    base = max(W / pw, H / ph)
    zl = (z ** depth) * scale_extra
    mx, my = pw / 2, ph / 2
    vx = mx + (cx - mx) * depth + ox
    vy = my + (cy - my) * depth + oy
    vw, vh = W / (base * zl), H / (base * zl)
    box = (vx - vw / 2, vy - vh / 2, vx + vw / 2, vy + vh / 2)
    return im.transform((W, H), Image.EXTENT, box, Image.BILINEAR)


def comp(frames):
    out = Image.new("RGBA", (W, H), (255, 255, 255, 255))
    for f in frames:
        out.alpha_composite(f)
    return out


def shake(t, t0, dur, amp, seed=0):
    if not (t0 <= t < t0 + dur):
        return 0, 0
    k = 1 - (t - t0) / dur
    r = np.random.default_rng(int(t * 1000) + seed)
    return r.uniform(-amp, amp) * k, r.uniform(-amp, amp) * k


def rain_layer(t, n=260, slant=0.25):
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    r = np.random.default_rng(42)
    xs, ys, sp, ln = r.uniform(0, W * 1.3, n), r.uniform(0, H, n), r.uniform(1400, 2200, n), r.uniform(30, 90, n)
    for x, y, s, l in zip(xs, ys, sp, ln):
        yy = (y + s * t) % (H + 100) - 50
        xx = x - yy * slant
        d.line([(xx, yy), (xx + l * slant, yy + l)], fill=(255, 255, 255, 170), width=2)
        d.line([(xx + 1, yy), (xx + 1 + l * slant, yy + l)], fill=(0, 0, 0, 60), width=1)
    return im


def pop(layer, t, t0, cx, cy, z, depth):
    """Onomatopea che 'esplode' in scena con overshoot."""
    if t < t0:
        return None
    x = t - t0
    s = 1 + 0.6 * math.exp(-x * 9) * math.cos(x * 30) if x < 1 else 1
    s = 0.2 + 0.8 * min(x / 0.08, 1) if x < 0.08 else s
    return view(layer, cx, cy, z, depth, scale_extra=s)


def fade(im, color, a):
    if a <= 0:
        return im
    ov = Image.new("RGBA", (W, H), color + (int(255 * min(a, 1)),))
    return Image.alpha_composite(im, ov)


# ----------------------------- SCENE -----------------------------
def s1(t):  # 0 - 7: citta' sotto la luna, pioggia
    x = ease(t / 7)
    cx, cy, z = lerp(1100, 1820, x), lerp(820, 860, x), lerp(1.0, 1.9, x)
    fr = [view("p1_bg", cx, cy, z, 0.3), view("p1_far", cx, cy, z, 0.6),
          view("p1_near", cx, cy, z, 1.0), view("p1_ren", cx, cy, z, 1.0)]
    # la sciarpa/silhouette "respira": micro oscillazione
    fr[-1] = view("p1_ren", cx, cy + math.sin(t * 2.2) * 2, z, 1.0)
    im = comp(fr)
    im.alpha_composite(rain_layer(t))
    if 3.0 <= t < 3.25:  # lampo
        im = fade(im, (255, 255, 255), 0.75 * (1 - (t - 3.0) / 0.25))
    return im


def s2(t):  # 7 - 12: occhi
    x = ease(t / 5)
    z = lerp(1.0, 1.28, x)
    cx, cy = 1400, 560 + 10 * x
    hair_dx = math.sin(t * 3.1) * 6
    im = comp([view("p2_bg", cx, cy, z, 0.5),
               view("p2_face", cx, cy, z, 1.0),
               view("p2_hair", cx, cy, z, 1.2, ox=hair_dx)])
    # "blink" d'intensita': lieve flash all'inizio della battuta
    if 0.55 <= t < 0.75:
        im = fade(im, (255, 255, 255), 0.35 * (1 - (t - 0.55) / 0.2))
    return im


def s3(t):  # 12 - 19: la Bestia
    x = ease(t / 7)
    z = lerp(1.0, 1.35, x)
    sx, sy = shake(t, 0.7, 2.6, 26, 1)
    sx2, sy2 = shake(t, 3.6, 2.6, 10, 2)
    cx, cy = 1400 + sx + sx2, 900 + sy + sy2
    bg = f"p3_bg{int(t * 12) % 3}"  # linee cinetiche "vive"
    fr = [view(bg, cx, cy, z, 0.6), view("p3_beast", cx, cy, z, 1.0)]
    eyes = view("p3_eyes", cx, cy, z, 1.0)
    glow = 0.55 + 0.45 * math.sin(t * 6) ** 2
    eyes.putalpha(eyes.getchannel("A").point(lambda a: int(a * glow)))
    fr.append(eyes)
    p = pop("p3_sfx", t, 0.7, cx, cy, z, 1.25)
    if p: fr.append(p)
    im = comp(fr)
    if 0.7 <= t < 0.85:
        im = fade(im, (0, 0, 0), 0.6)
    return im


def s4(t):  # 19 - 23.5: lo scatto
    x = ease(t / 4.5)
    cx, cy, z = lerp(2600, 1500, x), 760, lerp(1.25, 1.45, x)
    bg = f"p4_bg{int(t * 15) % 3}"
    off = (t * 2600) % 900
    sx, sy = shake(t, 0, 4.5, 5, 3)
    fr = [view(bg, cx + off, cy, z, 0.5),
          view("p4_ren", cx + sx, cy + sy + math.sin(t * 18) * 6, z, 1.0),
          view("p4_dust", cx - t * 300, cy, z, 1.4)]
    p = pop("p4_sfx", t, 2.3, cx, cy, z, 1.2)
    if p: fr.append(p)
    return comp(fr)


def s5(t):  # 23.5 - 27: il colpo
    sx, sy = shake(t, 0.12, 1.6, 40, 5)
    z = lerp(1.25, 1.05, ease(t / 3.5))
    cx, cy = 1400 + sx, 800 + sy
    fr = [view("p5_bg", cx, cy, z, 0.6), view("p5_beast", cx, cy, z, 1.0)]
    # il fendente si "srotola" da sinistra a destra
    sl = view("p5_slash", cx, cy, z, 1.0)
    reveal = ease(t / 0.18)
    m = Image.new("L", (W, H), 0)
    ImageDraw.Draw(m).rectangle([0, 0, int(W * reveal), H], fill=255)
    sl.putalpha(ImageChops.multiply(sl.getchannel("A"), m))
    fr.append(sl)
    p = pop("p5_sfx", t, 0.15, cx, cy, z, 1.3)
    if p: fr.append(p)
    im = comp(fr)
    if t < 0.12:  # frame bianco d'impatto + negativo
        im = Image.new("RGBA", (W, H), (255, 255, 255, 255))
    elif t < 0.3:
        im = Image.merge("RGBA", (*ImageChops.invert(im.convert("RGB")).split(), im.getchannel("A")))
    return fade(im, (0, 0, 0), ease((t - 2.9) / 0.6))


def s6(t):  # 27 - 31: finale
    im = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    d = ImageDraw.Draw(im)
    a = int(255 * ease((t - 0.3) / 1.0) * (1 - ease((t - 3.3) / 0.7)))
    f = ImageFont.truetype(FONT_I, 84)
    d.text((W / 2, H / 2), "Continua...", font=f, anchor="mm", fill=(a, a, a, 255))
    return im


SCENES = [(0, 7, s1), (7, 12, s2), (12, 19, s3), (19, 23.5, s4), (23.5, 27, s5), (27, 31, s6)]
LINES = json.loads((D / "audio" / "lines.json").read_text())

# overlay fissi: vignettatura + grana
yy, xx = np.mgrid[0:H, 0:W]
r = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
VIG = Image.fromarray((np.clip((r - 0.65) / 0.75, 0, 1) ** 1.6 * 200).astype(np.uint8))
VIG_RGBA = Image.new("RGBA", (W, H), (0, 0, 0, 0)); VIG_RGBA.putalpha(VIG)
GRAIN = []
g = np.random.default_rng(9)
for _ in range(6):
    n = g.normal(128, 22, (H // 2, W // 2)).clip(0, 255).astype(np.uint8)
    GRAIN.append(Image.fromarray(n).resize((W, H)).convert("RGB"))
PAPER = Image.new("RGB", (W, H), (244, 238, 226))  # carta leggermente calda


def subtitles(im, t):
    for ln in LINES:
        if ln["start"] - 0.1 <= t <= ln["end"] + 0.6:
            d = ImageDraw.Draw(im)
            f = ImageFont.truetype(FONT, 50)
            txt = (ln["who"] + ":  " if ln["who"] else "") + ln["text"]
            d.text((W / 2, H - 110), txt, font=f, anchor="mm", fill="white",
                   stroke_width=6, stroke_fill="black")
    return im


def title(im, t):
    if t > 3.2:
        return im
    a = ease(t / 0.6) * (1 - ease((t - 2.4) / 0.8))
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.text((W / 2, 150), "CAPITOLO 1  —  LA NOTTE DI KAIEN", font=ImageFont.truetype(FONT, 64),
           anchor="mm", fill=(255, 255, 255, int(255 * a)), stroke_width=5, stroke_fill=(0, 0, 0, int(255 * a)))
    return Image.alpha_composite(im, layer)


def frame(t):
    for a, b, fn in SCENES:
        if a <= t < b:
            lt = t - a
            im = fn(lt)
            # dissolvenza in nero tra scene (tranne il taglio secco sul colpo)
            if fn not in (s5, s6):
                im = fade(im, (0, 0, 0), max(1 - lt / 0.25, 0) if a > 0 else 1 - lt / 0.6)
            break
    rgb = im.convert("RGB")
    rgb = ImageChops.multiply(rgb, PAPER)
    rgb = ImageChops.overlay(rgb, GRAIN[int(t * FPS) % len(GRAIN)])
    out = rgb.convert("RGBA")
    out.alpha_composite(VIG_RGBA)
    out = title(out, t)
    out = subtitles(out, t)
    return out.convert("RGB")


def main(preview=False):
    out = D / "output" / ("preview.mp4" if preview else "demo.mp4")
    fps = 10 if preview else FPS
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                          "-s", f"{W}x{H}", "-r", str(fps), "-i", "-", "-i", str(D / "audio" / "mix.wav"),
                          "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
                          "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(out)],
                         stdin=subprocess.PIPE)
    n = int(TOTAL * fps)
    for i in range(n):
        p.stdin.write(frame(i / fps).tobytes())
        if i % 60 == 0:
            print(f"{i}/{n}", flush=True)
    p.stdin.close()
    p.wait()
    print("scritto", out)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "stills":
        for tt in [0.8, 4, 6.8, 9, 13.2, 17, 20, 22.5, 23.7, 25, 28.5]:
            frame(tt).resize((960, 540)).save(D / "output" / f"still_{tt:05.1f}.png")
    else:
        main(preview=len(sys.argv) > 1 and sys.argv[1] == "preview")
