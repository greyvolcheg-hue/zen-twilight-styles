#!/usr/bin/env python3
"""Generate Twilight overrides for three dark Warframe sites: warframe.market, wiki.warframe.com
and browse.wf.

Each site paints its dark theme through CSS custom properties: warframe.market through ~150
--color_* tokens on .theme--dark, the wiki through a palette (--lotus-blue-*, greys) on :root,
browse.wf through Bootstrap 5.3 --bs-* tokens on [data-bs-theme=dark]. This reads the live
stylesheets, takes the colour-valued properties under that selector and assigns each a cell of the
Twilight palette by role (text, border, background) and hue, as linkedin_tokens.py does for
LinkedIn. These sites are dark already, so backgrounds are ranked darkest to lightest rather than
read as light surfaces. Colours written as literals in the site rules are not covered.

Usage: tools/warframe_tokens.py [site ...]      (default: all three)
"""
import html
import json
import math
import re
import subprocess
import sys
import urllib.parse
from pathlib import Path

from linkedin_tokens import (
    ACC, ACC_ACTIVE, ACC_HOVER, BG0, BG1, BG2, BG3, ERR, FG, FG_BRIGHT, OUTLINE, PINK,
    PINK_BG, RED, SEL, SUB, DIM, WARN, WARN_BG, hue_class, luminance, parse, rgba, state_colour,
)

SITES = {
    "warframe.market": {
        "page": "https://warframe.market/",
        "css": r'href="(/static/build/css/[^"]+\.css)"',
        "block": r"\.theme--dark(?:,\.theme--light)?\{([^}]*)\}",  # shared block, then dark
        "selector": ":root, .theme--dark, .theme--light",
        "feature": "wfm-twilight colours",
    },
    "wiki.warframe.com": {
        "page": "https://wiki.warframe.com/w/Main_Page",
        "css": r'href="(/load\.php\?[^"]*modules=site\.styles[^"]*)"',
        "block": r":root\{([^}]*)\}",
        "selector": ":root",
        "feature": "wiki-twilight colours",
    },
    "browse.wf": {
        "page": "https://browse.wf/",
        "css": r'href="(https://cdn\.jsdelivr\.net/npm/bootstrap@[^"]+/bootstrap\.min\.css)"',
        # Light defaults first, then the dark block, so dark values win as in the cascade.
        "block": r"(?::root,\[data-bs-theme=light\]|\[data-bs-theme=dark\])\{([^}]*)\}",
        "selector": ":root, [data-bs-theme=dark]",
        "feature": "bwf-twilight colours",
    },
}

SKIP = re.compile(r"pygments|shadow")  # syntax highlighting keeps its hues; shadows stay dark
UA = "Mozilla/5.0 (X11; Linux x86_64; rv:140.0) Gecko/20100101 Firefox/140.0"


def fetch(url):
    # curl, not urllib: wiki.warframe.com answers urllib with 403 even under a browser User-Agent.
    out = subprocess.run(["curl", "-sfL", "-A", UA, url], capture_output=True, check=True)
    return out.stdout.decode("utf-8", "replace")


def role(name):
    n = name.lower()
    if any(k in n for k in ("border", "outline", "divider")):
        return "border"
    if any(k in n for k in ("background", "-bg", "_bg", "surface")):
        return "bg"
    if any(k in n for k in ("text", "link", "label", "icon", "title", "disclaimer", "heading",
                            "emphasis", "code", "placeholder")):
        return "fg"
    if re.search(r"[-_]h\d$", n) or n.endswith(("-color", "_color")) or n == "--color-base":
        return "fg"
    return None  # a palette entry: its luminance decides


def classify(name, value):
    """Return (role, hue class, luminance, alpha) for a colour token, or None to leave it alone."""
    p = parse(value)
    if p is None or SKIP.search(name):
        return None
    r, g, b, a = p
    lum = luminance(r, g, b)
    return role(name) or ("fg" if lum >= 0.18 else "bg"), hue_class(r, g, b), lum, a


def is_dark_surface(ro, hc, lum, a):
    """A near-black neutral or blue-tinted surface. Dark green, red and yellow surfaces carry
    a meaning (success, danger, warning) and go to the matching cells instead."""
    return ro == "bg" and a >= 0.999 and lum < 0.06 and hc in ("neutral", "accent", "violet")


