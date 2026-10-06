#!/usr/bin/env python3
"""Generate overrides/linkedin.com.json: LinkedIn's colour tokens remapped to the Twilight palette.

LinkedIn styles every page through ~800 CSS custom properties (--color-*), declared on :root and
on its theme classes. This reads them from a LinkedIn stylesheet, sorts each one by role (text,
border, background) and hue (neutral, accent, positive, negative, warning), and assigns a cell of
the Twilight palette. Every colour used is a cell of 40-computer-geek/niri/twilight-theme.json.

Usage: tools/linkedin_tokens.py [stylesheet URL or file]
"""
import colorsys
import json
import re
import sys
import urllib.request
from pathlib import Path

DEFAULT_CSS = "https://static.licdn.com/aero-v1/sc/h/e34z9ok0cr46ybpximu64wtan"

BG0, BG1, BG2, BG3 = "#0a000f", "#0f0016", "#14001e", "#1b0028"
FG, FG_BRIGHT, LIGHT = "#ba70e0", "#cc9ee2", "#e5d9ba"
SUB, DIM = "#8579bb", "#7265b9"
ACC, ACC_HOVER, ACC_ACTIVE = "#b690f7", "#cc9ee2", "#a097dd"
SEL, OUTLINE, PINK_BG = "#5f24a6", "#7641bb", "#400040"
PINK, ERR, RED, WARN, WARN_BG = "#d900d9", "#c86f3b", "#bb4d26", "#dea55c", "#43321c"


def parse(value):
    v = value.strip()
    if v.startswith("#"):
        h = v[1:]
        if len(h) in (3, 4):
            h = "".join(c * 2 for c in h)
        r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
        a = int(h[6:8], 16) / 255 if len(h) == 8 else 1.0
        return r, g, b, a
    m = re.match(r"rgba?\(([^)]+)\)", v)
    if m:
        parts = [p.strip() for p in m.group(1).replace("/", ",").split(",")]
        r, g, b = (float(p) for p in parts[:3])
        a = float(parts[3]) if len(parts) > 3 else 1.0
        return r, g, b, a
    return None


def rgba(hex_colour, a):
    r, g, b = (int(hex_colour[i:i + 2], 16) for i in (1, 3, 5))
    return hex_colour if a >= 0.999 else f"rgba({r}, {g}, {b}, {round(a, 3)})"


def role(name):
    if any(k in name for k in ("border", "divider", "outline")):
        return "border"
    if "container" in name or "background" in name or "surface" in name or "scrim" in name:
        return "bg"
    if any(k in name for k in ("text", "label", "icon", "value", "link", "placeholder", "action", "signal")):
        return "fg"
    return "bg"


def hue_class(r, g, b):
    h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    if s < 0.18 or l < 0.06 or l > 0.97:
        return "neutral"
    deg = h * 360
    if 180 <= deg < 255:
        return "accent"
    if 75 <= deg < 180:
        return "positive"
    if deg >= 330 or deg < 20:
        return "negative"
    if 20 <= deg < 75:
        return "warning"
    return "violet"


def luminance(r, g, b):
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r / 255) + 0.7152 * f(g / 255) + 0.0722 * f(b / 255)


def state_colour(name, base, hover, active):
    if "hover" in name:
        return hover
    if "active" in name or "pressed" in name:
        return active
    return base


def remap(name, value):
    p = parse(value)
    if p is None:
        return None
    r, g, b, a = p
    ro, hc, lum = role(name), hue_class(r, g, b), luminance(r, g, b)
    if "shadow" in name or "scrim" in name:
        return None  # dark overlays work on a dark page as they are
    if hc == "neutral":
        if ro == "fg":
            if lum > 0.5:
                return rgba(LIGHT, a)  # text meant for dark or coloured backgrounds
            return FG if a >= 0.85 else SUB if a >= 0.55 else DIM
        if ro == "border":
            return rgba(OUTLINE, max(a, 0.35)) if lum < 0.5 else rgba(OUTLINE, 0.35)
        if lum < 0.5 and a < 0.999:
            return rgba(ACC, a)  # black hover/press overlays become violet glows
        if "canvas" in name:
            return rgba(BG0, a)  # the page behind the cards, darker than the cards
        if lum > 0.9:
            return rgba(BG1, a)
        if lum > 0.6:
            return rgba(BG2, a)
        if lum > 0.3:
            return rgba(BG3, a)
        return rgba(BG0, a)
    if hc in ("accent", "violet"):
        if ro == "fg":
            return state_colour(name, ACC, ACC_HOVER, ACC_ACTIVE)
        if ro == "border":
            return rgba(ACC, a)
        return rgba(BG3, a) if lum > 0.75 else rgba(SEL, a)
    if hc == "positive":
        if ro == "bg":
            return rgba(BG3, a) if lum > 0.75 else rgba(PINK_BG, a)
        return rgba(PINK, a)
    if hc == "negative":
        if ro == "bg":
            return rgba(BG3, a) if lum > 0.75 else rgba(RED, a)
        return rgba(ERR, a)
    if ro == "bg":
        return rgba(WARN_BG, a) if lum > 0.6 else rgba(WARN, a)
    return rgba(WARN, a)


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_CSS
    css = urllib.request.urlopen(src).read().decode() if src.startswith("http") else Path(src).read_text()
    tokens = {}
    for name, value in re.findall(r"(--color-[a-z0-9-]+)\s*:\s*([^;}]+)", css):
        tokens.setdefault(name, value.strip())
    lines = []
    for name, value in sorted(tokens.items()):
        new = remap(name, value)
        if new:
            lines.append(f"  {name}: {new} !important;")
    css_out = (":root, html, body, [class*=\"theme--\"] {\n" + "\n".join(lines) + "\n}\n")
    out = Path(__file__).resolve().parent.parent / "overrides" / "linkedin.com.json"
    out.write_text(json.dumps({"+linkedin.com.css": {"in-twilight colours": css_out}}, indent=2) + "\n")
    print(f"{len(lines)} of {len(tokens)} tokens remapped -> {out}")


if __name__ == "__main__":
    main()
