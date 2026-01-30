# pairs: 5 (preset median)

| pair | reg resid | sil_iou_vs_real pred / crop / no-op | hem_chamfer pred / crop / no-op | dE_edge_band_vs_real pred / crop / no-op | fringe_iou_vs_real pred / crop / no-op | fringe_profile_dist pred / crop / no-op |
|---|---|---|---|---|---|---|
| 443d1d4658 | 5.8 | 0.70 / 0.66 / 0.60 | 89.21 / 105.07 / 189.88 | 20.88 / 21.74 / 10.33 | 0.14 / 0.00 / 0.33 | 0.25 / 0.29 / 0.71 |
| 4bfef03bd7 | 42.0 | 0.77 / 0.75 / 0.29 | 16.83 / 21.99 / 503.38 | 22.92 / 23.33 / 20.45 | 0.26 / 0.00 / 0.04 | 0.02 / 0.03 / 0.97 |
| 8d9f0df4ad | 31.3 | 0.94 / 0.94 / 0.42 | 8.26 / 8.86 / 303.19 | 22.13 / 22.26 / 23.19 | 0.11 / 0.00 / 0.02 | 0.01 / 0.01 / 0.99 |
| b630a78c19 | 9.5 | 0.74 / 0.74 / 0.73 | 155.69 / 157.52 / 141.83 | 16.21 / 15.51 / 14.10 | 0.13 / 0.00 / 0.41 | 0.31 / 0.34 / 0.66 |
| f9c0e56308 | 117.1 | 0.54 / 0.51 / 0.55 | 524.08 / 601.65 / 517.66 | 28.67 / 23.82 / 22.69 | 0.27 / 0.00 / 0.45 | 0.28 / 0.40 / 0.60 |

## Means and prediction − crop-only deltas
- sil_iou_vs_real: pred 0.738, crop 0.720, Δ +0.018 (n=5)
- hem_chamfer: pred 158.814, crop 179.018, Δ -20.204 (n=5)
- dE_edge_band_vs_real: pred 22.162, crop 21.331, Δ +0.831 (n=5)
- fringe_iou_vs_real: pred 0.184, crop 0.000, Δ +0.184 (n=5)
- fringe_profile_dist: pred 0.174, crop 0.215, Δ -0.040 (n=5)

Rule: heuristic thresholds (hemfit/autolm) change only with n >= 5 and this table attached.
