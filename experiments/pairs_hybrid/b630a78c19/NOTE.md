# PAIR — auto pipeline

flags: before: rotated 5.9° to upright; after: rotated 5.0° to upright; SAM fringe mask rejected: median depth 387px > 15% of garment height 1120px; fringe measured directly: 5.0px in the after frame (rel 0.0120, coverage 0.99); SAM/hem-fit said 13.5px; no fringe rendered: edge_treatment 'raw' with no wash does not fray (EXP_0017)
before: /Users/jefferyhuang/denim-twin/data/external/pair_images/b630a78c19_before_54931395.jpg 
after: /Users/jefferyhuang/denim-twin/data/external/pair_images/b630a78c19_after_cut_c7a4d702.jpg 
scale: UNKNOWN (1.0 placeholder; mm values are px)
landmarks: auto / auto (crotch: gap / gap)
fringe depth used: 0.0 px from measured from after-photo (NOT a prediction) [suppressed: finished hem]; measured on after-photo: 4.8 px (fabric/fringe split: colour split; registered-frame)
hem fit: left: angle -0.1°, depth 20 px, right: angle -3.8°, depth 7 px
registration residual (leave-one-landmark-out): 12.34px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.884 | 51.4 | 13.4 | 0.000 |
| pred median | 0.884 | 51.5 | 13.4 | 0.000 |
| pred aggressive | 0.884 | 51.6 | 13.4 | 0.000 |
| null:no-op | 0.727 | 291.2 | 12.7 | 0.081 |
| null:crop-only | 0.884 | 51.4 | 13.6 | 0.000 |
