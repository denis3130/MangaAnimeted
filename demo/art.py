"""Genera i livelli (PNG trasparenti) di una tavola manga ORIGINALE di prova.
Ogni vignetta e' divisa in livelli: bg (sfondo), mid, fg (personaggi), fx.
Render: SVG -> Chromium (Playwright) -> PNG.
"""
import math
import random
from pathlib import Path
import json

OUT = Path(__file__).parent / "layers"
OUT.mkdir(exist_ok=True)
random.seed(7)

DEFS = """
<defs>
  <pattern id="dots" width="10" height="10" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
    <circle cx="5" cy="5" r="2.2" fill="#000"/></pattern>
  <pattern id="dotsL" width="10" height="10" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
    <circle cx="5" cy="5" r="1.2" fill="#000"/></pattern>
  <pattern id="dotsW" width="10" height="10" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
    <circle cx="5" cy="5" r="1.6" fill="#fff"/></pattern>
  <pattern id="hatch" width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(-30)">
    <line x1="0" y1="0" x2="0" y2="8" stroke="#000" stroke-width="2"/></pattern>
  <radialGradient id="moonGlow"><stop offset="0" stop-color="#fff" stop-opacity="1"/>
    <stop offset="0.55" stop-color="#fff" stop-opacity="0.9"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient>
  <radialGradient id="eyeGlow"><stop offset="0" stop-color="#fff"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient>
  <linearGradient id="iris" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#000"/>
    <stop offset="0.7" stop-color="#333"/><stop offset="1" stop-color="#888"/></linearGradient>
  <mask id="fadeDown"><rect width="100%" height="100%" fill="url(#fdg)"/></mask>
  <linearGradient id="fdg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff"/><stop offset="1" stop-color="#000"/></linearGradient>
  <filter id="rough"><feTurbulence baseFrequency="0.04" numOctaves="2" seed="3"/>
    <feDisplacementMap in="SourceGraphic" scale="6"/></filter>
</defs>"""


def svg(w, h, body):
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">{DEFS}{body}</svg>'


def radial_lines(w, h, cx, cy, n, inner, color="#000", seed=0, wmax=14):
    r = random.Random(seed)
    out = []
    R = math.hypot(w, h)
    for _ in range(n):
        a = r.uniform(0, 2 * math.pi)
        ri = inner * r.uniform(0.8, 1.6)
        half = r.uniform(0.002, 0.012) * (wmax / 14)
        x1, y1 = cx + math.cos(a) * ri, cy + math.sin(a) * ri
        x2, y2 = cx + math.cos(a - half) * R, cy + math.sin(a - half) * R
        x3, y3 = cx + math.cos(a + half) * R, cy + math.sin(a + half) * R
        out.append(f'<polygon points="{x1:.0f},{y1:.0f} {x2:.0f},{y2:.0f} {x3:.0f},{y3:.0f}" fill="{color}"/>')
    return "".join(out)


def horiz_lines(w, h, n, color="#000", seed=0):
    r = random.Random(seed)
    out = []
    for _ in range(n):
        y = r.uniform(0, h)
        x = r.uniform(-w * 0.2, w)
        L = r.uniform(w * 0.15, w * 0.6)
        t = r.uniform(1.5, 9)
        out.append(f'<polygon points="{x:.0f},{y:.0f} {x+L:.0f},{y-t/2:.0f} {x+L:.0f},{y+t/2:.0f}" fill="{color}"/>')
    return "".join(out)


