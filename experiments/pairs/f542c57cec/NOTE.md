# PAIR — auto pipeline

flags: before: rotated -13.7° to upright
before: /Users/jefferyhuang/denim-twin/experiments/pairs/f542c57cec/cropped_before.png 
after: /Users/jefferyhuang/denim-twin/data/external/pair_images/f542c57cec_after_wash_9c55600a.jpg 
scale: UNKNOWN (1.0 placeholder; mm values are px)
landmarks: auto / auto (crotch: gap / gap)
fringe depth used: 112.0 px from measured from after-photo (NOT a prediction); measured on after-photo: 112.0 px (fabric/fringe split: SAM)
hem fit: left: angle 1.9°, depth 4, right: angle -1.4°, depth 220
registration residual (leave-one-landmark-out): 61.19px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.690 | 120.9 | 28.3 | 0.086 |
| pred median | 0.707 | 112.6 | 28.9 | 0.192 |
| pred aggressive | 0.717 | 108.3 | 29.2 | 0.262 |
| null:no-op | 0.514 | 460.8 | 27.8 | 0.224 |
| null:crop-only | 0.676 | 127.9 | 26.8 | 0.000 |
