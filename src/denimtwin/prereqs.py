"""What a check needs from outside the repository, whether it is here, and how to get it.

A clean clone of this repository has no photographs, no masks, no model weights and no network. That
is deliberate: `data/external/README.md` says only derived NUMBERS enter the repository, so every
garment photograph, every mask traced from one, and the 375 MB SAM checkpoint are gitignored. What
was *not* deliberate is how the suite discovered that fact -- one assertion at a time, in four
different dialects:

  * `tests/test_repeatability_harness.py` aborted pytest COLLECTION, because a tool it imports did a
    module-level `from denimtwin.seg.sam import ...` and that module imported torch. One missing
    optional dependency took the whole suite with it.
  * `tests/test_waistband.py` asserted `n >= 7` after a loop over gitignored masks, so absent
    evidence arrived as a red test indistinguishable from a broken algorithm.
  * `tools/make_reports.py` reported six reports STALE -- "the numbers no longer match the data" --
    when the truth was that the data was not there to match.
  * `tests/test_review6_exp0017_claims.py` said `pytest.skip("no scored pair runs in this checkout")`,
    which is the right answer, in prose no other tool could read.

All four are the same question, and it deserves one answer. A resource is declared here once, with a
probe that is cheap and side-effect free, the exact command that satisfies it, and -- the part that
matters scientifically -- a sentence saying what a check that needs it may still conclude when it is
absent. `tests/conftest.py` turns that into a skip or a failure depending on the profile,
`tools/verify.py` turns it into an UNAVAILABLE row rather than a pass, and `tools/make_reports.py`
uses it to tell "input absent" from "report drifted".

Nothing here imports numpy, cv2 or torch, and nothing here touches the network. Probing must be
safe to do from inside a conftest before any test has run.

The network is the one resource with no probe. It is never "available" because a machine happens to
have a route to the internet: `data/external/README.md` forbids redistributing the photographs this
project harvests, and a verification run that can silently fetch copyrighted material is a legal
problem before it is a reproducibility one. It becomes available only when a human sets
DENIMTWIN_ALLOW_NETWORK=1 for a deliberate harvest. No verification profile sets it.
"""
import functools
import glob
import shutil
import importlib.util
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

#: Profiles a verification run can ask for. See tools/verify.py.
#:   ci   -- hermetic. Committed inputs only: no torch, no SAM, no network, no photograph, no mask.
#:            A pass means the repository is internally consistent. It means nothing about physics.
#:   full -- every check, over real garment evidence. A pass here is the scientific claim, and it is
#:            not available at all unless every physical prerequisite below is actually present.
PROFILES = ("ci", "full")


class Resource:
    """One external prerequisite: how to detect it, how to get it, and what its absence proves.

    `absent_means` is not decoration. It is the sentence a verification report prints instead of a
    result, and it exists so that "we could not run this" can never be read as "this passed".
    """

    __slots__ = ("name", "kind", "what", "targets", "how", "absent_means", "min_count")

    def __init__(self, name, kind, what, targets, how, absent_means, min_count=1):
        self.name = name
        self.kind = kind              # "module" | "path" | "glob" | "optin"
        self.what = what
        self.targets = targets
        self.how = how
        self.absent_means = absent_means
        self.min_count = min_count

    # -- probing ---------------------------------------------------------------
    def _probe(self):
        if self.kind == "module":
            # find_spec, not import: importing torch costs seconds and we only need to know.
            for m in self.targets:
                try:
                    if importlib.util.find_spec(m) is None:
                        return False
                except (ImportError, ValueError):
                    return False
            return True
        if self.kind == "optin":
            return os.environ.get(self.targets[0], "") == "1"
        if self.kind == "exe":
            return all(shutil.which(t) is not None for t in self.targets)
        if self.kind == "path":
            return all((ROOT / t).exists() for t in self.targets)
        if self.kind == "glob":
            return all(len(glob.glob(str(ROOT / t), recursive=True)) >= self.min_count
                       for t in self.targets)
        raise ValueError(f"unknown probe kind {self.kind!r} for resource {self.name!r}")

    def available(self):
        return _cached_probe(self.name)

    def found(self):
        """How many artefacts the probe can see. Used for reporting, not for deciding."""
        if self.kind in ("module", "optin", "path", "exe"):
            return int(self._probe())
        return sum(len(glob.glob(str(ROOT / t), recursive=True)) for t in self.targets)


