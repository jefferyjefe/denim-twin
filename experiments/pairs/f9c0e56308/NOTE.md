# PAIR — auto pipeline

flags: after: touches the edge of a MANUAL crop (second object removed from frame); SAM fringe mask rejected: median depth 260px > 15% of garment height 811px; fringe measured directly: 11.0px in the after frame (rel 0.0121, coverage 0.75); SAM/hem-fit said 0.0px
before: /Users/jefferyhuang/denim-twin/data/external/pair_images/f9c0e56308_before_5de12702.jpg 
after: /Users/jefferyhuang/denim-twin/experiments/pairs/f9c0e56308/cropped_after_wash.png 
scale: UNKNOWN (1.0 placeholder; mm values are px)
landmarks: auto / auto (crotch: gap / gap)
fringe depth used: 8.7 px from measured from after-photo (NOT a prediction); measured on after-photo: 8.7 px (fabric/fringe split: colour split; registered-frame)
hem fit: left: angle 3.0°, depth 0 px, right: angle -11.1°, depth 0 px
registration residual (leave-one-landmark-out): 139.78px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.918 | 35.1 | 18.0 | 0.062 |
| pred median | 0.917 | 36.0 | 18.4 | 0.115 |
| pred aggressive | 0.916 | 37.1 | 18.7 | 0.115 |
| null:no-op | 0.436 | 732.4 | 15.2 | 0.002 |
| null:crop-only | 0.919 | 34.7 | 17.7 | 0.000 |
