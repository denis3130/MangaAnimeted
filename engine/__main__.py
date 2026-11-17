import argparse
import sys

from .motore import Film
from .regia import RegiaError


def main():
    ap = argparse.ArgumentParser(prog="python -m engine", description="Motore motion manga")
    ap.add_argument("comando", choices=["render", "provini", "info", "anteprima"])
    ap.add_argument("regia")
    ap.add_argument("-o", "--out")
    ap.add_argument("--rifai", help="numeri delle inquadrature da rifare comunque, es. 3,7")
    ap.add_argument("--porta", type=int, default=8765, help="porta dell'anteprima")
    ap.add_argument("--file", action="store_true", help="anteprima esportata in un unico file HTML")
    a = ap.parse_args()
    if a.comando == "anteprima":
        from .anteprima import export, serve
        return export(a.regia, a.out) if a.file else serve(a.regia, a.porta)
    try:
        f = Film(a.regia)
    except RegiaError as e:
        sys.exit(str(e))
    if a.comando == "info":
        f.info()
    elif a.comando == "provini":
        f.provini(a.out)
    else:
        only = {int(x) - 1 for x in a.rifai.split(",")} if a.rifai else None
        f.render(a.out, only)


main()
