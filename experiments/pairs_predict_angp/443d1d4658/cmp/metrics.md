registration residual (leave-one-landmark-out): 6.42 px; lighting matched on kept region

| system | sil_iou_vs_real | sil_chamfer | hem_chamfer | ssim_keep_vs_real | dE_keep_vs_real | feat_ret_keep_vs_real | ssim_keep_vs_before | ssim_keep_vs_before_aligned | feat_ret_keep_vs_before_aligned | align_scale | ssim_edge_band_vs_real | dE_edge_band_vs_real | fringe_iou_vs_real | fringe_profile_dist |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| prediction | 0.9117 | 6.9538 | 12.7360 | 0.2892 | 8.4043 | 0.0148 | 0.9966 | 0.9966 | 0.9476 | 1.0000 | 0.2453 | 13.5235 | 0.0000 | 0.0016 |
| null:no-op | 0.5871 | 49.8113 | 246.6012 | 0.2895 | 8.3983 | 0.0148 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.2172 | 18.2490 | 0.0018 | 0.9984 |
| null:crop-only | 0.9118 | 6.9530 | 12.7195 | 0.2895 | 8.3983 | 0.0111 | 1.0000 | 1.0000 | 0.7406 | 1.0000 | 0.2449 | 13.5694 | 0.0000 | 0.0016 |

(hem_chamfer in px)
