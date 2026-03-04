# PAIR — auto pipeline

flags: segmentation by consensus: 75% of prompt sets agree, area 0.45; segmentation by consensus: 100% of prompt sets agree, area 0.54; before: legs reach the frame bottom — original hem unknown; cut expressed vs frame, not inseam; before (refined): legs reach the frame bottom — original hem unknown; cut expressed vs frame, not inseam; fringe measured directly: 4.0px in the after frame (rel 0.0044, coverage 0.13); SAM/hem-fit said 6.4px; no fringe rendered: edge_treatment 'cuffed' with no wash does not fray (EXP_0017)
before: /Users/jefferyhuang/denim-twin/data/external/pair_images/8d9f0df4ad_before_d50cdc5d.JPG 
after: /Users/jefferyhuang/denim-twin/data/external/pair_images/8d9f0df4ad_after_cut_ed6196cc.JPG 
scale: UNKNOWN (1.0 placeholder; mm values are px)
landmarks: auto / auto (crotch: gap / gap)
fringe depth used: 0.0 px from measured from after-photo (NOT a prediction) [suppressed: finished hem]; measured on after-photo: 2.5 px (fabric/fringe split: SAM; after-frame)
hem fit: left: angle 20.6°, depth 1 px, right: angle -15.0°, depth 0 px
registration residual (leave-one-landmark-out): 28.30px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.956 | 3.5 | 20.8 | 0.060 |
| pred median | 0.956 | 3.5 | 20.8 | 0.088 |
| pred aggressive | 0.956 | 3.6 | 20.8 | 0.137 |
| null:no-op | 0.421 | 350.0 | 23.9 | 0.003 |
| null:crop-only | 0.956 | 3.5 | 20.9 | 0.000 |
