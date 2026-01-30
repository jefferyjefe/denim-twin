# PAIR — auto pipeline

flags: none
before: /Users/jefferyhuang/denim-twin/data/external/pair_images/f9c0e56308_before_5de12702.jpg 
after: /Users/jefferyhuang/denim-twin/experiments/pairs/f9c0e56308/cropped_after_wash.png 
scale: UNKNOWN (1.0 placeholder; mm values are px)
landmarks: auto / auto (crotch: gap / gap)
fringe depth used: 171.0 px from measured from after-photo (NOT a prediction); measured on after-photo: 171.0 px (fabric/fringe split: SAM)
hem fit: left: angle 5.3°, depth 264, right: angle -15.2°, depth 78
registration residual (leave-one-landmark-out): 107.92px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.734 | 162.3 | 25.2 | 0.130 |
| pred median | 0.780 | 118.6 | 26.8 | 0.303 |
| pred aggressive | 0.808 | 96.5 | 26.4 | 0.419 |
| null:no-op | 0.426 | 737.9 | 13.3 | 0.175 |
| null:crop-only | 0.699 | 197.7 | 20.9 | 0.000 |
