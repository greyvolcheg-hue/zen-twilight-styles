#!/usr/bin/env python3
"""Generate overrides/rutracker.org.json: rutracker.org recoloured onto the Twilight palette.

rutracker.org has no CSS custom properties: every colour is a literal inside a rule of its one
stylesheet (all.min.css on static.rutracker.cc). So this repeats each rule that sets a colour,
with the same selector and inside the same @media, and puts a Twilight cell in place of every
colour literal. The cell comes from the property (text, background, border), the hue and the
luminance, with the palette and helpers of linkedin_tokens.py: the site is light, as LinkedIn is.

Left as they are: shadows, filters, `transparent`, icons and sprites. Removed: the three
decorative raster gradients (table headers, news and sidebar titles), which would stay light.
Added: dark buttons, selects and text fields, which the site leaves to the browser.
Colours written inline in the page (news on the front page, BBCode colours in posts) cannot be
reached from a stylesheet and keep their own values.

Usage: tools/rutracker_colours.py
"""
import json
import re
import subprocess
import sys
from pathlib import Path

from linkedin_tokens import (
    ACC, ACC_ACTIVE, ACC_HOVER, BG0, BG1, BG2, BG3, ERR, FG, LIGHT, OUTLINE, PINK, PINK_BG, RED,
    SEL, SUB, DIM, WARN, WARN_BG, hue_class, luminance, parse, rgba, state_colour,
)

PAGE = "https://rutracker.org/forum/index.php"
CSS_LINK = r'href="(https://static\.rutracker\.cc/[^"]+\.css)"'
SITE_KEY = "rutracker.org.css"  # the stock repository's key, so the stock features stay beside ours
FEATURE = "rt-twilight colours"
UA = "Mozilla/5.0 (X11; Linux x86_64; rv:140.0) Gecko/20100101 Firefox/140.0"

NAMED = {"black": "#000000", "white": "#ffffff", "red": "#ff0000", "green": "#008000",
         "blue": "#0000ff", "brown": "#a52a2a", "gray": "#808080", "grey": "#808080"}
COLOUR = re.compile(r"#[0-9a-fA-F]{3,8}\b|rgba?\([^)]*\)|\b(?:" + "|".join(NAMED) + r")\b", re.I)
DECORATIVE = re.compile(r"cellpic3\.gif|hr\d+_ltr_gradient\.jpg")
# property -> (role, property to write). Shorthands are narrowed to their colour part.
PROPS = {
    "color": ("fg", "color"),
    "background": ("bg", "background-color"),
    "background-color": ("bg", "background-color"),
    "border": ("border", "border-color"),
    "border-color": ("border", "border-color"),
    "outline": ("border", "outline-color"),
}
for side in ("top", "right", "bottom", "left"):
    PROPS[f"border-{side}"] = ("border", f"border-{side}-color")
    PROPS[f"border-{side}-color"] = ("border", f"border-{side}-color")


# The site leaves buttons and selects to the browser, which draws them light. Placed first, so a
# rule of the site's own with the same specificity still wins.
FORM_CONTROLS = f"""input[type="submit"], input[type="button"], input[type="reset"], button, select {{
  background-color: {BG3} !important;
  color: {FG} !important;
  border-color: {OUTLINE} !important;
}}
input[type="text"], input[type="search"], input[type="password"], textarea {{
  background-color: {BG0} !important;
  color: {FG} !important;
  border-color: {OUTLINE} !important;
}}"""


def fetch(url, encoding="utf-8"):
    out = subprocess.run(["curl", "-sfL", "--compressed", "-A", UA, url], capture_output=True, check=True)
    return out.stdout.decode(encoding, "replace")


