"""Lettura e controllo dei file di regia (YAML).

Un file di regia descrive un video: da dove prendere tavole, clip AI e audio, e la lista delle
inquadrature (una per vignetta). I valori mancanti vengono dallo stile (stile.yaml) in base al tag.
"""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
STYLE_FILE = Path(__file__).resolve().parent / "stile.yaml"

KINDS = {"panel", "page", "black"}


class RegiaError(ValueError):
    pass


def load_style():
    return yaml.safe_load(STYLE_FILE.read_text())


def _resolve(base, p):
    p = Path(p)
    return p if p.is_absolute() else (base / p).resolve()


def load(path):
    path = Path(path).resolve()
    data = yaml.safe_load(path.read_text())
    style = load_style()
    base = _resolve(path.parent, data.get("base", "."))
    v = dict(style["video"], **data.get("video", {}))
    tags = style["tag"]

    pages = {int(k): _resolve(base, p) for k, p in (data.get("tavole") or {}).items()}
    clips = {k: _resolve(base, p) for k, p in (data.get("clip_ai") or {}).items()}

    shots = []
    t = 0.0
    errs = []
    for i, raw in enumerate(data.get("inquadrature") or []):
        s = dict(raw)
        s.setdefault("tipo", "panel")
        tag = s.setdefault("tag", "calm")
        where = f"inquadratura {i + 1}"
        if s["tipo"] not in KINDS:
            errs.append(f"{where}: tipo '{s['tipo']}' sconosciuto (usa {sorted(KINDS)})")
            continue
        if tag not in tags:
            errs.append(f"{where}: tag '{tag}' non definito in stile.yaml")
            continue
        d = {**tags[tag], **{k: s[k] for k in s if k in tags[tag]}}
        s["dur"] = float(s.get("dur", d["dur"]))
        if s["dur"] < style["regole"]["durata_min"]:
            errs.append(f"{where}: durata {s['dur']}s sotto il minimo di {style['regole']['durata_min']}s")
        s["zoom"] = tuple(s.get("zoom", d["zoom"]))
        s["pan"] = s.get("pan", d.get("pan"))
        s["shake"] = float(s.get("shake", d.get("shake", 0)))
        s["flash"] = bool(s.get("flash", d.get("flash", False)))
        s["entrata"] = s.get("entrata", d.get("entrata", "taglio"))
        if s["tipo"] in ("panel", "page"):
            if int(s.get("tavola", -1)) not in pages:
                errs.append(f"{where}: tavola {s.get('tavola')} non elencata in 'tavole'")
                continue
            s["tavola"] = int(s["tavola"])
        if s["tipo"] == "panel" and len(s.get("box", [])) != 4:
            errs.append(f"{where}: serve 'box: [x0, y0, x1, y1]'")
            continue
        if s.get("clip") and s["clip"] not in clips:
            errs.append(f"{where}: clip '{s['clip']}' non elencata in 'clip_ai'")
        s["idx"] = i
        s["start"] = t
        t += s["dur"]
        shots.append(s)
    if errs:
        raise RegiaError("Errori nella regia " + path.name + ":\n  " + "\n  ".join(errs))

    audio = dict(data.get("audio") or {})
    for k in ("sorgente", "musica"):
        if audio.get(k):
            audio[k] = _resolve(base, audio[k])
    sfx_dir = audio.get("sfx_dir")
    if sfx_dir:
        audio["sfx_dir"] = _resolve(base, sfx_dir)

    return dict(
        name=path.stem, path=path, video=v, style=style, pages=pages, clips=clips, shots=shots,
        total=t, audio=audio, output=_resolve(ROOT, data.get("output", f"demo/output/{path.stem}.mp4")),
    )
