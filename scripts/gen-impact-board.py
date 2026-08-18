#!/usr/bin/env python3
"""Render the "Impact overview" board as a standalone animated SVG.

GitHub strips <style>, CSS and <script> out of README markup, so a board like
this cannot be built from HTML. It can be built as one self-contained SVG and
embedded as an image: gradients, filters and SMIL animation all render inside an
<img>-loaded SVG. Only script does not, which is why every animation here is
SMIL rather than CSS -- SMIL is what the typing-SVG banner already relies on.

The numbers are career facts rather than live data, so unlike
gen-contribution-radar.py this needs no token and no scheduled workflow. Edit
TILES and re-run by hand.

Usage:
    python3 scripts/gen-impact-board.py
"""

import math
import os

OUT = os.path.join(os.path.dirname(__file__), "..", "assets", "impact-board.svg")

MONO = "ui-monospace,SFMono-Regular,SF Mono,JetBrains Mono,Menlo,Consolas,monospace"
SANS = "-apple-system,BlinkMacSystemFont,Segoe UI,Inter,Helvetica,Arial,sans-serif"

BG = "#08080b"
CARD_BG = "#0e0e13"
LINE = "#ffffff14"
TXT = "#fafafa"
MUTED = "#8b8b95"
FAINT = "#5c5c66"

# Portfolio tokens (src/index.css) mapped onto the six accents.
ACCENTS = {
    "green": {"line": "#4ade80", "deep": "#16a34a", "text": "#4ade80"},
    "blue": {"line": "#38bdf8", "deep": "#0284c7", "text": "#38bdf8"},
    "purple": {"line": "#a855f7", "deep": "#7c3aed", "text": "#a855f7"},
    "indigo": {"line": "#6366f1", "deep": "#4338ca", "text": "#818cf8"},
}

W, PAD, GUTTER = 1200, 32, 26
CARD_W = (W - 2 * PAD - GUTTER) // 2
CARD_H = 330
GRID_TOP = 84
H = GRID_TOP + 3 * CARD_H + 2 * GUTTER + PAD

HEAD_H = 54          # title strip inside a card
CHART_TOP = 180      # chart band, relative to the card
CHART_BOT = 316


# --------------------------------------------------------------------------
# geometry helpers
# --------------------------------------------------------------------------

def esc(text):
    """XML-escape label text. Without this an ampersand ("build & deploy") makes
    the whole file unparseable and GitHub renders a broken-image icon."""
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def points(vals, x0, x1, y_bot, y_top):
    """Map a 0..1 series onto the chart band."""
    n = len(vals)
    step = (x1 - x0) / (n - 1)
    return [(x0 + i * step, y_bot - v * (y_bot - y_top)) for i, v in enumerate(vals)]


def smooth(pts):
    """Catmull-Rom through the points, emitted as cubic beziers."""
    d = f"M {pts[0][0]:.1f} {pts[0][1]:.1f}"
    for i in range(len(pts) - 1):
        p0 = pts[i - 1] if i > 0 else pts[0]
        p1, p2 = pts[i], pts[i + 1]
        p3 = pts[i + 2] if i + 2 < len(pts) else p2
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        d += (f" C {c1[0]:.1f} {c1[1]:.1f} {c2[0]:.1f} {c2[1]:.1f}"
              f" {p2[0]:.1f} {p2[1]:.1f}")
    return d


def stepped(pts):
    """Square staircase through the points."""
    d = f"M {pts[0][0]:.1f} {pts[0][1]:.1f}"
    for i in range(1, len(pts)):
        d += f" H {pts[i][0]:.1f} V {pts[i][1]:.1f}"
    return d


def path_len(pts, curved):
    total = sum(math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1))
    if not curved:  # a staircase also walks every vertical riser
        total = sum(abs(pts[i][0] - pts[i + 1][0]) + abs(pts[i][1] - pts[i + 1][1])
                    for i in range(len(pts) - 1))
    return total * 1.04


# --------------------------------------------------------------------------
# animation helpers -- SMIL only
# --------------------------------------------------------------------------

