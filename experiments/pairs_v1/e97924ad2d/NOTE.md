# PAIR — auto pipeline

flags: before: touches the edge of a MANUAL crop (second object removed from frame); before (refined): touches the edge of a MANUAL crop (second object removed from frame)
before: /Users/jefferyhuang/denim-twin/experiments/pairs_v1/e97924ad2d/cropped_before.png 
after: /Users/jefferyhuang/denim-twin/data/external/pair_images/e97924ad2d_after_cut_b11dd634.JPG 
scale: UNKNOWN (1.0 placeholder; mm values are px)
landmarks: auto / auto (crotch: gap / gap)
fringe depth used: 1.0 px from measured from after-photo (NOT a prediction); measured on after-photo: 1.0 px (fabric/fringe split: colour split; registered-frame)
hem fit: left: angle 22.8°, depth 1, right: angle -20.0°, depth 1
registration residual (leave-one-landmark-out): 24.48px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.929 | 5.2 | 11.2 | 0.311 |
| pred median | 0.929 | 5.2 | 11.2 | 0.376 |
| pred aggressive | 0.929 | 5.4 | 11.3 | 0.434 |
| null:no-op | 0.578 | 99.7 | 18.7 | 0.011 |
| null:crop-only | 0.927 | 5.6 | 11.0 | 0.000 |
