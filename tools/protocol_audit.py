#!/usr/bin/env python3
"""Protocol-drift audit (deterministic part). Prints findings; exit 1 if any 'HARD' finding."""
import json, os, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from denimtwin.pilot import protocol_fields as PROTOFIELDS
proto = (ROOT / "protocol/PROTOCOL.md").read_text()
# The regex this used to use required a backtick either side of the bracket, so it missed every
# field written `[FILL] cm` / `[FILL] ml` / `[FILL] hours` / `[FILL] min` / `[FILL] mm` -- six of
# them -- and counted two sentences of prose that merely mention the convention. It reported 15
# where there are 19. That matters for the HARD rule below, which fires on `if fills`: filling
# only the visible ones emptied the list while the mount height, the water temperature, the
# detergent volume, the dryer setting, the conditioning period and the thread-count window were
# all still open, and the one guard standing between the pilot and an undecided protocol stopped
# firing exactly there. See src/denimtwin/pilot/protocol_fields.py.
# `hard` and `soft` are bound BEFORE the first finding, not after it. They used to be bound three
# lines further down, below the `if unknown:` block -- so the one finding that block can produce
# was an append to a name that did not exist yet, and the audit died with a NameError at exactly
# the moment it had something HARD to say. The trigger is the ordinary act the owner-decision packet
# asks for: add a [FILL] field to PROTOCOL.md. Every other path through this file left `unknown`
# empty, so the crash was unreachable until the guard was needed, which is the shape of defect the
# adversarial rounds keep finding.
hard, soft = [], []
classified = PROTOFIELDS.classify(proto)
fills = [f["raw"] for f in classified]
unknown = [f for f in classified if f["coverage"] is None]
if unknown:
    hard.append("PROTOCOL.md has %d [FILL] field(s) protocol_fields.COVERAGE does not classify "
                "(line(s) %s); the audit cannot say whether they block."
                % (len(unknown), ", ".join(str(f["line"]) for f in unknown)))
if fills:
    counts = PROTOFIELDS.summary(proto)
    soft.append(f"{len(fills)} unfilled [FILL] fields in PROTOCOL.md "
                f"(answered per garment: {counts['session']} by the session freeze, "
                f"{counts['wash']} by the wash record, {counts['cut']} by the cut record; "
                f"{counts['open']} answered by nothing and standing open)")
    for f in classified:
        if f["coverage"] == "open":
            soft.append(f"PROTOCOL.md:{f['line']} {f['raw']} is not answered by any per-garment "
                        f"record: {f['context'][:70]}")
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
