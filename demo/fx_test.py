"""Prova di animazione 2.5D su due vignette d'azione (10 s).
Livelli separati (AI isnet-anime + scontorno manuale), parallasse, oggetti che volano,
mosso, linee cinetiche animate, detriti, impatti. Musica: Kevin MacLeod (CC-BY). SFX: Mixkit."""
import math
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

D = Path(__file__).parent
FX = D / "gachi" / "fx"
SCR = Path("/tmp/claude-0/-home-user-MangaAnimeted/27c93ac4-f722-5215-875d-c055171a77eb/scratchpad")
W, H, FPS = 1920, 1080, 30
rng = np.random.default_rng(3)


def load(p):
    im = cv2.imread(str(p), cv2.IMREAD_COLOR)
    return cv2.cvtColor(im, cv2.COLOR_BGR2RGB).astype(np.float32)


def ease_out(x):
    x = min(max(x, 0), 1)
    return 1 - (1 - x) ** 3


def ease(x):
    x = min(max(x, 0), 1)
    return x * x * (3 - 2 * x)


def affine(cx, cy, s, rot, tx, ty):
    """Matrice: scala/ruota attorno a (cx,cy), poi trasla."""
    M = cv2.getRotationMatrix2D((cx, cy), rot, s)
    M[0, 2] += tx; M[1, 2] += ty
    return M


def compose(A, B):  # A dopo B
    A3 = np.vstack([A, [0, 0, 1]]); B3 = np.vstack([B, [0, 0, 1]])
    return (A3 @ B3)[:2]


def warp(img, M, border=cv2.BORDER_REPLICATE):
    return cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_CUBIC, borderMode=border)


def over(dst, rgb, a):
    a = a[..., None]
    return dst * (1 - a) + rgb * a


def poly_mask(shape, pts, feather=6):
    m = np.zeros(shape[:2], np.uint8)
    cv2.fillPoly(m, [np.array(pts, np.int32)], 255)
    return cv2.GaussianBlur(m, (0, 0), feather).astype(np.float32) / 255


def radial_lines(cx, cy, n, seed, inner=260, color=0.0):
    """Linee cinetiche radiali (stile manga) come maschera alpha."""
    r = np.random.default_rng(seed)
    m = np.zeros((H, W), np.uint8)
    R = 2400
    for _ in range(n):
        a = r.uniform(0, 2 * math.pi)
        ri = inner * r.uniform(0.9, 2.2)
        hw = r.uniform(0.002, 0.01)
        p = [(cx + math.cos(a) * ri, cy + math.sin(a) * ri),
             (cx + math.cos(a - hw) * R, cy + math.sin(a - hw) * R),
             (cx + math.cos(a + hw) * R, cy + math.sin(a + hw) * R)]
        cv2.fillPoly(m, [np.array(p, np.int32)], 255)
    return m.astype(np.float32) / 255


def dir_lines(angle, n, seed, phase):
    """Linee di velocita' parallele che scorrono nella direzione del movimento."""
    r = np.random.default_rng(seed)
    m = np.zeros((H, W), np.uint8)
    ca, sa = math.cos(angle), math.sin(angle)
    for _ in range(n):
        off = r.uniform(-1400, 1400)
        L = r.uniform(250, 900)
        p0 = r.uniform(-1500, 1500) + phase * r.uniform(1800, 3200)
        p0 = (p0 % 3000) - 1500
        cx, cy = W / 2 + ca * p0 - sa * off, H / 2 + sa * p0 + ca * off
        th = r.uniform(1.5, 6)
        pts = [(cx, cy), (cx - ca * L - sa * th, cy - sa * L + ca * th), (cx - ca * L + sa * th, cy - sa * L - ca * th)]
        cv2.fillPoly(m, [np.array(pts, np.int32)], 255)
    return m.astype(np.float32) / 255


