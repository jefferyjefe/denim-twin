# PAIR — auto pipeline

flags: before: rotated -15.2° to upright; after: rotated -3.0° to upright; fringe mask ignored for the hem fit: edge_treatment 'raw' cannot fray; direct fringe measurement failed (577 columns); falling back to the SAM/hem-fit value 9.0px; no fringe rendered: edge_treatment 'raw' with no wash does not fray (EXP_0017)
before: /Users/jefferyhuang/denim-twin/experiments/pairs_hemmask/963fcdd264/cropped_before.png 
after: /Users/jefferyhuang/denim-twin/data/external/pair_images/963fcdd264_after_cut_99243a19.jpg 
scale: UNKNOWN (1.0 placeholder; mm values are px)
landmarks: auto / auto (crotch: gap / gap)
fringe depth used: 0.0 px from measured from after-photo (NOT a prediction) [suppressed: finished hem]; measured on after-photo: 9.0 px (fabric/fringe split: SAM; after-frame)
hem fit: left: angle -32.8°, depth 0 px, right: angle 6.8°, depth 0 px
registration residual (leave-one-landmark-out): 49.91px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.532 | 5.5 | 27.2 | 0.013 |
| pred median | 0.532 | 5.5 | 27.2 | 0.017 |
| pred aggressive | 0.534 | 5.3 | 27.2 | 0.039 |
| null:no-op | 0.328 | 71.4 | 33.0 | 0.088 |
| null:crop-only | 0.531 | 5.5 | 27.0 | 0.000 |
