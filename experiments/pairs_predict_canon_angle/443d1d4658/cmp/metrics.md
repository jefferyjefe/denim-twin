registration residual (leave-one-landmark-out): 6.42 px; lighting matched on kept region

| system | sil_iou_vs_real | sil_chamfer | hem_chamfer | ssim_keep_vs_real | dE_keep_vs_real | feat_ret_keep_vs_real | ssim_keep_vs_before | ssim_keep_vs_before_aligned | feat_ret_keep_vs_before_aligned | align_scale | ssim_edge_band_vs_real | dE_edge_band_vs_real | fringe_iou_vs_real | fringe_profile_dist |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| prediction | 0.8895 | 8.8902 | 23.3808 | 0.2915 | 8.2678 | 0.0173 | 0.9947 | 0.9947 | 0.9483 | 1.0000 | 0.2453 | 15.3516 | 0.0035 | 0.0645 |
| null:no-op | 0.5871 | 49.8113 | 232.9828 | 0.2929 | 8.2348 | 0.0173 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.2390 | 14.2071 | 0.0712 | 0.9353 |
| null:crop-only | 0.8894 | 8.9082 | 23.4489 | 0.2929 | 8.2348 | 0.0135 | 1.0000 | 1.0000 | 0.7564 | 1.0000 | 0.2470 | 15.5993 | 0.0000 | 0.0647 |

(hem_chamfer in px)
