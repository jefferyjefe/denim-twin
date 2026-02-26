# PAIR — auto pipeline

flags: before: rotated -13.7° to upright; SAM fringe mask rejected: median depth 793px > 15% of garment height 3231px; wash preset median: shrink 2.0% along / 1.0% across (PRIOR, not measured); 644360 px changed
before: /Users/jefferyhuang/denim-twin/experiments/pairs_wash/f542c57cec/cropped_before.png 
after: /Users/jefferyhuang/denim-twin/data/external/pair_images/f542c57cec_after_wash_9c55600a.jpg 
scale: UNKNOWN (1.0 placeholder; mm values are px)
landmarks: auto / auto (crotch: gap / gap)
fringe depth used: 7.5 px from measured from after-photo (NOT a prediction); measured on after-photo: 7.5 px (fabric/fringe split: colour split; registered-frame)
hem fit: left: angle 44.8°, depth 2 px, right: angle 24.0°, depth 13 px
registration residual (leave-one-landmark-out): 61.19px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.854 | 50.7 | 28.5 | 0.005 |
| pred median | 0.856 | 49.7 | 28.5 | 0.026 |
| pred aggressive | 0.857 | 48.7 | 28.5 | 0.082 |
| null:no-op | 0.514 | 460.8 | 29.8 | 0.022 |
| null:crop-only | 0.858 | 50.2 | 28.4 | 0.000 |
