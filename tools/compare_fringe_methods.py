#!/usr/bin/env python3
"""SAM-prompted fringe mask vs direct thread measurement, on every after-wash photo we hold (EXP_0015).

The fringe prior is built from SAM's fringe mask. That mask is what `run_pair` has to gate as implausible, and on the
harvested unpaired photos it returns fabric, not threads. This scores both methods on the same images and writes a QA
contact sheet so the numbers can be checked by eye rather than trusted.

    compare_fringe_methods.py [--out reports/fringe_methods]
"""
import argparse, json, os, sys, glob, hashlib, urllib.parse
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import numpy as np, cv2

ap = argparse.ArgumentParser()
ap.add_argument("--out", default=str(ROOT / "reports/fringe_methods"))
a = ap.parse_args(); os.makedirs(a.out, exist_ok=True)

from denimtwin.seg.sam import SamSegmenter, segment_garment_coarse, segment_fringe
from denimtwin.canon.autolm import landmarks_from_mask
from denimtwin.eval.fringe_measure import measure_fringe_depth

def sources():
    """(label, image path) for every after-wash whole-garment photo: harvested unpaired + the paired after-photos."""
    web = ROOT / "data/priors/fringe_unpaired_web.json"
    if web.exists():
        for s in json.load(open(web))["samples"]:
            if s.get("file"): yield f"web:{s['file'][:8]}", str(ROOT / "data/external/unpaired_images" / s["file"])
    for d in sorted(glob.glob(str(ROOT / "experiments/pairs/*/after_used.png"))):
        pid = Path(d).parent.name
        note = (Path(d).parent / "NOTE.md")
        if note.exists() and "rejected" in note.read_text().splitlines()[0]: continue
        mod = Path(d).parent / "modification.json"
        if mod.exists() and json.load(open(mod)).get("wash", {}).get("cycles", 0) < 1: continue   # after_cut only
        if pid in EXCL: continue          # exclude.txt applies here too (review 5, finding 4)
        yield f"pair:{pid}", d

EXCL = {l.split()[0] for l in (ROOT / "data/priors/exclude.txt").read_text().splitlines()
        if l.strip() and not l.startswith("#")} if (ROOT / "data/priors/exclude.txt").exists() else set()
seg = SamSegmenter(); rows = []; tiles = []
for label, path in sources():
    img = cv2.imread(path)
    if img is None: continue
    m, sc, info = segment_garment_coarse(seg, img)
    if m is None: rows.append({"id": label, "status": "segmentation_failed"}); continue
    lm, conf = landmarks_from_mask(m)
    if "waist_left" not in lm: rows.append({"id": label, "status": "no_waist"}); continue
    ww = abs(lm["waist_right"][0] - lm["waist_left"][0])
    ys = np.nonzero(m.any(axis=1))[0]; gh = int(ys.max() - ys.min())
    # method A: SAM-prompted fringe mask (what the prior currently uses)
    fr = segment_fringe(seg, img, m); a_rel = a_px = None; a_note = "no mask"
    if fr is not None and fr.sum() > 50:
        ds = [np.nonzero(m[:, x])[0].max() - np.nonzero(fr[:, x])[0].min() for x in range(m.shape[1]) if m[:, x].any() and fr[:, x].any()]
        if len(ds) >= 20:
            a_px = float(np.median(ds)); a_rel = a_px / ww
            a_note = "implausible (>15% of garment height)" if a_px > 0.15 * gh else "ok"
    # method B: direct thread measurement
    b = measure_fringe_depth(img, m, waist_px=ww, return_mask=True)
    rows.append({"id": label, "status": "ok", "garment": conf.get("garment_type"), "waist_px": int(ww), "garment_h_px": gh,
                 "sam_px": a_px, "sam_rel": a_rel, "sam_note": a_note,
                 "direct_px": b["median_px"], "direct_rel": b.get("depth_rel"), "direct_coverage": round(b["coverage"], 3),
                 "direct_ok": b["ok"]})
    vis = img.copy()
    if fr is not None: vis[fr] = (0.35 * vis[fr] + 0.65 * np.array([255, 0, 255])).astype(np.uint8)   # SAM: magenta
    vis[b["mask"]] = (0, 255, 255)                                                                     # direct: yellow
    h = 420; vis = cv2.resize(vis, (int(vis.shape[1] * h / vis.shape[0]), h))
    cv2.putText(vis, f"{label} SAM {a_rel if a_rel is None else round(a_rel,3)} / direct {round(b.get('depth_rel',0),3)}",
                (8, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
    tiles.append(vis)
    print(rows[-1])

if tiles:
    w = max(t.shape[1] for t in tiles)
    tiles = [cv2.copyMakeBorder(t, 0, 0, 0, w - t.shape[1], cv2.BORDER_CONSTANT, value=(255, 255, 255)) for t in tiles]
    for i in range(0, len(tiles), 4):
        cv2.imwrite(f"{a.out}/sheet_{i // 4}.jpg", np.concatenate(tiles[i:i + 4], 0))
json.dump(rows, open(f"{a.out}/methods.json", "w"), indent=1)
ok = [r for r in rows if r.get("status") == "ok"]
md = "| photo | garment | waist px | SAM rel | SAM verdict | direct rel | coverage |\n|---|---|---|---|---|---|---|\n"
for r in ok:
    sam = "—" if r["sam_rel"] is None else f"{r['sam_rel']:.3f}"
    md += f"| {r['id']} | {r['garment']} | {r['waist_px']} | {sam} | {r['sam_note']} | {r['direct_rel']:.3f} | {r['direct_coverage']:.2f} |\n"
open(f"{a.out}/README.md", "w").write(md)
print(md)
