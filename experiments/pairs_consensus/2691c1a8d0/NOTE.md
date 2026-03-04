# PAIR — auto pipeline

flags: segmentation by consensus: 100% of prompt sets agree, area 0.73; segmentation by consensus: 100% of prompt sets agree, area 0.53; before: legs reach the frame bottom — original hem unknown; cut expressed vs frame, not inseam; SAM fringe mask rejected: median depth 116px > 15% of garment height 386px; before garment is short (bermuda/shorts): a short->shorter cut, not jeans->shorts; fringe measured directly: 3.0px in the after frame (rel 0.0110, coverage 1.00); SAM/hem-fit said 3.5px; no fringe rendered: edge_treatment 'raw' with no wash does not fray (EXP_0017)
before: /Users/jefferyhuang/denim-twin/data/external/pair_images/2691c1a8d0_before_b9f7f64b.jpg 
after: /Users/jefferyhuang/denim-twin/data/external/pair_images/2691c1a8d0_after_cut_b2330819.jpg 
scale: UNKNOWN (1.0 placeholder; mm values are px)
landmarks: auto / auto (crotch: gap / gap)
fringe depth used: 0.0 px from measured from after-photo (NOT a prediction) [suppressed: finished hem]; measured on after-photo: 4.5 px (fabric/fringe split: colour split; registered-frame)
hem fit: left: angle -8.8°, depth 2 px, right: angle 15.2°, depth 5 px
registration residual (leave-one-landmark-out): 74.51px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.843 | 23.9 | 20.5 | 0.002 |
| pred median | 0.843 | 23.9 | 20.5 | 0.005 |
| pred aggressive | 0.844 | 23.8 | 20.4 | 0.018 |
| null:no-op | 0.784 | 56.8 | 23.3 | 0.157 |
| null:crop-only | 0.843 | 23.9 | 20.6 | 0.000 |
