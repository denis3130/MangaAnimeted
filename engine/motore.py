"""Motore unico motion manga: legge una regia YAML e produce il video.

    python -m engine render  regie/x.yaml            # video completo (a spezzoni, con cache)
    python -m engine provini regie/x.yaml            # foglio provini: un fotogramma per inquadratura
    python -m engine info    regie/x.yaml            # controlla la regia e stampa la scaletta

Ogni fotogramma e' una funzione pura del tempo: frame(t). Per questo il video si puo' renderizzare
a spezzoni e rifare solo quelli cambiati.
"""
import hashlib
import json
import math
import multiprocessing as mp
import os
import subprocess
from pathlib import Path

import cv2
import numpy as np

from . import regia as R

_CODE = hashlib.sha1(Path(__file__).read_bytes()).hexdigest()  # se cambia il motore, la cache si rinnova


def ease(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


class Film:
    def __init__(self, path):
        self.r = R.load(path)
        v, st = self.r["video"], self.r["style"]["regole"]
        self.W, self.H, self.FPS = int(v["w"]), int(v["h"]), int(v["fps"])
        self.rule = st
        self.shots = self.r["shots"]
        self.total = self.r["total"]
        self.starts = np.array([s["start"] for s in self.shots] + [self.total])
        self._pages, self._clips, self._bg = {}, {}, {}
        W, H = self.W, self.H
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        vg = st["vignettatura"]
        d = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
        self.vig = (1 - np.clip((d - vg["raggio"]) / vg["morbidezza"], 0, 1) ** 1.5 * vg["forza"])[..., None]
        self.tint = np.array(st["tinta"], np.float32)

    # ------------------------------------------------------------ sorgenti
    def page(self, n):
        if n not in self._pages:
            p = self.r["pages"][n]
            im = cv2.imread(str(p))
            if im is None:
                raise FileNotFoundError(f"tavola {n} mancante: {p}")
            self._pages[n] = cv2.cvtColor(im, cv2.COLOR_BGR2RGB)
        return self._pages[n]

    def clip(self, k):
        if k not in self._clips:
            p = self.r["clips"][k]
            cap = cv2.VideoCapture(str(p))
            fr = []
            while True:
                ok, f = cap.read()
                if not ok:
                    break
                fr.append(cv2.cvtColor(f, cv2.COLOR_BGR2RGB))
            if not fr:
                raise FileNotFoundError(f"clip AI '{k}' mancante o vuota: {p}")
            self._clips[k] = fr + fr[::-1]  # andata e ritorno: loop senza scatti
        return self._clips[k]

    def source(self, s, lt):
        if s["tipo"] == "black":
            return np.zeros((self.H, self.W, 3), np.uint8)
        pg = self.page(s["tavola"])
        if s["tipo"] == "page":
            return pg
        x0, y0, x1, y1 = s["box"]
        if s.get("clip"):
            fr = self.clip(s["clip"])
            img = fr[int(lt * self.rule["clip_fps"]) % len(fr)]
            return cv2.resize(img, (x1 - x0, y1 - y0), interpolation=cv2.INTER_CUBIC)
        return pg[y0:y1, x0:x1]

    # ------------------------------------------------------------ camera
    def pan_points(self, s, pw, ph):
        p = s["pan"]
        if p == "auto":
            if ph / pw > 1.0:      # vignetta alta: dall'alto in basso
                return (0.5, 0.15), (0.5, 0.85)
            if pw / ph > 2.0:      # vignetta molto larga: da destra a sinistra (lettura manga)
                return (0.8, 0.5), (0.2, 0.5)
            return (0.5, 0.5), (0.5, 0.5)
        if not p:
            return (0.5, 0.5), (0.5, 0.5)
        return tuple(p[0]), tuple(p[1])

    def background(self, s, img):
        """Vignetta sfocata e scura dietro le vignette piccole. Per le vignette ferme si calcola una volta;
        per le clip AI si sfoca a bassa risoluzione (stesso aspetto, ~20 volte piu' veloce)."""
        rule, key = self.rule, s["idx"]
        if not s.get("clip") and key in self._bg:
            return self._bg[key]
        q = 8
        small = cv2.resize(img, (self.W // q, self.H // q), interpolation=cv2.INTER_AREA)
        small = cv2.GaussianBlur(small, (0, 0), rule["sfondo_blur"] / q)
        bg = cv2.resize(small, (self.W, self.H), interpolation=cv2.INTER_LINEAR) * rule["sfondo_luce"]
        if not s.get("clip"):
            self._bg[key] = bg
        return bg

    def shot_frame(self, s, lt):
        W, H, rule = self.W, self.H, self.rule
        img = self.source(s, lt).astype(np.float32)
        ph, pw = img.shape[:2]
        u = ease(lt / s["dur"])
        z = s["zoom"][0] + (s["zoom"][1] - s["zoom"][0]) * u
        mx, my = rule["margine"]
        fit = min(W * mx / pw, H * my / ph)
        if pw / ph > rule["riempi_se_larga"] or s["tipo"] == "black":
            fit = max(W / pw, H / ph)
        sc = fit * z
        (ax, ay), (bx, by) = self.pan_points(s, pw, ph)
        fx, fy = (ax + (bx - ax) * u) * pw, (ay + (by - ay) * u) * ph
        # centra il punto di fuoco, ma senza mostrare oltre il bordo della vignetta quando e' piu' grande dello schermo
        tx, ty = W / 2 - fx * sc, H / 2 - fy * sc
        sw, sh = pw * sc, ph * sc
        tx = min(0, max(W - sw, tx)) if sw > W else (W - sw) / 2
        ty = min(0, max(H - sh, ty)) if sh > H else (H - sh) / 2
        if s["shake"] and lt < 0.6:
            k = (1 - lt / 0.6) ** 2
            rg = np.random.default_rng(int(lt * 60) + s["idx"] * 7)
            tx += rg.uniform(-1, 1) * s["shake"] * k
            ty += rg.uniform(-1, 1) * s["shake"] * k
        M = np.float32([[sc, 0, tx], [0, sc, ty]])
        fg = cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_CUBIC)
        if sw >= W and sh >= H:
            out = fg
        else:
            mask = cv2.warpAffine(np.ones((ph, pw), np.float32), M, (W, H), flags=cv2.INTER_LINEAR)[..., None]
            bg = self.background(s, img)
            out = bg * (1 - mask) + fg * mask
        if s["flash"]:
            if lt < 0.06:
                out = 255 - out
            elif lt < 0.14:
                out = out * 0.4 + 150
        return out

    def index_at(self, t):
        return min(int(np.searchsorted(self.starts, t, side="right") - 1), len(self.shots) - 1)

    def frame(self, t):
        rule = self.rule
        i = self.index_at(t)
        s = self.shots[i]
        lt = t - s["start"]
        img = self.shot_frame(s, lt)
        xf = rule["dissolvenza"]
        if i > 0 and s["entrata"] == "dissolvenza" and lt < xf:
            p = self.shots[i - 1]
            img = img * (lt / xf) + self.shot_frame(p, p["dur"] - 0.01) * (1 - lt / xf)
        if t < rule["fade_inizio"]:
            img = img * (t / rule["fade_inizio"])
        if t > self.total - rule["fade_fine"]:
            img = img * max(0.0, (self.total - t) / rule["fade_fine"])
        img = img * self.vig * self.tint
        if rule["grana"]:
            img = img + np.random.default_rng(int(t * self.FPS)).normal(0, rule["grana"], (self.H, self.W, 1))
        return np.clip(img, 0, 255).astype(np.uint8)

    # ------------------------------------------------------------ audio
    def audio(self, out):
        a, T = self.r["audio"], self.total
        sfx_cfg = self.r["style"]["sfx"]
        inputs, filt, labels = [], [], []
        if a.get("sorgente"):
            a0, a1 = float(a["da"]), float(a["a"])
            inputs += ["-ss", str(a0), "-to", str(a1), "-i", str(a["sorgente"])]
            filt.append(f"[0:a]afade=t=in:d=0.3,apad=pad_dur={max(0, T - (a1 - a0)) + 2},"
                        f"afade=t=out:st={max(0, T - 2.5)}:d=2.5,atrim=0:{T}[m]")
            labels.append("[m]")
        if a.get("musica"):
            n = inputs.count("-i")
            inputs += ["-i", str(a["musica"])]
            vol = min(float(a.get("musica_vol", sfx_cfg["musica_vol"])), 1.0)
            filt.append(f"[{n}:a]volume={vol},afade=t=in:d=1,afade=t=out:st={max(0, T - 1.5)}:d=1.5,atrim=0:{T}[mu]")
            labels.append("[mu]")
        cues = []
        if a.get("sfx_dir"):
            for s in self.shots:
                for c in s.get("sfx", sfx_cfg["per_tag"].get(s["tag"], [])):
                    cues.append((c["file"], s["start"] + float(c.get("at", 0)), min(float(c.get("vol", 0.6)), sfx_cfg["vol_max"])))
        for name, at, vol in cues:
            f = next(iter(sorted(Path(a["sfx_dir"]).glob(name + ".*"))), None)
            if f is None:
                print(f"  avviso: effetto '{name}' non trovato in {a['sfx_dir']}, saltato")
                continue
            k = inputs.count("-i")
            inputs += ["-i", str(f)]
            filt.append(f"[{k}:a]volume={vol},adelay={int(at * 1000)}:all=1[s{k}]")
            labels.append(f"[s{k}]")
        if not labels:
            cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", str(T), str(out)]
        else:
            filt.append("".join(labels) + f"amix=inputs={len(labels)}:normalize=0,alimiter=limit=0.95,"
                        f"apad,atrim=0:{T}[o]")
            cmd = ["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", ";".join(filt),
                   "-map", "[o]", "-ac", "2", "-ar", "44100", str(out)]
        subprocess.run(cmd, check=True)

    # ------------------------------------------------------------ render a spezzoni
    def _chunk_key(self, i):
        """Impronta di cio' che influenza lo spezzone i: l'inquadratura, la precedente (dissolvenza),
        lo stile, e la data delle immagini usate."""
        def sig(s):
            d = {k: v for k, v in s.items() if k != "idx"}
            files = []
            if s.get("tavola") in self.r["pages"]:
                files.append(self.r["pages"][s["tavola"]])
            if s.get("clip"):
                files.append(self.r["clips"][s["clip"]])
            d["_files"] = [(str(f), f.stat().st_mtime if f.exists() else 0) for f in files]
            return d
        parts = [_CODE, sig(self.shots[i]), sig(self.shots[i - 1]) if i else None, self.r["style"], self.r["video"],
                 self.total if (i == len(self.shots) - 1 or self.shots[i]["start"] + self.shots[i]["dur"] > self.total - self.rule["fade_fine"]) else None]
        return hashlib.sha1(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()[:16]

    def write_chunk(self, i, f):
        a, b = self.frame_range(i)
        p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                              "-s", f"{self.W}x{self.H}", "-r", str(self.FPS), "-i", "-", "-c:v", "libx264",
                              "-threads", "1", "-profile:v", "main", "-crf", str(self.r["video"]["crf"]),
                              "-pix_fmt", "yuv420p", str(f) + ".tmp.mp4"], stdin=subprocess.PIPE)
        for k in range(a, b):
            p.stdin.write(self.frame(k / self.FPS).tobytes())
        p.stdin.close()
        if p.wait():
            raise RuntimeError(f"ffmpeg fallito sullo spezzone {i}")
        os.replace(str(f) + ".tmp.mp4", f)  # uno spezzone a meta' (render interrotto) non entra mai in cache

    def frame_range(self, i):
        a = round(self.shots[i]["start"] * self.FPS)
        b = round((self.shots[i]["start"] + self.shots[i]["dur"]) * self.FPS)
        return a, b

    def render(self, out=None, only=None):
        out = Path(out or self.r["output"])
        out.parent.mkdir(parents=True, exist_ok=True)
        cache = out.parent / ".spezzoni" / self.r["name"]
        cache.mkdir(parents=True, exist_ok=True)
        files, todo = [], []
        for i in range(len(self.shots)):
            f = cache / f"{i:03d}_{self._chunk_key(i)}.mp4"
            files.append(f)
            if f.exists() and (only is None or i not in only):
                continue
            for old in cache.glob(f"{i:03d}_*.mp4"):
                old.unlink()
            todo.append((i, str(f)))
        if todo:
            global _FILM
            _FILM = self
            n = max(1, min(len(todo), (os.cpu_count() or 2)))
            with mp.get_context("fork").Pool(n) as pool:
                for i in pool.imap_unordered(_render_chunk, todo):
                    print(f"  spezzone {i + 1}/{len(self.shots)} pronto", flush=True)
        rifatti = len(todo)
        lst = cache / "lista.txt"
        lst.write_text("".join(f"file '{f.name}'\n" for f in files))
        wav = cache / "audio.wav"
        self.audio(wav)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-i", str(wav),
                        "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", str(out)],
                       check=True)
        print(f"scritto {out}  {self.total:.1f}s, {len(self.shots)} inquadrature, spezzoni rifatti: {rifatti}/{len(self.shots)}")
        return out

    def provini(self, out=None, cols=4):
        """Un fotogramma a meta' di ogni inquadratura, con numero e tag: per controllare la regia in un'occhiata."""
        tw, th = 320, 180
        cells = []
        for s in self.shots:
            im = cv2.resize(self.frame(s["start"] + s["dur"] * 0.5), (tw, th), interpolation=cv2.INTER_AREA)
            label = f"{s['idx'] + 1} {s['tag']} {s['dur']:.1f}s" + (f" ai:{s['clip']}" if s.get("clip") else "")
            cv2.rectangle(im, (0, 0), (tw, 22), (0, 0, 0), -1)
            cv2.putText(im, label, (6, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)
            cells.append(im)
        rows = math.ceil(len(cells) / cols)
        sheet = np.full((rows * th, cols * tw, 3), 20, np.uint8)
        for k, im in enumerate(cells):
            r, c = divmod(k, cols)
            sheet[r * th:(r + 1) * th, c * tw:(c + 1) * tw] = im
        out = Path(out or Path(self.r["output"]).with_suffix(".provini.jpg"))
        out.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(out), cv2.cvtColor(sheet, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 88])
        print("scritto", out)
        return out

    def info(self):
        print(f"{self.r['name']}: {self.total:.1f}s, {len(self.shots)} inquadrature, {self.W}x{self.H}@{self.FPS}")
        for s in self.shots:
            where = f"t{s['tavola']} {s.get('box', '')}" if s["tipo"] != "black" else "nero"
            print(f"  {s['idx'] + 1:>3}  {s['start']:6.2f}s  {s['dur']:4.1f}s  {s['tag']:<7} {where}"
                  + (f"  ai:{s['clip']}" if s.get("clip") else "") + (f"  # {s['nota']}" if s.get("nota") else ""))


_FILM = None


def _render_chunk(job):
    i, f = job
    cv2.setNumThreads(1)
    _FILM.write_chunk(i, f)
    return i
