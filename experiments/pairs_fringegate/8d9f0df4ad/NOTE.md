# PAIR — auto pipeline

flags: before: rotated -1.2° to upright; after: rotated 1.1° to upright; before: legs reach the frame bottom — original hem unknown; cut expressed vs frame, not inseam; before (refined): legs reach the frame bottom — original hem unknown; cut expressed vs frame, not inseam; fringe mask ignored for the hem fit: edge_treatment 'cuffed' cannot fray; fringe measured directly: 5.0px in the after frame (rel 0.0055, coverage 0.12); SAM/hem-fit said 4.5px; no fringe rendered: edge_treatment 'cuffed' with no wash does not fray (EXP_0017)
before: /Users/jefferyhuang/denim-twin/data/external/pair_images/8d9f0df4ad_before_d50cdc5d.JPG 
after: /Users/jefferyhuang/denim-twin/data/external/pair_images/8d9f0df4ad_after_cut_ed6196cc.JPG 
scale: UNKNOWN (1.0 placeholder; mm values are px)
landmarks: auto / auto (crotch: gap / gap)
fringe depth used: 0.0 px from measured from after-photo (NOT a prediction) [suppressed: finished hem]; measured on after-photo: 3.2 px (fabric/fringe split: SAM; after-frame)
hem fit: left: angle 21.5°, depth 3 px, right: angle -16.8°, depth 1 px
registration residual (leave-one-landmark-out): 27.94px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.956 | 4.0 | 20.1 | 0.063 |
| pred median | 0.956 | 4.0 | 20.1 | 0.090 |
| pred aggressive | 0.956 | 3.9 | 20.0 | 0.155 |
| null:no-op | 0.422 | 353.0 | 22.8 | 0.005 |
| null:crop-only | 0.956 | 4.2 | 20.2 | 0.000 |