class Debris:
    """Frammenti di carta/rifiuti che esplodono dal centro, inchiostrati in stile manga."""

    def __init__(self, n, cx, cy, seed):
        r = np.random.default_rng(seed)
        self.p = []
        for _ in range(n):
            a = r.uniform(0, 2 * math.pi)
            sp = r.uniform(500, 1900)
            k = r.integers(3, 7)
            shape = [(math.cos(2 * math.pi * j / k) * r.uniform(0.5, 1), math.sin(2 * math.pi * j / k) * r.uniform(0.5, 1))
                     for j in range(k)]
            self.p.append(dict(x=cx, y=cy, vx=math.cos(a) * sp, vy=math.sin(a) * sp - 300, size=r.uniform(8, 34),
                               rot=r.uniform(0, 6), vr=r.uniform(-12, 12), shape=shape, delay=r.uniform(0, 0.25)))

    def draw(self, img, t):
        for q in self.p:
            tt = t - q["delay"]
            if tt <= 0:
                continue
            x = q["x"] + q["vx"] * tt
            y = q["y"] + q["vy"] * tt + 900 * tt * tt
            s = q["size"] * (1 + tt * 1.5)
            ang = q["rot"] + q["vr"] * tt
            pts = np.array([(x + s * (px * math.cos(ang) - py * math.sin(ang)), y + s * (px * math.sin(ang) + py * math.cos(ang)))
                            for px, py in q["shape"]], np.int32)
            cv2.fillPoly(img, [pts], (250, 250, 250))
            cv2.polylines(img, [pts], True, (10, 10, 10), 3, cv2.LINE_AA)


def motion_blur(img, alpha, dx, dy, steps=6):
    """Mosso: media di copie spostate lungo la direzione del movimento."""
    acc_c = np.zeros_like(img); acc_a = np.zeros_like(alpha)
    for i in range(steps):
        f = i / (steps - 1)
        M = np.float32([[1, 0, -dx * f], [0, 1, -dy * f]])
        a = cv2.warpAffine(alpha, M, (W, H))
        c = cv2.warpAffine(img, M, (W, H))
        acc_c += c * a[..., None]; acc_a += a
    a = np.clip(acc_a / steps, 0, 1)
    c = acc_c / np.maximum(acc_a[..., None], 1e-3)
    return c, a


# ============================ SCENA A: i sacchi esplodono ============================
A = load(FX / "A.png")                     # 2450 x 1810 circa
ah, aw = A.shape[:2]
big_bag = poly_mask(A.shape, [(380, 520), (560, 300), (900, 200), (1180, 260), (1330, 470), (1320, 760), (1180, 1020),
                              (900, 1090), (640, 1060), (430, 930), (360, 720)], 10)
m2 = cv2.imread(str(FX / "A_mask_u2net.png"), 0).astype(np.float32) / 255
small_bag = np.where((np.arange(aw)[None, :] > 1650) & (np.arange(ah)[:, None] > 1100), m2, 0)
small_bag = np.clip((small_bag - 0.3) / 0.4, 0, 1)
hero = poly_mask(A.shape, [(1480, 860), (1760, 840), (1980, 900), (2080, 1000), (1900, 1120), (1760, 1240),
                           (1560, 1240), (1470, 1080)], 6)
# sfondo senza i sacchi (ricostruito) — si vede solo quando volano via
hole = ((big_bag > 0.1) | (small_bag > 0.1)).astype(np.uint8) * 255
# dove c'erano i sacchi: nube bianca d'esplosione (stile manga) invece di una ricostruzione sporca
hm = cv2.GaussianBlur(cv2.dilate(hole, np.ones((25, 25), np.uint8)), (0, 0), 25).astype(np.float32)[..., None] / 255
A_bg = A * (1 - hm) + 252 * hm
A_lines = [radial_lines(1150, 520, 220, s, 320) for s in range(3)]
DEB_A = Debris(70, 1150, 520, 1)


