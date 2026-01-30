# PAIR — auto pipeline

flags: none
before: /Users/jefferyhuang/denim-twin/data/external/pair_images/f9c0e56308_before_5de12702.jpg 
after: /Users/jefferyhuang/denim-twin/data/external/pair_images/f9c0e56308_after_wash_a77d6342.jpg 
scale: UNKNOWN (1.0 placeholder; mm values are px)
landmarks: auto / auto (crotch: gap / gap)
fringe depth used: 546.8 px from measured from after-photo (NOT a prediction); measured on after-photo: 546.8 px (fabric/fringe split: SAM)
hem fit: left: angle 6.2°, depth 605, right: angle -5.7°, depth 488
registration residual (leave-one-landmark-out): 117.07px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.522 | 566.2 | 28.0 | 0.132 |
| pred median | 0.537 | 524.1 | 28.7 | 0.273 |
| pred aggressive | 0.549 | 489.8 | 28.4 | 0.365 |
| null:no-op | 0.553 | 517.7 | 22.7 | 0.448 |
| null:crop-only | 0.510 | 601.7 | 23.8 | 0.000 |
