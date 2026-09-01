# EXP_0002 — Procedural raw edge v0 on a real photo (qualitative only)

**Date:** 2026-01-11  **Input:** Grailed 501 cutout (EXP_0001), SAM mask, hand landmarks, cut at 35% inseam.
**Scale:** no fiducial in this photo; mm_per_px=0.42 assumed for the demo. Backdrop recoloured grey so pale threads are visible.

## What v0 does (src/denimtwin/canon/rawedge.py)
Jagged edge (bites ≤ jag_mm) → abraded lighter band (edge_band_mm) → hanging weft threads (Gaussian length around fray_depth_mm, density threads_per_cm, 15% indigo warp). Three presets: conservative / median / aggressive. Deterministic per seed. Changes nothing further than band+jag inside the kept garment (tested).

## Honest read of rawedge_panel.jpg
- Reads as a cut denim hem; the three presets are visibly ordered.
- Real once-washed raw hems have a **dense, short, fuzzy fringe** (hundreds of ~2–5 mm weft ends per cm, tangled) plus curl; v0 draws sparse, long, individual threads. Density and length distribution are placeholders until Phase 5 fits them from measured fray data.
- No edge curl, no shadowing, no thread thickness variation, no lighter "bleed" into the fabric weave.
- Not validated against any real post-wash capture — this is a rendering, not a prediction, until DENIM_0001/0002 are cut and washed.

## Next
Register a real before/after pair, then fit fray_depth / density / band from measured hems (Phase 5 gate: beat the global-average fray depth).
