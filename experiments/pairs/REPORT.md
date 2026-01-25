# pairs: 2 (preset median)

| pair | reg resid | sil_iou_vs_real pred / crop / no-op | hem_chamfer pred / crop / no-op | dE_edge_band_vs_real pred / crop / no-op | fringe_iou_vs_real pred / crop / no-op | fringe_profile_dist pred / crop / no-op |
|---|---|---|---|---|---|---|
| 4bfef03bd7 | 11.1 | 0.79 / 0.79 / 0.35 | 25.03 / 24.63 / 458.16 | 22.52 / 22.65 / 24.91 | 0.03 / 0.00 / 0.00 | 0.00 / 0.00 / 1.00 |
| b630a78c19 | 9.5 | 0.88 / 0.88 / 0.73 | 58.05 / 60.24 / 141.83 | 13.65 / 13.68 / 12.53 | 0.10 / 0.00 / 0.11 | 0.07 / 0.08 / 0.92 |

## Means and prediction − crop-only deltas
- sil_iou_vs_real: pred 0.839, crop 0.838, Δ +0.001 (n=2)
- hem_chamfer: pred 41.538, crop 42.435, Δ -0.897 (n=2)
- dE_edge_band_vs_real: pred 18.083, crop 18.167, Δ -0.084 (n=2)
- fringe_iou_vs_real: pred 0.065, crop 0.000, Δ +0.065 (n=2)
- fringe_profile_dist: pred 0.036, crop 0.041, Δ -0.005 (n=2)

Rule: heuristic thresholds (hemfit/autolm) change only with n >= 5 and this table attached.