# ---------- Personaggio originale: "Ren", spadaccina col mantello e la sciarpa ----------
def ren_standing(x, y, s, fill="#000", rim="#fff"):
    """Silhouette in piedi, origine ai piedi."""
    p = f"""
    <g transform="translate({x},{y}) scale({s}) translate(-100,-400)" >
      <!-- sciarpa al vento -->
      <path d="M112,92 C170,70 220,95 290,60 C320,48 350,58 380,40 C350,80 320,85 300,95 C260,120 200,110 120,112 Z" fill="{fill}" stroke="{rim}" stroke-width="3"/>
      <path d="M118,104 C180,110 230,140 300,125 C330,120 350,130 372,118 C350,150 300,155 270,150 C220,145 170,130 118,118Z" fill="{fill}" stroke="{rim}" stroke-width="3"/>
      <!-- spada sulla schiena -->
      <rect x="40" y="10" width="12" height="210" transform="rotate(-28 46 115)" fill="{fill}" stroke="{rim}" stroke-width="3"/>
      <rect x="26" y="70" width="40" height="10" transform="rotate(-28 46 115)" fill="{fill}" stroke="{rim}" stroke-width="3"/>
      <!-- mantello -->
      <path d="M72,96 Q100,84 130,96 L150,200 L168,330 L150,322 L140,338 L122,326 L108,342 L92,326 L76,340 L62,322 L42,334 L56,200 Z" fill="{fill}" stroke="{rim}" stroke-width="3"/>
      <!-- gambe -->
      <path d="M80,330 L86,398 L100,398 L98,330 Z M108,330 L114,398 L128,398 L122,330 Z" fill="{fill}" stroke="{rim}" stroke-width="3"/>
      <!-- testa e capelli -->
      <path d="M70,62 L58,40 L76,46 L72,20 L90,34 L98,8 L110,32 L126,14 L126,40 L144,34 L132,60 L138,78 Q120,100 100,96 Q76,94 68,76 Z" fill="{fill}" stroke="{rim}" stroke-width="3"/>
    </g>"""
    return p


def ren_running(x, y, s, fill="#000", rim="#fff"):
    return f"""
    <g transform="translate({x},{y}) scale({s})">
      <!-- sciarpa dietro -->
      <path d="M-30,-250 C-120,-270 -200,-230 -330,-260 C-380,-270 -430,-250 -470,-262 C-430,-220 -380,-215 -330,-210 C-220,-200 -120,-215 -30,-225Z" fill="{fill}" stroke="{rim}" stroke-width="4"/>
      <!-- mantello che vola -->
      <path d="M-20,-240 C-120,-230 -210,-170 -300,-150 L-260,-130 L-310,-100 L-240,-95 L-280,-60 L-180,-80 C-120,-100 -60,-120 10,-130 Z" fill="{fill}" stroke="{rim}" stroke-width="4"/>
      <!-- busto inclinato -->
      <path d="M-40,-250 Q10,-280 60,-245 L40,-120 Q0,-100 -30,-125 Z" fill="{fill}" stroke="{rim}" stroke-width="4"/>
      <!-- testa -->
      <path d="M30,-300 L10,-330 L36,-322 L40,-356 L60,-330 L80,-352 L84,-322 L110,-326 L96,-300 Q100,-270 76,-258 Q40,-250 30,-275Z" fill="{fill}" stroke="{rim}" stroke-width="4"/>
      <!-- gamba avanti -->
      <path d="M20,-130 L110,-70 L100,0 L80,0 L88,-60 L0,-100Z" fill="{fill}" stroke="{rim}" stroke-width="4"/>
      <!-- gamba dietro -->
      <path d="M-20,-125 L-110,-60 L-190,-70 L-185,-50 L-100,-35 L0,-95Z" fill="{fill}" stroke="{rim}" stroke-width="4"/>
      <!-- braccio e spada tenuta indietro -->
      <path d="M30,-230 L-40,-170 L-60,-180 L10,-245Z" fill="{fill}" stroke="{rim}" stroke-width="4"/>
      <path d="M-50,-175 L-420,-60 L-425,-48 L-40,-160Z" fill="#fff" stroke="#000" stroke-width="4"/>
      <rect x="-70" y="-190" width="14" height="44" transform="rotate(-18 -63 -168)" fill="{fill}" stroke="{rim}" stroke-width="3"/>
    </g>"""


