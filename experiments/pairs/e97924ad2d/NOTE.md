# PAIR — auto pipeline

flags: before: touches the edge of a MANUAL crop (second object removed from frame); before (refined): touches the edge of a MANUAL crop (second object removed from frame); fringe measured directly: 6.0px in the after frame (rel 0.0154, coverage 0.97); SAM/hem-fit said 1.0px
before: /Users/jefferyhuang/denim-twin/experiments/pairs/e97924ad2d/cropped_before.png 
after: /Users/jefferyhuang/denim-twin/data/external/pair_images/e97924ad2d_after_cut_b11dd634.JPG 
scale: UNKNOWN (1.0 placeholder; mm values are px)
landmarks: auto / auto (crotch: gap / gap)
fringe depth used: 2.0 px from measured from after-photo (NOT a prediction); measured on after-photo: 2.0 px (fabric/fringe split: colour split; registered-frame)
hem fit: left: angle 23.4°, depth 1 px, right: angle -22.0°, depth 1 px
registration residual (leave-one-landmark-out): 28.17px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.897 | 1.3 | 11.2 | 0.220 |
| pred median | 0.896 | 1.5 | 11.2 | 0.244 |
| pred aggressive | 0.893 | 2.1 | 11.3 | 0.216 |
| null:no-op | 0.544 | 128.5 | 18.4 | 0.007 |
| null:crop-only | 0.897 | 1.3 | 11.0 | 0.000 |
