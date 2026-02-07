# pairs: 7 (preset median)

| pair | reg resid | sil_iou_vs_real pred / crop / no-op | hem_chamfer pred / crop / no-op | dE_edge_band_vs_real pred / crop / no-op | fringe_iou_vs_real pred / crop / no-op | fringe_profile_dist pred / crop / no-op |
|---|---|---|---|---|---|---|
| 2691c1a8d0 | 86.8 | 0.69 / 0.69 / 0.58 | 27.23 / 27.28 / 100.45 | 14.86 / 15.05 / 17.47 | 0.01 / 0.00 / 0.10 | 0.06 / 0.06 / 0.94 |
| 26b1041d00 | 14.6 | 0.69 / 0.69 / 0.73 | 46.13 / 46.18 / 48.06 | 34.70 / 34.84 / 25.41 | 0.00 / 0.00 / 0.48 | 0.41 / 0.41 / 0.59 |
| 443d1d4658 | 6.4 | 0.92 / 0.92 / 0.59 | 13.43 / 13.44 / 190.55 | 18.25 / 18.34 / 21.37 | 0.01 / 0.00 / 0.00 | 0.00 / 0.00 / 1.00 |
| 4bfef03bd7 | 42.0 | 0.78 / 0.75 / 0.29 | 16.08 / 21.99 / 503.38 | 22.79 / 23.33 / 20.45 | 0.46 / 0.00 / 0.04 | 0.00 / 0.03 / 0.97 |
| 8d9f0df4ad | 31.2 | 0.94 / 0.94 / 0.42 | 8.47 / 8.66 / 303.39 | 21.21 / 21.53 / 22.66 | 0.04 / 0.00 / 0.02 | 0.01 / 0.01 / 0.99 |
| b630a78c19 | 698.7 | 0.46 / 0.46 / 0.54 | 367.62 / 367.66 / 296.25 | 17.36 / 17.42 / 16.36 | 0.00 / 0.00 / 0.58 | 0.63 / 0.63 / 0.37 |
| f542c57cec | 61.2 | 0.70 / 0.68 / 0.51 | 114.51 / 127.89 / 460.82 | 28.82 / 26.75 / 27.82 | 0.17 / 0.00 / 0.22 | 0.14 / 0.19 / 0.81 |

## Means and prediction − crop-only deltas
- sil_iou_vs_real: pred 0.740, crop 0.733, Δ +0.008 (n=7)
- hem_chamfer: pred 84.782, crop 87.586, Δ -2.803 (n=7)
- dE_edge_band_vs_real: pred 22.570, crop 22.467, Δ +0.103 (n=7)
- fringe_iou_vs_real: pred 0.097, crop 0.000, Δ +0.097 (n=7)
- fringe_profile_dist: pred 0.180, crop 0.191, Δ -0.011 (n=7)

Rule: heuristic thresholds (hemfit/autolm) change only with n >= 5 and this table attached.
