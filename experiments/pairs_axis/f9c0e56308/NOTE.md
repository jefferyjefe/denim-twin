# PAIR — auto pipeline

flags: before: rotated -1.0° to upright; after: rotated -0.7° to upright; SAM fringe mask rejected: median depth 264px > 15% of garment height 811px; fringe measured directly: 13.0px in the after frame (rel 0.0143, coverage 0.85); SAM/hem-fit said 0.0px
before: /Users/jefferyhuang/denim-twin/data/external/pair_images/f9c0e56308_before_5de12702.jpg 
after: /Users/jefferyhuang/denim-twin/experiments/pairs_axis/f9c0e56308/cropped_after_wash.png 
scale: UNKNOWN (1.0 placeholder; mm values are px)
landmarks: auto / auto (crotch: gap / gap)
fringe depth used: 10.3 px from measured from after-photo (NOT a prediction); measured on after-photo: 10.3 px (fabric/fringe split: colour split; registered-frame)
hem fit: left: angle 1.8°, depth 0 px, right: angle -12.4°, depth 0 px
registration residual (leave-one-landmark-out): 137.20px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.916 | 35.5 | 18.6 | 0.110 |
| pred median | 0.914 | 36.9 | 19.1 | 0.140 |
| pred aggressive | 0.913 | 38.3 | 19.5 | 0.132 |
| null:no-op | 0.435 | 731.5 | 17.8 | 0.002 |
| null:crop-only | 0.917 | 34.9 | 18.3 | 0.000 |
