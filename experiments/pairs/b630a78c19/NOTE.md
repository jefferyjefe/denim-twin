# PAIR — auto pipeline

flags: after: rotated -10.7° to upright; SAM fringe mask rejected: median depth 254px > 15% of garment height 1190px; fringe measured directly: 7.0px in the after frame (rel 0.0207, coverage 1.00); SAM/hem-fit said 4.5px
before: /Users/jefferyhuang/denim-twin/data/external/pair_images/b630a78c19_before_54931395.jpg 
after: /Users/jefferyhuang/denim-twin/data/external/pair_images/b630a78c19_after_cut_c7a4d702.jpg 
scale: UNKNOWN (1.0 placeholder; mm values are px)
landmarks: auto / auto (crotch: gap / gap)
fringe depth used: 8.4 px from measured from after-photo (NOT a prediction); measured on after-photo: 8.4 px (fabric/fringe split: colour split; registered-frame)
hem fit: left: angle 72.1°, depth 4 px, right: angle 0.1°, depth 5 px
registration residual (leave-one-landmark-out): 41.30px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.490 | 316.4 | 18.8 | 0.009 |
| pred median | 0.491 | 311.7 | 18.7 | 0.023 |
| pred aggressive | 0.492 | 306.1 | 18.7 | 0.035 |
| null:no-op | 0.536 | 257.3 | 14.3 | 0.549 |
| null:crop-only | 0.489 | 320.5 | 19.1 | 0.000 |
