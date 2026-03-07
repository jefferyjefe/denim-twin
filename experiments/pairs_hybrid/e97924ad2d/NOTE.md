# PAIR — auto pipeline

flags: before: rotated 2.9° to upright; after: rotated -0.8° to upright; fringe measured directly: 6.0px in the after frame (rel 0.0154, coverage 0.98); SAM/hem-fit said 6.4px; no fringe rendered: edge_treatment 'raw' with no wash does not fray (EXP_0017)
before: /Users/jefferyhuang/denim-twin/experiments/pairs_hybrid/e97924ad2d/cropped_before.png 
after: /Users/jefferyhuang/denim-twin/data/external/pair_images/e97924ad2d_after_cut_b11dd634.JPG 
scale: UNKNOWN (1.0 placeholder; mm values are px)
landmarks: auto / auto (crotch: gap / gap)
fringe depth used: 0.0 px from measured from after-photo (NOT a prediction) [suppressed: finished hem]; measured on after-photo: 2.0 px (fabric/fringe split: SAM; after-frame)
hem fit: left: angle 23.8°, depth 1 px, right: angle -12.5°, depth 8 px
registration residual (leave-one-landmark-out): 28.28px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.883 | 5.3 | 12.1 | 0.104 |
| pred median | 0.883 | 5.3 | 12.1 | 0.128 |
| pred aggressive | 0.881 | 5.8 | 12.2 | 0.137 |
| null:no-op | 0.540 | 129.3 | 19.1 | 0.021 |
| null:crop-only | 0.883 | 5.4 | 12.0 | 0.000 |
