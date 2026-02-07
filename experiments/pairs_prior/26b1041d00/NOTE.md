# PAIR — auto pipeline

flags: before garment is short (bermuda/shorts): a short->shorter cut, not jeans->shorts
before: /Users/jefferyhuang/denim-twin/data/external/pair_images/26b1041d00_before_62dc9a85.jpg 
after: /Users/jefferyhuang/denim-twin/data/external/pair_images/26b1041d00_after_cut_38ff38d5.jpg 
scale: UNKNOWN (1.0 placeholder; mm values are px)
landmarks: auto / auto (crotch: gap / gap)
fringe depth used: 3.5 px from prior[after_cut] (n=2 after excluding self, INSUFFICIENT); measured on after-photo: 45.0 px (fabric/fringe split: SAM)
hem fit: left: angle -5.4°, depth 64, right: angle -0.7°, depth 26
registration residual (leave-one-landmark-out): 14.59px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.688 | 46.1 | 34.7 | 0.002 |
| pred median | 0.690 | 45.6 | 34.6 | 0.010 |
| pred aggressive | 0.692 | 45.1 | 34.4 | 0.019 |
| null:no-op | 0.732 | 48.1 | 25.4 | 0.480 |
| null:crop-only | 0.688 | 46.2 | 34.8 | 0.000 |
