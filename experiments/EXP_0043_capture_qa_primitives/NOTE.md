# EXP_0043 — What the pilot's three new capture checks can decide, and one control that was wrong

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

## B. What separates five re-lays from one lay photographed five times

> **Corrected step 43.** The first version of this section reported that image similarity
> *cannot* separate the two cases, and built the check on a high-pass of the registered garment
> interior. Both were artefacts of a wrong model of the control. It modelled "the same lay
> photographed again" as a FRESH RENDER with a new texture seed — which changes the cloth's own
> micro-texture, the one thing that does not change when nobody touches the garment. The numbers
> below come from the honest control: the same frame, new sensor noise, a pixel or two of camera
> shake.

This is the check that stops five copies of one lay satisfying five independent repeats.

| | whole-image NCC | registered interior, high-passed | registered interior, crease band |
|---|---|---|---|
| the same lay, photographed again | ~0.938125 | 0.75 – 0.93 | **0.988482** and above |
| genuinely independent re-lays | ≤ 0.997583 | 0.04 – 0.06 | ≤ **0.826518** |
| separates the two? | by -0.0595 | **no** | **yes, by 0.161964** |

**The high-pass was backwards, and it was a false pass.** A crease is a broad, soft shading
structure. High-passing the interior deleted exactly that and kept pixel grain — so an ordinary
re-shot of an unmoved garment, whose grain is entirely different, correlated 0.75–0.93 and read as a
genuine re-lay. The check now band-passes at the scale creases occupy (Gaussian sigma
2.5 to 32.0 px on a 256-square normalised interior): the low cut removes sensor grain, the high
cut removes the illumination gradient, so a frame that is merely brighter does not read as a
different lay.

**Whole-image similarity does separate them, and is still the wrong instrument.** With the honest
control it puts the same lay at ~0.938125 and re-lays at ≤0.997583 — a gap of -0.0595, sitting
directly on the near-duplicate threshold, where a re-encode or a brightness shift also lives. The
crease band's gap is 0.161964, an order of magnitude wider, and it is measuring the thing that
physically changed rather than a summary of the whole frame.

**Displacement is now corroboration only.** With camera shake in the control, a garment that was not
moved shows a centroid shift up to **0.7003 mm** while independent re-lays never landed closer than
**0.8465 mm** to each other — bands that nearly touch. It is kept because a sub-millimetre
reproduction is still evidence the garment did not move, but it no longer carries the decision.

**The limitation this rests on.** The crease field in the fixture is a model, and so is the sensor
noise. On real photographs both figures will move. The unresolved band returns
HUMAN_VERIFICATION_REQUIRED, so a mis-set threshold costs a confirmation and never a false pass —
and the check never returns PASS on geometry alone, because a garment dragged rather than lifted
looks the same. Re-derive both edges from the first real session.

## C. Duplicates

Exact content hash catches the copied file. Near-duplicate correlation catches the re-encoded or
brightened copy: those measured at or above **0.999642**, against at most 0.997583 for genuine
re-lays. Between the two bands nothing is decided automatically.

## What this licenses

The tilt check may gate `mm_per_px` validity. The relay check may *refuse* a repeat, and may never
*grant* one without the operator's recorded confirmation. Neither may be quoted as a statement about
a real garment until re-derived on real captures.
