#!/usr/bin/env python3
"""Build styles.json for Zen Internet: the stock repository with overrides/*.json on top.

Zen Internet reads styles from exactly one URL, so this file carries the stock styles too. For a
site present in both, features from overrides/ are added, and a feature with the same name
replaces the stock one. overrides/mapping.json adds domains to a site's entry, in the stock
"mapping" format ({"+site.com.css": ["other.domain"]}).
"""
import json
import urllib.request
from pathlib import Path

STOCK = "https://sameerasw.github.io/my-internet/styles.json"
root = Path(__file__).resolve().parent

styles = json.load(urllib.request.urlopen(STOCK))
sites = styles.setdefault("website", {})
mapping = styles.setdefault("mapping", {})
overrides = sorted(p for p in (root / "overrides").glob("*.json") if p.name != "mapping.json")
for path in overrides:
    for site, features in json.loads(path.read_text()).items():
        sites.setdefault(site, {}).update(features)
for site, domains in json.loads((root / "overrides" / "mapping.json").read_text()).items():
    mapping[site] = sorted(set(mapping.get(site, [])) | set(domains))

(root / "styles.json").write_text(json.dumps(styles, indent=1, ensure_ascii=False) + "\n")
print(f"{len(sites)} sites, overrides from {len(overrides)} file(s)")
