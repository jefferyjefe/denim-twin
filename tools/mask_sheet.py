#!/usr/bin/env python3
"""Contact sheets of the coarse garment mask over every harvested photo, for human verification (EXP_0018).

    mask_sheet.py [--out reports/masks] [--dir data/external/unpaired_images data/external/control_images]

Verdicts go in data/external/mask_verdicts.json; anything unverified is refused by the ingest path.
"""
import argparse, os, sys, glob
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "src"))
import numpy as np, cv2
from denimtwin.seg.sam import SamSegmenter, segment_garment_coarse

ap = argparse.ArgumentParser()
ap.add_argument("--out", default=str(ROOT / "reports/masks"))
ap.add_argument("--dir", nargs="*", default=[str(ROOT / "data/external/unpaired_images"), str(ROOT / "data/external/control_images")])
ap.add_argument("--per-sheet", type=int, default=4)
a = ap.parse_args(); os.makedirs(a.out, exist_ok=True)
files = [f for d in a.dir for f in sorted(glob.glob(os.path.join(d, "*"))) if os.path.isfile(f)]
seg = SamSegmenter(); tiles = []
for p in files:
    img = cv2.imread(p)
    if img is None: continue
    m, sc, info = segment_garment_coarse(seg, img)
    vis = img.copy()
    if m is not None: vis[m] = (0.55 * vis[m] + 0.45 * np.array([0, 0, 255])).astype(np.uint8)
    h = 300; vis = cv2.resize(vis, (int(vis.shape[1] * h / vis.shape[0]), h))
    cv2.putText(vis, f"{os.path.basename(p)[:10]} score={sc:.2f} area={0 if m is None else m.mean():.2f}",
                (6, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
    tiles.append(vis); print(os.path.basename(p), round(float(sc), 3))
if tiles:
    W = max(t.shape[1] for t in tiles)
    tiles = [cv2.copyMakeBorder(t, 0, 0, 0, W - t.shape[1], cv2.BORDER_CONSTANT, value=(255, 255, 255)) for t in tiles]
    for i in range(0, len(tiles), a.per_sheet):
        cv2.imwrite(f"{a.out}/sheet_{i // a.per_sheet}.jpg", np.concatenate(tiles[i:i + a.per_sheet], 0))
    print(f"wrote {(len(tiles) + a.per_sheet - 1) // a.per_sheet} sheets to {a.out}")
