# PREDICTION — before_native.png

**This is a prediction, not a measurement.** No after-photo exists for this garment.

- cut: inseam fraction **0.068** — removes 60% of the garment
- state: **after_cut**
- scale: **unknown** — every length below is in pixels
- fringe depth: **0.0 px** (80% interval 0.0–0.0 px) from edge treatment 'raw' does not fray
- interval calibration: **not established** (EXP_0009 coverage 0/10) — read the range as a spread, not a guarantee
- fringe depth provenance: **no validated measurement exists** (EXP_0015) — the number above is a placeholder and the
  three renders differ only in a quantity nobody has yet measured on real garments

flags: mask score 0.994, area 0.46 of frame; mask chosen by SAM's own score, which does not detect a confidently wrong object (EXP_0018 found a back pocket returned at 0.906): look at diff.png, or use --seg consensus; rotated -1.9° to upright; legs reach the frame bottom: the original hem is out of frame, so an inseam fraction is measured against the frame, not the hem; fringe depth 0.0 px is below the renderer's resolution: the three renders differ by less than a pixel of fringe and must not be read as an interval (EXP_0015 — the depth itself is a placeholder)

| file | what |
|---|---|
| `panel.jpg` | before + the three predictions side by side |
| `pred_median.png` | the central prediction |
| `pred_conservative.png` / `pred_aggressive.png` | the ends of the fringe interval |
| `diff.png` | exactly which pixels the system changed (§4.8) |
| `modification.json` | the modification as structured parameters (§4.5) |
| `prediction.json` | machine-readable prediction + provenance |

Outside the cut region, 1.8% of kept pixels differ from the input photo (a strict pixel copy: only the abraded band at the cut edge).