# ---------- Creatura originale: la "Bestia d'ombra" ----------
def beast(cx, cy, s):
    teeth = []
    for i in range(9):
        tx = -230 + i * 55
        teeth.append(f'<polygon points="{tx},40 {tx+46},40 {tx+23},{120 + (i%2)*40}" fill="#fff" stroke="#000" stroke-width="4"/>')
        teeth.append(f'<polygon points="{tx+10},260 {tx+50},260 {tx+30},{190 - (i%2)*30}" fill="#fff" stroke="#000" stroke-width="4"/>')
    return f"""
    <g transform="translate({cx},{cy}) scale({s})">
      <path d="M-700,700 C-760,300 -620,-80 -420,-260 L-560,-620 L-300,-330 L-200,-760 L-80,-380
               C-20,-400 40,-400 90,-380 L230,-760 L320,-330 L600,-620 L440,-250
               C640,-60 760,300 700,700 Z" fill="#000" stroke="#fff" stroke-width="6"/>
      <!-- pelo/tratteggi -->
      <path d="M-500,200 l-60,40 M-460,330 l-70,30 M500,200 l60,40 M470,330 l70,30 M-300,-200 l-40,-50 M300,-200 l40,-50"
            stroke="#fff" stroke-width="5" fill="none"/>
      <!-- bocca -->
      <path d="M-260,30 Q0,-20 260,30 Q240,280 0,300 Q-240,280 -260,30Z" fill="#fff" stroke="#000" stroke-width="5"/>
      <path d="M-240,50 Q0,10 240,50 Q220,250 0,270 Q-220,250 -240,50Z" fill="url(#dots)"/>
      <path d="M-200,90 Q0,60 200,90 Q180,230 0,240 Q-180,230 -200,90Z" fill="#000"/>
      {''.join(teeth)}
    </g>"""


def beast_eyes(cx, cy, s):
    return f"""
    <g transform="translate({cx},{cy}) scale({s})">
      <ellipse cx="-190" cy="-170" rx="170" ry="90" fill="url(#eyeGlow)" opacity="0.8"/>
      <ellipse cx="190" cy="-170" rx="170" ry="90" fill="url(#eyeGlow)" opacity="0.8"/>
      <path d="M-300,-210 Q-200,-170 -90,-150 Q-200,-130 -290,-160Z" fill="#fff" stroke="#000" stroke-width="3"/>
      <path d="M300,-210 Q200,-170 90,-150 Q200,-130 290,-160Z" fill="#fff" stroke="#000" stroke-width="3"/>
      <ellipse cx="-180" cy="-162" rx="8" ry="22" fill="#000"/>
      <ellipse cx="180" cy="-162" rx="8" ry="22" fill="#000"/>
    </g>"""


def sfx_text(x, y, text, size, rot, fill="#fff", stroke="#000", sw=18, skew=-12):
    return f"""<g transform="translate({x},{y}) rotate({rot}) skewX({skew})">
      <text x="0" y="0" font-family="DejaVu Sans" font-weight="bold" font-size="{size}" text-anchor="middle"
        fill="{fill}" stroke="{stroke}" stroke-width="{sw}" paint-order="stroke" stroke-linejoin="round" letter-spacing="-8">{text}</text></g>"""


# ======================= VIGNETTE =======================
layers = {}

# --- P1: citta' in rovina sotto la luna ---
W, H = 2800, 1500
sky = f'<rect width="{W}" height="{H}" fill="#fff"/><rect width="{W}" height="{H}" fill="url(#dotsL)"/>' \
      f'<rect width="{W}" height="{H*0.55}" fill="url(#dots)" opacity="0.9"/>' \
      f'<circle cx="1900" cy="520" r="560" fill="url(#moonGlow)"/>' \
      f'<circle cx="1900" cy="520" r="330" fill="#fff" stroke="#000" stroke-width="5"/>' \
      f'<circle cx="1800" cy="450" r="60" fill="url(#dotsL)"/><circle cx="2010" cy="600" r="90" fill="url(#dotsL)"/>' \
      f'<circle cx="1950" cy="380" r="35" fill="url(#dotsL)"/>'
layers["p1_bg"] = (W, H, sky)

