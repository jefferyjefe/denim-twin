# PAIR — auto pipeline

flags: before: rotated -13.7° to upright
before: /Users/jefferyhuang/denim-twin/experiments/pairs_prior/f542c57cec/cropped_before.png 
after: /Users/jefferyhuang/denim-twin/data/external/pair_images/f542c57cec_after_wash_9c55600a.jpg 
scale: UNKNOWN (1.0 placeholder; mm values are px)
landmarks: auto / auto (crotch: gap / gap)
fringe depth used: 30.2 px from prior[after_wash] (n=3 after excluding self, INSUFFICIENT); measured on after-photo: 163.6 px (fabric/fringe split: SAM; after-frame)
hem fit: left: angle 1.9°, depth 4 px, right: angle -1.4°, depth 220 px
registration residual (leave-one-landmark-out): 61.19px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.680 | 125.8 | 28.1 | 0.023 |
| pred median | 0.686 | 123.3 | 28.2 | 0.057 |
| pred aggressive | 0.690 | 121.3 | 28.4 | 0.082 |
| null:no-op | 0.514 | 460.8 | 27.8 | 0.224 |
| null:crop-only | 0.676 | 127.9 | 26.8 | 0.000 |
