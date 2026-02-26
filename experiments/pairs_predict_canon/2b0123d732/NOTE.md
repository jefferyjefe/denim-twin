# PREDICTION — before_used.png

**This is a prediction, not a measurement.** No after-photo exists for this garment.

- cut: inseam fraction **0.461** — removes 38% of the garment
- state: **after_cut**
- scale: **unknown** — every length below is in pixels
- fringe depth: **0.0 px** (80% interval 0.0–0.0 px) from edge treatment 'raw' does not fray
- interval calibration: **not established** (EXP_0009 coverage 0/10) — read the range as a spread, not a guarantee

flags: mask score 0.955, area 0.36 of frame; rotated 24.3° to upright

| file | what |
|---|---|
| `panel.jpg` | before + the three predictions side by side |
| `pred_median.png` | the central prediction |
| `pred_conservative.png` / `pred_aggressive.png` | the ends of the fringe interval |
| `diff.png` | exactly which pixels the system changed (§4.8) |
| `modification.json` | the modification as structured parameters (§4.5) |
| `prediction.json` | machine-readable prediction + provenance |

Outside the cut region, 0.4% of kept pixels differ from the input photo (a strict pixel copy: only the abraded band at the cut edge).
