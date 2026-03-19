# PAIR — auto pipeline

flags: before: rotated -23.5° to upright; before: tilt -23.5° estimated from a near-isotropic silhouette — the principal-axis estimate is off by up to 4.7° there (EXP_0022) and the correction may be several degrees out; fringe mask ignored for the hem fit: edge_treatment 'cuffed' cannot fray; fringe measured directly: 2.0px in the after frame (rel 0.0069, coverage 0.91); SAM/hem-fit said 8.1px; no fringe rendered: edge_treatment 'cuffed' with no wash does not fray (EXP_0017)
before: /Users/jefferyhuang/denim-twin/data/external/pair_images/2b0123d732_before_07ba40f3.JPG 
after: /Users/jefferyhuang/denim-twin/data/external/pair_images/2b0123d732_after_cut_23fa579b.JPG 
scale: UNKNOWN (1.0 placeholder; mm values are px)
landmarks: auto / auto (crotch: gap / gap)
fringe depth used: 0.0 px from measured from after-photo (NOT a prediction) [suppressed: finished hem]; measured on after-photo: 2.0 px (fabric/fringe split: SAM; after-frame)
hem fit: left: angle -10.4°, depth 11 px, right: angle 51.6°, depth 1 px
registration residual (leave-one-landmark-out): 76.77px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.838 | 7.2 | 15.4 | 0.010 |
| pred median | 0.838 | 7.2 | 15.4 | 0.013 |
| pred aggressive | 0.838 | 7.2 | 15.4 | 0.036 |
| null:no-op | 0.664 | 110.5 | 18.4 | 0.056 |
| null:crop-only | 0.838 | 7.2 | 15.1 | 0.000 |
