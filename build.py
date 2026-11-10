#!/usr/bin/env python3
"""Build styles.json for Zen Internet from overrides/*.json.

The file carries only our features, no stock styles (dropped 2026-11-10). overrides/mapping.json
adds domains to a site's entry, in the stock "mapping" format ({"+site.com.css": ["other.domain"]}).
"""
import json
from pathlib import Path

root = Path(__file__).resolve().parent

sites = {}
overrides = sorted(p for p in (root / "overrides").glob("*.json") if p.name != "mapping.json")
for path in overrides:
    for site, features in json.loads(path.read_text()).items():
        sites.setdefault(site, {}).update(features)
mapping = {site: sorted(set(domains))
           for site, domains in json.loads((root / "overrides" / "mapping.json").read_text()).items()}

styles = {"website": sites, "mapping": mapping}
(root / "styles.json").write_text(json.dumps(styles, indent=1, ensure_ascii=False) + "\n")
print(f"{len(sites)} sites, overrides from {len(overrides)} file(s)")
