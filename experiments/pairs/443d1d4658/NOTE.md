# PAIR — auto pipeline

flags: none
before: /Users/jefferyhuang/denim-twin/data/external/pair_images/443d1d4658_before_fa971284.jpg 
after: /Users/jefferyhuang/denim-twin/data/external/pair_images/443d1d4658_after_cut_340b311d.jpg 
scale: UNKNOWN (1.0 placeholder; mm values are px)
landmarks: auto / auto (crotch: gap / gap)
fringe depth used: 60.2 px from measured from after-photo (NOT a prediction); measured on after-photo: 60.2 px (fabric/fringe split: SAM)
hem fit: left: angle 0.9°, depth 30, right: angle -0.7°, depth 90
registration residual (leave-one-landmark-out): 5.76px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.677 | 98.9 | 21.4 | 0.057 |
| pred median | 0.702 | 89.2 | 20.9 | 0.142 |
| pred aggressive | 0.722 | 80.6 | 20.2 | 0.212 |
| null:no-op | 0.597 | 189.9 | 10.3 | 0.329 |
| null:crop-only | 0.661 | 105.1 | 21.7 | 0.000 |
