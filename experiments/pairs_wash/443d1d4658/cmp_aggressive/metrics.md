registration residual (leave-one-landmark-out): 6.42 px; lighting matched on kept region

| system | sil_iou_vs_real | sil_chamfer | hem_chamfer | ssim_keep_vs_real | dE_keep_vs_real | feat_ret_keep_vs_real | ssim_keep_vs_before | ssim_keep_vs_before_aligned | feat_ret_keep_vs_before_aligned | align_scale | ssim_edge_band_vs_real | dE_edge_band_vs_real | fringe_iou_vs_real | fringe_profile_dist |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| prediction | 0.9170 | 6.1596 | 9.6061 | 0.3319 | 8.7355 | 0.0191 | 0.4258 | 0.8884 | 0.6319 | 1.0152 | 0.2424 | 18.5900 | 0.0427 | 0.0039 |
| null:no-op | 0.5871 | 48.6657 | 240.6956 | 0.2893 | 8.3905 | 0.0148 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.2234 | 21.3731 | 0.0048 | 0.9956 |
| null:crop-only | 0.9180 | 6.2738 | 8.9256 | 0.2893 | 8.3905 | 0.0111 | 1.0000 | 1.0000 | 0.7392 | 1.0000 | 0.2475 | 18.3384 | 0.0000 | 0.0044 |

(hem_chamfer in mm)
