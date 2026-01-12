#!/usr/bin/env python3
"""Tutorial-pair manifest: data/external/pairs.jsonl. One record per SOURCE PAGE that shows the same
garment before and after a cut-off (and optionally after washing). Records are created by the
pair-finder agent (web search + page reading) and validated here. Images are NOT downloaded by this
script; `--fetch` downloads the referenced images for local research use only (respect each page's
terms; nothing is redistributed).

Record: {page_url, title, source_type: blog|video|forum|social, garment_desc, images: [{url, role:
before|marked|after_cut|after_wash|detail, note}], wash_described: bool, wash_notes, scale_ref:
none|ruler|coin|known_object, license_or_terms, found_at}
"""
import argparse, hashlib, json, os, sys, urllib.request, urllib.parse
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; P = ROOT / "data/external/pairs.jsonl"; IMG = ROOT / "data/external/pair_images"
ROLES = {"before", "marked", "after_cut", "after_wash", "detail"}
UA = "denim-twin-research (jefferyh619@gmail.com; academic; not redistributed)"

def load():
    return [json.loads(l) for l in P.read_text().splitlines() if l.strip()] if P.exists() else []

def validate(recs):
    errs = []; seen = set()
    for i, r in enumerate(recs):
        for k in ("page_url", "source_type", "images", "found_at"):
            if k not in r: errs.append(f"#{i}: missing {k}")
        if r.get("page_url") in seen: errs.append(f"#{i}: duplicate page {r.get('page_url')}")
        seen.add(r.get("page_url"))
        roles = {im.get("role") for im in r.get("images", [])}
        bad = roles - ROLES
        if bad: errs.append(f"#{i}: bad roles {bad}")
        if "before" not in roles or not ({"after_cut", "after_wash"} & roles): errs.append(f"#{i}: not a pair (needs before + after_*)")
    return errs

def fetch(recs, limit):
    IMG.mkdir(parents=True, exist_ok=True); n = 0
    for r in recs:
        pid = hashlib.sha1(r["page_url"].encode()).hexdigest()[:10]
        for im in r["images"]:
            out = IMG / f"{pid}_{im['role']}_{hashlib.sha1(im['url'].encode()).hexdigest()[:8]}{os.path.splitext(urllib.parse.urlparse(im['url']).path)[1] or '.jpg'}"
            if out.exists() or n >= limit: continue
            try:
                req = urllib.request.Request(im["url"], headers={"User-Agent": UA})
                with urllib.request.urlopen(req, timeout=60) as resp: data = resp.read(20_000_000)
                out.write_bytes(data); n += 1
            except Exception as e: print("warn", im["url"], e, file=sys.stderr)
    print(f"fetched {n}")

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--fetch", type=int, default=0); a = ap.parse_args()
    recs = load(); errs = validate(recs)
    print(f"{len(recs)} pair pages; {sum(len(r['images']) for r in recs)} images; "
          f"{sum(1 for r in recs if any(i['role']=='after_wash' for i in r['images']))} with after-wash; "
          f"{sum(1 for r in recs if r.get('scale_ref','none')!='none')} with scale ref")
    for e in errs: print("ERR", e)
    if a.fetch: fetch(recs, a.fetch)
    sys.exit(1 if errs else 0)