EASE = 'calcMode="spline" keyTimes="0;1" keySplines="0.22 1 0.36 1"'


def ease(attr, a, b, dur, begin):
    return (f'<animate attributeName="{attr}" values="{a};{b}" dur="{dur}s" '
            f'begin="{begin:.2f}s" fill="freeze" {EASE}/>')


def rise(begin, dy=10):
    """Fade up. Wrap in a <g>; SVG text cannot be transformed in place."""
    return (f'{ease("opacity", 0, 1, 0.55, begin)}'
            f'<animateTransform attributeName="transform" type="translate" '
            f'values="0 {dy};0 0" dur="0.55s" begin="{begin:.2f}s" fill="freeze" {EASE}/>')


def draw(d, colour, width, begin, length, dash=None, glow=None):
    """A stroke that draws itself in left to right."""
    filt = f' filter="url(#{glow})"' if glow else ""
    if dash:  # a dashed line cannot also use the dash array to draw itself
        return (f'<path d="{d}" fill="none" stroke="{colour}" stroke-width="{width}" '
                f'stroke-dasharray="{dash}" stroke-linecap="round" opacity="0"{filt}>'
                f'{ease("opacity", 0, 1, 0.7, begin)}</path>')
    return (f'<path d="{d}" fill="none" stroke="{colour}" stroke-width="{width}" '
            f'stroke-linecap="round" stroke-linejoin="round" '
            f'stroke-dasharray="{length:.0f}" stroke-dashoffset="{length:.0f}"{filt}>'
            f'{ease("stroke-dashoffset", f"{length:.0f}", 0, 1.5, begin)}</path>')


