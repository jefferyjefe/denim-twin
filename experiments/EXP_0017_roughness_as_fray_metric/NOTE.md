# EXP_0017 — Scoring the fringe renderer on the one fray metric that passes a control

EXP_0016 gave us hem roughness: a fray observable with 0/14 false positives on finished-hem controls. It is now
computed for every system in `compare.py` (`hem_rough_p90_pred`, `hem_rough_p90_real`, `hem_rough_err_px`), which lets
us ask, for the first time with a controlled metric, whether the procedural fringe renderer produces a hem of
approximately the right raggedness.

## Result (11 usable found pairs, median preset)

| system | mean \|roughness error\| |
|---|---|
| prediction (cut + procedural fringe) | **0.91 px** |
| null: crop-only (a clean cut, no fringe) | 1.27 px |
| null: no-op (the uncut jeans) | 1.55 px |

Per pair, the prediction is closer to the real hem's roughness than crop-only on **6**, worse on 3, tied on 2.

## Read: directionally right, statistically nothing
A sign test on the 9 decided pairs gives **p = 0.51**. Six-three is what a coin does. The ordering
(prediction < crop-only < no-op) is the ordering we would want, and it is the first time the fringe renderer has beaten
a null on a metric whose control passes — but with n = 11 and a 0.36 px margin it is **not evidence** that the renderer
models fray. It is evidence that the metric is worth keeping and that the renderer is not obviously wrong.

## The failure mode worth naming
On three pairs the prediction puts roughness on a hem the real garment left smooth (b630a78c19, 443d1d4658,
e97924ad2d — all `after_cut` or finished-hem garments, predicted p90 1.0 px against a real 0.0). The renderer frays
whenever it is asked to render, including where the modification says the edge was cuffed or unwashed. The
`expects_fringe()` rule already exists in `modification.py`; `run_pair` does not consult it when rendering. That is a
concrete, testable fix — but it changes rendered output, so it is recorded here and left for the next round rather than
being slipped in alongside the measurement work (docs/GATES.md tuning rule).

## Status of the fray claim after EXP_0015–0017
- fringe **depth**: no valid measurement exists, at any resolution we can obtain (EXP_0015, EXP_0016).
- fringe **presence/roughness**: measurable, specific (0 false positives), resolution-limited (reliable above ~600–1000
  px of waistband).
- the **renderer**: produces roughness in the right direction, at p = 0.51. Nothing more can be said until there are
  more washed garments to score against.
