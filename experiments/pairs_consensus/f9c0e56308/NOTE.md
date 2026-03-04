# PAIR — auto pipeline

flags: segmentation by consensus: 88% of prompt sets agree, area 0.42; segmentation by consensus: 100% of prompt sets agree, area 0.53; after: touches the edge of a MANUAL crop (second object removed from frame); SAM fringe mask rejected: median depth 262px > 15% of garment height 813px; fringe measured directly: 9.0px in the after frame (rel 0.0098, coverage 0.36); SAM/hem-fit said 0.0px
before: /Users/jefferyhuang/denim-twin/data/external/pair_images/f9c0e56308_before_5de12702.jpg 
after: /Users/jefferyhuang/denim-twin/experiments/pairs_consensus/f9c0e56308/cropped_after_wash.png 
scale: UNKNOWN (1.0 placeholder; mm values are px)
landmarks: auto / auto (crotch: gap / gap)
fringe depth used: 7.1 px from measured from after-photo (NOT a prediction); measured on after-photo: 7.1 px (fabric/fringe split: colour split; registered-frame)
hem fit: left: angle 12.3°, depth 0 px, right: angle -12.0°, depth 0 px
registration residual (leave-one-landmark-out): 119.96px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.918 | 19.9 | 18.9 | 0.074 |
| pred median | 0.917 | 20.6 | 19.1 | 0.138 |
| pred aggressive | 0.916 | 21.7 | 19.3 | 0.107 |
| null:no-op | 0.429 | 737.0 | 16.3 | 0.001 |
| null:crop-only | 0.918 | 19.5 | 18.6 | 0.000 |
