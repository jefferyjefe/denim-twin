# PAIR — auto pipeline

flags: before: legs reach the frame bottom — original hem unknown; cut expressed vs frame, not inseam; before (refined): legs reach the frame bottom — original hem unknown; cut expressed vs frame, not inseam; fringe measured directly: 3.0px in the after frame (rel 0.0033, coverage 0.12); SAM/hem-fit said 21.2px
before: /Users/jefferyhuang/denim-twin/data/external/pair_images/8d9f0df4ad_before_d50cdc5d.JPG 
after: /Users/jefferyhuang/denim-twin/data/external/pair_images/8d9f0df4ad_after_cut_ed6196cc.JPG 
scale: UNKNOWN (1.0 placeholder; mm values are px)
landmarks: auto / auto (crotch: gap / gap)
fringe depth used: 1.9 px from measured from after-photo (NOT a prediction); measured on after-photo: 1.9 px (fabric/fringe split: SAM; after-frame)
hem fit: left: angle 14.1°, depth 7 px, right: angle -14.8°, depth 1 px
registration residual (leave-one-landmark-out): 31.22px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.944 | 8.8 | 21.2 | 0.032 |
| pred median | 0.944 | 8.6 | 21.2 | 0.064 |
| pred aggressive | 0.945 | 8.5 | 21.2 | 0.108 |
| null:no-op | 0.421 | 339.5 | 22.7 | 0.015 |
| null:crop-only | 0.943 | 9.0 | 21.5 | 0.000 |
