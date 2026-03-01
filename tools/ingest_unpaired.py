#!/usr/bin/env python3
"""Ingest UNPAIRED after-wash photos of frayed cut-offs into the fringe-depth prior (plan §4.7/§4.9, §5 online variant).

Input: data/external/unpaired_candidates.jsonl — one record per candidate photo, keys:
  page_url, title, source_type, found_at, license_or_terms, image_url, image_note, state_evidence, hem_finish, resolution
Only 'frayed' hems that the page's own words place AFTER a wash are usable; every record must carry `state_evidence`
(the sentence that establishes it) or it is refused. Nothing here is redistributed: images land in
data/external/unpaired_images/ (gitignored) and only scale-free numbers enter the repo.

    ingest_unpaired.py [--fetch] [--limit N]

Measurement is identical to tools/fringe_unpaired.py — median per-column (garment tip − first fringe row) divided by
waistband width — so samples from both channels are commensurable. Writes data/priors/fringe_unpaired_web.json and
prints a yield table. Merge into the prior with fit_fringe.py.
"""
import argparse, json, os, sys, hashlib, urllib.parse, urllib.request, statistics as st
from pathlib import Path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import numpy as np, cv2

ROOT = Path(__file__).resolve().parents[1]
CAND = ROOT / "data/external/unpaired_candidates.jsonl"
IMG = ROOT / "data/external/unpaired_images"
OUT = ROOT / "data/priors/fringe_unpaired_web.json"
UA = "denim-twin-research-harvester/0.1 (jefferyh619@gmail.com; academic garment dataset; https://github.com/jefferyjefe/denim-twin)"
REQUIRED = ("page_url", "image_url", "license_or_terms", "state_evidence", "hem_finish")

def validate(rec):
    """Return None if usable, else the reason it is refused."""
    for k in REQUIRED:
        if not str(rec.get(k, "")).strip(): return f"missing_{k}"
    if rec.get("hem_finish") != "frayed": return f"hem_finish={rec.get('hem_finish')}"
    ev = rec["state_evidence"].strip()
    if len(ev) < 12: return "state_evidence_too_short"      # must be a real sentence from the page, not a label
    stems = ("wash", "dryer", "dried", "laundr", "lav", "wasch", "wäsche", "lessive", "bucato", "tvätt", "tvatt", "vask", "pesu")   # en/de/fr/es/it/sv/da/no/fi
    if not any(w in ev.lower() for w in stems):
        return "state_evidence_does_not_mention_a_wash"
    if not urllib.parse.urlparse(rec["image_url"]).scheme.startswith("http"): return "image_url_not_http"
    return None

def fname(rec):
    ext = os.path.splitext(urllib.parse.urlparse(rec["image_url"]).path)[1].lower()
    if ext not in (".jpg", ".jpeg", ".png", ".webp"): ext = ".jpg"
    return f"{hashlib.sha1(rec['image_url'].encode()).hexdigest()[:10]}{ext}"

def fetch(rec):
    IMG.mkdir(parents=True, exist_ok=True); p = IMG / fname(rec)
    if p.exists() and p.stat().st_size > 1000: return p
    req = urllib.request.Request(rec["image_url"], headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r: data = r.read()
    if len(data) < 5000: raise ValueError(f"suspiciously small download ({len(data)} bytes)")
    p.write_bytes(data); return p

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fetch", action="store_true", help="download the images (research use, kept out of git)")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    if not CAND.exists(): print(f"no candidates file at {CAND}"); return 1
    recs = [json.loads(l) for l in CAND.read_text().splitlines() if l.strip()]
    seen = set(); uniq = []
    for r in recs:
        if r.get("image_url") in seen: continue
        seen.add(r.get("image_url")); uniq.append(r)
    if a.limit: uniq = uniq[:a.limit]
    from denimtwin.seg.sam import SamSegmenter, segment_garment_coarse
    from denimtwin.canon.autolm import landmarks_from_mask
    seg = SamSegmenter(); out = []
    for rec in uniq:
        base = {"pair": hashlib.sha1(rec["page_url"].encode()).hexdigest()[:10],   # same id as pairs.jsonl: a page in
                "page_url": rec["page_url"], "image_url": rec["image_url"],        # both channels must exclude as one
                "license_or_terms": rec.get("license_or_terms"), "state_evidence": rec.get("state_evidence"),
                "source": "web_unpaired"}
        why = validate(rec)
        if why: out.append({**base, "status": why}); print(f"REFUSED {why}: {rec.get('page_url','?')[:60]}"); continue
        if not a.fetch: out.append({**base, "status": "not_fetched"}); continue
        try: p = fetch(rec)
        except Exception as e: out.append({**base, "status": f"download_failed: {type(e).__name__}"}); print("download failed:", rec["image_url"][:70]); continue
        img = cv2.imread(str(p))
        if img is None: out.append({**base, "status": "unreadable"}); continue
        if min(img.shape[:2]) < 500: out.append({**base, "status": f"too_small_{img.shape[1]}x{img.shape[0]}"}); continue
        m, sc, info = segment_garment_coarse(seg, img)
        if m is None: out.append({**base, "status": "segmentation_failed"}); continue
        lm, conf = landmarks_from_mask(m)
        if "waist_left" not in lm or "waist_right" not in lm: out.append({**base, "status": "no_waist_landmarks"}); continue
        ww = abs(lm["waist_right"][0] - lm["waist_left"][0])
        from denimtwin.eval.fringe_measure import measure_fringe_depth
        r_ = measure_fringe_depth(img, m, waist_px=ww)     # EXP_0015: SAM's prompted fringe mask returns fabric
        if not r_["ok"]: out.append({**base, "status": "no_fringe_columns"}); continue
        d = float(r_["median_px"]); rel = float(r_["depth_rel"])
        ys = np.nonzero(m.any(axis=1))[0]; gh = ys.max() - ys.min()
        bad = None
        if conf.get("garment_type") != "shorts": bad = f"not_shorts ({conf.get('garment_type')})"
        elif ww < 0.3 * m.shape[1]: bad = "waist_too_narrow_for_frame"
        elif d > 0.15 * gh: bad = "depth_implausible_vs_height"
        elif rel > 0.5: bad = "depth_implausible"
        out.append({**base, "status": "ok" if bad is None else bad, "file": p.name, "waist_px": int(ww),
                    "depth_px": d, "depth_rel": rel, "coverage": round(r_["coverage"], 3), "method": "direct", "garment": conf.get("garment_type"), "sam_score": round(float(sc), 3)})
        print(f"{'OK ' if bad is None else 'REJ'} {p.name} waist {ww:4d}px depth {d:6.1f}px rel {rel:.3f} {bad or ''}")
    ok = [o for o in out if o["status"] == "ok"]
    res = {"n": len(ok), "depth_rel_mean": st.mean([o["depth_rel"] for o in ok]) if ok else None,
           "depth_rel_sd": st.pstdev([o["depth_rel"] for o in ok]) if len(ok) > 1 else None,
           "candidates": len(uniq), "samples": out}
    OUT.write_text(json.dumps(res, indent=1))
    from collections import Counter
    print(json.dumps({k: v for k, v in res.items() if k != "samples"}, indent=1))
    print("outcomes:", dict(Counter(o["status"].split(":")[0].split(" (")[0] for o in out)))
    return 0

if __name__ == "__main__": sys.exit(main())
