#!/usr/bin/env python3
"""Generate overrides/last.fm.json: last.fm recoloured onto the Twilight palette.

last.fm writes its colours as literals: ~3000 in the main stylesheet against ~170 var() calls,
almost none of them colours. So this works as rutracker_colours.py does: each rule that sets a
colour is repeated with a Twilight cell in place of every literal.

The stylesheets come from the links on the front page (/static/styles/build/*.css): the full
app-*.css, the app-reduced-*.css subset and the front page's own sheet. Their names carry a build
hash that changes with each release, so the GitHub Action reruns this daily. Page-specific sheets
of other pages are not covered: those pages answer scripts with a JavaScript challenge.

last.fm's brand red (#d92323 and its hover and pale variants) takes the accent cells, as
LinkedIn's blue does. Pale yellow surfaces (the now-scrobbling row) take BG3; saturated yellow
ones (the Pro buttons) take WARN, and dark text on them takes BG0. Its native dark surfaces (header, footer) fall to the darkest cell.
Shadows, images and the album art stay as they are. Rules written with CSS nesting (Swiper's
carousel: slide shadows, the preloader) are skipped.

Usage: tools/lastfm_colours.py
"""
import json
import re
import sys
from pathlib import Path

from linkedin_tokens import ACC, ACC_ACTIVE, ACC_HOVER, BG0, BG3, LIGHT, SEL, WARN, hue_class, luminance, parse, rgba, state_colour
from rutracker_colours import COLOUR, FORM_CONTROLS, NAMED, PROPS, cell as rutracker_cell, fetch

SITE = "https://www.last.fm"
CSS_LINK = r'href="(/static/styles/build/[^"]+\.css)"'
SITE_KEY = "+last.fm.css"
FEATURE = "lfm-twilight colours"


def cell(role, rgb_a, selector, on_yellow=False):
    """rutracker_colours.cell, with the reds read as the accent and last.fm's yellows."""
    r, g, b, a = rgb_a
    hc = hue_class(r, g, b)
    if hc == "warning" and role == "bg":
        return rgba(BG3, a) if luminance(r, g, b) > 0.85 else rgba(WARN, a)
    if on_yellow and role == "fg" and hc == "neutral" and luminance(r, g, b) < 0.35:
        return rgba(BG0, a)  # #222 on the Pro buttons
    if hc != "negative":
        return rutracker_cell(role, rgb_a, selector)
    lum = luminance(r, g, b)
    if role == "fg":
        if lum >= 0.6:
            return rgba(LIGHT, a)
        state = "hover" if ":hover" in selector else "active" if ":active" in selector else ""
        return state_colour(state, ACC, ACC_HOVER, ACC_ACTIVE)
    if role == "border":
        return rgba(ACC, a)
    return rgba(BG3, a) if lum > 0.75 else rgba(SEL, a)


def recolour(value, role, selector, on_yellow=False):
    """Replace every colour literal in a value. None if nothing in it is a colour to change."""
    changed = False

    def one(m):
        nonlocal changed
        lit = m.group(0)
        p = parse(NAMED.get(lit.lower(), lit))
        if p is None:
            return lit
        changed = True
        return cell(role, p, selector, on_yellow)

    try:
        out = COLOUR.sub(one, value)
    except ValueError:
        return None  # a colour syntax parse() does not read
    return out if changed else None


def yellow_bg(body):
    """True if the rule sets a saturated yellow background, one that becomes WARN."""
    for m in re.finditer(r"background(?:-color)?\s*:([^;]*)", body, re.I):
        for c in COLOUR.finditer(m.group(1)):
            p = parse(NAMED.get(c.group(0).lower(), c.group(0)))
            if p and hue_class(*p[:3]) == "warning" and luminance(*p[:3]) <= 0.85:
                return True
    return False


def rule_out(selector, body):
    """The override declarations for one rule."""
    lines, on_yellow = [], yellow_bg(body)
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
        if prop not in PROPS:
            continue  # shadows, filters, images
        role, target = PROPS[prop]
        colours = [c.group(0) for c in COLOUR.finditer(value)]
        if not colours:
            continue  # transparent, inherit, url() only
        new = recolour(colours[-1] if target != prop else value, role, selector, on_yellow)
        if new:
            lines.append(f"{target}: {new}")
    return [f"  {line} !important;" for line in lines]


def block_end(css, j):
    """The index after the } that closes the { at j."""
    depth, k = 1, j + 1
    while depth and k < len(css):
        depth += {"{": 1, "}": -1}.get(css[k], 0)
        k += 1
    return k


def walk(css):
    """rutracker_colours.walk, brace-aware: yield (at-rule prefix or None, selector, body) for
    every plain rule, descending into @media, skipping other at-rules and nested rules."""
    i, n = 0, len(css)
    while i < n:
        j = css.find("{", i)
        if j < 0:
            return
        head, k = css[i:j].strip(), block_end(css, j)
        body = css[j + 1:k - 1]
        if head.startswith("@media"):
            for _, sel, b in walk(body):
                yield head, sel, b
        elif not head.startswith("@") and "{" not in body:
            yield None, head, body
        i = k


def main():
    links = list(dict.fromkeys(re.findall(CSS_LINK, fetch(SITE + "/"))))
    if not any("/app-" in h for h in links):
        sys.exit(f"no app stylesheet matching {CSS_LINK} on {SITE}/")
    blocks, seen, rules, decls = {}, set(), 0, 0
    for href in links:
        css = re.sub(r"/\*.*?\*/", "", fetch(SITE + href), flags=re.S)
        css = re.sub(r"@(?:charset|import)[^;]*;", "", css)
        for media, selector, body in walk(css):
            lines = rule_out(selector, body)
            block = f"{selector} {{\n" + "\n".join(lines) + "\n}"
            if not lines or (media, block) in seen:
                continue  # app-reduced repeats rules of app
            seen.add((media, block))
            rules += 1
            decls += len(lines)
            blocks.setdefault(media, []).append(block)
    parts = [FORM_CONTROLS] + blocks.pop(None, [])
    for media, rs in blocks.items():
        parts.append(media + " {\n" + "\n".join(rs) + "\n}")
    out = Path(__file__).resolve().parent.parent / "overrides" / "last.fm.json"
    out.write_text(json.dumps({SITE_KEY: {FEATURE: "\n".join(parts) + "\n"}}, indent=2) + "\n")
    print(f"last.fm: {decls} declarations in {rules} rules from {', '.join(links)} -> {out.name}")


if __name__ == "__main__":
    main()