# The registry. Order is the order verify.py prints its prerequisite audit in: dependencies first,
# then weights, then evidence, then the network.
_R = [
    Resource(
        "torch", "module", "PyTorch (an optional dependency: only the segmenter needs it)",
        ["torch"],
        "pip install -r requirements.txt   # or: pip install torch torchvision",
        "the segmentation code path did not execute. Nothing is known about whether it works; this "
        "is not evidence that it is broken.",
    ),
    Resource(
        "segment_anything", "module", "Meta's segment-anything package",
        ["segment_anything"],
        "pip install -r requirements.txt   # or: pip install segment-anything",
        "no mask could be produced from a photograph in this run.",
    ),
    Resource(
        "open_clip", "module", "open_clip_torch, used by the image role/CLIP gate",
        ["open_clip"],
        "pip install -r requirements.txt   # or: pip install open_clip_torch",
        "the CLIP role check did not run; harvested images were not classified in this run.",
    ),
    Resource(
        "sam_checkpoint", "path", "the SAM ViT-B checkpoint (375 MB, gitignored)",
        ["models/sam_vit_b_01ec64.pth"],
        "mkdir -p models && curl -L -o models/sam_vit_b_01ec64.pth "
        "https://dl.fbaipublicfiles.com/segment_anything/sam_vit_b_01ec64.pth",
        "no photograph was segmented. Every downstream number that starts at a mask is unverified "
        "in this run, not refuted.",
    ),
    Resource(
        "pair_runs", "glob",
        "the committed per-pair records (modification/landmarks/measure JSON)",
        ["experiments/pairs/*/modification.json"],
        "these are committed; if they are missing the checkout is damaged -- git checkout experiments/pairs",
        "no pair record was readable, so nothing that describes the found-pair set could be checked.",
        min_count=7,
    ),
    Resource(
        "pair_masks", "glob",
        "the segmented before/after masks for the found pairs (gitignored: traced from "
        "all-rights-reserved photographs)",
        ["experiments/pairs/*/amask.png"],
        "PAIRS_OUT=experiments/pairs python tools/run_pairs_batch.py   "
        "# needs sam_checkpoint, torch and data/external/pair_images",
        "no real mask was measured. Rules that were only ever validated against real masks -- the "
        "top-edge rule, the waistband corners, landmark stability -- are UNTESTED here, and a "
        "synthetic mask is not a substitute for them.",
        min_count=7,
    ),
    Resource(
        "experiment_masks", "glob",
        "any real segmentation mask under experiments/ (gitignored: every one is traced from an "
        "all-rights-reserved photograph)",
        ["experiments/**/*mask*.png"],
        "PAIRS_OUT=experiments/pairs python tools/run_pairs_batch.py   "
        "# and the variant batches named in the experiment NOTEs",
        "no mask produced by this pipeline was available to compare against. The probe asks only "
        "whether real masks exist AT ALL -- a test's own minimum-count assertion still guards "
        "completeness, so a half-deleted batch fails loudly instead of reporting UNAVAILABLE.",
        min_count=1,
    ),
    Resource(
        "pair_cmp_metrics", "glob",
        "per-pair scoring output (cmp_*/metrics.json), written by a scoring batch run",
        ["experiments/pairs/*/cmp_median/metrics.json"],
        "PAIRS_OUT=experiments/pairs python tools/run_pairs_batch.py",
        "no pair was scored, so no accuracy comparison in this repository was re-derived.",
        min_count=7,
    ),
    Resource(
        "pair_predict_batch", "glob",
        "the product-path batch used by the prediction-vs-crop-only comparison",
        ["experiments/pairs_predict_post0038/*/cmp/keep_mask.png"],
        "PAIRS_OUT=experiments/pairs_predict_post0038 python tools/run_pairs_batch.py --predict",
        "EXP_0034's demonstration that the crop-only null was the prediction compared with itself "
        "was not re-derived here. The finding stands on its committed report; this run adds nothing.",
        min_count=7,
    ),
    Resource(
        "pair_prefringegate", "glob",
        "the pre-fringe-gate A/B arm (gitignored batch output)",
        ["experiments/pairs_prefringegate/*/cmp_median/metrics.json"],
        "PAIRS_OUT=experiments/pairs_prefringegate python tools/run_pairs_batch.py",
        "the fringe-gate A/B was not recomputed.",
        min_count=7,
    ),
    Resource(
        "pair_images", "glob", "the found-pair photographs (all rights reserved, never redistributed)",
        ["data/external/pair_images/*"],
        "python tools/tutorial_pairs.py --fetch   # downloads copyrighted images to a gitignored "
        "directory; requires DENIMTWIN_ALLOW_NETWORK=1",
        "the pipeline was not run from a photograph in this checkout.",
        min_count=2,
    ),
    Resource(
        "external_images", "glob", "the harvested CC-licensed image set",
        ["data/external/images/*"],
        "DENIMTWIN_ALLOW_NETWORK=1 python tools/harvest_images.py",
        "the harvested set was not inspected; claims about its yield rest on the committed manifest.",
    ),
    Resource(
        "unpaired_images", "glob", "unpaired CC images used by the repeatability harness",
        ["data/external/unpaired_images/*"],
        "DENIMTWIN_ALLOW_NETWORK=1 python tools/ingest_unpaired.py --fetch",
        "the repeatability harness had no subjects.",
    ),
    Resource(
        "control_images", "glob", "control photographs for the repeatability harness",
        ["data/external/control_images/*"],
        "see data/external/README.md -- controls are added by hand, not fetched",
        "the repeatability harness had no controls.",
    ),
    Resource(
        "repeatability_masks", "glob", "masks written by the repeatability harness (gitignored)",
        ["reports/repeatability/masks/*.png"],
        "python tools/experiment_repeatability.py",
        "EXP_0021's masks were not re-measured.",
    ),
    Resource(
        "garment_images", "glob", "capture-protocol photographs of the physical garments",
        ["data/garments/*/images/*"],
        "capture them following protocol/PROTOCOL.md; they are gitignored by design",
        "no physical garment capture was examined. This is the resource whose absence makes a "
        "physical-accuracy claim impossible, not merely unproven.",
    ),
    Resource(
        "node", "exe", "a JavaScript runtime, to execute the capture app's own ui/app.js",
        ["node"],
        "install Node.js (brew install node, or your platform's package)",
        "the phone screen's own logic was not executed. The banner an operator reads immediately "
        "before an irreversible cut is written in JavaScript, and nothing else in this suite can "
        "run it -- a Python re-implementation would be testing a copy.",
    ),
    Resource(
        "network", "optin", "permission to make outbound HTTP requests",
        ["DENIMTWIN_ALLOW_NETWORK"],
        "DENIMTWIN_ALLOW_NETWORK=1 <command>   # deliberate, human-initiated, never in a verify profile",
        "no live service was contacted. A check that needs one is NOT RUN -- never passed, never "
        "failed. Verification does not fetch anything, by design.",
    ),
]

