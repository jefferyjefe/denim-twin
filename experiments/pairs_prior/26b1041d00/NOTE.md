# PAIR — auto pipeline

flags: SAM fringe mask rejected: median depth 45px > 15% of garment height 274px; before garment is short (bermuda/shorts): a short->shorter cut, not jeans->shorts; direct fringe measurement failed (342 columns); falling back to the SAM/hem-fit value 0.0px; no fringe rendered: edge_treatment 'cuffed' with no wash does not fray (EXP_0017)
before: /Users/jefferyhuang/denim-twin/data/external/pair_images/26b1041d00_before_62dc9a85.jpg 
after: /Users/jefferyhuang/denim-twin/data/external/pair_images/26b1041d00_after_cut_38ff38d5.jpg 
scale: UNKNOWN (1.0 placeholder; mm values are px)
landmarks: auto / auto (crotch: gap / gap)
fringe depth used: 0.0 px from prior[after_cut] (n=4 after excluding self, INSUFFICIENT) [suppressed: finished hem]; measured on after-photo: 0.0 px (fabric/fringe split: colour split; registered-frame)
hem fit: left: angle 9.1°, depth 0 px, right: angle -9.5°, depth 0 px
registration residual (leave-one-landmark-out): 14.59px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.888 | 2.8 | 24.3 | 0.025 |
| pred median | 0.888 | 2.8 | 24.3 | 0.033 |
| pred aggressive | 0.888 | 2.8 | 24.3 | 0.098 |
| null:no-op | 0.732 | 51.5 | 33.0 | 0.016 |
| null:crop-only | 0.888 | 2.8 | 24.3 | 0.000 |
