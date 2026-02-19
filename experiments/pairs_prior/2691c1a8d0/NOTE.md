# PAIR — auto pipeline

flags: none
before: /Users/jefferyhuang/denim-twin/data/external/pair_images/2691c1a8d0_before_b9f7f64b.jpg 
after: /Users/jefferyhuang/denim-twin/data/external/pair_images/2691c1a8d0_after_cut_b2330819.jpg 
scale: UNKNOWN (1.0 placeholder; mm values are px)
landmarks: auto / auto (crotch: gap / gap)
fringe depth used: 0.4 px from prior[after_cut] (n=5 after excluding self); measured on after-photo: 120.2 px (fabric/fringe split: SAM; after-frame)
hem fit: left: angle -36.4°, depth 2 px, right: angle -48.2°, depth 62 px
registration residual (leave-one-landmark-out): 86.85px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.694 | 25.0 | 14.9 | 0.004 |
| pred median | 0.694 | 25.0 | 14.9 | 0.005 |
| pred aggressive | 0.695 | 24.9 | 14.9 | 0.012 |
| null:no-op | 0.579 | 109.7 | 17.5 | 0.101 |
| null:crop-only | 0.694 | 25.1 | 15.1 | 0.000 |
