"""Genera i passaggi animati (disegni intermedi AI) tra vignette consecutive del capitolo.
Usa Wan 2.2 primo+ultimo fotogramma su Hugging Face (quota gratuita dell'account, token iniettato dal proxy).
Riprende da dove si era fermato; si ferma da solo quando la quota del giorno finisce."""
import shutil
import sys
import time
from pathlib import Path

from gradio_client import Client, handle_file
from PIL import Image

import gachi as g

D = Path(__file__).parent
OUT = D / "gachi" / "inb"
OUT.mkdir(exist_ok=True)
SW, SH = 832, 480  # 16:9 circa
PROMPT = ("black and white manga animation, smooth anime motion between the two panels, characters move naturally, "
          "keep the original ink line art and screentone style")


def panels():
    seq = []
    for n in sorted(g.P):
        for k, (box, tag, dur) in enumerate(g.P[n]):
            seq.append((n, k, box))
    return seq


def still(n, box, path):
    im = Image.open(g.PG / f"{n:02d}.jpg").convert("RGB").crop(box)
    s = max(SW / im.width, SH / im.height)
    im = im.resize((int(im.width * s) + 1, int(im.height * s) + 1), Image.LANCZOS)
    l, t = (im.width - SW) // 2, (im.height - SH) // 2
    im.crop((l, t, l + SW, t + SH)).save(path)


def main():
    seq = panels()
    c = Client("https://multimodalart-wan-2-2-first-last-frame.hf.space",
               headers={"Authorization": "Bearer proxy-injected"}, verbose=False)
    done = 0
    for i in range(len(seq) - 1):
        (n1, k1, b1), (n2, k2, b2) = seq[i], seq[i + 1]
        out = OUT / f"{i:03d}_p{n1}-{k1}_p{n2}-{k2}.mp4"
        if out.exists():
            continue
        a, b = OUT / f"{i:03d}_a.png", OUT / f"{i:03d}_b.png"
        still(n1, b1, a); still(n2, b2, b)
        for attempt in range(2):
            t = time.time()
            try:
                r = c.predict(start_image_pil=handle_file(str(a)), end_image_pil=handle_file(str(b)), prompt=PROMPT,
                              duration_seconds=2.5, api_name="/generate_video")
                v = r[0]["video"] if isinstance(r[0], dict) else r[0]
                shutil.copy(v, out)
                done += 1
                print(f"{out.name} OK {time.time()-t:.0f}s", flush=True)
                break
            except Exception as e:
                msg = repr(e)
                print(f"{out.name} ERR {msg[:160]}", flush=True)
                if "quota" in msg.lower() or "limit" in msg.lower():
                    print(f"QUOTA FINITA dopo {done} nuovi passaggi", flush=True)
                    return
                time.sleep(10)
    print(f"FINITO: {done} nuovi passaggi, totale {len(list(OUT.glob('*.mp4')))}/{len(seq)-1}", flush=True)


if __name__ == "__main__":
    main()
