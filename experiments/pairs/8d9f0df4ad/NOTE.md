# PAIR — auto pipeline

flags: before: legs reach the frame bottom — original hem unknown; cut expressed vs frame, not inseam; before (refined): legs reach the frame bottom — original hem unknown; cut expressed vs frame, not inseam
before: /Users/jefferyhuang/denim-twin/data/external/pair_images/8d9f0df4ad_before_d50cdc5d.JPG 
after: /Users/jefferyhuang/denim-twin/data/external/pair_images/8d9f0df4ad_after_cut_ed6196cc.JPG 
scale: UNKNOWN (1.0 placeholder; mm values are px)
landmarks: auto / auto (crotch: gap / gap)
fringe depth used: 21.2 px from measured from after-photo (NOT a prediction); measured on after-photo: 21.2 px (fabric/fringe split: SAM; after-frame)
hem fit: left: angle 14.1°, depth 7, right: angle -14.8°, depth 1
registration residual (leave-one-landmark-out): 31.22px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.946 | 7.7 | 21.1 | 0.194 |
| pred median | 0.945 | 8.2 | 21.0 | 0.311 |
| pred aggressive | 0.943 | 9.4 | 21.1 | 0.348 |
| null:no-op | 0.421 | 303.4 | 22.7 | 0.015 |
| null:crop-only | 0.943 | 8.7 | 21.5 | 0.000 |
