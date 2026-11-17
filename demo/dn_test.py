"""Prova Death Note, tavole 1-2: vignette (alcune animate con AI) montate sull'audio originale dell'episodio."""
import subprocess
from pathlib import Path

import cv2
import numpy as np

D = Path(__file__).parent / "dn"
W, H, FPS = 1280, 720, 30
SRC = D / "src" / "ep05.mp4"
A0, A1 = 592.9, 621.7          # pezzo di audio usato (continuo, niente tagli nella musica)
TAIL = 6.0                     # vignette finali senza dialogo nell'episodio

# (pagina, box, durata, ai_clip, movimento camera (z0,z1), dissolvenza in entrata)
SHOTS = [
    (1, (681, 6, 1262, 949), 3.3, "f", (1.0, 1.06)),         # padre: "No, non ho intenzione..."
    (1, (136, 572, 662, 949), 1.4, None, (1.04, 1.0)),       # Light "..." ascolta
    (1, (681, 6, 1262, 949), 1.35, "f", (1.12, 1.16)),       # padre: "...di fronte al male"
    (1, (136, 120, 662, 523), 4.85, "md", (1.0, 1.05)),      # "Ma papà..." "Oh, caro..."
    (1, (576, 994, 1258, 1881), 3.2, None, (1.0, 1.08)),     # "Sono fiero di te, papà"
    (1, (136, 994, 566, 1777), 2.6, None, (1.06, 1.0)),      # "E se mai dovesse succederti qualcosa"
    (2, (383, 105, 1167, 945), 6.6, "lt", (1.0, 1.1)),       # "...ti giuro che sarò io stesso..."
    (2, (35, 105, 374, 945), 2.0, None, (1.0, 1.04)),        # reazione del padre
    (2, (34, 975, 1166, 1342), 3.9, None, (1.0, 1.06)),      # "Light... Light..." SLAM
    (2, (534, 1370, 1290, 1845), 4.5, "ry", (1.0, 1.06)),    # Ryuk sulle scale
    (2, (69, 1369, 528, 1845), 4.0, None, (1.0, 1.12)),      # Light "..." nel buio
]
TOTAL = sum(s[2] for s in SHOTS)

pages = {n: cv2.cvtColor(cv2.imread(str(D / "pages" / f"{n:02d}.png")), cv2.COLOR_BGR2RGB) for n in (1, 2)}


def load_clip(k):
    cap = cv2.VideoCapture(str(D / "ai" / f"{k}.mp4"))
    fr = []
    while True:
        ok, f = cap.read()
        if not ok:
            break
        fr.append(cv2.cvtColor(f, cv2.COLOR_BGR2RGB))
    return fr + fr[::-1]  # andata e ritorno: loop senza scatti


CLIPS = {k: load_clip(k) for k in ("f", "md", "lt", "ry")}


def ease(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def panel_img(s, lt):
    pg, (x0, y0, x1, y1), dur, ai, _ = s
    if ai:
        fr = CLIPS[ai]
        img = fr[int(lt * 16) % len(fr)]
        img = cv2.resize(img, (x1 - x0, y1 - y0), interpolation=cv2.INTER_CUBIC)
    else:
        img = pages[pg][y0:y1, x0:x1]
    return img


def render(i, lt):
    s = SHOTS[i]
    img = panel_img(s, lt).astype(np.float32)
    ph, pw = img.shape[:2]
    z = s[4][0] + (s[4][1] - s[4][0]) * ease(lt / s[2])
    # sfondo: la vignetta stessa, sfocata e scura
    bg = cv2.GaussianBlur(cv2.resize(img, (W, H)), (0, 0), 25) * 0.25
    fit = min(W * 0.92 / pw, H * 0.94 / ph)
    if pw / ph > 1.45:  # vignetta larga: riempie lo schermo
        fit = max(W / pw, H / ph)
    sc = fit * z
    M = np.float32([[sc, 0, W / 2 - pw / 2 * sc], [0, sc, H / 2 - ph / 2 * sc]])
    fg = cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_CONSTANT, borderValue=(-1, -1, -1))
    mask = cv2.warpAffine(np.ones((ph, pw), np.float32), M, (W, H), flags=cv2.INTER_LINEAR)[..., None]
    out = bg * (1 - mask) + fg * mask
    return out


starts = np.cumsum([0] + [s[2] for s in SHOTS])
yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
VIG = (1 - np.clip((np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2) - 0.7) / 0.7, 0, 1) ** 1.5 * 0.55)[..., None]
TINT = np.array([0.93, 0.97, 1.0], np.float32)  # tono freddo, come l'anime


def frame(t):
    i = min(int(np.searchsorted(starts, t, side="right") - 1), len(SHOTS) - 1)
    lt = t - starts[i]
    img = render(i, lt)
    if i > 0 and lt < 0.2 and SHOTS[i][0] == SHOTS[i - 1][0] and i in (3, 9):  # dissolvenze morbide solo in pochi punti
        img = img * (lt / 0.2) + render(i - 1, starts[i] - starts[i - 1] - 0.01) * (1 - lt / 0.2)
    if t < 0.6:
        img *= t / 0.6
    if t > TOTAL - 1.2:
        img *= max(0, (TOTAL - t) / 1.2)
    img = img * VIG * TINT + np.random.default_rng(int(t * 30)).normal(0, 3, (H, W, 1))
    return np.clip(img, 0, 255).astype(np.uint8)


def audio(out):
    # audio originale continuo + coda di silenzio ambientale per le ultime vignette
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(A0), "-to", str(A1), "-i", str(SRC),
                    "-af", f"afade=t=in:d=0.3,apad=pad_dur={TOTAL - (A1 - A0) + 2},afade=t=out:st={TOTAL - 2.5}:d=2.5,atrim=0:{TOTAL}",
                    "-ac", "2", "-ar", "44100", str(out)], check=True)


if __name__ == "__main__":
    wav = D / "test_audio.wav"
    audio(wav)
    out = Path(__file__).parent / "output" / "deathnote_prova_tavole1-2.mp4"
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                          "-r", str(FPS), "-i", "-", "-i", str(wav), "-c:v", "libx264", "-profile:v", "main", "-crf", "21",
                          "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart",
                          str(out)], stdin=subprocess.PIPE)
    for k in range(int(TOTAL * FPS)):
        p.stdin.write(frame(k / FPS).tobytes())
    p.stdin.close(); p.wait()
    print("scritto", out, f"{TOTAL:.1f}s (audio {A1 - A0:.1f}s)")