RESOURCES = {r.name: r for r in _R}

#: Resources a `--profile ci` run is allowed to depend on. Everything else is, by construction,
#: unavailable there -- so a CI pass cannot rest on a photograph, a weight file or a socket.
CI_RESOURCES = frozenset({"pair_runs"})

#: Resources `--profile full` must have before it may issue a scientific pass. Absence of any one of
#: them is not a failure of the algorithm; it is a refusal to make the claim.
#: It must cover EVERY non-opt-in resource any test declares. `experiment_masks` and
#: `external_images` were missing from the first version of this list, and the consequence was the
#: precise failure this whole mechanism exists to prevent: verify.py printed an all-"have"
#: prerequisite audit, ran the suite, and reported `FAIL tests -- a behaviour changed or a guard test
#: caught a regression` when the truth was that nobody had the photographs. Absent evidence wearing
#: the costume of a broken algorithm, one level up from where it was fixed.
#: tests/test_verify_profiles.py now derives the marker set from the suite by AST and fails if this
#: list does not cover it, so the two cannot drift apart again.
FULL_RESOURCES = frozenset({
    "torch", "segment_anything", "sam_checkpoint",
    "pair_runs", "pair_masks", "experiment_masks", "pair_cmp_metrics", "pair_predict_batch",
    "pair_images", "external_images", "node",
})


