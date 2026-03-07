# PAIR — auto pipeline

flags: before: rotated -4.2° to upright; after: rotated -2.2° to upright; SAM fringe mask rejected: median depth 806px > 15% of garment height 3181px; fringe measured directly: 29.0px in the after frame (rel 0.0105, coverage 0.70); SAM/hem-fit said 8.0px
before: /Users/jefferyhuang/denim-twin/experiments/pairs_hybrid/f542c57cec/cropped_before.png 
after: /Users/jefferyhuang/denim-twin/data/external/pair_images/f542c57cec_after_wash_9c55600a.jpg 
scale: UNKNOWN (1.0 placeholder; mm values are px)
landmarks: auto / auto (crotch: gap / gap)
fringe depth used: 5.0 px from measured from after-photo (NOT a prediction); measured on after-photo: 5.0 px (fabric/fringe split: colour split; registered-frame)
hem fit: left: angle 61.0°, depth 8 px, right: angle -48.6°, depth 8 px
registration residual (leave-one-landmark-out): 70.10px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.838 | 29.4 | 27.7 | 0.017 |
| pred median | 0.838 | 29.5 | 27.7 | 0.058 |
| pred aggressive | 0.838 | 30.0 | 27.7 | 0.098 |
| null:no-op | 0.490 | 423.8 | 30.0 | 0.026 |
| null:crop-only | 0.838 | 29.0 | 27.4 | 0.000 |
