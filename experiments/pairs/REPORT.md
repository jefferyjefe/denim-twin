# pairs: 4 (preset median)

| pair | reg resid | sil_iou_vs_real pred / crop / no-op | hem_chamfer pred / crop / no-op | dE_edge_band_vs_real pred / crop / no-op | fringe_iou_vs_real pred / crop / no-op | fringe_profile_dist pred / crop / no-op |
|---|---|---|---|---|---|---|
| 443d1d4658 | 6.4 | 0.92 / 0.92 / 0.59 | 14.36 / 13.76 / 195.04 | 13.20 / 13.05 / 17.61 | 0.14 / 0.00 / 0.00 | 0.00 / 0.00 / 1.00 |
| 4bfef03bd7 | 42.0 | 0.77 / 0.75 / 0.29 | 16.83 / 21.99 / 503.38 | 22.92 / 23.33 / 20.45 | 0.26 / 0.00 / 0.04 | 0.02 / 0.03 / 0.97 |
| 8d9f0df4ad | 31.2 | 0.94 / 0.94 / 0.42 | 8.08 / 8.66 / 303.39 | 21.42 / 21.53 / 22.66 | 0.11 / 0.00 / 0.02 | 0.01 / 0.01 / 0.99 |
| b630a78c19 | 698.7 | 0.46 / 0.46 / 0.54 | 363.33 / 367.66 / 296.25 | 17.48 / 17.42 / 16.36 | 0.02 / 0.00 / 0.58 | 0.62 / 0.63 / 0.37 |

## Means and prediction − crop-only deltas
- sil_iou_vs_real: pred 0.772, crop 0.768, Δ +0.004 (n=4)
- hem_chamfer: pred 100.649, crop 103.016, Δ -2.367 (n=4)
- dE_edge_band_vs_real: pred 18.752, crop 18.833, Δ -0.081 (n=4)
- fringe_iou_vs_real: pred 0.133, crop 0.000, Δ +0.133 (n=4)
- fringe_profile_dist: pred 0.162, crop 0.170, Δ -0.008 (n=4)

Rule: heuristic thresholds (hemfit/autolm) change only with n >= 5 and this table attached.
