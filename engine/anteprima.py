"""Anteprima dal vivo nel browser: la regia si vede subito, senza render, e si lasciano note.

    python -m engine anteprima regie/x.yaml [--porta 8765]

- La pagina disegna le inquadrature su canvas con la stessa camera del motore (zoom, pan, scossa, flash, fade).
- Se la regia o lo stile cambiano su disco, la pagina si aggiorna da sola restando allo stesso minuto.
- Le note vanno in regie/<nome>.note.md, una riga per nota: "- [ ] 00:12.3 #4 testo".
"""
import io
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import cv2
import numpy as np

from . import regia as R
from .motore import Film

HTML = Path(__file__).with_name("anteprima.html")
SPRITE_W = 360  # larghezza di un fotogramma di clip AI nello sprite


def fmt(t):
    return f"{int(t // 60):02d}:{t % 60:04.1f}"


class Preview:
    def __init__(self, path):
        self.path = Path(path).resolve()
        self.notes = self.path.with_name(self.path.stem + ".note.md")
        self.lock = threading.Lock()
        self.film = None
        self.error = None
        self.stamp = None
        self.audio = None
        self.sprites = {}
        self.reload()

    def mtime(self):
        return (self.path.stat().st_mtime, R.STYLE_FILE.stat().st_mtime)

    def reload(self):
        stamp = self.mtime()
        try:
            film = Film(self.path)
        except Exception as e:  # regia sbagliata: la pagina mostra l'errore e aspetta la correzione
            self.film, self.error, self.stamp = None, str(e), stamp
            return
        old_audio = self.film.r["audio"] if self.film else None
        self.film, self.error, self.stamp = film, None, stamp
        if old_audio != film.r["audio"] or film.total != getattr(self, "_audio_total", None):
            self.audio = None
        self.sprites = {}

    def check(self):
        with self.lock:
            if self.mtime() != self.stamp:
                self.reload()
            return self.stamp

    # ---------------------------------------------------------------- dati per la pagina
    def data(self):
        f = self.film
        if f is None:
            return {"errore": self.error, "versione": str(self.stamp)}
        shots = []
        for s in f.shots:
            d = {k: s[k] for k in ("idx", "tipo", "tag", "dur", "start", "zoom", "shake", "flash", "entrata")}
            d["nota"] = s.get("nota", "")
            if s["tipo"] in ("panel", "page"):
                d["tavola"] = s["tavola"]
                pg = f.page(s["tavola"])
                d["box"] = list(s["box"]) if s["tipo"] == "panel" else [0, 0, pg.shape[1], pg.shape[0]]
                pw, ph = d["box"][2] - d["box"][0], d["box"][3] - d["box"][1]
                a, b = f.pan_points(s, pw, ph)
                d["pan"] = [list(a), list(b)]
            if s.get("clip"):
                d["clip"] = s["clip"]
                d["clip_n"] = len(self.sprite(s["clip"])[1])
            shots.append(d)
        return {"nome": f.r["name"], "w": f.W, "h": f.H, "fps": f.FPS, "totale": f.total, "regole": f.rule,
                "inquadrature": shots, "versione": str(self.stamp), "sprite_w": SPRITE_W}

    def sprite(self, k):
        """Le clip AI diventano uno sprite JPEG (fotogrammi in fila, gia' andata e ritorno): niente seek video."""
        if k not in self.sprites:
            fr = self.film.clip(k)
            h = round(fr[0].shape[0] * SPRITE_W / fr[0].shape[1])
            row = np.hstack([cv2.resize(x, (SPRITE_W, h), interpolation=cv2.INTER_AREA) for x in fr])
            ok, buf = cv2.imencode(".jpg", cv2.cvtColor(row, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 85])
            self.sprites[k] = (buf.tobytes(), fr)
        return self.sprites[k]

    def page_jpg(self, n):
        ok, buf = cv2.imencode(".jpg", cv2.cvtColor(self.film.page(n), cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 92])
        return buf.tobytes()

    def audio_wav(self):
        if self.audio is None:
            out = Path(self.film.r["output"]).parent / ".spezzoni" / self.film.r["name"] / "anteprima.wav"
            out.parent.mkdir(parents=True, exist_ok=True)
            self.film.audio(out)
            self.audio = out.read_bytes()
            self._audio_total = self.film.total
        return self.audio

    # ---------------------------------------------------------------- note
    def read_notes(self):
        if not self.notes.exists():
            return []
        out = []
        for line in self.notes.read_text().splitlines():
            if line.startswith("- ["):
                out.append(line)
        return out

    def add_note(self, t, text):
        f = self.film
        i = f.index_at(t) if f else -1
        line = f"- [ ] {fmt(t)} #{i + 1} {text.strip()}"
        with self.lock:
            new = not self.notes.exists()
            with self.notes.open("a") as fh:
                if new:
                    fh.write(f"# Note di revisione: {self.path.name}\n\n"
                             "Formato: - [ ] minuto #inquadratura testo. Spunta [x] quando e' corretta.\n\n")
                fh.write(line + "\n")
        return line


