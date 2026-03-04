registration residual (leave-one-landmark-out): 30.52 px; lighting matched on kept region

| system | sil_iou_vs_real | sil_chamfer | hem_chamfer | ssim_keep_vs_real | dE_keep_vs_real | feat_ret_keep_vs_real | ssim_keep_vs_before | ssim_keep_vs_before_aligned | feat_ret_keep_vs_before_aligned | align_scale | ssim_edge_band_vs_real | dE_edge_band_vs_real | hem_rough_p90_pred | hem_rough_p90_real | hem_rough_err_px | hem_rough_refused | fringe_iou_vs_real | fringe_profile_dist |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| prediction | 0.7616 | 8.8472 | 2.9024 | 0.2332 | 13.6005 | 0.0000 | 0.9913 | 0.9914 | 0.9414 | 0.9999 | 0.2019 | 20.5684 | 1.0000 | 0.0000 | 1.0000 | 0.0000 | 0.0829 | 0.0008 |
| null:no-op | 0.2236 | 75.3797 | 261.5325 | 0.2356 | 13.5898 | 0.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.1783 | 31.3153 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0032 | 0.9971 |
| null:crop-only | 0.7642 | 8.7203 | 2.4634 | 0.2356 | 13.5898 | 0.0000 | 1.0000 | 1.0000 | 0.9059 | 1.0000 | 0.2057 | 20.5033 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0029 |

(hem_chamfer in px)
