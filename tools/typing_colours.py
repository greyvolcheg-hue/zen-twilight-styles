#!/usr/bin/env python3
"""Generate overrides/typing.com.json: typing.com recoloured onto the Twilight palette.

typing.com has no colour tokens: its colours are literals in two stylesheets, one for the public
site (/dist/site_typing/css/app.N.css) and one for the lessons (/dist/student/css/app.min.N.css,
the default skin; other skins load other files and are not covered). N is the site's cacheId and
changes with each release, so the GitHub Action reruns this daily. Each rule that sets a colour is
repeated with a Twilight cell in place of every literal, as rutracker_colours.py does.

The two stylesheets share ~960 class names with different colours, so each set of rules is held
to its own pages with @scope: lesson pages carry body[data-path], site pages do not. A rule on
html moves to :scope, the body. Greys up to #4a4a4a become body text (FG). Tailwind
colours with a var() alpha (rgba(255,255,255,var(--tw-bg-opacity))) are read as opaque and keep
their var(). Images and the skin's sprites stay as they are.

Usage: tools/typing_colours.py
"""
import json
import re
import sys
from pathlib import Path

from rutracker_colours import COLOUR, FORM_CONTROLS, NAMED, PROPS, cell as rutracker_cell, fetch, walk
from linkedin_tokens import FG, hue_class, luminance, parse, rgba

SITE = "https://www.typing.com"
CACHE_ID = r"cacheId: '(\d+)'"
SHEETS = [  # (stylesheet path, scope root): the public site, then the lessons
    ("/dist/site_typing/css/app.{}.css", "body:not([data-path])"),
    ("/dist/student/css/app.min.{}.css", "body[data-path]"),
]
SITE_KEY = "+typing.com.css"
FEATURE = "typing-twilight colours"
VAR_ALPHA = re.compile(r"rgba\(([^()]*?),\s*(var\([^)]*\))\)")
COLOUR_OR_VAR = re.compile(VAR_ALPHA.pattern + "|" + COLOUR.pattern, re.I)
TYPE_PROPS = dict(PROPS, **{"fill": ("fg", "fill"), "stroke": ("fg", "stroke")})
BODY_TEXT_LUM = 0.08  # typing.com's body text is #4a4a4a (luminance 0.069), lighter than rutracker's


def cell(role, rgb_a, selector):
    """rutracker_colours.cell, with typing.com's darker greys read as body text."""
    r, g, b, a = rgb_a
    if role == "fg" and hue_class(r, g, b) == "neutral" and luminance(r, g, b) < BODY_TEXT_LUM:
        return rgba(FG, a)
    return rutracker_cell(role, rgb_a, selector)


def recolour(value, role, selector):
    """Replace every colour literal in a value. None if nothing in it is a colour to change."""
    changed = False

    def one(m):
        nonlocal changed
        lit = m.group(0)
        alpha = VAR_ALPHA.fullmatch(lit)
        p = parse(f"rgb({alpha.group(1)})" if alpha else NAMED.get(lit.lower(), lit))
        if p is None:
            return lit
        changed = True
        new = cell(role, p, selector)
        if alpha:  # keep the Tailwind opacity variable
            r, g, b = (int(new[i:i + 2], 16) for i in (1, 3, 5))
            return f"rgba({r}, {g}, {b}, {alpha.group(2)})"
        return new

    try:
        out = COLOUR_OR_VAR.sub(one, value)
    except ValueError:
        return None  # a colour syntax parse() does not read
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
        if "gradient" in value and prop in ("background", "background-image"):
            new = recolour(value, "bg", selector)
            if new:
                lines.append(f"{prop}: {new}")
            continue
        if prop not in TYPE_PROPS:
            continue  # shadows, filters, images
        role, target = TYPE_PROPS[prop]
        colours = [c.group(0) for c in COLOUR_OR_VAR.finditer(value)]
        if not colours:
            continue  # transparent, inherit, url() only
        new = recolour(colours[-1] if target != prop else value, role, selector)
        if new:
            lines.append(f"{target}: {new}")
    return [f"  {line} !important;" for line in lines]


def recolour_sheet(css):
    """The recoloured rules of one stylesheet, @media blocks last. Returns (css, rules, decls)."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    css = re.sub(r"@(?:charset|import)[^;]*;", "", css)
    blocks, rules, decls = {}, 0, 0
    for media, selector, body in walk(css):
        lines = rule_out(selector, body)
        if selector in ("html", ":root"):
            selector = ":scope"  # html lies outside the body scope; body inherits from it
        if lines:
            rules += 1
            decls += len(lines)
            blocks.setdefault(media, []).append(f"{selector} {{\n" + "\n".join(lines) + "\n}")
    parts = blocks.pop(None, [])
    for media, rs in blocks.items():
        parts.append(media + " {\n" + "\n".join(rs) + "\n}")
    return "\n".join(parts), rules, decls


def main():
    m = re.search(CACHE_ID, fetch(SITE + "/"))
    if not m:
        sys.exit(f"no {CACHE_ID} on {SITE}/")
    parts, report = [FORM_CONTROLS], []
    for path, root in SHEETS:
        url = SITE + path.format(m.group(1))
        css, rules, decls = recolour_sheet(fetch(url))
        parts.append(f"@scope ({root}) {{\n{css}\n}}")
        report.append(f"{decls} declarations in {rules} rules from {url}")
    out = Path(__file__).resolve().parent.parent / "overrides" / "typing.com.json"
    out.write_text(json.dumps({SITE_KEY: {FEATURE: "\n".join(parts) + "\n"}}, indent=2) + "\n")
    print("typing.com: " + "; ".join(report) + f" -> {out.name}")


if __name__ == "__main__":
    main()
