# PAIR — auto pipeline

flags: segmentation by consensus: 100% of prompt sets agree, area 0.64; segmentation by consensus: 100% of prompt sets agree, area 0.48; before: rotated -8.9° to upright; before: touches the edge of a MANUAL crop (second object removed from frame); before (refined): touches the edge of a MANUAL crop (second object removed from frame); fringe measured directly: 5.0px in the after frame (rel 0.0172, coverage 1.00); SAM/hem-fit said 0.0px; no fringe rendered: edge_treatment 'raw' with no wash does not fray (EXP_0017)
before: /Users/jefferyhuang/denim-twin/experiments/pairs_consensus/2e2063b93f/cropped_before.png 
after: /Users/jefferyhuang/denim-twin/data/external/pair_images/2e2063b93f_after_cut_94d919e9.jpg 
scale: UNKNOWN (1.0 placeholder; mm values are px)
landmarks: auto / auto (crotch: prior_no_gap_jeans / gap)
fringe depth used: 0.0 px from measured from after-photo (NOT a prediction) [suppressed: finished hem]; measured on after-photo: 2.3 px (fabric/fringe split: colour split; registered-frame)
hem fit: left: angle -7.0°, depth 0 px, right: angle -5.0°, depth 0 px
registration residual (leave-one-landmark-out): 30.52px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.762 | 2.8 | 20.5 | 0.080 |
| pred median | 0.762 | 2.9 | 20.6 | 0.083 |
| pred aggressive | 0.758 | 3.4 | 20.7 | 0.088 |
| null:no-op | 0.224 | 261.5 | 31.3 | 0.003 |
| null:crop-only | 0.764 | 2.5 | 20.5 | 0.000 |
