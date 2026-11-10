# zen-twilight-styles

Site styles for the [Zen Internet](https://addons.mozilla.org/firefox/addon/zen-internet/) add-on:
Twilight recolours only, no stock styles (dropped 2026-11-10). Twilight is a dark violet palette built from the
Warframe Twilight colours.

## Use

Zen Internet → Data viewer → Custom Styles Repository:

```
https://raw.githubusercontent.com/greyvolcheg-hue/zen-twilight-styles/main/styles.json
```

Then "Fetch latest styles" in the add-on popup and enable the site. Each recolour is its own
feature switch, for example `in-twilight colours` on linkedin.com.

## How it works

- `overrides/*.json`: our features per site, in the Zen Internet format
  (`{"+site.com.css": {"feature name": "css"}}`).
- `build.py`: joins the overrides into `styles.json`.
- A GitHub Action rebuilds `styles.json` daily and on every change to `overrides/`.
- `tools/linkedin_tokens.py`: regenerates the LinkedIn recolour from LinkedIn's own colour tokens.
- `tools/hh_tokens.py`: the same for hh.ru (`hh-twilight colours`), from its Magritte and Bloko
  tokens. hh.ru puts its design system version into every token name, so the Action reruns it
  daily. hh.kz serves the same stylesheets and gets the feature through `overrides/mapping.json`.
- `tools/warframe_tokens.py`: the same for warframe.market, wiki.warframe.com and browse.wf
  (`wfm-`, `wiki-` and `bwf-twilight colours`). These sites are dark already, so their surfaces
  are ranked darkest to lightest onto the four Twilight background cells. Colours the sites write
  as literals, outside their tokens, stay as they are.
- `tools/rutracker_colours.py`: rutracker.org (`rt-twilight colours`). The site has no colour
  tokens, so every rule of its stylesheet that sets a colour is repeated with a Twilight cell in
  place of each literal. The site key keeps the stock spelling `rutracker.org.css`. Colours written
  inline in the page (news, BBCode in posts) stay as they are.
- `tools/typing_colours.py`: typing.com (`typing-twilight colours`), the public site and the
  lessons in the default skin. No colour tokens either, so it works as the rutracker tool does;
  the site's two stylesheets share class names, so `@scope` holds each to its own pages. The
  stylesheet URLs carry the release number, so the Action reruns it daily.
