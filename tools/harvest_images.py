#!/usr/bin/env python3
"""Harvest CC-licensed jeans/denim images from Openverse and Wikimedia Commons.

Writes/updates data/external/manifest.jsonl (one record per unique image: source, id, url,
license, attribution, title, tags, width, height, first_seen). Dedup by (source,id) and by URL.
No API keys required. Respects both APIs' rate guidance (short sleeps).

Usage:
  harvest_images.py                  # update manifest only
  harvest_images.py --download N     # also download up to N not-yet-downloaded images into data/external/images/
"""
import argparse, json, os, sys, time, hashlib, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data/external/manifest.jsonl"
IMG_DIR = ROOT / "data/external/images"
UA = "denim-twin-research-harvester/0.1 (jefferyh619@gmail.com; academic garment dataset; https://github.com/jefferyjefe/denim-twin)"
QUERIES = ["jeans flat lay", "denim jeans", "blue jeans", "denim shorts", "cut off jeans", "jorts",
           "frayed denim", "distressed jeans", "vintage levis", "raw denim", "jeans hem", "denim fabric"]

def get(url, params=None):
    if params: url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)

def openverse(q, page=1):
    d = get("https://api.openverse.org/v1/images/", {"q": q, "page_size": 50, "page": page,
            "license_type": "all-cc", "category": "photograph"})
    for it in d.get("results", []):
        yield dict(source="openverse", id=it["id"], url=it["url"], page_url=it.get("foreign_landing_url"),
                   license=f"{it.get('license')}-{it.get('license_version')}", attribution=it.get("attribution"),
                   creator=it.get("creator"), title=it.get("title"), tags=[t["name"] for t in (it.get("tags") or [])][:15],
                   width=it.get("width"), height=it.get("height"), provider=it.get("provider"), query=q)

def commons(q, offset=0):
    d = get("https://commons.wikimedia.org/w/api.php", {"action": "query", "format": "json", "generator": "search",
            "gsrsearch": f"{q} filetype:bitmap", "gsrnamespace": 6, "gsrlimit": 50, "gsroffset": offset,
            "prop": "imageinfo", "iiprop": "url|size|extmetadata"})
    for p in (d.get("query", {}).get("pages") or {}).values():
        ii = (p.get("imageinfo") or [{}])[0]; em = ii.get("extmetadata", {})
        lic = em.get("LicenseShortName", {}).get("value", "")
        if not lic or "copyright" in lic.lower(): continue
        yield dict(source="commons", id=str(p["pageid"]), url=ii.get("url"), page_url=ii.get("descriptionurl"),
                   license=lic, attribution=em.get("Artist", {}).get("value"), creator=em.get("Artist", {}).get("value"),
                   title=p.get("title"), tags=[], width=ii.get("width"), height=ii.get("height"), provider="wikimedia", query=q)

def load_manifest():
    recs = {}
    if MANIFEST.exists():
        for line in MANIFEST.read_text().splitlines():
            if line.strip():
                r = json.loads(line); recs[(r["source"], r["id"])] = r
    return recs

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--download", type=int, default=0); ap.add_argument("--pages", type=int, default=2)
    a = ap.parse_args()
    recs = load_manifest(); seen_urls = {r["url"] for r in recs.values()}; new = 0
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for q in QUERIES:
        for fetch, pages in ((openverse, range(1, a.pages + 1)), (commons, range(0, 50 * a.pages, 50))):
            for pg in pages:
                try:
                    for r in fetch(q, pg):
                        k = (r["source"], r["id"])
                        if k in recs or not r["url"] or r["url"] in seen_urls: continue
                        if (r.get("width") or 0) < 600: continue
                        r["first_seen"] = now; recs[k] = r; seen_urls.add(r["url"]); new += 1
                except Exception as e:
                    print(f"warn {fetch.__name__} {q!r} p{pg}: {e}", file=sys.stderr)
                time.sleep(2.0 if fetch is openverse else 0.5)
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    with open(MANIFEST, "w") as f:
        for r in recs.values(): f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"manifest: {len(recs)} records (+{new} new)")
    if a.download:
        IMG_DIR.mkdir(parents=True, exist_ok=True); got = 0
        for r in recs.values():
            out = IMG_DIR / f"{r['source']}_{hashlib.sha1(r['url'].encode()).hexdigest()[:12]}{os.path.splitext(urllib.parse.urlparse(r['url']).path)[1] or '.jpg'}"
            if out.exists(): continue
            try:
                req = urllib.request.Request(r["url"], headers={"User-Agent": UA})
                with urllib.request.urlopen(req, timeout=60) as resp, open(out, "wb") as f: f.write(resp.read())
                got += 1; time.sleep(0.3)
            except Exception as e:
                print(f"warn download {r['url']}: {e}", file=sys.stderr)
            if got >= a.download: break
        print(f"downloaded {got}")

if __name__ == "__main__":
    main()
