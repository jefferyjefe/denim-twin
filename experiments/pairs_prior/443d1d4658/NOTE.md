# PAIR — auto pipeline

flags: after: touches the edge of a MANUAL crop (second object removed from frame)
before: /Users/jefferyhuang/denim-twin/data/external/pair_images/443d1d4658_before_fa971284.jpg 
after: /Users/jefferyhuang/denim-twin/experiments/pairs_prior/443d1d4658/cropped_after_cut.png 
scale: given
landmarks: auto / auto (crotch: gap / gap)
fringe depth used: 52.0 px from prior (n=3 after excluding self, INSUFFICIENT); measured on after-photo: 7.8 px (fabric/fringe split: colour split)
hem fit: left: angle 11.4°, depth 13, right: angle -11.3°, depth 2
registration residual (leave-one-landmark-out): 6.42px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.911 | 17.0 | 19.4 | 0.181 |
| pred median | 0.896 | 23.8 | 21.1 | 0.090 |
| pred aggressive | 0.883 | 31.7 | 21.4 | 0.059 |
| null:no-op | 0.587 | 190.6 | 21.4 | 0.005 |
| null:crop-only | 0.918 | 13.4 | 18.3 | 0.000 |
