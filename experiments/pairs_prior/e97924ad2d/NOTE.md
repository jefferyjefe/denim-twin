# PAIR — auto pipeline

flags: before: touches the edge of a MANUAL crop (second object removed from frame); before (refined): touches the edge of a MANUAL crop (second object removed from frame); fringe measured directly: 6.0px in the after frame (rel 0.0154, coverage 0.97); SAM/hem-fit said 1.0px; no fringe rendered: edge_treatment 'raw' with no wash does not fray (EXP_0017)
before: /Users/jefferyhuang/denim-twin/experiments/pairs_prior/e97924ad2d/cropped_before.png 
after: /Users/jefferyhuang/denim-twin/data/external/pair_images/e97924ad2d_after_cut_b11dd634.JPG 
scale: UNKNOWN (1.0 placeholder; mm values are px)
landmarks: auto / auto (crotch: gap / gap)
fringe depth used: 0.0 px from prior[after_cut] (n=4 after excluding self, INSUFFICIENT) [suppressed: finished hem]; measured on after-photo: 2.0 px (fabric/fringe split: colour split; registered-frame)
hem fit: left: angle 23.4°, depth 1 px, right: angle -22.0°, depth 1 px
registration residual (leave-one-landmark-out): 28.17px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.897 | 1.2 | 11.2 | 0.205 |
| pred median | 0.897 | 1.3 | 11.2 | 0.233 |
| pred aggressive | 0.895 | 1.7 | 11.3 | 0.225 |
| null:no-op | 0.544 | 128.5 | 18.4 | 0.007 |
| null:crop-only | 0.897 | 1.3 | 11.0 | 0.000 |
