# EXP_0043 — Two of the pilot's three new capture checks measure what they claim; the third cannot, and says so

The Pilot Capture Navigator gates a physical, irreversible act: it decides whether enough evidence
exists to cut a garment. Three of the checks standing behind that decision have no implementation in
this repository, and each could fail in the direction that matters — returning PASS when the
evidence does not support one. This measures what each can actually decide.

Nothing here needs a photograph. The captures are synthesised with a real ChArUco board at a scale
the script sets, so the error in a measured mm/px is *known* rather than estimated against a second
measurement of the same image. That is why these thresholds can be re-derived in clean CI, and it is
also the limitation: a synthetic garment is not a garment. Where that matters, it is said below.

Reproduce: `tools/experiment_capture_primitives.py` → `reports/pilot_qa_primitives.json`.

## A. `mm_per_pixel` is biased by tilt long before tilt is visible

`capture/board.mm_per_pixel` takes the **median** spacing of adjacent chessboard corners. On a board
that is not fronto-parallel, that median is a biased estimate of scale, and the bias arrives early:

| keystone warp | 0° | 1° | 2° | 3° | 4° | 6° | 8° | 12° | 18° |
|---|---|---|---|---|---|---|---|---|---|
| scale error (median) | 0.4% | 1.0% | 2.1% | 4.0% | 5.5% | 8.2% | **11.6%** | 18.3% | 32.3% |
| `scale_range_ratio` (median) | 1.030 | 1.037 | 1.046 | 1.057 | 1.065 | 1.086 | 1.112 | 1.172 | 1.272 |

A fray depth of 5 mm read to 0.5 mm is a 10% measurement. At a warp a person would call "near
enough overhead", the scale is already **11.6%** wrong — larger than the quantity being measured.
This is the defect the check exists for, and it is invisible in the existing pipeline because
`mm_per_pixel` returns one confident number either way.

The observable is `scale_range_ratio`: the 95th over the 5th percentile of local corner spacing. It
is 1.0 for a fronto-parallel board, needs **no camera intrinsics**, and is precisely the quantity
that decides whether one mm/px can describe the frame. Its noise floor is not zero — level boards
measured a median of **1.03015** and a maximum of **1.04039** from corner-detection noise alone — so
the PASS band cannot sit below about 1.05 without failing genuinely level captures.

Across 108 captures, the worst scale error on anything the check called PASS was **0.0414** of the true scale (4.1%).

An `approx_tilt_deg` is also computed, from a homography with an **assumed** focal length. It is
reported for a human to read and nothing turns on it, because the assumption is unverifiable from
the frame.

## B. Image similarity cannot tell five re-lays from one photograph five times — the crease field can

This is the check that stops five copies of one image satisfying five independent repeats, and the
obvious implementation does not work. Measured:

| | whole-image NCC | registered interior NCC |
|---|---|---|
| the same lay, photographed again | 0.99715 | 0.985279 |
| genuinely independent re-lays | 0.996925 | ≤ **0.865029** |
| separates the two? | **no** | **yes, by 0.12025** |

Whole-image correlation put every case between 0.996636 and 1.0000 — the same lay re-shot scored
**higher** than some genuine re-lays. The silhouette and the backdrop dominate that number, and they
are exactly what does *not* change.

What does change is the cloth. Lift a garment and lay it out again and it falls into a different set
of creases. Aligning the two captures on centroid and principal axis and correlating the garment
**interiors** separates the cases with a margin of **0.12025** and no overlap.

Garment displacement corroborates it: not moving the garment reproduced its centroid to within
**0.0372 mm**, while independent re-lays never landed closer than **0.3669 mm** to each other.

**The limitation this rests on.** The crease field in the fixture is a model. On real photographs the
same-lay figure will fall (sensor noise, lighting drift, camera shake) and the re-lay figure may rise
(a lay reproduced carefully). Both band edges must be re-derived from the first real session. The
unresolved band returns HUMAN_VERIFICATION_REQUIRED, so a mis-set threshold costs a confirmation,
never a false pass — and the check never returns PASS on geometry alone, because a garment that was
dragged rather than lifted looks the same.

## C. Duplicates

Exact content hash catches the copied file. Near-duplicate correlation catches the re-encoded or
brightened copy: those measured at or above **0.999593**, against at most 0.996925 for genuine
re-lays. Between the two bands nothing is decided automatically.

## What this licenses

The tilt check may gate `mm_per_px` validity. The relay check may *refuse* a repeat, and may never
*grant* one without the operator's recorded confirmation. Neither may be quoted as a statement about
a real garment until re-derived on real captures.
