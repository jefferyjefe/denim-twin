# PAIR — auto pipeline

flags: after: rotated 2.1° to upright; SAM fringe mask rejected: median depth 44px > 15% of garment height 269px; before garment is short (bermuda/shorts): a short->shorter cut, not jeans->shorts; wash preset median: shrink 2.0% along / 1.0% across (PRIOR, not measured); 71496 px changed; direct fringe measurement failed (350 columns); falling back to the SAM/hem-fit value 0.5px; no fringe rendered: edge_treatment 'cuffed' with no wash does not fray (EXP_0017)
before: /Users/jefferyhuang/denim-twin/data/external/pair_images/26b1041d00_before_62dc9a85.jpg 
after: /Users/jefferyhuang/denim-twin/data/external/pair_images/26b1041d00_after_cut_38ff38d5.jpg 
scale: UNKNOWN (1.0 placeholder; mm values are px)
landmarks: auto / auto (crotch: gap / gap)
fringe depth used: 0.0 px from measured from after-photo (NOT a prediction) [suppressed: finished hem]; measured on after-photo: 0.5 px (fabric/fringe split: colour split; registered-frame)
hem fit: left: angle 12.6°, depth 1 px, right: angle -9.5°, depth 0 px
registration residual (leave-one-landmark-out): 11.21px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.894 | 3.9 | 23.2 | 0.000 |
| pred median | 0.894 | 3.9 | 23.2 | 0.000 |
| pred aggressive | 0.894 | 3.9 | 23.2 | 0.000 |
| null:no-op | 0.736 | 53.4 | 34.2 | 0.015 |
| null:crop-only | 0.899 | 2.9 | 24.2 | 0.000 |
