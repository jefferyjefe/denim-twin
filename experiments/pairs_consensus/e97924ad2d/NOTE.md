# PAIR — auto pipeline

flags: segmentation by consensus: 62% of prompt sets agree, area 0.46; segmentation by consensus: 100% of prompt sets agree, area 0.61; after: rotated -8.5° to upright; before: touches the edge of a MANUAL crop (second object removed from frame); before (refined): touches the edge of a MANUAL crop (second object removed from frame); fringe measured directly: 7.0px in the after frame (rel 0.0231, coverage 0.98); SAM/hem-fit said 0.0px; no fringe rendered: edge_treatment 'raw' with no wash does not fray (EXP_0017)
before: /Users/jefferyhuang/denim-twin/experiments/pairs_consensus/e97924ad2d/cropped_before.png 
after: /Users/jefferyhuang/denim-twin/data/external/pair_images/e97924ad2d_after_cut_b11dd634.JPG 
scale: UNKNOWN (1.0 placeholder; mm values are px)
landmarks: auto / auto (crotch: gap / gap)
fringe depth used: 0.0 px from measured from after-photo (NOT a prediction) [suppressed: finished hem]; measured on after-photo: 3.0 px (fabric/fringe split: colour split; registered-frame)
hem fit: left: angle -8.1°, depth 0 px, right: angle -4.3°, depth 0 px
registration residual (leave-one-landmark-out): 21.51px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.879 | 14.6 | 10.4 | 0.247 |
| pred median | 0.879 | 14.7 | 10.4 | 0.273 |
| pred aggressive | 0.876 | 15.3 | 10.5 | 0.199 |
| null:no-op | 0.517 | 144.6 | 15.8 | 0.005 |
| null:crop-only | 0.879 | 14.5 | 10.2 | 0.000 |
