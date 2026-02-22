# PAIR — auto pipeline

flags: SAM fringe mask rejected: median depth 45px > 15% of garment height 274px; before garment is short (bermuda/shorts): a short->shorter cut, not jeans->shorts; wash preset median: shrink 2.0% along / 1.0% across (PRIOR, not measured); 71505 px changed
before: /Users/jefferyhuang/denim-twin/data/external/pair_images/26b1041d00_before_62dc9a85.jpg 
after: /Users/jefferyhuang/denim-twin/data/external/pair_images/26b1041d00_after_cut_38ff38d5.jpg 
scale: UNKNOWN (1.0 placeholder; mm values are px)
landmarks: auto / auto (crotch: gap / gap)
fringe depth used: 0.0 px from measured from after-photo (NOT a prediction); measured on after-photo: 0.0 px (fabric/fringe split: colour split; registered-frame)
hem fit: left: angle 9.1°, depth 0 px, right: angle -9.5°, depth 0 px
registration residual (leave-one-landmark-out): 14.59px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.879 | 3.8 | 22.6 | 0.016 |
| pred median | 0.879 | 3.8 | 22.6 | 0.027 |
| pred aggressive | 0.880 | 3.8 | 22.6 | 0.062 |
| null:no-op | 0.738 | 48.4 | 31.6 | 0.048 |
| null:crop-only | 0.879 | 3.9 | 24.0 | 0.000 |
