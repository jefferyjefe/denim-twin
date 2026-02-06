#!/usr/bin/env python3
"""Scale-free fringe depth from UNPAIRED after-wash photos of cut-off shorts.
For every after_wash image in the manifest (whole-garment tag), run the coarse garment pick, SAM fringe segmentation,
per-column edge (first fringe row) / tip (last garment row), and report median depth / waist width.
Writes data/priors/fringe_unpaired.json. Complements fit_fringe.py (paired) for the depth prior."""
import json, hashlib, os, sys, urllib.parse, statistics as st
from pathlib import Path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import numpy as np, cv2
from denimtwin.seg.sam import SamSegmenter, segment_garment_coarse, segment_fringe
from denimtwin.canon.autolm import landmarks_from_mask
ROOT = Path(__file__).resolve().parents[1]; IMG = ROOT / "data/external/pair_images"
recs = [json.loads(l) for l in (ROOT / "data/external/pairs.jsonl").read_text().splitlines() if l.strip()]
val = {v["page_url"]: v for v in (json.loads(l) for l in (ROOT / "data/external/pairs_validation.jsonl").read_text().splitlines() if l.strip())}
seg = SamSegmenter(); out = []
for r in recs:
    pid = hashlib.sha1(r["page_url"].encode()).hexdigest()[:10]; v = val.get(r["page_url"])
    for im in r["images"]:
        if im["role"] != "after_wash": continue
        f = f"{pid}_{im['role']}_{hashlib.sha1(im['url'].encode()).hexdigest()[:8]}{os.path.splitext(urllib.parse.urlparse(im['url']).path)[1] or '.jpg'}"
        tag = next((t.get("tag") for t in (v["images"] if v else []) if t.get("file") == f), None)
        if tag != "whole_garment_flat" or not (IMG / f).exists(): continue
        img = cv2.imread(str(IMG / f))
        if im.get("crop"): h, w = img.shape[:2]; x0, y0, x1, y1 = im["crop"]; img = img[int(y0 * h):int(y1 * h), int(x0 * w):int(x1 * w)]
        m, sc, info = segment_garment_coarse(seg, img)
        if m is None: continue
        lm, conf = landmarks_from_mask(m); ww = abs(lm["waist_right"][0] - lm["waist_left"][0])
        fr = segment_fringe(seg, img, m)
        if fr is None or fr.sum() < 50: out.append(dict(pair=pid, file=f, status="no_fringe_mask")); continue
        depths = []
        for x in range(m.shape[1]):
            t = np.nonzero(m[:, x])[0]; fcol = np.nonzero(fr[:, x])[0]
            if len(t) and len(fcol): depths.append(t.max() - fcol.min())
        if len(depths) < 20: out.append(dict(pair=pid, file=f, status="too_few_columns")); continue
        d = float(np.median(depths)); out.append(dict(pair=pid, file=f, status="ok", waist_px=ww, depth_px=d, depth_rel=d / ww, garment=conf.get("garment_type"), sam_score=round(sc, 3)))
        print(f"{pid} {f[:40]:40s} waist {ww:4d}px depth {d:5.1f}px rel {d/ww:.3f}")
ok = [o for o in out if o["status"] == "ok"]
res = dict(n=len(ok), depth_rel_mean=st.mean([o["depth_rel"] for o in ok]) if ok else None, depth_rel_sd=st.pstdev([o["depth_rel"] for o in ok]) if len(ok) > 1 else None, samples=out)
(ROOT / "data/priors/fringe_unpaired.json").write_text(json.dumps(res, indent=1)); print(json.dumps({k: v for k, v in res.items() if k != "samples"}))
