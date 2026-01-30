# PAIR — auto pipeline

flags: after: touches the edge of a MANUAL crop (second object removed from frame)
before: /Users/jefferyhuang/denim-twin/data/external/pair_images/443d1d4658_before_fa971284.jpg 
after: /Users/jefferyhuang/denim-twin/experiments/pairs/443d1d4658/cropped_after_cut.png 
scale: UNKNOWN (1.0 placeholder; mm values are px)
landmarks: auto / auto (crotch: gap / gap)
fringe depth used: 12.2 px from measured from after-photo (NOT a prediction); measured on after-photo: 12.2 px (fabric/fringe split: colour split)
hem fit: left: angle 10.7°, depth 22, right: angle -11.6°, depth 3
registration residual (leave-one-landmark-out): 7.26px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.919 | 13.9 | 13.1 | 0.071 |
| pred median | 0.917 | 14.7 | 13.2 | 0.214 |
| pred aggressive | 0.915 | 15.9 | 13.4 | 0.183 |
| null:no-op | 0.589 | 194.4 | 17.6 | 0.005 |
| null:crop-only | 0.920 | 13.6 | 13.0 | 0.000 |
