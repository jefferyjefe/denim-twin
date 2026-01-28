# PAIR — auto pipeline

flags: before: legs reach the frame bottom — original hem unknown; cut expressed vs frame, not inseam; before (refined): legs reach the frame bottom — original hem unknown; cut expressed vs frame, not inseam
before: /Users/jefferyhuang/denim-twin/data/external/pair_images/8d9f0df4ad_before_d50cdc5d.JPG 
after: /Users/jefferyhuang/denim-twin/data/external/pair_images/8d9f0df4ad_after_cut_ed6196cc.JPG 
scale: UNKNOWN (1.0 placeholder; mm values are px)
landmarks: auto / auto (crotch: gap / gap)
fringe depth used: 4.0 px from measured from after-photo (NOT a prediction); measured on after-photo: 4.0 px (fabric/fringe split: SAM)
hem fit: left: angle 13.6°, depth 7, right: angle -14.4°, depth 1
registration residual (leave-one-landmark-out): 31.25px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.939 | 8.6 | 22.2 | 0.050 |
| pred median | 0.940 | 8.3 | 22.1 | 0.105 |
| pred aggressive | 0.940 | 8.2 | 22.1 | 0.155 |
| null:no-op | 0.419 | 303.2 | 23.2 | 0.016 |
| null:crop-only | 0.938 | 8.9 | 22.3 | 0.000 |
