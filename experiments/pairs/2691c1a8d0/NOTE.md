# PAIR — auto pipeline

flags: none
before: /Users/jefferyhuang/denim-twin/data/external/pair_images/2691c1a8d0_before_b9f7f64b.jpg 
after: /Users/jefferyhuang/denim-twin/data/external/pair_images/2691c1a8d0_after_cut_b2330819.jpg 
scale: UNKNOWN (1.0 placeholder; mm values are px)
landmarks: auto / auto (crotch: gap / gap)
fringe depth used: 31.8 px from measured from after-photo (NOT a prediction); measured on after-photo: 31.8 px (fabric/fringe split: SAM)
hem fit: left: angle -36.4°, depth 2, right: angle -48.2°, depth 62
registration residual (leave-one-landmark-out): 86.85px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.699 | 25.8 | 15.1 | 0.211 |
| pred median | 0.703 | 24.2 | 15.5 | 0.392 |
| pred aggressive | 0.703 | 24.4 | 15.8 | 0.426 |
| null:no-op | 0.579 | 100.5 | 17.5 | 0.101 |
| null:crop-only | 0.694 | 27.3 | 15.1 | 0.000 |