r = random.Random(1)
far = []
x = -50
while x < W:
    bw = r.randint(120, 260); bh = r.randint(350, 750)
    top = H - bh
    pts = f"{x},{H} {x},{top} "
    for k in range(5):  # cima spezzata
        pts += f"{x + bw*(k+1)/6:.0f},{top + r.randint(-40, 90)} "
    pts += f"{x+bw},{top+r.randint(0,120)} {x+bw},{H}"
    far.append(f'<polygon points="{pts}" fill="#555" stroke="#222" stroke-width="3"/>')
    for wy in range(top + 80, H - 40, 70):
        for wx in range(x + 20, x + bw - 30, 50):
            if r.random() < 0.25:
                far.append(f'<rect x="{wx}" y="{wy}" width="18" height="30" fill="#ddd"/>')
    x += bw + r.randint(10, 60)
layers["p1_far"] = (W, H, "".join(far))

near = []
x = -100
while x < W:
    bw = r.randint(280, 520); bh = r.randint(160, 420)
    top = H - bh
    pts = f"{x},{H} {x},{top} "
    for k in range(7):
        pts += f"{x + bw*(k+1)/8:.0f},{top + r.randint(-60, 70)} "
    pts += f"{x+bw},{top+r.randint(-20,80)} {x+bw},{H}"
    near.append(f'<polygon points="{pts}" fill="#000" stroke="#fff" stroke-width="4"/>')
    for k in range(4):
        sx = x + r.randint(20, bw - 40); sy = top + r.randint(40, bh)
        near.append(f'<line x1="{sx}" y1="{sy}" x2="{sx+r.randint(-60,60)}" y2="{sy+r.randint(30,90)}" stroke="#fff" stroke-width="3"/>')
    x += bw + r.randint(-40, 40)
# tetto su cui sta Ren
near.append(f'<polygon points="1500,{H} 1500,1080 1640,1050 1760,1070 1900,1040 2120,1065 2200,1100 2200,{H}" fill="#000" stroke="#fff" stroke-width="5"/>')
layers["p1_near"] = (W, H, "".join(near))
layers["p1_ren"] = (W, H, ren_standing(1880, 1052, 1.45))

# --- P2: primo piano occhi ---
W, H = 2800, 1200
bg2 = f'<rect width="{W}" height="{H}" fill="#fff"/>' + radial_lines(W, H, W/2, H/2, 260, 900, "#000", seed=2, wmax=8)
layers["p2_bg"] = (W, H, bg2)


def eye(cx, cy, flip):
    sx = -1 if flip else 1
    return f"""
    <g transform="translate({cx},{cy}) scale({sx},1)">
      <path d="M-330,-20 Q-80,-190 300,-70 Q140,-40 -330,-20Z" fill="#000"/>
      <path d="M-300,-10 Q-60,-150 270,-60 Q150,140 -40,150 Q-220,120 -300,-10Z" fill="#fff" stroke="#000" stroke-width="10"/>
      <clipPath id="ec{int(flip)}"><path d="M-300,-10 Q-60,-150 270,-60 Q150,140 -40,150 Q-220,120 -300,-10Z"/></clipPath>
      <g clip-path="url(#ec{int(flip)})">
        <ellipse cx="0" cy="10" rx="130" ry="150" fill="url(#iris)" stroke="#000" stroke-width="8"/>
        <ellipse cx="0" cy="10" rx="95" ry="115" fill="none" stroke="#fff" stroke-width="3" stroke-dasharray="6 10"/>
        <ellipse cx="0" cy="10" rx="22" ry="80" fill="#000"/>
        <circle cx="-55" cy="-50" r="34" fill="#fff"/><circle cx="50" cy="60" r="14" fill="#fff"/>
        <rect x="-300" y="-150" width="600" height="110" fill="url(#dots)" opacity="0.7"/>
      </g>
      <path d="M-360,-260 Q-60,-330 320,-210 L330,-180 Q-40,-270 -350,-220Z" fill="#000"/>
      <path d="M-200,190 Q-40,215 140,170" stroke="#000" stroke-width="6" fill="none"/>
    </g>"""


