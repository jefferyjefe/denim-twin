# pairs: 4 (preset median)

| pair | reg resid | sil_iou_vs_real pred / crop / no-op | hem_chamfer pred / crop / no-op | dE_edge_band_vs_real pred / crop / no-op | fringe_iou_vs_real pred / crop / no-op | fringe_profile_dist pred / crop / no-op |
|---|---|---|---|---|---|---|
| 443d1d4658 | 7.3 | 0.92 / 0.92 / 0.59 | 14.73 / 13.59 / 194.38 | 13.25 / 13.00 / 17.61 | 0.21 / 0.00 / 0.01 | 0.00 / 0.00 / 1.00 |
| 4bfef03bd7 | 42.0 | 0.77 / 0.75 / 0.29 | 16.83 / 21.99 / 503.38 | 22.92 / 23.33 / 20.45 | 0.26 / 0.00 / 0.04 | 0.02 / 0.03 / 0.97 |
| 8d9f0df4ad | 31.3 | 0.94 / 0.94 / 0.42 | 8.26 / 8.86 / 303.19 | 22.13 / 22.26 / 23.19 | 0.11 / 0.00 / 0.02 | 0.01 / 0.01 / 0.99 |
| b630a78c19 | 711.7 | 0.56 / 0.56 / 0.53 | 242.15 / 244.21 / 295.90 | 16.01 / 16.04 / 15.06 | 0.22 / 0.00 / 0.17 | 0.11 / 0.17 / 0.83 |

## Means and prediction − crop-only deltas
- sil_iou_vs_real: pred 0.796, crop 0.791, Δ +0.005 (n=4)
- hem_chamfer: pred 70.494, crop 72.163, Δ -1.670 (n=4)
- dE_edge_band_vs_real: pred 18.575, crop 18.655, Δ -0.080 (n=4)
- fringe_iou_vs_real: pred 0.200, crop 0.000, Δ +0.200 (n=4)
- fringe_profile_dist: pred 0.036, crop 0.053, Δ -0.017 (n=4)

Rule: heuristic thresholds (hemfit/autolm) change only with n >= 5 and this table attached.
