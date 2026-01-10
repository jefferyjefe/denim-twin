#!/usr/bin/env python3
"""Protocol-drift audit (deterministic part). Prints findings; exit 1 if any 'HARD' finding."""
import json, re, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
proto = (ROOT / "protocol/PROTOCOL.md").read_text()
fills = re.findall(r"`\[FILL[^\]]*\]`", proto)
hard, soft = [], []
if fills: soft.append(f"{len(fills)} unfilled [FILL] fields in PROTOCOL.md: " + ", ".join(sorted(set(fills))[:8]))
for rp in sorted(ROOT.glob("data/garments/DENIM_*/record.json")):
    r = json.loads(rp.read_text()); g = r["garment_id"]
    for k in ("waist_cm", "front_rise_cm", "original_inseam_cm", "leg_opening_cm", "thigh_cm", "mass_grams", "fabric_thickness_mm"):
        if r.get(k) is not None and not r.get("measurement_readings", {}).get(k):
            (soft if r.get("measurements_source") != "measured" else hard).append(f"{g}: {k}={r[k]} has no measurement_readings (source={r.get('measurements_source')})")
    if r.get("cut_path_coordinates") and not r.get("cut_path_frame"): hard.append(f"{g}: cut path without cut_path_frame")
    if r.get("immediate_after_image_paths") and not r.get("cut_tool"): hard.append(f"{g}: cut performed but cut_tool missing")
    if r.get("post_wash_image_paths") and not r.get("wash"): hard.append(f"{g}: post-wash images but no wash block")
    if r.get("post_wash_image_paths") and not r.get("fray_measurements"): soft.append(f"{g}: post-wash captured, fray not measured")
    if r.get("before_image_paths") and r.get("capture_mm_per_px") is None: hard.append(f"{g}: captures without capture_mm_per_px (board missing?)")
    if fills and (r.get("wash") or r.get("cut_tool")): hard.append(f"{g}: physical steps recorded while protocol has unfilled [FILL] fields")
for h in hard: print("HARD:", h)
for s in soft: print("soft:", s)
if not hard and not soft: print("protocol audit: clean")
sys.exit(1 if hard else 0)
