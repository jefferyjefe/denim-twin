registration residual (leave-one-landmark-out): 28.30 px; lighting matched on kept region

| system | sil_iou_vs_real | sil_chamfer | hem_chamfer | ssim_keep_vs_real | dE_keep_vs_real | feat_ret_keep_vs_real | ssim_keep_vs_before | ssim_keep_vs_before_aligned | feat_ret_keep_vs_before_aligned | align_scale | ssim_edge_band_vs_real | dE_edge_band_vs_real | hem_rough_p90_pred | hem_rough_p90_real | hem_rough_err_px | hem_rough_refused | fringe_iou_vs_real | fringe_profile_dist |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| prediction | 0.9561 | 5.8247 | 3.4863 | 0.0972 | 14.7269 | 0.0000 | 0.9986 | 0.9986 | 0.9705 | 1.0000 | 0.1195 | 20.8097 | 1.0000 | 2.0000 | 1.0000 | 0.0000 | 0.0601 | 0.0023 |
| null:no-op | 0.4206 | 112.7824 | 349.9836 | 0.0967 | 14.7211 | 0.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.1342 | 23.9266 | nan | 2.0000 | nan | 1.0000 | 0.0034 | 0.9974 |
| null:crop-only | 0.9561 | 5.8668 | 3.4759 | 0.0967 | 14.7211 | 0.0000 | 1.0000 | 1.0000 | 0.8845 | 1.0000 | 0.1149 | 20.8677 | 0.0000 | 2.0000 | 2.0000 | 0.0000 | 0.0000 | 0.0026 |

(hem_chamfer in px)