def surface_cell(lum, surfaces):
    """surfaces: the site's dark-surface luminances above zero, sorted. Bin on a log scale between
    the darkest and the lightest, so the page lands on BG0 and raised panels step up to BG3."""
    if lum <= 0 or len(surfaces) < 2:
        return BG0
    lo, hi = math.log(surfaces[0]), math.log(surfaces[-1])
    return (BG0, BG1, BG2, BG3)[min(3, max(0, int(4 * (math.log(lum) - lo) / (hi - lo))))]


def remap(name, value, surfaces):
    c = classify(name, value)
    if c is None:
        return None
    ro, hc, lum, a = c
    if ro == "bg" and a < 0.999:
        # white overlays on a dark page are hover glows; black ones are shades and stay
        return rgba(ACC, a) if lum > 0.5 else None
    if is_dark_surface(ro, hc, lum, a):
        return surface_cell(lum, surfaces)
    if ro == "border":
        return rgba(ACC, a) if hc in ("accent", "violet") and lum >= 0.18 else rgba(OUTLINE, a)
    if hc == "neutral":
        if ro == "fg":
            if lum >= 0.8:
                return rgba(FG_BRIGHT, a)  # headings and white emphasis; body text is FG
            if lum >= 0.35:
                return rgba(FG, a)
            return rgba(SUB, a) if lum >= 0.15 else rgba(DIM, a)
        return rgba(OUTLINE, a)  # light greys used as fills: chips, hover rows
    if hc in ("accent", "violet"):
        if ro == "fg":
            return rgba(FG_BRIGHT, a) if lum >= 0.6 else state_colour(name, ACC, ACC_HOVER, ACC_ACTIVE)
        return rgba(SEL, a)
    if hc == "positive":
        return rgba(PINK, a) if ro == "fg" or lum >= 0.1 else rgba(PINK_BG, a)
    if hc == "negative":
        if ro == "fg":
            return rgba(ERR, a)
        # Twilight has no dark red: a dark danger surface is the error cell at a quarter strength
        return rgba(ERR, 0.25 * a) if lum < 0.1 else rgba(RED, a)
    return rgba(WARN, a) if ro == "fg" or lum >= 0.1 else rgba(WARN_BG, a)


def as_colour(name, value, tokens):
    """Bootstrap pairs --x with --x-rgb ("13,110,253") for rgba() maths. Read the triplet as a
    colour under the base token's name, so both get the same role and the same cell."""
    if name.endswith("-rgb") and re.fullmatch(r"\s*\d+\s*,\s*\d+\s*,\s*\d+\s*", value):
        base = name[: -len("-rgb")]
        return (base if base in tokens else name), "rgb(" + value + ")"
    return name, value


def remap_rgb_triplet(name, value, tokens, surfaces):
    if not name.endswith("-rgb"):
        return None
    new = remap(*as_colour(name, value, tokens), surfaces)
    if new is None or not new.startswith("#"):
        return None
    return ", ".join(str(int(new[i:i + 2], 16)) for i in (1, 3, 5))


def build(site, cfg):
    page = fetch(cfg["page"])
    hrefs = [html.unescape(h) for h in re.findall(cfg["css"], page)]
    if not hrefs:
        sys.exit(f"{site}: no stylesheet matching {cfg['css']}")
    css = "".join(fetch(urllib.parse.urljoin(cfg["page"], h)) for h in hrefs)
    tokens = {}
    for block in re.findall(cfg["block"], css):
        for name, value in re.findall(r"(--[A-Za-z0-9_-]+)\s*:\s*([^;}]+)", block):
            tokens[name] = value.strip().removesuffix("!important").strip()
    surfaces = set()
    for name, value in tokens.items():
        c = classify(*as_colour(name, value, tokens))
        if c and is_dark_surface(*c) and c[2] > 0:
            surfaces.add(c[2])
    surfaces = sorted(surfaces)
    lines = []
    for name, value in sorted(tokens.items()):
        if name.endswith("-rgb"):
            new = remap_rgb_triplet(name, value, tokens, surfaces)
        else:
            new = remap(name, value, surfaces)
        if new:
            lines.append(f"  {name}: {new} !important;")
    css_out = cfg["selector"] + " {\n" + "\n".join(lines) + "\n}\n"
    out = Path(__file__).resolve().parent.parent / "overrides" / f"{site}.json"
    out.write_text(json.dumps({f"+{site}.css": {cfg["feature"]: css_out}}, indent=2) + "\n")
    print(f"{site}: {len(lines)} of {len(tokens)} tokens remapped -> {out.name}")


def main():
    for site in sys.argv[1:] or SITES:
        build(site, SITES[site])


if __name__ == "__main__":
    main()