def scene_a(t):
    base = max(W / aw, H / ah) * 1.04
    push = ease((t - 1.0) / 3.5)
    cxp, cyp = lerp(aw / 2, 1780, push * 0.7), lerp(ah / 2, 1040, push * 0.7)
    z = base * (1.0 + 0.35 * push)
    cam = affine(cxp, cyp, z, 0, W / 2 - cxp, H / 2 - cyp)
    k = max(0, 1 - t / 0.9) ** 2 + max(0, 1 - abs(t - 2.6) / 0.35) ** 2 * 0.5
    cam[0, 2] += rng.uniform(-40, 40) * k; cam[1, 2] += rng.uniform(-40, 40) * k
    img = warp(A_bg, cam)
    ln = A_lines[int(t * 15) % 3] * (0.55 + 0.25 * math.sin(t * 20))
    img = over(img, np.zeros_like(img), ln * 0.55)
    # personaggio: due fendenti (t=0 e t=2.6) con scatto e mosso
    hs = 0.0
    for t0 in (0.0, 2.6):
        if t >= t0:
            hs = 40 * ease_out((t - t0) / 0.3) * (1 - ease((t - t0 - 0.3) / 0.8)) + hs * 0
    Mh = compose(cam, affine(1780, 1040, 1.0 + 0.03 * math.sin(t * 3), 0, -hs, 0))
    hc, ha = warp(A, Mh), warp(hero, Mh, cv2.BORDER_CONSTANT)
    if t < 0.35 or 2.6 <= t < 2.95:
        hc, ha = motion_blur(hc, ha, -80, 0)
    img = over(img, hc, ha)
    # sacco piccolo: schizza in basso a destra e sparisce
    sb = ease_out((t - 0.1) / 1.0)
    if t < 1.3:
        Ms = compose(cam, affine(1960, 1420, 1 + 1.2 * sb, -35 * sb, 700 * sb, 520 * sb))
        sc, sa = warp(A, Ms), warp(small_bag, Ms, cv2.BORDER_CONSTANT)
        sc, sa = motion_blur(sc, sa, 90 * (1 - sb) + 20, 70 * (1 - sb) + 15)
        img = over(img, sc, sa * (1 - ease((t - 0.9) / 0.4)))
    # sacco grande: esplode verso la camera in alto a sinistra ed esce
    bb = ease_out(t / 0.9)
    if t < 1.1:
        Mb = compose(cam, affine(850, 650, 1 + 1.4 * bb, 22 * bb, -1100 * bb, -650 * bb))
        bc, ba = warp(A, Mb), warp(big_bag, Mb, cv2.BORDER_CONSTANT)
        bc, ba = motion_blur(bc, ba, -140 * (1 - bb) - 30, -80 * (1 - bb) - 15)
        img = over(img, bc, ba * (1 - ease((t - 0.7) / 0.4)))
    DEB_A.draw(img, t * 0.7)
    if t < 0.07 or 2.6 <= t < 2.65:
        img = 255 - img
    elif t < 0.16 or 2.65 <= t < 2.72:
        img = img * 0.4 + 255 * 0.6
    return img


def lerp(a, b, x):
    return a + (b - a) * x


# ============================ SCENA B: il salto ============================
B = load(FX / "B.png")
bh, bw = B.shape[:2]
mb = cv2.imread(str(FX / "B_mask_isnet-anime.png"), 0).astype(np.float32) / 255
mb[:, 1800:] = 0
mb[: 560, 1700:] = 0
mb = np.clip((mb - 0.35) / 0.3, 0, 1)
mb = cv2.GaussianBlur(cv2.dilate(mb, np.ones((5, 5), np.uint8)), (0, 0), 2)
B_bg = cv2.inpaint(np.clip(B, 0, 255).astype(np.uint8), (mb > 0.05).astype(np.uint8) * 255, 9,
                   cv2.INPAINT_TELEA).astype(np.float32)
ANG = math.atan2(-0.45, -1.0)  # direzione del salto: verso sinistra e in alto
DEB_B = Debris(30, 1500, 820, 2)


def wobble(img, alpha, t, amp=5):
    """Ondeggiamento di vestiti/capelli: deformazione a onda piu' forte ai bordi del personaggio."""
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    dx = np.sin(yy / 60 + t * 11) * amp
    dy = np.sin(xx / 75 + t * 9) * amp * 0.6
    return (cv2.remap(img, xx + dx, yy + dy, cv2.INTER_LINEAR), cv2.remap(alpha, xx + dx, yy + dy, cv2.INTER_LINEAR))


