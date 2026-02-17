# PAIR — auto pipeline

flags: before: legs reach the frame bottom — original hem unknown; cut expressed vs frame, not inseam; before (refined): legs reach the frame bottom — original hem unknown; cut expressed vs frame, not inseam
before: /Users/jefferyhuang/denim-twin/data/external/pair_images/8d9f0df4ad_before_d50cdc5d.JPG 
after: /Users/jefferyhuang/denim-twin/data/external/pair_images/8d9f0df4ad_after_cut_ed6196cc.JPG 
scale: UNKNOWN (1.0 placeholder; mm values are px)
landmarks: auto / auto (crotch: gap / gap)
fringe depth used: 19.9 px from measured from after-photo (NOT a prediction); measured on after-photo: 19.9 px (fabric/fringe split: SAM; after-frame)
hem fit: left: angle 9.3°, depth 9, right: angle -10.6°, depth 1
registration residual (leave-one-landmark-out): 54.55px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.939 | 9.9 | 19.4 | 0.149 |
| pred median | 0.939 | 10.0 | 19.4 | 0.277 |
| pred aggressive | 0.938 | 10.8 | 19.5 | 0.323 |
| null:no-op | 0.427 | 303.8 | 21.1 | 0.018 |
| null:crop-only | 0.937 | 10.7 | 19.9 | 0.000 |