#: Comma-separated resource names to treat as ABSENT regardless of what the probe finds.
#:
#: This exists so the profile machinery can be tested on a machine that happens to have everything.
#: It is safe by construction and the direction is the whole reason: it can only ever REMOVE a
#: resource, never supply one. There is no switch here that makes an absent photograph look present,
#: so this cannot be used to manufacture a passing --profile full run -- the worst it can do is make
#: a verification refuse to make a claim it would otherwise have made, which is the failure mode this
#: repository prefers. tests/test_verify_profiles.py asserts both halves of that.
FORCE_ABSENT_ENV = "DENIMTWIN_FORCE_ABSENT"


def _forced_absent():
    return {x.strip() for x in os.environ.get(FORCE_ABSENT_ENV, "").split(",") if x.strip()}


@functools.lru_cache(maxsize=None)
def _cached_probe(name):
    """Probes are stable for the life of a process; a test run must not pay for them repeatedly."""
    if name in _forced_absent():
        return False
    return RESOURCES[name]._probe()


def available(name):
    if name not in RESOURCES:
        raise KeyError(f"unknown resource {name!r}; declare it in {__file__}")
    return _cached_probe(name)


def missing(names):
    """The subset of `names` that is not here, in registry order so reports are stable."""
    want = set(names)
    unknown = want - set(RESOURCES)
    if unknown:
        raise KeyError(f"unknown resource(s): {sorted(unknown)}")
    return [n for n in RESOURCES if n in want and not available(n)]


def explain(name):
    """One line for a human staring at an UNAVAILABLE row."""
    r = RESOURCES[name]
    return f"{r.what}\n      satisfy with: {r.how}\n      absence means: {r.absent_means}"


def status():
    """Everything the registry knows, for a machine-readable prerequisite audit."""
    return {
        n: {"available": available(n), "what": r.what, "kind": r.kind,
            "targets": list(r.targets), "found": r.found(), "how": r.how,
            "absent_means": r.absent_means}
        for n, r in RESOURCES.items()
    }


def profile_resources(profile):
    if profile not in PROFILES:
        raise ValueError(f"unknown profile {profile!r}; expected one of {PROFILES}")
    return CI_RESOURCES if profile == "ci" else FULL_RESOURCES


def require_network(tool, what):
    """Refuse to make an outbound request unless a human deliberately allowed it.

    The registry has documented DENIMTWIN_ALLOW_NETWORK=1 as the way to satisfy the `network`
    resource since it was written, and until this function existed nothing enforced it: the four
    tools that fetch would happily reach out to anyone who ran them, including from inside an
    automated job. A documented guarantee nothing implements is worse than no guarantee, because
    people plan around it.

    Fetching here means downloading photographs this project is explicitly NOT licensed to
    redistribute (`data/external/README.md`), so the safe default is to refuse and say so. Call this
    at the point of fetching, not at import: reading a manifest, validating records and printing a
    plan must all keep working offline.
    """
    if available("network"):
        return
    raise SystemExit(
        f"\n{tool}: refusing to {what}.\n\n"
        f"  This would make outbound requests and write copyrighted images to disk. Downloading is\n"
        f"  opt-in on purpose -- no verification profile enables it, so `tools/verify.py` can never\n"
        f"  fetch anything, and neither can a test run.\n\n"
        f"  If you mean to, say so explicitly:\n\n"
        f"      DENIMTWIN_ALLOW_NETWORK=1 {tool} ...\n\n"
        f"  Everything that does not need the network -- reading the manifest, validating records,\n"
        f"  printing what WOULD be fetched -- still works without it.\n")


def reset_cache():
    """Only for tests that create and remove artefacts inside one process."""
    _cached_probe.cache_clear()