face = f'<rect x="0" y="0" width="{W}" height="{H}" fill="none"/>' \
       f'<path d="M0,0 L{W},0 L{W},{H} L0,{H}Z" fill="#fff" opacity="0"/>' \
       f'<path d="M150,-50 Q1400,-140 2650,-50 L2750,{H+50} L50,{H+50}Z" fill="#fff" stroke="#000" stroke-width="8"/>' \
       + eye(870, 560, False) + eye(1930, 560, True) + \
       f'<path d="M1340,640 Q1400,820 1380,900 L1430,890" stroke="#000" stroke-width="7" fill="none"/>' \
       f'<path d="M2250,820 l140,-70 M2280,850 l120,-60" stroke="#000" stroke-width="8"/>' \
       f'<rect x="150" y="900" width="2600" height="400" fill="url(#hatch)" opacity="0.5"/>'
hair = "".join(
    f'<path d="M{x0},-20 Q{x0+40},{200+ (i*53)%180} {x0 + (i%2*2-1)*60},{260 + (i*97)%220} L{x0+50},-20Z" fill="#000" stroke="#fff" stroke-width="3"/>'
    for i, x0 in enumerate(range(80, 2800, 150)))
layers["p2_face"] = (W, H, face)
layers["p2_hair"] = (W, H, hair)

# --- P3: la Bestia ruggisce ---
W, H = 2800, 1700
for v in range(3):  # 3 varianti di linee cinetiche per l'effetto "boil"
    layers[f"p3_bg{v}"] = (W, H, f'<rect width="{W}" height="{H}" fill="#fff"/>' +
                           radial_lines(W, H, W/2, H*0.55, 340, 700, "#000", seed=10 + v))
layers["p3_beast"] = (W, H, beast(W/2, H*0.62, 1.15))
layers["p3_eyes"] = (W, H, beast_eyes(W/2, H*0.62, 1.15))
layers["p3_sfx"] = (W, H, sfx_text(820, 520, "GROOAAR", 330, -10) + sfx_text(2200, 1500, "!!", 300, 12))

# --- P4: lo scatto ---
W, H = 3600, 1400
for v in range(3):
    layers[f"p4_bg{v}"] = (W, H, f'<rect width="{W}" height="{H}" fill="#fff"/>' + horiz_lines(W, H, 220, "#000", seed=20 + v)
                           + f'<rect y="{H-260}" width="{W}" height="260" fill="url(#dots)"/>')
layers["p4_ren"] = (W, H, ren_running(2100, 1180, 2.4))
dust = "".join(f'<circle cx="{random.uniform(1500,2400):.0f}" cy="{random.uniform(1100,1300):.0f}" r="{random.uniform(8,40):.0f}" '
               f'fill="#fff" stroke="#000" stroke-width="4"/>' for _ in range(28))
layers["p4_dust"] = (W, H, dust)
layers["p4_sfx"] = (W, H, sfx_text(900, 380, "DASH", 260, -6, sw=16))

# --- P5: colpo ---
W, H = 2800, 1600
layers["p5_bg"] = (W, H, f'<rect width="{W}" height="{H}" fill="#000"/>' + radial_lines(W, H, W/2, H/2, 300, 300, "#fff", seed=30))
layers["p5_beast"] = (W, H, beast(W/2, H*0.6, 0.9))
slash = f'<path d="M-100,{H*0.95} Q{W*0.45},{H*0.45} {W+100},-80 L{W+100},40 Q{W*0.5},{H*0.55} -100,{H*1.05}Z" fill="#fff" stroke="#000" stroke-width="14"/>' \
        f'<path d="M-100,{H*0.99} Q{W*0.48},{H*0.5} {W+100},-20" stroke="#000" stroke-width="5" fill="none"/>'
layers["p5_slash"] = (W, H, slash)
layers["p5_sfx"] = (W, H, sfx_text(1000, 700, "ZAN!", 520, -14, fill="#000", stroke="#fff", sw=26))


def main():
    (OUT / "svg").mkdir(exist_ok=True)
    jobs = []
    for name, (w, h, body) in layers.items():
        f = OUT / "svg" / f"{name}.svg"
        f.write_text(svg(w, h, body))
        jobs.append({"svg": str(f), "png": str(OUT / f"{name}.png"), "w": w, "h": h})
    (OUT / "svg" / "jobs.json").write_text(json.dumps(jobs))


if __name__ == "__main__":
    main()
