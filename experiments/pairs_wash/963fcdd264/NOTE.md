# PAIR — auto pipeline

flags: before: rotated -15.2° to upright; after: rotated -3.0° to upright; wash preset median: shrink 2.0% along / 1.0% across (PRIOR, not measured); 33272 px changed; direct fringe measurement failed (577 columns); falling back to the SAM/hem-fit value 9.0px; no fringe rendered: edge_treatment 'raw' with no wash does not fray (EXP_0017)
before: /Users/jefferyhuang/denim-twin/experiments/pairs_wash/963fcdd264/cropped_before.png 
after: /Users/jefferyhuang/denim-twin/data/external/pair_images/963fcdd264_after_cut_99243a19.jpg 
scale: UNKNOWN (1.0 placeholder; mm values are px)
landmarks: auto / auto (crotch: gap / gap)
fringe depth used: 0.0 px from measured from after-photo (NOT a prediction) [suppressed: finished hem]; measured on after-photo: 9.0 px (fabric/fringe split: SAM; after-frame)
hem fit: left: angle -25.5°, depth 6 px, right: angle 6.8°, depth 0 px
registration residual (leave-one-landmark-out): 49.91px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.523 | 10.8 | 26.7 | 0.022 |
| pred median | 0.523 | 10.7 | 26.8 | 0.022 |
| pred aggressive | 0.525 | 10.5 | 26.8 | 0.029 |
| null:no-op | 0.328 | 71.4 | 32.9 | 0.092 |
| null:crop-only | 0.526 | 10.7 | 27.2 | 0.000 |
