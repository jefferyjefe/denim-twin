# PAIR — auto pipeline

flags: before: rotated -13.7° to upright
before: /Users/jefferyhuang/denim-twin/experiments/pairs_prior/f542c57cec/cropped_before.png 
after: /Users/jefferyhuang/denim-twin/data/external/pair_images/f542c57cec_after_wash_9c55600a.jpg 
scale: UNKNOWN (1.0 placeholder; mm values are px)
landmarks: auto / auto (crotch: gap / gap)
fringe depth used: 83.0 px from prior (n=4 after excluding self, INSUFFICIENT); measured on after-photo: 112.0 px (fabric/fringe split: SAM)
hem fit: left: angle 1.9°, depth 4, right: angle -1.4°, depth 220
registration residual (leave-one-landmark-out): 61.19px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.687 | 122.4 | 28.3 | 0.066 |
| pred median | 0.700 | 116.4 | 28.7 | 0.147 |
| pred aggressive | 0.709 | 111.9 | 29.0 | 0.206 |
| null:no-op | 0.514 | 460.8 | 27.8 | 0.224 |
| null:crop-only | 0.676 | 127.9 | 26.8 | 0.000 |
