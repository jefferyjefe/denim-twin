# PAIR — auto pipeline

flags: after: touches the edge of a MANUAL crop (second object removed from frame)
before: /Users/jefferyhuang/denim-twin/data/external/pair_images/443d1d4658_before_fa971284.jpg 
after: /Users/jefferyhuang/denim-twin/experiments/pairs_v1/443d1d4658/cropped_after_cut.png 
scale: given
landmarks: auto / auto (crotch: gap / gap)
fringe depth used: 9.5 px from measured from after-photo (NOT a prediction); measured on after-photo: 9.5 px (fabric/fringe split: colour split; registered-frame)
hem fit: left: angle 8.5°, depth 16, right: angle -8.2°, depth 3
registration residual (leave-one-landmark-out): 16.65px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.917 | 12.3 | 15.6 | 0.065 |
| pred median | 0.916 | 12.7 | 15.8 | 0.173 |
| pred aggressive | 0.914 | 13.5 | 16.1 | 0.160 |
| null:no-op | 0.609 | 179.2 | 19.3 | 0.006 |
| null:crop-only | 0.917 | 12.1 | 15.6 | 0.000 |
