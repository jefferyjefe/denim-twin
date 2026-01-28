# pairs: 2 (preset median)

| pair | reg resid | sil_iou_vs_real pred / crop / no-op | hem_chamfer pred / crop / no-op | dE_edge_band_vs_real pred / crop / no-op | fringe_iou_vs_real pred / crop / no-op | fringe_profile_dist pred / crop / no-op |
|---|---|---|---|---|---|---|
| 4bfef03bd7 | 42.0 | 0.77 / 0.75 / 0.29 | 16.83 / 21.99 / 503.38 | 22.92 / 23.33 / 20.45 | 0.26 / 0.00 / 0.04 | 0.02 / 0.03 / 0.97 |
| b630a78c19 | 9.5 | 0.74 / 0.74 / 0.73 | 155.69 / 157.52 / 141.83 | 16.21 / 15.51 / 14.10 | 0.13 / 0.00 / 0.41 | 0.31 / 0.34 / 0.66 |

## Means and prediction − crop-only deltas
- sil_iou_vs_real: pred 0.756, crop 0.744, Δ +0.011 (n=2)
- hem_chamfer: pred 86.259, crop 89.754, Δ -3.495 (n=2)
- dE_edge_band_vs_real: pred 19.565, crop 19.418, Δ +0.147 (n=2)
- fringe_iou_vs_real: pred 0.198, crop 0.000, Δ +0.198 (n=2)
- fringe_profile_dist: pred 0.163, crop 0.184, Δ -0.021 (n=2)

Rule: heuristic thresholds (hemfit/autolm) change only with n >= 5 and this table attached.
