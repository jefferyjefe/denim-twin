# PAIR — auto pipeline

flags: before: rotated -13.7° to upright; after: rotated -2.8° to upright; SAM fringe mask rejected: median depth 913px > 15% of garment height 3165px; fringe measured directly: 28.0px in the after frame (rel 0.0101, coverage 0.71); SAM/hem-fit said 8.5px
before: /Users/jefferyhuang/denim-twin/experiments/pairs_hemmask/f542c57cec/cropped_before.png 
after: /Users/jefferyhuang/denim-twin/data/external/pair_images/f542c57cec_after_wash_9c55600a.jpg 
scale: UNKNOWN (1.0 placeholder; mm values are px)
landmarks: auto / auto (crotch: gap / gap)
fringe depth used: 5.8 px from measured from after-photo (NOT a prediction); measured on after-photo: 5.8 px (fabric/fringe split: colour split; registered-frame)
hem fit: left: angle 43.8°, depth 3 px, right: angle -42.9°, depth 14 px
registration residual (leave-one-landmark-out): 56.31px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.859 | 36.7 | 25.6 | 0.021 |
| pred median | 0.861 | 35.7 | 25.7 | 0.059 |
| pred aggressive | 0.863 | 34.9 | 25.7 | 0.090 |
| null:no-op | 0.519 | 457.8 | 26.9 | 0.076 |
| null:crop-only | 0.858 | 37.3 | 25.1 | 0.000 |