def scene_b(t):
    base = max(W / bw, H / bh) * 1.08
    # la camera segue il salto (pan verso sinistra) con leggero zoom
    p = ease(t / 5)
    cam = affine(bw / 2, bh / 2, base * (1.0 + 0.06 * p), 0, W / 2 - bw / 2 + 140 * p, H / 2 - bh / 2 + 50 * p)
    img = warp(B_bg, cam)
    # linee di velocita' che scorrono
    sl = dir_lines(ANG, 90, 5, t * 0.9)
    img = over(img, np.zeros_like(img), sl * 0.55)
    # personaggio: entra con slancio, poi continua a muoversi nel salto (hang time) mentre la camera lo segue
    def pos(tt):
        j = ease_out(tt / 0.8)
        return 220 * (1 - j) - 30 * tt, 100 * (1 - j) - 14 * tt + math.sin(tt * 2.2) * 8, j
    tx, ty, j = pos(t)
    Mc = compose(cam, affine(1000, 900, 1.0 + 0.05 * j + 0.01 * t, -3 * (1 - j) + math.sin(t * 1.7) * 0.8, tx, ty))
    cc, ca = warp(B, Mc), warp(mb, Mc, cv2.BORDER_CONSTANT)
    cc, ca = wobble(cc, ca, t, 3)
    if t < 0.8:
        cc, ca = motion_blur(cc, ca, 260 * (1 - j), 120 * (1 - j), 8)
    for g, alpha in ((0.1, 0.22), (0.2, 0.1)):
        if t < 1.0:
            gx, gy, _ = pos(max(t - g, 0))
            Mg = compose(cam, affine(1000, 900, 1.0, 0, gx, gy))
            img = over(img, warp(B, Mg) * 0.6 + 100, warp(mb, Mg, cv2.BORDER_CONSTANT) * alpha)
    img = over(img, cc, ca)
    DEB_B.draw(img, t * 0.8)
    if t < 0.08:
        img = img * 0.3 + 255 * 0.7
    return img


SCENES = [(0.0, 4.6, scene_a), (4.6, 10.0, scene_b)]
TOTAL = 10.0
yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
VIG = (1 - np.clip((np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2) - 0.8) / 0.7, 0, 1) ** 1.5 * 0.5)[..., None]


def frame(t):
    for a, b, fn in SCENES:
        if a <= t < b:
            img = fn(t - a)
            break
    else:
        img = SCENES[-1][2](SCENES[-1][1] - SCENES[-1][0] - 1e-3)
    img = img * VIG + rng.normal(0, 4, (H, W, 1))
    return np.clip(img, 0, 255).astype(np.uint8)


def audio(out):
    mus = SCR / "music" / "Volatile_Reaction.mp3"
    sfx = SCR / "sfx"
    # (file, istante, volume)
    cues = [("1338", 0.0, 1.0), ("2150", 0.0, 0.9), ("1489", 0.05, 0.6), ("2047", 0.1, 0.7),
            ("2052", 2.6, 0.8), ("1485", 2.5, 0.6), ("1491", 4.2, 0.9), ("2049", 4.6, 0.8), ("1485", 4.75, 0.6)]
    inputs = ["-ss", "4", "-t", str(TOTAL), "-i", str(mus)]
    filt = [f"[0:a]volume=0.55,afade=t=in:d=0.3,afade=t=out:st={TOTAL-0.8}:d=0.8[m]"]
    for k, (f, at, v) in enumerate(cues, 1):
        inputs += ["-i", str(sfx / f"{f}.mp3")]
        filt.append(f"[{k}:a]volume={v},adelay={int(at*1000)}:all=1[s{k}]")
    mix = "[m]" + "".join(f"[s{k}]" for k in range(1, len(cues) + 1))
    filt.append(f"{mix}amix=inputs={len(cues)+1}:normalize=0,alimiter=limit=0.95,atrim=0:{TOTAL}[out]")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", ";".join(filt), "-map", "[out]",
                    "-ac", "2", "-ar", "44100", str(out)], check=True)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "stills":
        from PIL import Image
        ims = [Image.fromarray(frame(t)).resize((640, 360)) for t in (0.05, 0.4, 1.2, 2.7, 4.3, 4.7, 5.3, 6.5, 8.0, 9.8)]
        sheet = Image.new("RGB", (640 * 5, 360 * 2))
        for k, im in enumerate(ims):
            sheet.paste(im, ((k % 5) * 640, (k // 5) * 360))
        sheet.save(SCR / "fx_sheet.png")
    else:
        wav = FX / "fx_audio.wav"
        audio(wav)
        out = D / "output" / "prova_animazione.mp4"
        p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                              "-r", str(FPS), "-i", "-", "-i", str(wav), "-c:v", "libx264", "-preset", "medium", "-crf", "22",
                              "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart",
                              str(out)], stdin=subprocess.PIPE)
        for i in range(int(TOTAL * FPS)):
            p.stdin.write(frame(i / FPS).tobytes())
        p.stdin.close(); p.wait()
        print("scritto", out)
