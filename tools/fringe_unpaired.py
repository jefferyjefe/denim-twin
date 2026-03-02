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
from denimtwin.eval.fringe_measure import measure_fringe_depth   # EXP_0015: SAM's fringe mask returns fabric
ROOT = Path(__file__).resolve().parents[1]; IMG = ROOT / "data/external/pair_images"
recs = [json.loads(l) for l in (ROOT / "data/external/pairs.jsonl").read_text().splitlines() if l.strip()]
EXCL = {l.split()[0] for l in (ROOT / "data/priors/exclude.txt").read_text().splitlines() if l.strip() and not l.startswith("#")} if (ROOT / "data/priors/exclude.txt").exists() else set()
val = {v["page_url"]: v for v in (json.loads(l) for l in (ROOT / "data/external/pairs_validation.jsonl").read_text().splitlines() if l.strip())}
seg = SamSegmenter(); out = []
for r in recs:
    pid = hashlib.sha1(r["page_url"].encode()).hexdigest()[:10]; v = val.get(r["page_url"])
    if pid in EXCL: continue                                             # exclude.txt applies to the unpaired pool too
    pn = ROOT / "experiments/pairs" / pid / "NOTE.md"
    if pn.exists() and not pn.read_text().splitlines()[0].startswith("# PAIR — rejected"): out.append(dict(pair=pid, status="paired_elsewhere")); continue   # its after-photo is already a paired sample
    for im in r["images"]:
        if im["role"] != "after_wash": continue
        # the thesis is ONE wash on a RAW cut edge: a photo after several washes, or of a hem whose finish is not
        # evidenced as frayed, is a different quantity and must not enter the prior (review 5, finding 10)
        note = (im.get("note") or "").lower()
        if any(w in note for w in ("several wash", "second wash", "third wash", "multiple wash", "each wash", "washes")):
            out.append(dict(pair=pid, file=None, status="more_than_one_wash", note=im.get("note"))); continue
        finish = r.get("hem_finish")
        if finish != "frayed" and "fray" not in note:
            out.append(dict(pair=pid, file=None, status="hem_finish_not_evidenced_as_frayed", note=im.get("note"))); continue
        f = f"{pid}_{im['role']}_{hashlib.sha1(im['url'].encode()).hexdigest()[:8]}{os.path.splitext(urllib.parse.urlparse(im['url']).path)[1] or '.jpg'}"
        tag = next((t.get("tag") for t in (v["images"] if v else []) if t.get("file") == f), None)
        if tag != "whole_garment_flat" or not (IMG / f).exists(): continue
        img = cv2.imread(str(IMG / f))
        if im.get("crop"): h, w = img.shape[:2]; x0, y0, x1, y1 = im["crop"]; img = img[int(y0 * h):int(y1 * h), int(x0 * w):int(x1 * w)]
        m, sc, info = segment_garment_coarse(seg, img)
        if m is None: continue
        lm, conf = landmarks_from_mask(m); ww = abs(lm["waist_right"][0] - lm["waist_left"][0])
        r_ = measure_fringe_depth(img, m, waist_px=ww)
        if not r_["ok"]: out.append(dict(pair=pid, file=f, status="no_fringe_columns")); continue
        d = float(r_["median_px"]); rel = float(r_["depth_rel"])
        bad = None
        if conf.get("garment_type") != "shorts": bad = "not_shorts"
        elif ww < 0.3 * m.shape[1]: bad = "waist_too_narrow_for_frame"      # close-ups / partial garments
        elif rel > 0.5: bad = "depth_implausible"                            # worn shots, mis-segmentation
        out.append(dict(pair=pid, file=f, status="ok" if bad is None else bad, waist_px=ww, depth_px=d, depth_rel=rel, coverage=round(r_["coverage"], 3), method="direct", garment=conf.get("garment_type"), sam_score=round(sc, 3)))
        print(f"{pid} {f[:40]:40s} waist {ww:4d}px depth {d:5.1f}px rel {d/ww:.3f}")
ok = [o for o in out if o["status"] == "ok"]
res = dict(n=len(ok), depth_rel_mean=st.mean([o["depth_rel"] for o in ok]) if ok else None, depth_rel_sd=st.pstdev([o["depth_rel"] for o in ok]) if len(ok) > 1 else None, samples=out)
(ROOT / "data/priors/fringe_unpaired.json").write_text(json.dumps(res, indent=1)); print(json.dumps({k: v for k, v in res.items() if k != "samples"}))
