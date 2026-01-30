# pairs: 5 (preset median)

| pair | reg resid | sil_iou_vs_real pred / crop / no-op | hem_chamfer pred / crop / no-op | dE_edge_band_vs_real pred / crop / no-op | fringe_iou_vs_real pred / crop / no-op | fringe_profile_dist pred / crop / no-op |
|---|---|---|---|---|---|---|
| 443d1d4658 | 7.3 | 0.92 / 0.92 / 0.59 | 14.73 / 13.59 / 194.38 | 13.25 / 13.00 / 17.61 | 0.21 / 0.00 / 0.01 | 0.00 / 0.00 / 1.00 |
| 4bfef03bd7 | 42.0 | 0.77 / 0.75 / 0.29 | 16.83 / 21.99 / 503.38 | 22.92 / 23.33 / 20.45 | 0.26 / 0.00 / 0.04 | 0.02 / 0.03 / 0.97 |
| 8d9f0df4ad | 31.3 | 0.94 / 0.94 / 0.42 | 8.26 / 8.86 / 303.19 | 22.13 / 22.26 / 23.19 | 0.11 / 0.00 / 0.02 | 0.01 / 0.01 / 0.99 |
| b630a78c19 | 9.5 | 0.74 / 0.74 / 0.73 | 155.69 / 157.52 / 141.83 | 16.21 / 15.51 / 14.10 | 0.13 / 0.00 / 0.41 | 0.31 / 0.34 / 0.66 |
| f9c0e56308 | 107.9 | 0.78 / 0.70 / 0.43 | 118.62 / 197.72 / 737.93 | 26.77 / 20.95 / 13.32 | 0.30 / 0.00 / 0.17 | 0.10 / 0.14 / 0.86 |

## Means and prediction − crop-only deltas
- sil_iou_vs_real: pred 0.830, crop 0.809, Δ +0.021 (n=5)
- hem_chamfer: pred 62.827, crop 79.936, Δ -17.109 (n=5)
- dE_edge_band_vs_real: pred 20.254, crop 19.008, Δ +1.247 (n=5)
- fringe_iou_vs_real: pred 0.204, crop 0.000, Δ +0.204 (n=5)
- fringe_profile_dist: pred 0.087, crop 0.104, Δ -0.017 (n=5)

Rule: heuristic thresholds (hemfit/autolm) change only with n >= 5 and this table attached.
