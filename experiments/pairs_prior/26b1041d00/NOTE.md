# PAIR — auto pipeline

flags: SAM fringe mask rejected: median depth 45px > 15% of garment height 274px; before garment is short (bermuda/shorts): a short->shorter cut, not jeans->shorts; fringe measured directly: 4.0px in the after frame (rel 0.0166, coverage 0.93); SAM/hem-fit said 0.0px
before: /Users/jefferyhuang/denim-twin/data/external/pair_images/26b1041d00_before_62dc9a85.jpg 
after: /Users/jefferyhuang/denim-twin/data/external/pair_images/26b1041d00_after_cut_38ff38d5.jpg 
scale: UNKNOWN (1.0 placeholder; mm values are px)
landmarks: auto / auto (crotch: gap / gap)
fringe depth used: 0.6 px from prior[after_cut] (n=4 after excluding self, INSUFFICIENT); measured on after-photo: 4.0 px (fabric/fringe split: colour split; registered-frame)
hem fit: left: angle 9.1°, depth 0 px, right: angle -9.5°, depth 0 px
registration residual (leave-one-landmark-out): 14.59px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.888 | 2.8 | 24.3 | 0.025 |
| pred median | 0.888 | 2.8 | 24.3 | 0.033 |
| pred aggressive | 0.888 | 2.9 | 24.3 | 0.100 |
| null:no-op | 0.732 | 51.5 | 33.0 | 0.016 |
| null:crop-only | 0.888 | 2.8 | 24.3 | 0.000 |
