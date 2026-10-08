# zen-twilight-styles

Site styles for the [Zen Internet](https://addons.mozilla.org/firefox/addon/zen-internet/) add-on:
the stock repository plus Twilight recolours. Twilight is a dark violet palette built from the
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
- `build.py`: downloads the stock `styles.json` and lays the overrides on top. A same-named feature
  replaces the stock one.
- A GitHub Action rebuilds `styles.json` daily and on every change to `overrides/`.
- `tools/linkedin_tokens.py`: regenerates the LinkedIn recolour from LinkedIn's own colour tokens.
- `tools/warframe_tokens.py`: the same for warframe.market, wiki.warframe.com and browse.wf
  (`wfm-`, `wiki-` and `bwf-twilight colours`). These sites are dark already, so their surfaces
  are ranked darkest to lightest onto the four Twilight background cells. Colours the sites write
  as literals, outside their tokens, stay as they are.
