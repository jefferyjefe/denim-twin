# pairs: 7 (preset median)

| pair | reg resid | sil_iou_vs_real pred / crop / no-op | hem_chamfer pred / crop / no-op | dE_edge_band_vs_real pred / crop / no-op | fringe_iou_vs_real pred / crop / no-op | fringe_profile_dist pred / crop / no-op |
|---|---|---|---|---|---|---|
| 2691c1a8d0 | 86.8 | 0.70 / 0.69 / 0.58 | 25.20 / 27.28 / 100.45 | 15.28 / 15.05 / 17.47 | 0.30 / 0.00 / 0.10 | 0.03 / 0.06 / 0.94 |
| 26b1041d00 | 14.6 | 0.69 / 0.69 / 0.73 | 45.62 / 46.18 / 48.06 | 34.57 / 34.84 / 25.41 | 0.01 / 0.00 / 0.48 | 0.41 / 0.41 / 0.59 |
| 443d1d4658 | 6.4 | 0.91 / 0.92 / 0.59 | 19.28 / 13.44 / 190.55 | 20.20 / 18.34 / 21.37 | 0.14 / 0.00 / 0.00 | 0.03 / 0.00 / 1.00 |
| 4bfef03bd7 | 42.0 | 0.78 / 0.75 / 0.29 | 16.08 / 21.99 / 503.38 | 22.79 / 23.33 / 20.45 | 0.46 / 0.00 / 0.04 | 0.00 / 0.03 / 0.97 |
| 8d9f0df4ad | 31.2 | 0.93 / 0.94 / 0.42 | 15.24 / 8.66 / 303.39 | 21.02 / 21.53 / 22.66 | 0.33 / 0.00 / 0.02 | 0.01 / 0.01 / 0.99 |
| b630a78c19 | 698.7 | 0.46 / 0.46 / 0.54 | 363.58 / 367.66 / 296.25 | 17.49 / 17.42 / 16.36 | 0.02 / 0.00 / 0.58 | 0.62 / 0.63 / 0.37 |
| f542c57cec | 61.2 | 0.70 / 0.68 / 0.51 | 114.51 / 127.89 / 460.82 | 28.82 / 26.75 / 27.82 | 0.17 / 0.00 / 0.22 | 0.14 / 0.19 / 0.81 |

## Means and prediction − crop-only deltas
- sil_iou_vs_real: pred 0.738, crop 0.733, Δ +0.006 (n=7)
- hem_chamfer: pred 85.646, crop 87.586, Δ -1.940 (n=7)
- dE_edge_band_vs_real: pred 22.883, crop 22.467, Δ +0.416 (n=7)
- fringe_iou_vs_real: pred 0.204, crop 0.000, Δ +0.204 (n=7)
- fringe_profile_dist: pred 0.177, crop 0.191, Δ -0.014 (n=7)

Rule: heuristic thresholds (hemfit/autolm) change only with n >= 5 and this table attached.