def ping(x, y, colour, begin):
    """End-of-series marker with a slow radar pulse."""
    return (
        f'<g opacity="0">{ease("opacity", 0, 1, 0.4, begin + 1.3)}'
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="none" stroke="{colour}" '
        f'stroke-width="1.5">'
        f'<animate attributeName="r" values="4;15" dur="2.4s" begin="{begin + 1.6:.2f}s" '
        f'repeatCount="indefinite"/>'
        f'<animate attributeName="stroke-opacity" values="0.8;0" dur="2.4s" '
        f'begin="{begin + 1.6:.2f}s" repeatCount="indefinite"/></circle>'
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{colour}"/></g>')


def grid(begin):
    out = []
    for f in (0.18, 0.5, 0.82):
        y = CHART_BOT - (CHART_BOT - CHART_TOP) * f
        out.append(f'<line x1="14" y1="{y:.1f}" x2="{CARD_W - 14}" y2="{y:.1f}" '
                   f'stroke="#ffffff0d" stroke-width="1" stroke-dasharray="3 7" '
                   f'opacity="0">{ease("opacity", 0, 1, 0.6, begin)}</line>')
    return "".join(out)


# --------------------------------------------------------------------------
# the six charts
# --------------------------------------------------------------------------

def chart_gauge(a, begin):
    """Uptime: a 180-degree arc that sweeps in."""
    cx, cy, r = CARD_W / 2, CHART_BOT - 20, 76
    d = f"M {cx - r} {cy} A {r} {r} 0 0 1 {cx + r} {cy}"
    length = math.pi * r * 1.02
    return (
        f'<path d="{d}" fill="none" stroke="#ffffff0f" stroke-width="17" '
        f'stroke-linecap="round"/>'
        f'<path d="{d}" fill="none" stroke="{a["line"]}" stroke-width="17" '
        f'stroke-linecap="round" filter="url(#glow-green)" '
        f'stroke-dasharray="{length:.0f}" stroke-dashoffset="{length:.0f}">'
        f'{ease("stroke-dashoffset", f"{length:.0f}", 0, 1.7, begin)}</path>'
        f'<g opacity="0">{ease("opacity", 0, 1, 0.5, begin + 1.4)}'
        f'<text x="{cx - r:.0f}" y="{cy + 18:.0f}" text-anchor="middle" fill="{FAINT}" '
        f'font-family="{MONO}" font-size="11">0</text>'
        f'<text x="{cx + r:.0f}" y="{cy + 18:.0f}" text-anchor="middle" fill="{FAINT}" '
        f'font-family="{MONO}" font-size="11">100</text></g>')


def chart_two_lines(a, begin):
    """Cost cut: a dashed baseline over a solid, glowing spend line."""
    x0, x1 = 10, CARD_W - 10
    top = points([.74, .77, .80, .82, .83, .81, .79, .80, .82, .80],
                 x0, x1, CHART_BOT, CHART_TOP)
    bot = points([.40, .42, .47, .45, .38, .34, .36, .35, .32, .34, .40],
                 x0, x1, CHART_BOT, CHART_TOP)
    return (
        grid(begin)
        + draw(smooth(top), "#38bdf8", 2.5, begin + 0.15, 0, dash="9 8")
        + f'<g opacity="0">{ease("opacity", 0, 1, 0.5, begin + 0.6)}'
        + f'<circle cx="{top[-1][0]:.1f}" cy="{top[-1][1]:.1f}" r="4" fill="#38bdf8"/></g>'
        + draw(smooth(bot), a["line"], 3, begin + 0.3, path_len(bot, True),
               glow="glow-green")
        + ping(bot[-1][0], bot[-1][1], a["line"], begin + 0.3))


def chart_area(a, begin, vals, glow, gradient):
    """Peak traffic: a smooth curve over a fading gradient fill."""
    x0, x1 = 4, CARD_W - 4
    pts = points(vals, x0, x1, CHART_BOT, CHART_TOP)
    fill = (smooth(pts) + f" L {x1} {CHART_BOT + 6} L {x0} {CHART_BOT + 6} Z")
    return (
        grid(begin)
        + f'<path d="{fill}" fill="url(#{gradient})" opacity="0">'
        + ease("opacity", 0, 1, 0.9, begin + 0.7) + "</path>"
        + draw(smooth(pts), a["line"], 3, begin + 0.15, path_len(pts, True), glow=glow)
        + ping(pts[-1][0], pts[-1][1], a["line"], begin + 0.15))


def chart_steps(a, begin, vals, glow, gradient):
    """Stepped charts: a staircase over a gradient fill."""
    x0, x1 = 6, CARD_W - 6
    pts = points(vals, x0, x1, CHART_BOT, CHART_TOP)
    fill = stepped(pts) + f" L {x1} {CHART_BOT + 6} L {x0} {CHART_BOT + 6} Z"
    return (
        grid(begin)
        + f'<path d="{fill}" fill="url(#{gradient})" opacity="0">'
        + ease("opacity", 0, 1, 0.9, begin + 0.7) + "</path>"
        + draw(stepped(pts), a["line"], 3, begin + 0.15, path_len(pts, False), glow=glow)
        + ping(pts[-1][0], pts[-1][1], a["line"], begin + 0.15))


def chart_bars3d(a, begin):
    """Devtron: extruded bars, revealed by a left-to-right wipe."""
    vals = [.20, .20, .21, .22, .22, .23, .24, .25, .27, .34, .44, .56, .70, .84, .96]
    x0, x1, depth = 16, CARD_W - 26, 13
    span = (x1 - x0) / len(vals)
    bw, h_max = span * 0.62, CHART_BOT - CHART_TOP - 22
    bars = []
    for i, v in enumerate(vals):
        x = x0 + i * span
        h = v * h_max
        top, bot = CHART_BOT - h, CHART_BOT
        bars.append(
            f'<polygon points="{x:.1f},{top:.1f} {x + depth:.1f},{top - depth:.1f} '
            f'{x + bw + depth:.1f},{top - depth:.1f} {x + bw:.1f},{top:.1f}" '
            f'fill="#d8b4fe"/>'
            f'<polygon points="{x + bw:.1f},{top:.1f} {x + bw + depth:.1f},{top - depth:.1f} '
            f'{x + bw + depth:.1f},{bot - depth:.1f} {x + bw:.1f},{bot:.1f}" '
            f'fill="#5b21b6"/>'
            f'<rect x="{x:.1f}" y="{top:.1f}" width="{bw:.1f}" height="{h:.1f}" '
            f'fill="url(#grad-bar)"/>')
    wipe = (f'<rect x="{x0 - 4}" y="{CHART_TOP - 30}" width="0" '
            f'height="{CHART_BOT - CHART_TOP + 40}">'
            f'<animate attributeName="width" values="0;{x1 - x0 + 12}" dur="1.5s" '
            f'begin="{begin:.2f}s" fill="freeze" {EASE}/></rect>')
    return (grid(begin) + f'<clipPath id="wipe-bars">{wipe}</clipPath>'
            + f'<g clip-path="url(#wipe-bars)">{"".join(bars)}</g>')


# --------------------------------------------------------------------------
# tiles
# --------------------------------------------------------------------------

TILES = [
    {"title": "UPTIME", "meta": "ON UPGRADES", "accent": "green",
     "value": "100%", "sub": "zero downtime · staging → beta → prod",
     "chart": lambda a, b: chart_gauge(a, b)},
    {"title": "AWS COST CUT", "meta": "PROD / STAGING", "accent": "green",
     "value": "25% / 65%", "sub": "FinOps right-sizing, 2 accounts",
     "chart": chart_two_lines},
    {"title": "PEAK TRAFFIC", "meta": "REQ / 30 MIN", "accent": "blue",
     "value": "5 Lakh+", "sub": "UP Board Results event",
     "chart": lambda a, b: chart_area(
         a, b,
         [.16, .20, .18, .24, .32, .44, .60, .76, .88, .80, .64, .50,
          .42, .38, .46, .52, .42, .32, .26, .20, .14, .09],
         "glow-blue", "grad-blue")},
    {"title": "PLATFORM BUILD", "meta": "URUMI · EMDASH", "accent": "purple",
     "value": "POC → Prod", "sub": "8+ AWS services as Terraform IaC",
     "border": True,
     "chart": lambda a, b: chart_steps(
         a, b, [.50, .78, .72, .90, .64, .48, .32, .24],
         "glow-purple", "grad-purple")},
    {"title": "EKS UPGRADE", "meta": "CONTROL PLANE", "accent": "indigo",
     "value": "1.24 → 1.31", "sub": "stepped, zero downtime",
     "chart": lambda a, b: chart_steps(
         a, b, [.08, .20, .32, .30, .44, .56, .74, .70, .86],
         "glow-indigo", "grad-indigo")},
    {"title": "DEVTRON", "meta": "FROM SCRATCH", "accent": "purple",
     "value": "150+ Apps", "sub": "build & deploy across 3 envs",
     "chart": chart_bars3d},
]


def render_tile(t, col, row, index):
    a = ACCENTS[t["accent"]]
    x = PAD + col * (CARD_W + GUTTER)
    y = GRID_TOP + row * (CARD_H + GUTTER)
    begin = 0.35 + index * 0.16
    border = a["line"] + "66" if t.get("border") else LINE

    head = (
        f'<rect x="0.5" y="0.5" width="{CARD_W - 1}" height="{CARD_H - 1}" rx="12" '
        f'fill="{CARD_BG}" stroke="{border}"/>'
        f'<path d="M 0 {HEAD_H} H {CARD_W}" stroke="{LINE}" stroke-width="1"/>'
        f'<circle cx="22" cy="27" r="4.5" fill="{a["line"]}">'
        f'<animate attributeName="opacity" values="1;0.3;1" dur="2.8s" '
        f'begin="{begin + 1.2:.2f}s" repeatCount="indefinite"/></circle>'
        f'<text x="40" y="33" fill="#d9d9e0" font-family="{MONO}" font-size="15" '
        f'letter-spacing="2.4" font-weight="500">{esc(t["title"])}</text>'
        f'<text x="{CARD_W - 22}" y="33" text-anchor="end" fill="{FAINT}" '
        f'font-family="{MONO}" font-size="14" letter-spacing="2.2">{esc(t["meta"])}</text>')

    body = (
        f'<g opacity="0">{rise(begin + 0.1)}'
        f'<text x="30" y="122" fill="{a["text"]}" font-family="{SANS}" font-size="46" '
        f'font-weight="700" filter="url(#soft-{t["accent"]})">{esc(t["value"])}</text>'
        f'<text x="32" y="156" fill="{MUTED}" font-family="{SANS}" '
        f'font-size="15">{esc(t["sub"])}</text></g>')

    return (f'<g transform="translate({x} {y})">{head}{body}'
            f'{t["chart"](a, begin + 0.25)}</g>')


def defs():
    out = ['<defs>']
    for name, key in (("green", "green"), ("blue", "blue"),
                      ("purple", "purple"), ("indigo", "indigo")):
        c = ACCENTS[key]["line"]
        out.append(
            f'<filter id="glow-{name}" x="-60%" y="-60%" width="220%" height="220%">'
            f'<feGaussianBlur stdDeviation="5" result="b"/>'
            f'<feMerge><feMergeNode in="b"/><feMergeNode in="b"/>'
            f'<feMergeNode in="SourceGraphic"/></feMerge></filter>'
            f'<filter id="soft-{name}" x="-40%" y="-40%" width="180%" height="180%">'
            f'<feGaussianBlur stdDeviation="7" result="b"/>'
            f'<feColorMatrix in="b" type="matrix" result="d" values="'
            f'1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 0.5 0"/>'
            f'<feMerge><feMergeNode in="d"/><feMergeNode in="SourceGraphic"/>'
            f'</feMerge></filter>')
        out.append(
            f'<linearGradient id="grad-{name}" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0%" stop-color="{c}" stop-opacity="0.42"/>'
            f'<stop offset="100%" stop-color="{c}" stop-opacity="0.02"/></linearGradient>')
    out.append(
        '<linearGradient id="grad-bar" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0%" stop-color="#a855f7"/>'
        '<stop offset="100%" stop-color="#7c3aed"/></linearGradient>'
        f'<pattern id="mesh" width="46" height="46" patternUnits="userSpaceOnUse">'
        f'<path d="M 46 0 L 0 0 0 46" fill="none" stroke="#ffffff08" '
        f'stroke-width="1"/></pattern>')
    out.append('</defs>')
    return "".join(out)


def render():
    rule_x = 360
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}" role="img" '
        f'aria-label="Impact overview: 100% uptime on upgrades, 25%/65% AWS cost cut, '
        f'5 lakh+ requests in 30 minutes, POC to production platform build, '
        f'EKS 1.24 to 1.31, 150+ apps on Devtron">',
        defs(),
        f'<rect width="{W}" height="{H}" fill="{BG}"/>',
        f'<rect width="{W}" height="{H}" fill="url(#mesh)"/>',
        # header
        f'<g opacity="0">{rise(0.1, 6)}'
        f'<circle cx="{PAD + 14}" cy="46" r="5" fill="#4ade80">'
        f'<animate attributeName="opacity" values="1;0.25;1" dur="2.6s" '
        f'begin="1.2s" repeatCount="indefinite"/></circle>'
        f'<text x="{PAD + 32}" y="52" fill="#d9d9e0" font-family="{MONO}" '
        f'font-size="17" letter-spacing="3.4" font-weight="500">IMPACT OVERVIEW</text>'
        f'<text x="{W - PAD}" y="52" text-anchor="end" fill="{FAINT}" '
        f'font-family="{MONO}" font-size="15" letter-spacing="2">urumi · careers360</text></g>',
        f'<line x1="{rule_x}" y1="46" x2="{rule_x}" y2="46" stroke="{LINE}" '
        f'stroke-width="1">'
        f'<animate attributeName="x2" values="{rule_x};{W - 170}" dur="1.1s" '
        f'begin="0.45s" fill="freeze" {EASE}/></line>',
    ]
    for i, t in enumerate(TILES):
        parts.append(render_tile(t, i % 2, i // 2, i))
    parts.append("</svg>")
    return "".join(parts)


if __name__ == "__main__":
    svg = render()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(svg)
    print(f"wrote {os.path.normpath(OUT)} ({len(svg):,} bytes, {W}x{H})")
