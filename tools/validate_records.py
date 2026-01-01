#!/usr/bin/env python3
"""Validate every data/garments/*/record.json against the schema and sanity checks."""
import json, sys
from pathlib import Path
import jsonschema

ROOT = Path(__file__).resolve().parents[1]
schema = json.loads((ROOT / "data/schemas/garment.schema.json").read_text())
bad = 0
for rec_path in sorted(ROOT.glob("data/garments/DENIM_*/record.json")):
    rec = json.loads(rec_path.read_text())
    errs = [e.message for e in jsonschema.Draft202012Validator(schema).iter_errors(rec)]
    if rec["garment_id"] != rec_path.parent.name:
        errs.append("garment_id does not match directory name")
    oi, ti = rec.get("original_inseam_cm"), rec.get("target_inseam_cm")
    if oi is not None and ti is not None and ti >= oi:
        errs.append("target_inseam must be shorter than original_inseam")
    for p in rec.get("before_image_paths", []) + rec.get("post_wash_image_paths", []):
        if not (rec_path.parent / p).exists():
            errs.append(f"missing image: {p}")
    if errs:
        bad += 1
        print(f"{rec['garment_id']}:")
        for e in errs: print("   -", e)
    else:
        print(f"{rec['garment_id']}: ok")
sys.exit(1 if bad else 0)
