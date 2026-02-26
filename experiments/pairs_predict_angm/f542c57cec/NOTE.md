# PREDICTION — before_used.png

**This is a prediction, not a measurement.** No after-photo exists for this garment.

- cut: inseam fraction **0.000**, angle -34.4° — removes 22% of the garment
- state: **after_wash**, wash preset 'none'
- scale: **unknown** — every length below is in pixels
- fringe depth: **52.6 px** (80% interval 41.4–63.8 px) from prior[after_wash] n=3 — INSUFFICIENT (<5 samples): treat as a placeholder
- interval calibration: **not established** (EXP_0009 coverage 0/10) — read the range as a spread, not a guarantee

flags: mask score 0.974, area 0.47 of frame; landmark heuristic calls this 'shorts', not full-length jeans: a shorter->shorter cut; angled cut -34.4°: inner fraction 0.000, outer 0.081; fringe prior has only n=3 samples: the depth below is not yet evidence-backed

| file | what |
|---|---|
| `panel.jpg` | before + the three predictions side by side |
| `pred_median.png` | the central prediction |
| `pred_conservative.png` / `pred_aggressive.png` | the ends of the fringe interval |
| `diff.png` | exactly which pixels the system changed (§4.8) |
| `modification.json` | the modification as structured parameters (§4.5) |
| `prediction.json` | machine-readable prediction + provenance |

Outside the cut region, 0.2% of kept pixels differ from the input photo (a strict pixel copy: only the abraded band at the cut edge).
