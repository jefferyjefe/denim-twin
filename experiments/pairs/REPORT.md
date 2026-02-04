# pairs: 5 (preset median)

| pair | reg resid | sil_iou_vs_real pred / crop / no-op | hem_chamfer pred / crop / no-op | dE_edge_band_vs_real pred / crop / no-op | fringe_iou_vs_real pred / crop / no-op | fringe_profile_dist pred / crop / no-op |
|---|---|---|---|---|---|---|
| 2691c1a8d0 | 86.8 | 0.70 / 0.69 / 0.58 | 24.16 / 27.28 / 100.45 | 15.54 / 15.05 / 17.47 | 0.39 / 0.00 / 0.10 | 0.01 / 0.06 / 0.94 |
| 443d1d4658 | 6.4 | 0.92 / 0.92 / 0.59 | 14.02 / 13.44 / 190.55 | 18.54 / 18.34 / 21.37 | 0.14 / 0.00 / 0.00 | 0.00 / 0.00 / 1.00 |
| 4bfef03bd7 | 42.0 | 0.77 / 0.75 / 0.29 | 16.83 / 21.99 / 503.38 | 22.99 / 23.33 / 20.45 | 0.26 / 0.00 / 0.04 | 0.02 / 0.03 / 0.97 |
| 8d9f0df4ad | 31.2 | 0.94 / 0.94 / 0.42 | 8.08 / 8.66 / 303.39 | 21.16 / 21.53 / 22.66 | 0.11 / 0.00 / 0.02 | 0.01 / 0.01 / 0.99 |
| b630a78c19 | 698.7 | 0.46 / 0.46 / 0.54 | 363.33 / 367.66 / 296.25 | 17.50 / 17.42 / 16.36 | 0.02 / 0.00 / 0.58 | 0.62 / 0.63 / 0.37 |

## Means and prediction − crop-only deltas
- sil_iou_vs_real: pred 0.758, crop 0.753, Δ +0.005 (n=5)
- hem_chamfer: pred 85.285, crop 87.806, Δ -2.521 (n=5)
- dE_edge_band_vs_real: pred 19.146, crop 19.135, Δ +0.011 (n=5)
- fringe_iou_vs_real: pred 0.185, crop 0.000, Δ +0.185 (n=5)
- fringe_profile_dist: pred 0.132, crop 0.148, Δ -0.016 (n=5)

Rule: heuristic thresholds (hemfit/autolm) change only with n >= 5 and this table attached.