def export(path, out=None):
    """Anteprima in un unico file HTML (tavole, clip e audio dentro): si apre ovunque, anche dal telefono.
    Le note restano nel browser; il bottone "Copia note" le copia per incollarle in chat."""
    import base64
    import subprocess
    import tempfile
    pv = Preview(path)
    if pv.error:
        raise SystemExit(pv.error)
    d = pv.data()
    b64 = lambda b, mime: f"data:{mime};base64," + base64.b64encode(b).decode()
    tav = {n: b64(pv.page_jpg(n), "image/jpeg") for n in {s["tavola"] for s in d["inquadrature"] if "tavola" in s}}
    clip = {k: b64(pv.sprite(k)[0], "image/jpeg") for k in {s["clip"] for s in d["inquadrature"] if "clip" in s}}
    with tempfile.TemporaryDirectory() as tmp:
        wav, m4a = Path(tmp) / "a.wav", Path(tmp) / "a.m4a"
        pv.film.audio(wav)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-c:a", "aac", "-b:a", "128k", str(m4a)], check=True)
        audio = b64(m4a.read_bytes(), "audio/mp4")
    emb = json.dumps({"regia": d, "tavole": tav, "clip": clip, "audio": audio})
    html = HTML.read_text().replace("<!--EMBED-->", f"<script>window.EMBED = {emb};</script>")
    out = Path(out or Path(pv.film.r["output"]).with_suffix(".anteprima.html"))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html)
    print(f"scritto {out} ({out.stat().st_size / 1e6:.1f} MB)")
    return out


def serve(path, port=8765, open_host="127.0.0.1"):
    pv = Preview(path)

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def send(self, body, ctype, code=200):
            if isinstance(body, str):
                body = body.encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            p = self.path.split("?")[0]
            try:
                if p == "/":
                    return self.send(HTML.read_text(), "text/html; charset=utf-8")
                if p == "/versione":
                    return self.send(str(pv.check()), "text/plain")
                if p == "/regia.json":
                    pv.check()
                    return self.send(json.dumps(pv.data()), "application/json")
                if p == "/note":
                    return self.send(json.dumps(pv.read_notes()), "application/json")
                if pv.film is None:
                    return self.send("regia con errori", "text/plain", 409)
                if p.startswith("/tavola/"):
                    return self.send(pv.page_jpg(int(p.rsplit("/", 1)[1])), "image/jpeg")
                if p.startswith("/clip/"):
                    return self.send(pv.sprite(p.rsplit("/", 1)[1])[0], "image/jpeg")
                if p == "/audio.wav":
                    return self.send(pv.audio_wav(), "audio/wav")
            except Exception as e:
                return self.send(f"errore: {e}", "text/plain", 500)
            self.send("non trovato", "text/plain", 404)

        def do_POST(self):
            if self.path != "/note":
                return self.send("non trovato", "text/plain", 404)
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            text = str(body.get("testo", "")).strip()
            if not text:
                return self.send("nota vuota", "text/plain", 400)
            line = pv.add_note(float(body.get("t", 0)), text)
            self.send(json.dumps({"ok": True, "riga": line}), "application/json")

    srv = ThreadingHTTPServer((open_host, port), H)
    print(f"anteprima di {pv.path.name} su http://{open_host}:{port}  (note in {pv.notes})")
    if pv.error:
        print(pv.error)
    srv.serve_forever()
