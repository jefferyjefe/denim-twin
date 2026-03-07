# PAIR — auto pipeline

flags: before: rotated -1.2° to upright; after: rotated 1.1° to upright; before: legs reach the frame bottom — original hem unknown; cut expressed vs frame, not inseam; before (refined): legs reach the frame bottom — original hem unknown; cut expressed vs frame, not inseam; fringe measured directly: 5.0px in the after frame (rel 0.0055, coverage 0.12); SAM/hem-fit said 4.5px; no fringe rendered: edge_treatment 'cuffed' with no wash does not fray (EXP_0017)
before: /Users/jefferyhuang/denim-twin/data/external/pair_images/8d9f0df4ad_before_d50cdc5d.JPG 
after: /Users/jefferyhuang/denim-twin/data/external/pair_images/8d9f0df4ad_after_cut_ed6196cc.JPG 
scale: UNKNOWN (1.0 placeholder; mm values are px)
landmarks: auto / auto (crotch: gap / gap)
fringe depth used: 0.0 px from measured from after-photo (NOT a prediction) [suppressed: finished hem]; measured on after-photo: 3.2 px (fabric/fringe split: SAM; after-frame)
hem fit: left: angle 21.4°, depth 1 px, right: angle -14.4°, depth 0 px
registration residual (leave-one-landmark-out): 27.94px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.958 | 3.2 | 19.9 | 0.082 |
| pred median | 0.958 | 3.2 | 19.9 | 0.118 |
| pred aggressive | 0.958 | 3.2 | 19.9 | 0.190 |
| null:no-op | 0.422 | 350.8 | 22.9 | 0.004 |
| null:crop-only | 0.958 | 3.4 | 20.0 | 0.000 |
