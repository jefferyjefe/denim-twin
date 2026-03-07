# PAIR — auto pipeline

flags: before: rotated 2.7° to upright; after: rotated 1.1° to upright; fringe measured directly: 3.0px in the after frame (rel 0.0123, coverage 0.98); SAM/hem-fit said 8.6px; no fringe rendered: edge_treatment 'raw' with no wash does not fray (EXP_0017)
before: /Users/jefferyhuang/denim-twin/data/external/pair_images/22a5857a0c_before_b45c63d8.jpg collage split (side-by-side) at x=319, kept left
after: /Users/jefferyhuang/denim-twin/data/external/pair_images/22a5857a0c_after_cut_714a806c.jpg collage split (side-by-side) at x=319, kept left
scale: UNKNOWN (1.0 placeholder; mm values are px)
landmarks: auto / auto (crotch: gap / gap)
fringe depth used: 0.0 px from measured from after-photo (NOT a prediction) [suppressed: finished hem]; measured on after-photo: 2.0 px (fabric/fringe split: SAM; after-frame)
hem fit: left: angle 2.9°, depth 0 px, right: angle -2.6°, depth 7 px
registration residual (leave-one-landmark-out): 13.70px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.894 | 7.3 | 17.0 | 0.019 |
| pred median | 0.893 | 7.3 | 17.0 | 0.024 |
| pred aggressive | 0.891 | 7.5 | 17.1 | 0.050 |
| null:no-op | 0.484 | 97.1 | 26.3 | 0.029 |
| null:crop-only | 0.895 | 7.1 | 17.2 | 0.000 |
