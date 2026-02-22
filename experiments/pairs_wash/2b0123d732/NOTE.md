# PAIR — auto pipeline

flags: before: rotated -23.5° to upright; wash preset median: shrink 2.0% along / 1.0% across (PRIOR, not measured); 104277 px changed
before: /Users/jefferyhuang/denim-twin/data/external/pair_images/2b0123d732_before_07ba40f3.JPG 
after: /Users/jefferyhuang/denim-twin/data/external/pair_images/2b0123d732_after_cut_23fa579b.JPG 
scale: UNKNOWN (1.0 placeholder; mm values are px)
landmarks: auto / auto (crotch: gap / gap)
fringe depth used: 8.1 px from measured from after-photo (NOT a prediction); measured on after-photo: 8.1 px (fabric/fringe split: SAM; after-frame)
hem fit: left: angle -20.0°, depth 1 px, right: angle 54.9°, depth 5 px
registration residual (leave-one-landmark-out): 76.77px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.837 | 4.8 | 15.1 | 0.153 |
| pred median | 0.839 | 4.2 | 15.2 | 0.380 |
| pred aggressive | 0.839 | 4.8 | 15.3 | 0.422 |
| null:no-op | 0.665 | 108.7 | 19.1 | 0.039 |
| null:crop-only | 0.836 | 5.3 | 15.2 | 0.000 |