def cell(role, rgb_a, selector):
    """The Twilight cell for one colour. Light site: white and light-grey surfaces become the dark
    background cells, dark text becomes the light text cells."""
    r, g, b, a = rgb_a
    hc, lum = hue_class(r, g, b), luminance(r, g, b)
    state = "hover" if ":hover" in selector else "active" if ":active" in selector else ""
    if hc == "neutral":
        if role == "fg":
            if lum >= 0.85:
                return rgba(LIGHT, a)  # white text on coloured headers and buttons
            if lum < 0.06:
                return rgba(FG, a)     # #000 ... #444: body text
            return rgba(SUB, a) if lum < 0.35 else rgba(DIM, a)  # greys: secondary, then hints
        if role == "border":
            return rgba(OUTLINE, a) if lum < 0.5 else rgba(OUTLINE, 0.35 * a)
        if lum > 0.9:
            return rgba(BG1, a)
        if lum > 0.6:
            return rgba(BG2, a)
        if lum > 0.3:
            return rgba(BG3, a)
        return rgba(BG0, a)
    if hc in ("accent", "violet"):
        if role == "fg":
            if lum >= 0.6:
                return rgba(LIGHT, a)  # pale blue text on the dark blue table headers
            return state_colour(state, ACC, ACC_HOVER, ACC_ACTIVE)
        if role == "border":
            return rgba(ACC, a)
        return rgba(BG3, a) if lum > 0.75 else rgba(SEL, a)
    if hc == "positive":
        if role == "bg":
            return rgba(BG3, a) if lum > 0.75 else rgba(PINK_BG, a)
        return rgba(PINK, a)
    if hc == "negative":
        if role == "bg":
            return rgba(BG3, a) if lum > 0.75 else rgba(RED, a)
        return rgba(ERR, a)
    if role == "bg":
        return rgba(WARN_BG, a) if lum > 0.6 else rgba(WARN, a)
    return rgba(WARN, a)


def recolour(value, role, selector):
    """Replace every colour literal in a value. None if nothing in it is a colour to change."""
    changed = False

    def one(m):
        nonlocal changed
        lit = m.group(0)
        p = parse(NAMED.get(lit.lower(), lit))
        if p is None:
            return lit
        changed = True
        return cell(role, p, selector)

    out = COLOUR.sub(one, value)
    return out if changed else None


def rule_out(selector, body):
    """The override declarations for one rule."""
    lines = []
    for decl in body.split(";"):
        if ":" not in decl:
            continue
        prop, value = (s.strip() for s in decl.split(":", 1))
        prop = prop.lower()
        value = value.replace("!important", "").strip()
        if prop not in PROPS:
            continue  # shadows, filters, list images
        role, target = PROPS[prop]
        if prop == "background" and DECORATIVE.search(value):
            lines.append("background-image: none")
        if prop == "background" and "gradient" in value:
            new = recolour(value, role, selector)
            if new:
                lines.append(f"background: {new}")
            continue
        colours = COLOUR.findall(value)
        if not colours:
            continue  # transparent, inherit, url() only
        new = recolour(" ".join(colours) if target != prop else value, role, selector)
        if new:
            lines.append(f"{target}: {new}")
    return [f"  {line} !important;" for line in lines]


def walk(css):
    """Yield (at-rule prefix or None, selector, body) for every plain rule, descending into @media."""
    i, n = 0, len(css)
    while i < n:
        j = css.find("{", i)
        if j < 0:
            return
        head = css[i:j].strip()
        if head.startswith("@media"):
            depth, k = 1, j + 1
            while depth and k < n:
                depth += {"{": 1, "}": -1}.get(css[k], 0)
                k += 1
            for _, sel, body in walk(css[j + 1:k - 1]):
                yield head, sel, body
            i = k
        elif head.startswith("@"):
            depth, k = 1, j + 1  # keyframes, page: skip the whole block
            while depth and k < n:
                depth += {"{": 1, "}": -1}.get(css[k], 0)
                k += 1
            i = k
        else:
            k = css.find("}", j)
            yield None, head, css[j + 1:k]
            i = k + 1


def main():
    page = fetch(PAGE, "cp1251")
    links = re.findall(CSS_LINK, page)
    if not links:
        sys.exit(f"no stylesheet matching {CSS_LINK}")
    css = re.sub(r"/\*.*?\*/", "", "".join(fetch(h) for h in links), flags=re.S)
    css = re.sub(r"@(?:charset|import)[^;]*;", "", css)  # statements without a block
    blocks, rules, decls = {}, 0, 0
    for media, selector, body in walk(css):
        lines = rule_out(selector, body)
        if lines:
            rules += 1
            decls += len(lines)
            blocks.setdefault(media, []).append(f"{selector} {{\n" + "\n".join(lines) + "\n}")
    parts = [FORM_CONTROLS] + blocks.pop(None, [])
    for media, rs in blocks.items():
        parts.append(media + " {\n" + "\n".join(rs) + "\n}")
    out = Path(__file__).resolve().parent.parent / "overrides" / "rutracker.org.json"
    out.write_text(json.dumps({SITE_KEY: {FEATURE: "\n".join(parts) + "\n"}}, indent=2, ensure_ascii=False) + "\n")
    print(f"rutracker.org: {decls} declarations in {rules} rules recoloured -> {out.name} ({', '.join(links)})")


if __name__ == "__main__":
    main()
