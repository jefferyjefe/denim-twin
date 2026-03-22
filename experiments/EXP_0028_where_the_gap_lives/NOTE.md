# EXP_0028 — The product path's gap is not the cut specification

> **Partly superseded by EXP_0034.** The eval-vs-product analysis stands; the "dead heat" framing
> against the crop-only null does not — that null crops at the model's own predicted cut line.


EXP_0027 left one number as the research problem: the product path scores 0.803 silhouette IoU where the evaluation
path, which may look at the real after-photo, scores 0.857. The obvious hypothesis is that the difference is what the
user can say about the cut — one height against a fitted, per-leg, angled line. This tests it by handing the product
path progressively more of the answer.

`predict.py` gained `--cut-path`: the cut as a **polyline in canonical coordinates**, which is what a user drawing on
their own photo would supply and the most information the interface can carry. `score_predict.py --path-source
fitted` extracts that polyline from the evaluation path's own removed mask.

## The ladder (7 pairs after `exclude.txt`, `--wash none`)

| what the product path is told | silhouette IoU | hem error |
|---|---|---|
| one canonical inseam fraction | **0.8232** | 20.9 px |
| + the fitted cut angle | 0.8168 | 22.5 px |
| + the **whole fitted cut line**, 16 canonical samples | 0.8190 | 21.9 px |
| — evaluation path, which fits the cut to the real after-photo — | **0.8566** | 7.8 px |

**Giving the product path the exact cut line recovers none of the gap.** It is not better than a single number, and
neither is the angle. Whatever separates the two paths, it is not what the user is allowed to say about the cut.

## Where the gap actually is

On five of the seven pairs the two paths produce nearly the same garment: predicted-silhouette IoU between them is
0.952, 0.990, 0.995, 0.995, 0.997, and their scores differ by 0.006–0.029. The aggregate gap is carried by two pairs
where the same canonical cut yields a different removed region:

| pair | IoU between the two predictions | removed fraction, evaluation vs product |
|---|---|---|
| 2b0123d732 | 0.815 | 0.251 vs 0.352 |
| 8d9f0df4ad | 0.904 | 0.566 vs 0.522 |

Registration is not the cause — the residual is identical to the tenth of a pixel on all seven pairs, because both
paths register the same after-photo with the same landmarks. Nor is the canonical frame, once the harness bug below
is fixed: the two paths' canonical maps now agree exactly.

## A harness bug worth its own paragraph, because EXP_0022 caused it

`score_predict.py` fed `predict.py` the file `run_pair` writes as `before_used.png` — which `run_pair` **overwrites
with the uprighted image**. While the upright deadband was 8° that was almost always harmless. Once EXP_0022 set it
to 0, every pair was uprighted twice, and on 2b0123d732 `run_pair` rotated the photo −23.5° and `predict`, handed the
result, rotated it **+24.3°** back. Segmenting a rotated, border-filled image is not the same as segmenting the
original, so the round trip is not the identity.

Cost across the set: **0.020 of silhouette IoU and 11 px of hem error**. `run_pair` now writes `before_native.png`
and `after_native.png` — the photographs as they came in — and `score_predict` uses them. EXP_0027's headline is
corrected from 0.803 to **0.823**; its conclusion is unchanged, because the crop-only null moves with it and the two
remain a dead heat (0.8232 against 0.8233).

`tests/test_upright.py` now pins the invariant that broke: uprighting an already-uprighted image, **re-segmenting it
in between**, must not rotate it again.

## What this leaves

The research problem is smaller and more specific than "predict the cut": on five of seven pairs the product path
already reproduces what the evaluation path produces. What it does not have is a way to know, from the before-photo
alone, where those other two garments were actually cut — and no richer cut interface fixes that, because the
interface was never the limit.
