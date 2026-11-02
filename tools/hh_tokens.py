#!/usr/bin/env python3
"""Generate the hh-twilight colours feature in overrides/hh.ru.json: hh.ru's colour tokens
remapped to the Twilight palette. hh.kz serves the same stylesheets and reaches this feature
through overrides/mapping.json.

hh.ru paints its pages through two token sets on :root: Magritte (~1450 --magritte-color-*) and
the older Bloko (~730 --bloko-*color*). Every token name carries the design system version
(-v26-0-2), so the names change with each hh.ru release; the GitHub Action reruns this daily. The
stylesheet URLs are read from the live home page for the same reason. Tokens are remapped by role
and hue as linkedin_tokens.py does for LinkedIn. Tokens that point at another token through var()
are restated as they are, so the night theme cannot repaint them. Colours written as literals in
the site rules are not covered.

Usage: tools/hh_tokens.py
"""
import colorsys
import html
import json
import re
import subprocess
import urllib.parse
from pathlib import Path

from linkedin_tokens import (
    BG0, BG1, BG2, BG3, DIM, FG, LIGHT, SUB, luminance, parse, remap as linkedin_remap, rgba, role,
)

PAGE = "https://hh.ru/"
CSS = r'href="(https://i\.hh\.ru/[^"]+\.css)"'
TOKEN = r"(--(?:magritte|bloko)-[a-z0-9-]*color[a-z0-9-]*)\s*:\s*([^;}]+)"
SELECTOR = ':root, html, body, [class*="magritte-"][class*="-theme"]'
FEATURE = "hh-twilight colours"
NEUTRAL_SPREAD = 40  # max - min channel below this is a grey; hh.ru accents start at 83
UA = "Mozilla/5.0 (X11; Linux x86_64; rv:140.0) Gecko/20100101 Firefox/140.0"


def fetch(url):
    out = subprocess.run(["curl", "-sfL", "-A", UA, url], capture_output=True, check=True)
    return out.stdout.decode("utf-8", "replace")


def remap(name, value):
    # hsla() is not in parse(); Bloko writes its transparent fills that way.
    m = re.match(r"hsla?\(([^,]+),([^,]+)%,([^,]+)%(?:,([^)]+))?\)", value)
    if m:
        r, g, b = colorsys.hls_to_rgb(float(m[1]) / 360, float(m[3]) / 100, float(m[2]) / 100)
        hexed = "#%02x%02x%02x" % (round(r * 255), round(g * 255), round(b * 255))
        value = rgba(hexed, float(m[4]) if m[4] else 1.0)
    p = parse(value)
    if p is None:
        return None
    # Magritte calls borders "stroke", Bloko calls text "typography"; linkedin_tokens.role()
    # knows neither word.
    name = name.replace("stroke", "border").replace("typography", "text")
    r, g, b, a = p
    if max(r, g, b) - min(r, g, b) >= NEUTRAL_SPREAD:
        return linkedin_remap(name, value)
    # hh.ru greys are blue-tinted (#dce3eb, #768694), and HLS saturation, which hue_class()
    # reads, calls the light ones blue. They are greyed here so linkedin_remap() sees a neutral.
    lum = luminance(r, g, b)
    if role(name) == "fg":
        # hh.ru marks secondary text by a lighter grey, not by alpha as LinkedIn does.
        cell = FG if lum < 0.1 else SUB if lum < 0.35 else DIM if lum < 0.65 else LIGHT
        return rgba(cell, a)
    if role(name) == "bg" and lum >= 0.6:
        # LinkedIn's ladder puts #fff and #f1f4f9 (0.905) on one cell; hh.ru's cards and
        # panels differ by only that step. The body is the page behind them, like LinkedIn's
        # canvas.
        cell = BG0 if "background-body" in name else BG1 if lum >= 0.99 else BG2 if lum >= 0.85 else BG3
        return rgba(cell, a)
    grey =round((0.2126 * r + 0.7152 * g + 0.0722 * b))
    return linkedin_remap(name, rgba("#%02x%02x%02x" % (grey, grey, grey), a))


def main():
    page = fetch(PAGE)
    hrefs = sorted(set(html.unescape(h) for h in re.findall(CSS, page)))
    if not hrefs:
        raise SystemExit(f"hh.ru: no stylesheet matching {CSS}")
    css = "".join(fetch(urllib.parse.urljoin(PAGE, h)) for h in hrefs)
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    tokens = {}
    for block in re.findall(r"(?:^|})\s*:root\s*\{([^}]*)\}", css):
        for name, value in re.findall(TOKEN, block):
            tokens.setdefault(name, value.strip().removesuffix("!important").strip())
    lines = []
    for name, value in sorted(tokens.items()):
        new = value if value.startswith("var(") else remap(name, value)
        if new:
            lines.append(f"  {name}: {new} !important;")
    out = Path(__file__).resolve().parent.parent / "overrides" / "hh.ru.json"
    data = json.loads(out.read_text())
    data["+hh.ru.css"][FEATURE] = SELECTOR + " {\n" + "\n".join(lines) + "\n}\n"
    out.write_text(json.dumps(data, indent=2) + "\n")
    print(f"hh.ru: {len(lines)} of {len(tokens)} tokens remapped from {len(hrefs)} stylesheet(s)")


if __name__ == "__main__":
    main()
