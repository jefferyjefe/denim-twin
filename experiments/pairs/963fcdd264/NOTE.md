# PAIR — auto pipeline

flags: before: rotated -15.2° to upright; after: rotated -3.0° to upright; fringe mask ignored for the hem fit: edge_treatment 'raw' cannot fray; direct fringe measurement failed (577 columns); falling back to the SAM/hem-fit value 9.0px; no fringe rendered: edge_treatment 'raw' with no wash does not fray (EXP_0017)
before: /Users/jefferyhuang/denim-twin/experiments/pairs/963fcdd264/cropped_before.png 
after: /Users/jefferyhuang/denim-twin/data/external/pair_images/963fcdd264_after_cut_99243a19.jpg 
scale: UNKNOWN (1.0 placeholder; mm values are px)
landmarks: auto / auto (crotch: gap / gap)
fringe depth used: 0.0 px from measured from after-photo (NOT a prediction) [suppressed: finished hem]; measured on after-photo: 9.0 px (fabric/fringe split: SAM; after-frame)
hem fit: left: angle -27.3°, depth 2 px, right: angle 6.1°, depth 0 px
registration residual (leave-one-landmark-out): 49.91px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.542 | 8.6 | 26.9 | 0.013 |
| pred median | 0.542 | 8.5 | 26.9 | 0.019 |
| pred aggressive | 0.543 | 8.3 | 27.0 | 0.040 |
| null:no-op | 0.328 | 71.4 | 32.9 | 0.079 |
| null:crop-only | 0.541 | 8.8 | 26.8 | 0.000 |
