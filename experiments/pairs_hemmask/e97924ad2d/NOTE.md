# PAIR — auto pipeline

flags: before: rotated -1.9° to upright; after: rotated 2.2° to upright; before: touches the edge of a MANUAL crop (second object removed from frame); before (refined): touches the edge of a MANUAL crop (second object removed from frame); fringe measured directly: 6.0px in the after frame (rel 0.0154, coverage 0.96); SAM/hem-fit said 1.0px; no fringe rendered: edge_treatment 'raw' with no wash does not fray (EXP_0017)
before: /Users/jefferyhuang/denim-twin/experiments/pairs_hemmask/e97924ad2d/cropped_before.png 
after: /Users/jefferyhuang/denim-twin/data/external/pair_images/e97924ad2d_after_cut_b11dd634.JPG 
scale: UNKNOWN (1.0 placeholder; mm values are px)
landmarks: auto / auto (crotch: gap / gap)
fringe depth used: 0.0 px from measured from after-photo (NOT a prediction) [suppressed: finished hem]; measured on after-photo: 2.0 px (fabric/fringe split: colour split; registered-frame)
hem fit: left: angle 25.3°, depth 1 px, right: angle -20.4°, depth 1 px
registration residual (leave-one-landmark-out): 27.48px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.893 | 1.2 | 11.6 | 0.283 |
| pred median | 0.893 | 1.3 | 11.7 | 0.323 |
| pred aggressive | 0.891 | 1.8 | 11.8 | 0.271 |
| null:no-op | 0.542 | 129.0 | 19.6 | 0.008 |
| null:crop-only | 0.893 | 1.5 | 11.5 | 0.000 |
