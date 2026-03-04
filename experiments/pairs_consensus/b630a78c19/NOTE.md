# PAIR — auto pipeline

flags: segmentation by consensus: 50% of prompt sets agree, area 0.42; segmentation by consensus: 50% of prompt sets agree, area 0.35; after: rotated -10.7° to upright; SAM fringe mask rejected: median depth 254px > 15% of garment height 1189px; fringe measured directly: 8.0px in the after frame (rel 0.0240, coverage 1.00); SAM/hem-fit said 2.5px; no fringe rendered: edge_treatment 'raw' with no wash does not fray (EXP_0017)
before: /Users/jefferyhuang/denim-twin/data/external/pair_images/b630a78c19_before_54931395.jpg 
after: /Users/jefferyhuang/denim-twin/data/external/pair_images/b630a78c19_after_cut_c7a4d702.jpg 
scale: UNKNOWN (1.0 placeholder; mm values are px)
landmarks: auto / auto (crotch: gap / gap)
fringe depth used: 0.0 px from measured from after-photo (NOT a prediction) [suppressed: finished hem]; measured on after-photo: 9.7 px (fabric/fringe split: colour split; registered-frame)
hem fit: left: angle 71.2°, depth 4 px, right: angle 0.3°, depth 1 px
registration residual (leave-one-landmark-out): 44.96px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.484 | 332.4 | 18.9 | 0.003 |
| pred median | 0.485 | 331.9 | 18.9 | 0.004 |
| pred aggressive | 0.485 | 330.2 | 18.8 | 0.008 |
| null:no-op | 0.534 | 261.2 | 14.6 | 0.552 |
| null:crop-only | 0.484 | 333.7 | 19.2 | 0.000 |
