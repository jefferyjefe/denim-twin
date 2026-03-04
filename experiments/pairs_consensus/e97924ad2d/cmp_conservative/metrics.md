registration residual (leave-one-landmark-out): 21.51 px; lighting matched on kept region

| system | sil_iou_vs_real | sil_chamfer | hem_chamfer | ssim_keep_vs_real | dE_keep_vs_real | feat_ret_keep_vs_real | ssim_keep_vs_before | ssim_keep_vs_before_aligned | feat_ret_keep_vs_before_aligned | align_scale | ssim_edge_band_vs_real | dE_edge_band_vs_real | hem_rough_p90_pred | hem_rough_p90_real | hem_rough_err_px | hem_rough_refused | fringe_iou_vs_real | fringe_profile_dist |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| prediction | 0.8790 | 4.2949 | 14.5822 | 0.5406 | 8.0919 | 0.0149 | 0.9801 | 0.9801 | 0.9640 | 0.9999 | 0.4905 | 10.3960 | 1.0000 | 1.0000 | 0.0000 | 0.0000 | 0.2466 | 0.0006 |
| null:no-op | 0.5168 | 24.6781 | 144.6216 | 0.5501 | 7.9707 | 0.0149 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.4354 | 15.7842 | nan | 1.0000 | nan | 1.0000 | 0.0049 | 0.9957 |
| null:crop-only | 0.8792 | 4.3392 | 14.4589 | 0.5501 | 7.9707 | 0.0000 | 1.0000 | 0.9999 | 0.7838 | 1.0002 | 0.4956 | 10.2491 | 0.0000 | 1.0000 | 1.0000 | 0.0000 | 0.0000 | 0.0043 |

(hem_chamfer in px)
