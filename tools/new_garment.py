#!/usr/bin/env python3
"""Create the next DENIM_NNNN garment record and directory layout."""
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GARMENTS = ROOT / "data" / "garments"
STATES = ["before", "marked", "immediate_after", "post_wash"]

def next_id():
    ids = [int(m.group(1)) for p in GARMENTS.iterdir()
           if (m := re.fullmatch(r"DENIM_(\d{4})", p.name))]
    return f"DENIM_{(max(ids) + 1) if ids else 1:04d}"

def main():
    gid = next_id()
    d = GARMENTS / gid
    for s in STATES:
        (d / "images" / s).mkdir(parents=True)
    for sub in ("masks", "landmarks", "measurements", "meshes", "renders"):
        (d / sub).mkdir()
    record = {
        "garment_id": gid, "protocol_version": "0.1",
        "acquisition_source": "", "acquisition_price_usd": None, "brand_optional": None,
        "garment_style": "other", "wash_shade": "other",
        "fiber_composition": "", "elastane_percentage": 0,
        "mass_grams": None, "fabric_thickness_mm": None, "waist_cm": None,
        "front_rise_cm": None, "leg_opening_cm": None,
        "original_inseam_cm": None, "target_inseam_cm": None,
        "cut_path_coordinates": None, "cut_tool": None, "cut_operator": None,
        "cut_legs_together": False, "wash": None,
        "capture_device": None, "capture_calibration": None,
        "before_image_paths": [], "marked_image_paths": [],
        "immediate_after_image_paths": [], "post_wash_image_paths": [],
        "segmentation_masks": [], "landmarks": None,
        "existing_damage_annotations": [], "fray_measurements": None,
        "quality_flags": [], "protocol_deviations": [],
        "dataset_split": "unassigned",
    }
    (d / "record.json").write_text(json.dumps(record, indent=2) + "\n")
    (d / "images" / ".gitkeep").touch()
    print(gid)

if __name__ == "__main__":
    main()
