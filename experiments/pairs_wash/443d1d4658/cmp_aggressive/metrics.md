registration residual (leave-one-landmark-out): 6.42 px; lighting matched on kept region

| system | sil_iou_vs_real | sil_chamfer | hem_chamfer | ssim_keep_vs_real | dE_keep_vs_real | feat_ret_keep_vs_real | ssim_keep_vs_before | ssim_edge_band_vs_real | dE_edge_band_vs_real | fringe_iou_vs_real | fringe_profile_dist |
|---|---|---|---|---|---|---|---|---|---|---|---|
| prediction | 0.9170 | 6.1596 | 9.5968 | 0.3425 | 8.1532 | 0.0193 | 0.4490 | 0.2723 | 16.3713 | 0.2285 | 0.0042 |
| null:no-op | 0.5944 | 46.8114 | 232.4599 | 0.2869 | 8.3055 | 0.0168 | 1.0000 | 0.2311 | 18.3954 | 0.0141 | 0.9874 |
| null:crop-only | 0.9171 | 6.2994 | 9.4661 | 0.2869 | 8.3055 | 0.0081 | 1.0000 | 0.2379 | 16.9799 | 0.0000 | 0.0126 |

(hem_chamfer in mm)
