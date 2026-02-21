# PAIR — auto pipeline

flags: before: rotated -13.7° to upright; SAM fringe mask rejected: median depth 793px > 15% of garment height 3231px
before: /Users/jefferyhuang/denim-twin/experiments/pairs_prior/f542c57cec/cropped_before.png 
after: /Users/jefferyhuang/denim-twin/data/external/pair_images/f542c57cec_after_wash_9c55600a.jpg 
scale: UNKNOWN (1.0 placeholder; mm values are px)
landmarks: auto / auto (crotch: gap / gap)
fringe depth used: 30.2 px from prior[after_wash] (n=3 after excluding self, INSUFFICIENT); measured on after-photo: 7.5 px (fabric/fringe split: colour split; registered-frame)
hem fit: left: angle 44.8°, depth 2 px, right: angle 24.0°, depth 13 px
registration residual (leave-one-landmark-out): 61.19px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.859 | 49.5 | 28.8 | 0.222 |
| pred median | 0.857 | 51.5 | 29.0 | 0.316 |
| pred aggressive | 0.854 | 55.0 | 29.1 | 0.312 |
| null:no-op | 0.514 | 460.8 | 29.8 | 0.022 |
| null:crop-only | 0.858 | 50.2 | 28.4 | 0.000 |
