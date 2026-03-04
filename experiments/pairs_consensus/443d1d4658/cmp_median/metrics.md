registration residual (leave-one-landmark-out): 5.99 px; lighting matched on kept region

| system | sil_iou_vs_real | sil_chamfer | hem_chamfer | ssim_keep_vs_real | dE_keep_vs_real | feat_ret_keep_vs_real | ssim_keep_vs_before | ssim_keep_vs_before_aligned | feat_ret_keep_vs_before_aligned | align_scale | ssim_edge_band_vs_real | dE_edge_band_vs_real | hem_rough_p90_pred | hem_rough_p90_real | hem_rough_err_px | hem_rough_refused | fringe_iou_vs_real | fringe_profile_dist |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| prediction | 0.9179 | 6.2831 | 9.2491 | 0.2903 | 8.3702 | 0.0201 | 0.9959 | 0.9959 | 0.9414 | 1.0000 | 0.2534 | 18.0664 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0072 | 0.0045 |
| null:no-op | 0.5874 | 48.6279 | 240.8575 | 0.2908 | 8.3581 | 0.0201 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.2273 | 21.2026 | nan | 0.0000 | nan | 1.0000 | 0.0051 | 0.9954 |
| null:crop-only | 0.9179 | 6.2847 | 9.2459 | 0.2908 | 8.3581 | 0.0122 | 1.0000 | 1.0000 | 0.7435 | 1.0000 | 0.2521 | 18.1728 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0046 |

(hem_chamfer in mm)
