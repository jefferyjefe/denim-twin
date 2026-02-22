registration residual (leave-one-landmark-out): 6.42 px; lighting matched on kept region

| system | sil_iou_vs_real | sil_chamfer | hem_chamfer | ssim_keep_vs_real | dE_keep_vs_real | feat_ret_keep_vs_real | ssim_keep_vs_before | ssim_keep_vs_before_aligned | feat_ret_keep_vs_before_aligned | align_scale | ssim_edge_band_vs_real | dE_edge_band_vs_real | fringe_iou_vs_real | fringe_profile_dist |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| prediction | 0.9100 | 7.1363 | 14.1154 | 0.2908 | 8.3426 | 0.0143 | 0.9955 | 0.9955 | 0.9481 | 1.0000 | 0.2435 | 13.7926 | 0.0000 | 0.0127 |
| null:no-op | 0.5871 | 49.8113 | 241.7754 | 0.2910 | 8.3288 | 0.0143 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.2217 | 17.4869 | 0.0140 | 0.9872 |
| null:crop-only | 0.9100 | 7.1346 | 14.1058 | 0.2910 | 8.3288 | 0.0100 | 1.0000 | 1.0000 | 0.7517 | 1.0000 | 0.2432 | 13.8752 | 0.0000 | 0.0128 |

(hem_chamfer in px)
