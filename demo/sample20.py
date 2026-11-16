"""Clip di prova (~19 s): tavola 9 con detriti e impatti + vignetta del salto animata da AI (Wan 2.2, gratis).
Musica Kevin MacLeod (CC-BY), effetti Mixkit."""
import subprocess
from pathlib import Path

import cv2
import numpy as np

import fx_test as fx
import gachi as g

D = Path(__file__).parent
SCR = Path("/tmp/claude-0/-home-user-MangaAnimeted/27c93ac4-f722-5215-875d-c055171a77eb/scratchpad")
W, H, FPS = 1920, 1080, 30

P9 = g.P[9]
shots = [
    ("page", dict(kind="page", page=9, dur=1.6, mood="tense")),
    ("panel", dict(kind="panel", page=9, box=P9[0][0], tag="tense", dur=2.6, idx=0, mood="tense")),
    ("panel", dict(kind="panel", page=9, box=P9[1][0], tag="tense", dur=2.6, idx=1, mood="tense")),
    ("panel", dict(kind="panel", page=9, box=P9[2][0], tag="hit", dur=2.8, idx=2, mood="tense")),
    ("bags", dict(dur=4.6)),
    ("ai", dict(dur=3.5)),
]
t = 0.0
for _, s in shots:
    s["start"] = t; t += s["dur"]
TOTAL = t + 0.6

cap = cv2.VideoCapture(str(SCR / "hf" / "jump_ai.mp4"))
AI = []
while True:
    ok, fr = cap.read()
    if not ok:
        break
    AI.append(cv2.cvtColor(fr, cv2.COLOR_BGR2RGB).astype(np.float32))
AI_FPS = 16
DEB_HIT = fx.Debris(45, W * 0.55, H * 0.45, 7)


def ai_frame(lt):
    k = min(int(lt * AI_FPS), len(AI) - 1)
    k2 = min(k + 1, len(AI) - 1)
    a = lt * AI_FPS - int(lt * AI_FPS)
    f = AI[k] * (1 - a) + AI[k2] * a  # fusione tra fotogrammi: 16 -> 30 fps piu' fluido
    bg = cv2.GaussianBlur(cv2.resize(f, (W, H)), (0, 0), 30) * 0.35
    h = H; w = int(f.shape[1] * H / f.shape[0])
    fg = cv2.resize(f, (w, h), interpolation=cv2.INTER_CUBIC)
    x0 = (W - w) // 2
    bg[:, x0:x0 + w] = fg
    return bg


def render(i, lt):
    kind, s = shots[i]
    if kind == "page":
        return g.render_page(s, lt)
    if kind == "panel":
        img = g.render_panel(s, lt)
        if s["tag"] == "hit":
            img = np.ascontiguousarray(img)
            DEB_HIT.draw(img, lt * 0.8)
            ln = fx.A_lines[int(lt * 15) % 3]
            img = fx.over(img, np.zeros_like(img), ln * 0.35)
        return img
    if kind == "bags":
        return fx.scene_a(lt)
    return ai_frame(lt)


def frame(tt):
    i = next((k for k, (_, s) in enumerate(shots) if s["start"] <= tt < s["start"] + s["dur"]), len(shots) - 1)
    lt = min(tt - shots[i][1]["start"], shots[i][1]["dur"] - 1e-3)
    img = render(i, lt)
    if i > 0 and lt < 0.25 and shots[i][0] in ("panel",) and shots[i][1].get("tag") != "hit":
        prev = render(i - 1, shots[i - 1][1]["dur"] - 1e-3)
        a = lt / 0.25
        img = prev * (1 - a) + img * a
    if tt > TOTAL - 0.8:
        img = img * max(0, (TOTAL - tt) / 0.8)
    img = img * fx.VIG + np.random.default_rng(int(tt * 100)).normal(0, 4, (H, W, 1))
    return np.clip(img, 0, 255).astype(np.uint8)


def audio(out):
    m, s = SCR / "music", SCR / "sfx"
    st = {k: shots[k][1]["start"] for k in range(len(shots))}
    cues = [("2150", st[3], 0.9), ("2047", st[3] + 0.05, 0.7), ("1489", st[4] - 0.3, 0.6), ("1338", st[4], 1.0),
            ("2150", st[4], 0.9), ("2047", st[4] + 0.1, 0.7), ("2052", st[4] + 2.6, 0.8), ("1485", st[4] + 2.5, 0.6),
            ("1491", st[5] - 0.4, 0.9), ("2049", st[5], 0.6)]
    inp = ["-t", str(st[4] + 0.5), "-i", str(m / "Darkest_Child.mp3"),
           "-ss", "4", "-t", str(TOTAL - st[4] + 0.5), "-i", str(m / "Volatile_Reaction.mp3")]
    f = [f"[0:a]volume=0.7,afade=t=in:d=1,afade=t=out:st={st[4]-0.3}:d=0.6[a0]",
         f"[1:a]volume=0.6,adelay={int((st[4]-0.1)*1000)}:all=1,afade=t=out:st={TOTAL-1}:d=1[a1]"]
    for k, (n, at, v) in enumerate(cues, 2):
        inp += ["-i", str(s / f"{n}.mp3")]
        f.append(f"[{k}:a]volume={v},adelay={int(at*1000)}:all=1[s{k}]")
    f.append("[a0][a1]" + "".join(f"[s{k}]" for k in range(2, len(cues) + 2)) +
             f"amix=inputs={len(cues)+2}:normalize=0,alimiter=limit=0.95,atrim=0:{TOTAL}[o]")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *inp, "-filter_complex", ";".join(f), "-map", "[o]",
                    "-ac", "2", "-ar", "44100", str(out)], check=True)


if __name__ == "__main__":
    wav = SCR / "sample20.wav"
    audio(wav)
    out = D / "output" / "prova20_720p.mp4"
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                          "-r", str(FPS), "-i", "-", "-i", str(wav), "-vf", "scale=1280:720", "-c:v", "libx264",
                          "-profile:v", "main", "-crf", "22", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
                          "-shortest", "-movflags", "+faststart", str(out)], stdin=subprocess.PIPE)
    for i in range(int(TOTAL * FPS)):
        p.stdin.write(frame(i / FPS).tobytes())
    p.stdin.close(); p.wait()
    print("scritto", out, f"{TOTAL:.1f}s")
