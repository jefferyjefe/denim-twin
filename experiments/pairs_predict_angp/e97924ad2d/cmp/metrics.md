registration residual (leave-one-landmark-out): 28.17 px; lighting matched on kept region

| system | sil_iou_vs_real | sil_chamfer | hem_chamfer | ssim_keep_vs_real | dE_keep_vs_real | feat_ret_keep_vs_real | ssim_keep_vs_before | ssim_keep_vs_before_aligned | feat_ret_keep_vs_before_aligned | align_scale | ssim_edge_band_vs_real | dE_edge_band_vs_real | fringe_iou_vs_real | fringe_profile_dist |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| prediction | 0.8894 | 3.7867 | 2.7165 | 0.5769 | 9.6070 | 0.0000 | 0.9806 | 0.9803 | 0.9561 | 0.9998 | 0.5400 | 11.3076 | 0.0751 | 0.0004 |
| null:no-op | 0.5436 | 21.1563 | 128.4724 | 0.5836 | 9.5507 | 0.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.4600 | 18.4847 | 0.0052 | 0.9953 |
| null:crop-only | 0.8914 | 3.7415 | 2.2677 | 0.5836 | 9.5507 | 0.0000 | 1.0000 | 0.9999 | 0.7544 | 1.0002 | 0.5396 | 11.2577 | 0.0000 | 0.0047 |

(hem_chamfer in px)
