# Reproducibility

Two environments, two claims. They are not interchangeable, and the difference between them is the
difference between "this repository agrees with itself" and "this system says something true about
a real pair of jeans".

## The install files

| file | installs | Python it is run on | what it is for |
|---|---|---|---|
| `requirements-ci.txt` | the hermetic core: numpy, OpenCV (**headless**), Pillow, PyYAML, jsonschema, scikit-image, SciPy, pytest | CPython 3.11 in CI | `tools/verify.py --profile ci`. No torch, no SAM, no network, no photographs. |
| `requirements.txt` | the same core with the **GUI** OpenCV build, plus torch, torchvision, segment-anything, open_clip_torch | CPython 3.9.6 on the maintainer's machine | local development and `tools/verify.py --profile full`. Roughly 3 GB. |
| `constraints.txt` | nothing on its own | both | the pinned transitive closure. Both files above apply it automatically with `-c`, so neither can be installed unpinned and the two cannot disagree about a shared version without pip aborting. |

Every version in those files was read from the maintainer's working virtualenv with
`.venv/bin/python -m pip list`; they are the versions the artefacts under `reports/` and
`experiments/` were produced with. `constraints.txt` records the provenance in full.

**OpenCV, GUI vs headless.** Both files pin the same OpenCV release and differ only in the build.
CI installs headless because a GitHub runner has no display and the GUI build's `import cv2` would
fail on missing GTK/Qt libraries. Local development installs the GUI build because
`tools/annotate_landmarks.py` opens a window (`cv2.imshow`, `cv2.setMouseCallback`) — it is the only
thing in the repository that does, it is an interactive annotator, and it is not part of any
verification profile. If you never annotate by hand, `requirements-ci.txt` is enough to run the
tests. Installing both distributions into one environment is a mistake: they both provide `cv2`.

## (i) Clean-CI verification, from a fresh clone, with no private data

This is what CI runs and what anyone can run. It needs no photographs, no masks, no model weights
and no network beyond the initial `pip install`.

    git clone <repo> && cd denim-twin
    python3.11 -m venv .venv && source .venv/bin/activate
    pip install -r requirements-ci.txt
    python tools/verify.py --profile ci

Exit codes: `0` every required check passed; `1` a check failed; `2` the profile could not be
satisfied, so nothing is claimed. To run only the test suite:

    DENIMTWIN_PROFILE=ci python -m pytest tests -q

Checks that need evidence a clean clone does not have are reported `UNAVAILABLE`, each with the
command that would satisfy it. `UNAVAILABLE` is counted separately from a pass and never printed as
one. The registry of those prerequisites is `src/denimtwin/prereqs.py`.

## (ii) Full verification, with real garment evidence

This is the scientific claim, and it can be refused.

    python3 -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt

Then obtain the evidence, none of which is in the repository:

* the SAM ViT-B checkpoint — see "Models" in `README.md`;
* the pair photographs and the batch outputs derived from them.

Every one of those is a named resource in `src/denimtwin/prereqs.py`, and each carries the exact
command that produces it in `RESOURCES[name].how`. `tools/verify.py --profile full` prints the list
of what is missing rather than making you guess. Then:

    python tools/verify.py --profile full

If any prerequisite is absent the run exits `2` and refuses: it does not fail the algorithm, and it
does not pass either. A `--profile full` pass is only issued when every check ran against real
evidence.

**Photographs are never redistributed.** They are all-rights-reserved, they are gitignored, and only
derived numbers enter this repository. See `data/external/README.md`. No verification profile fetches
anything; the test suite blocks outbound sockets unless `DENIMTWIN_ALLOW_NETWORK=1` is set by hand.

## What a clean-CI pass proves

That the repository is internally consistent: the numbers quoted in the notes match the artefacts
they were derived from, the schemas validate, the scope and provenance gates hold, the tools resolve
their paths against the repository rather than the working directory, and the deterministic tests
pass.

**It proves nothing about physical prediction accuracy.** No garment is measured in a clean-CI run,
because no garment is present in a clean clone. A green badge on this repository is a statement about
the repository, not about denim.

## The Python version discrepancy

CI pins CPython 3.11. The maintainer's `.venv` — the environment every committed result was produced
in — is CPython 3.9.6, the system Python on macOS. Every pin resolves to a wheel on both, so both
install identically and nothing is built from source, but they are still two interpreters and this
document should not pretend otherwise.

Recommendation, not applied here: move CI to 3.9 to match the environment the results came from, or
move the maintainer to 3.11 to match CI, and say which in the commit. Adding 3.9 as a second CI
matrix entry is the cheap version of the same thing and catches the interesting case — a result that
reproduces on one interpreter and not the other. Changing the CI interpreter is a change to
`.github/workflows/tests.yml`, which is not this document's to make. 3.9 is also near the end of its
security support, which argues for converging on 3.11 rather than on 3.9.

## Changing a pin

Bump it in `constraints.txt` (and in whichever requirements file names it), re-run the verification
above, and say in the commit message what moved and what it changed. A pin bumped without a re-run
silently detaches the committed numbers from the environment that produced them, which is the defect
this file exists to prevent.
