# PAIR — auto pipeline

flags: after: touches the edge of a MANUAL crop (second object removed from frame)
before: /Users/jefferyhuang/denim-twin/data/external/pair_images/443d1d4658_before_fa971284.jpg 
after: /Users/jefferyhuang/denim-twin/experiments/pairs/443d1d4658/cropped_after_cut.png 
scale: given
landmarks: auto / auto (crotch: gap / gap)
fringe depth used: 7.8 px from measured from after-photo (NOT a prediction); measured on after-photo: 7.8 px (fabric/fringe split: colour split; registered-frame)
hem fit: left: angle 11.4°, depth 14 px, right: angle -11.3°, depth 2 px (mm_per_px 0.9770)
registration residual (leave-one-landmark-out): 6.42px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.918 | 9.1 | 18.3 | 0.068 |
| pred median | 0.917 | 9.7 | 18.5 | 0.142 |
| pred aggressive | 0.915 | 10.6 | 18.7 | 0.121 |
| null:no-op | 0.587 | 240.7 | 21.4 | 0.005 |
| null:crop-only | 0.918 | 8.9 | 18.3 | 0.000 |
