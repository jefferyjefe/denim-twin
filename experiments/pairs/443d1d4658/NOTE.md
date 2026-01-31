# PAIR — auto pipeline

flags: after: touches the edge of a MANUAL crop (second object removed from frame)
before: /Users/jefferyhuang/denim-twin/data/external/pair_images/443d1d4658_before_fa971284.jpg 
after: /Users/jefferyhuang/denim-twin/experiments/pairs/443d1d4658/cropped_after_cut.png 
scale: UNKNOWN (1.0 placeholder; mm values are px)
landmarks: auto / auto (crotch: gap / gap)
fringe depth used: 7.8 px from measured from after-photo (NOT a prediction); measured on after-photo: 7.8 px (fabric/fringe split: colour split)
hem fit: left: angle 11.4°, depth 14, right: angle -11.3°, depth 2
registration residual (leave-one-landmark-out): 6.42px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.918 | 13.9 | 13.1 | 0.068 |
| pred median | 0.917 | 14.4 | 13.2 | 0.141 |
| pred aggressive | 0.915 | 15.0 | 13.3 | 0.124 |
| null:no-op | 0.587 | 195.0 | 17.6 | 0.005 |
| null:crop-only | 0.918 | 13.8 | 13.0 | 0.000 |
