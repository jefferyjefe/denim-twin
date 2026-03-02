#!/usr/bin/env python3
"""EXP_0016 — at what image resolution does a fringe measurement start to mean anything?

EXP_0015 established that at flat-lay resolution our fringe depth cannot tell a cuffed hem from a frayed one. That is a
statement about a mixture of resolutions (waist 191–2801 px). This measures the dependence directly: the SAME photos,
re-segmented and re-measured at decreasing scale, split into

  * FRAYED  — raw cut edges that were washed (the thing we want to measure), and
  * CONTROL — cuffed/hemmed garments, which have no fringe, so anything measured on them is the method's floor.

The output is the number a contributor needs: the fringe must span at least N pixels for the measurement to separate
frayed from finished. Everything is re-run per scale (segmentation included), because the dominant error — the garment
mask sitting a few pixels inside the true fabric edge — is itself resolution dependent.

    experiment_resolution.py [--out experiments/EXP_0016_resolution_threshold]
"""
import argparse, json, os, sys, glob, hashlib
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import numpy as np, cv2

ap = argparse.ArgumentParser()
ap.add_argument("--out", default=str(ROOT / "experiments/EXP_0016_resolution_threshold"))
ap.add_argument("--scales", default="1.0,0.7,0.5,0.35,0.25,0.15")
a = ap.parse_args(); os.makedirs(a.out, exist_ok=True)
SCALES = [float(x) for x in a.scales.split(",")]

from denimtwin.seg.sam import SamSegmenter, segment_garment_coarse
from denimtwin.canon.autolm import landmarks_from_mask
from denimtwin.eval.fringe_measure import measure_fringe_depth
from denimtwin.eval.hem_texture import hem_roughness

RECS = {hashlib.sha1(json.loads(l)["page_url"].encode()).hexdigest()[:10]: json.loads(l)
        for l in (ROOT / "data/external/pairs.jsonl").read_text().splitlines() if l.strip()}

def subjects():
    """(id, group, path). Only photos big enough that downscaling has room to say something."""
    for f in sorted(glob.glob(str(ROOT / "experiments/pairs/*/after_used.png"))):
        pid = Path(f).parent.name
        if "rejected" in (Path(f).parent / "NOTE.md").read_text().splitlines()[0]: continue
        hf = RECS.get(pid, {}).get("hem_finish")
        if hf == "frayed": g = "frayed"
        elif hf in ("cuffed", "hemmed", "serged"): g = "control"
        else: continue
        im = cv2.imread(f)
        if im is None or min(im.shape[:2]) < 400: continue
        yield f"pair:{pid}", g, f
    web = ROOT / "data/priors/fringe_unpaired_web.json"
    if web.exists():
        for s in json.load(open(web))["samples"]:
            if s.get("status") == "ok" and s.get("file"):
                yield f"web:{s['file'][:8]}", "frayed", str(ROOT / "data/external/unpaired_images" / s["file"])

seg = SamSegmenter(); rows = []
for sid, group, path in subjects():
    img0 = cv2.imread(path)
    for s in SCALES:
        img = img0 if s == 1.0 else cv2.resize(img0, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
        if min(img.shape[:2]) < 120: continue
        m, sc, info = segment_garment_coarse(seg, img)
        if m is None: rows.append(dict(id=sid, group=group, scale=s, status="seg_failed")); continue
        lm, conf = landmarks_from_mask(m)
        if "waist_left" not in lm: rows.append(dict(id=sid, group=group, scale=s, status="no_waist")); continue
        ww = abs(lm["waist_right"][0] - lm["waist_left"][0])
        r = measure_fringe_depth(img, m, waist_px=ww)
        g_ = hem_roughness(m, waist_px=ww)
        rows.append(dict(id=sid, group=group, scale=s, status="ok", waist_px=int(ww), width_px=img.shape[1],
                         depth_px=r["median_px"], depth_rel=r.get("depth_rel"), coverage=round(r["coverage"], 3),
                         rough_p90_px=g_["p90_px"], rough_mean_px=g_["mean_px"], rough_ok=g_["ok"],
                         garment=conf.get("garment_type")))
        print(f"{sid:22s} {group:8s} s={s:4.2f} waist={int(ww):5d} depth={r['median_px']:6.1f}px rel={r.get('depth_rel', 0):.4f} rough_p90={g_['p90_px']:5.1f}px")
json.dump(rows, open(f"{a.out}/rows.json", "w"), indent=1)

ok = [r for r in rows if r.get("status") == "ok"]
md = "# EXP_0016 — resolution dependence of the fringe measurement\n\n"
md += "| scale | frayed n | frayed mean depth_rel | control n | control mean depth_rel | separation |\n|---|---|---|---|---|---|\n"
for s in SCALES:
    fr = [r["depth_rel"] for r in ok if r["scale"] == s and r["group"] == "frayed"]
    ct = [r["depth_rel"] for r in ok if r["scale"] == s and r["group"] == "control"]
    if not fr or not ct: continue
    sep = np.mean(fr) - np.mean(ct)
    md += f"| {s:.2f} | {len(fr)} | {np.mean(fr):.4f} | {len(ct)} | {np.mean(ct):.4f} | {sep:+.4f} |\n"
md += "\n| scale | frayed mean depth px | control mean depth px | ratio |\n|---|---|---|---|\n"
for s in SCALES:
    fr = [r["depth_px"] for r in ok if r["scale"] == s and r["group"] == "frayed"]
    ct = [r["depth_px"] for r in ok if r["scale"] == s and r["group"] == "control"]
    if not fr or not ct: continue
    md += f"| {s:.2f} | {np.mean(fr):.1f} | {np.mean(ct):.1f} | {np.mean(fr) / max(np.mean(ct), 1e-6):.2f} |\n"
md += "\n## Hem roughness (eval/hem_texture.py) — the alternative observable\n\n"
md += "| scale | frayed n | frayed p90 px | frayed p90>0 | control n | control p90 px | control p90>0 |\n|---|---|---|---|---|---|---|\n"
for s in SCALES:
    fr = [r for r in ok if r["scale"] == s and r["group"] == "frayed" and r.get("rough_ok")]
    ct = [r for r in ok if r["scale"] == s and r["group"] == "control" and r.get("rough_ok")]
    if not fr or not ct: continue
    md += (f"| {s:.2f} | {len(fr)} | {np.mean([r['rough_p90_px'] for r in fr]):.2f} | "
           f"{sum(1 for r in fr if r['rough_p90_px'] > 0)}/{len(fr)} | {len(ct)} | "
           f"{np.mean([r['rough_p90_px'] for r in ct]):.2f} | {sum(1 for r in ct if r['rough_p90_px'] > 0)}/{len(ct)} |\n")
open(f"{a.out}/TABLE.md", "w").write(md); print("\n" + md)
