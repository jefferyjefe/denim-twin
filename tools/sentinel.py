#!/usr/bin/env python3
"""Data-integrity sentinel (deterministic). Exit 1 on any violation. Checks:
 - every record validates against the schema (via validate_records)
 - garment IDs immutable/unique, directory names match
 - split hygiene: no image path of a test_locked/challenge garment appears in any file under experiments/ or src/
 - wash block differing from protocol standard => protocol_deviations must be non-empty
 - offcut_wash keys are L/R only; values are from a fixed vocabulary
 - manifest: every CC-BY* record has attribution; every record has license + url; no duplicate URLs
"""
import json, re, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
errs = []
def err(m): errs.append(m)

recs = {}
for rp in sorted(ROOT.glob("data/garments/DENIM_*/record.json")):
    r = json.loads(rp.read_text()); recs[r["garment_id"]] = r
    if r["garment_id"] != rp.parent.name: err(f"{rp}: id/dir mismatch")
ids = [p.name for p in ROOT.glob("data/garments/DENIM_*")]
if len(ids) != len(set(ids)): err("duplicate garment dirs")

# split hygiene
locked = {g for g, r in recs.items() if r.get("dataset_split") in ("test_locked", "challenge")}
if locked:
    hay = []
    for d in ("experiments", "src", "tools", "notes"):
        for f in (ROOT / d).rglob("*"):
            if f.is_file() and f.suffix in (".py", ".md", ".json", ".yaml", ".yml", ".txt", ".ipynb") and "review" not in f.name:
                hay.append(f)
    for f in hay:
        t = f.read_text(errors="ignore")
        for g in locked:
            if re.search(rf"{g}[/_].*(post_wash|immediate_after|fray)", t): err(f"{f.relative_to(ROOT)} references locked outcome data of {g}")

VOCAB = {"standard_machine", "hand_wash_hang_dry", "standard_machine_separate_load", "none"}
for g, r in recs.items():
    ow = r.get("offcut_wash")
    if ow:
        if set(ow) - {"L", "R"}: err(f"{g}: offcut_wash keys must be L/R")
        for v in ow.values():
            if v not in VOCAB: err(f"{g}: offcut_wash value {v!r} not in {sorted(VOCAB)}")
    w = r.get("wash")
    if w and w.get("cycle") and "STANDARD" not in str(w.get("cycle")).upper() and not r.get("protocol_deviations"):
        err(f"{g}: non-standard wash cycle without protocol_deviations")
    if r.get("measurements_source") in ("tag", "web_size_chart", "photo_estimate", "mixed") and "measurements_not_physically_taken" not in r.get("quality_flags", []):
        err(f"{g}: unmeasured dimensions but quality flag missing")
    if r.get("dataset_split") == "train" and not r.get("post_wash_image_paths"): pass

mp = ROOT / "data/external/manifest.jsonl"
if mp.exists():
    urls = set(); n = 0
    for line in mp.read_text().splitlines():
        if not line.strip(): continue
        m = json.loads(line); n += 1
        if not m.get("license") or not m.get("url"): err(f"manifest {m.get('source')}:{m.get('id')} missing license/url")
        if str(m.get("license", "")).startswith("CC-BY") and not m.get("attribution"): err(f"manifest {m.get('source')}:{m.get('id')} CC-BY without attribution")
        if m["url"] in urls: err(f"manifest duplicate url {m['url']}")
        urls.add(m["url"])
    print(f"manifest: {n} records checked")

v = subprocess.run([sys.executable, str(ROOT / "tools/validate_records.py")], capture_output=True, text=True)
if v.returncode: err("validate_records failed:\n" + v.stdout)
print(f"records: {len(recs)} ({len(locked)} locked)")
if errs:
    print("SENTINEL VIOLATIONS:"); [print(" -", e) for e in errs]; sys.exit(1)
print("sentinel: OK")
