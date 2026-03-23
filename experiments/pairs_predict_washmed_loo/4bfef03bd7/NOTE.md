# PREDICTION — before_native.png

**This is a prediction, not a measurement.** No after-photo exists for this garment.

- cut: inseam fraction **0.000** — removes 64% of the garment
- state: **after_wash**, wash preset 'median'
- scale: **unknown** — every length below is in pixels
- fringe depth: **3.4 px** (80% interval 3.4–3.4 px) from prior[after_wash] n=1 after excluding self — UNVALIDATED — EXP_0015/0016 and review 5: the direct measurement returns garment-mask boundary error, displaced drop shadows and mottled backdrops as 'fringe' with full coverage, and cannot separate a cuffed hem from a frayed one. Rows carry both the rule-adjusted depth and the raw measurement (depth_*_measured) so the difference is visible. Do not fit anything to them.
- interval calibration: **not established** (EXP_0009 coverage 0/10) — read the range as a spread, not a guarantee
- fringe depth provenance: **no validated measurement exists** (EXP_0015) — the number above is a placeholder and the
  three renders differ only in a quantity nobody has yet measured on real garments

flags: mask score 0.991, area 0.55 of frame; mask chosen by SAM's own score, which does not detect a confidently wrong object (EXP_0018 found a back pocket returned at 0.906): look at diff.png, or use --seg consensus; rotated 0.5° to upright; wash 'median': shrink 2.0% along / 1.0% across, hem roll 5 px — with no metric scale the roll width parameter is applied as pixels, so it is NOT a physical width — PRIOR values, not measured (EXP_0013); the prior for 'after_wash' rests on 1 sample(s); fringe depth is a PLACEHOLDER, not an estimate: EXP_0015/0016 and review 5: the direct measurement returns garment-mask boundary error, displaced drop shadows and mottled backdrops as 'fringe' with full coverage, and cannot separate a cuffed hem from a frayed one. Rows carry both the rule-adjusted depth and the raw measurement (depth_*_measured) so the difference is visible. Do not fit anything to them.; the only sourced fray depth we have is 12.7 mm — itsalwaysautumn.com frayed method: a straight stitch is sewn 1/2 in (12.7 mm) above the raw cut edge before washing, and after ONE wash/dry the page states the fray 'formed up to stitch line'. Caveat: the fray was ARRESTED by the stitching, so 12.7 mm is what one wash reached against a stop, not a free fray depth; and it is one garment, one fabric, one machine.; fringe prior has only n=1 samples: the depth below is not yet evidence-backed; fringe depth 3.4 px is below the renderer's resolution: the three renders differ by less than a pixel of fringe and must not be read as an interval (EXP_0015 — the depth itself is a placeholder)

| file | what |
|---|---|
| `panel.jpg` | before + the three predictions side by side |
| `pred_median.png` | the central prediction |
| `pred_conservative.png` / `pred_aggressive.png` | the ends of the fringe interval |
| `diff.png` | exactly which pixels the system changed (§4.8) |
| `modification.json` | the modification as structured parameters (§4.5) |
| `prediction.json` | machine-readable prediction + provenance |

Outside the cut region, 52.1% of kept pixels differ from the input photo (the wash model's shrink, hem roll and dye loss — set `--wash none` for a strict pixel copy).
