# PAIR — auto pipeline

flags: after: touches the edge of a MANUAL crop (second object removed from frame)
before: /Users/jefferyhuang/denim-twin/data/external/pair_images/443d1d4658_before_fa971284.jpg 
after: /Users/jefferyhuang/denim-twin/experiments/pairs_prior/443d1d4658/cropped_after_cut.png 
scale: given
landmarks: auto / auto (crotch: gap / gap)
fringe depth used: 32.5 px from prior[after_cut] (n=2 after excluding self, INSUFFICIENT); measured on after-photo: 7.8 px (fabric/fringe split: colour split)
hem fit: left: angle 11.4°, depth 13, right: angle -11.3°, depth 2
registration residual (leave-one-landmark-out): 6.42px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.915 | 14.9 | 18.9 | 0.224 |
| pred median | 0.906 | 19.3 | 20.2 | 0.137 |
| pred aggressive | 0.899 | 22.6 | 21.0 | 0.098 |
| null:no-op | 0.587 | 190.6 | 21.4 | 0.005 |
| null:crop-only | 0.918 | 13.4 | 18.3 | 0.000 |
