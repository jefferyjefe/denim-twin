#!/usr/bin/env python3
"""One command that says whether the repository is in a publishable state -- and what "publishable" meant.

The checks existed; nothing ran them together, and CI ran three of them with `|| true` so they
could not fail. Two defects reached the README that way -- a headline comparison that was void
(EXP_0034) and a scope check that flagged the line declaring its own ban and was therefore
ignored. This is the gate: every check, one exit code, and a table saying which one broke.

What this file now adds is the distinction that was missing underneath it. A verification run can
mean two completely different things, and until they were named, one was quietly standing in for the
other:

    tools/verify.py --profile ci      the repository is internally consistent
    tools/verify.py --profile full    the repository's claims about a real garment still hold

`--profile ci` checks only what a clean clone can check: no torch, no SAM checkpoint, no network, no
photograph, no mask -- none of which exist in a clean clone, all of which existed on the machine
where the numbers were produced. The profile does not FORCE those things absent, so running it on a
developer's machine is not itself a hermetic run and the summary says so; the hermetic property is
asserted by the clean-CI job, which refuses to start if the heavy packages are installed. What it
checks: the deterministic tests, the claim
bindings, the scope gates, the sentinels, the provenance manifest, the experiment index, and the
reports whose inputs are committed. A pass means the repository agrees with itself. It says NOTHING
about whether this system predicts anything about physical denim, and this file refuses to print a
line that could be read as saying otherwise.

`--profile full` is the scientific claim, and it is the one that can be refused. Every check that
needs real garment evidence declares that evidence in src/denimtwin/prereqs.py. If any of it is
absent, the affected checks are reported NOT RUN -- never passed, never failed -- each with the
exact command that would satisfy it, and the run exits 2 rather than 0. "We could not run this" and
"this passed" are different sentences and now have different exit codes.

The third thing worth stating plainly: a check that is UNAVAILABLE is not a check that failed. The
old output had one column for both, so an absent photograph and a broken algorithm produced the same
red row, and the honest response to each is opposite -- go and take a photograph, versus go and fix
the code.

    tools/verify.py [--profile ci|full] [--fast] [--no-bench] [--json PATH]

    --profile   ci (default): hermetic. full: everything, over real evidence.
    --fast      skip the pair bench (the slow one)
    --no-bench  same, kept explicit for CI
    --json      write the machine-readable run summary here as well

Exit 0 all required checks passed for this profile
     1 a required check FAILED -- something is wrong with the code or the numbers
     2 the profile could not be satisfied -- evidence is missing, nothing is claimed
"""
import argparse, json, os, subprocess, sys, time
from collections import namedtuple
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from denimtwin import prereqs as P   # noqa: E402  (path first)

PY_ = sys.executable

Check = namedtuple("Check", "name argv profiles needs required full_args meaning")

# (name, argv, profiles it runs in, resources it needs, required, extra argv under --profile full,
#  what a failure means)
CHECKS = [Check(*c) for c in [
    ("tests", [PY_, "-m", "pytest", "-q", "tests"], ("ci", "full"), (), True, [],
     "a behaviour changed or a guard test caught a regression"),
    ("claims", [PY_, "tools/check_claims.py"], ("ci", "full"), (), True, [],
     "a number quoted in a NOTE, the README or docs/ no longer matches the artefact it came from"),
    ("scope", [PY_, "tools/scope_check.py"], ("ci", "full"), (), True, [],
     "a file reaches past its phase gate, or names a treatment banned in year one"),
    ("sentinel", [PY_, "tools/sentinel.py"], ("ci", "full"), (), True, [],
     "a sentinel invariant broke"),
    ("provenance", [PY_, "tools/validate_provenance.py"], ("ci", "full"), (), True, [],
     "a data record claims rights, a pair type or an exact-garment status that does not validate; "
     "see docs/DATA_ELIGIBILITY.md"),
    ("reports", [PY_, "tools/make_reports.py", "--check", "--all"], ("ci", "full"), (), True,
     ["--require-inputs"],
     "a report no longer matches the data it is derived from: run tools/make_reports.py --write and "
     "update any NOTE quoting it (review 7 found four experiments publishing numbers that no longer reproduced)"),
    ("index", [PY_, "tools/experiment_index.py", "--check"], ("ci", "full"), (), True, [],
     "experiments/README.md is stale: run tools/experiment_index.py"),
    ("protocol", [PY_, "tools/protocol_audit.py"], ("ci", "full"), (), False, [],
     "a capture protocol drifted from its spec"),
    ("bench", [PY_, "tools/bench.py"], ("full",), ("pair_masks", "pair_cmp_metrics"), False, [],
     "a pair metric moved; two regressions against 443d1d4658 are documented and expected"),
    # The pilot's cut gate is the only check in this file that guards an IRREVERSIBLE PHYSICAL ACT.
    # It runs in the hermetic profile because it needs no photograph: the self test synthesises its
    # own captures around a real ChArUco board, so a clean clone can still prove that the gate
    # refuses incomplete evidence and opens on complete evidence.
    ("pilot", [PY_, "tools/pilot.py", "selftest"], ("ci", "full"), (), True, [],
     "the capture navigator's cut gate can be made to say READY without the evidence, or refuses "
     "to say it with the evidence -- either way a garment is at risk"),
    ("runbook", [PY_, "tools/make_runbook.py", "--check"], ("ci", "full"), (), True, [],
     "the printed pilot documents no longer match the shot plan: run tools/make_runbook.py --write. "
     "A runbook that has drifted sends the operator to collect a different set of evidence from the "
     "one the gate requires, and they find out with a garment on the table"),
    ("shotplan", [PY_, "tools/check_shotplan.py"], ("ci", "full"), (), True, [],
     "the shot-plan specification does not load, or a shot points at a region, feature or matched "
     "shot that does not exist -- each of which silently deletes a required photograph"),
]]

# The two closing statements, as data rather than as a run of print() calls. They are the most
# quotable lines this tool emits -- the ones someone screenshots next to a green tick -- so they are
# kept where a test can read them whole. Spread across print() calls, "anything whatsoever about
# physical prediction accuracy" was not a substring of this file at all, and the test asserting it
# was matching on hope.
CI_PROVES = """What a clean-CI pass proves: the committed inputs, claims, schemas, scope gates,
sentinels and experiment index agree with each other, and the deterministic tests pass over
committed inputs alone, with no outbound connection made from the suite.

What it does NOT prove, on any machine: anything whatsoever about physical prediction accuracy.
No garment was measured. Run --profile full for that, on a checkout that has the evidence;
see docs/PROJECT_STATUS.md."""

CI_NOT_HERMETIC = """NOTE: this run was NOT hermetic. The ci profile checks committed inputs; it does
not FORCE anything absent, and this machine has: {present}. Whichever of those are present really
were used -- heavy imports really happened, evidence-gated tests really executed, and if `network`
is listed then the socket block never installed itself, so the sentence above about outbound
connections describes a run that was free to make them. The hermetic claim belongs to the clean-CI
job, which asserts their absence before running (.github/workflows/tests.yml). To reproduce it
locally: a fresh clone plus requirements-ci.txt, or force them absent, e.g.
DENIMTWIN_FORCE_ABSENT=torch,sam_checkpoint,pair_masks tools/verify.py --profile ci"""

FULL_PROVES = """A --profile full pass means every check above ran against the evidence this
repository actually has: the found tutorial pairs and the artefacts derived from them. It is NOT a
claim about a controlled physical capture -- no such pair exists yet (docs/PROJECT_STATUS.md, "What
is blocked by missing physical data"), and `garment_images` is deliberately not a prerequisite of
this profile, because requiring it would make the profile unrunnable rather than merely bounded.
It is bounded by what these checks measure -- see docs/PROJECT_STATUS.md for which claims are
validated and which remain experimental."""


# Statuses, and the one rule that matters about them: UNAVAIL is not a synonym for FAIL, and neither
# of them is a synonym for OK.
OK, FAIL, WARN, SKIP, UNAVAIL = "OK", "FAIL", "WARN", "SKIP", "UNAVAIL"


def _run(check, profile, env):
    argv = list(check.argv) + (list(check.full_args) if profile == "full" else [])
    t0 = time.time()
    r = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, env=env)
    return r, time.time() - t0, argv


def _prereq_audit(profile):
    """What this profile needs from outside the repository, and what is actually here."""
    wanted = sorted(P.profile_resources(profile))
    return [(n, P.available(n), P.RESOURCES[n]) for n in wanted]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--profile", choices=P.PROFILES, default="ci",
                    help="ci (default): hermetic, committed inputs only. full: over real evidence.")
    ap.add_argument("--fast", action="store_true", help="skip the bench")
    ap.add_argument("--no-bench", action="store_true")
    ap.add_argument("--json", metavar="PATH", help="also write the run summary here")
    a = ap.parse_args()
    profile = a.profile
    skip_bench = a.fast or a.no_bench

    # ---------------------------------------------------------------- prerequisites
    audit = _prereq_audit(profile)
    absent = [(n, r) for n, ok, r in audit if not ok]

    print(f"\n  denim-twin verification -- profile: {profile}")
    print(f"  {'-' * 68}")
    if profile == "full":
        print("  prerequisites for a full scientific verification:")
        for n, ok, r in audit:
            mark = "have" if ok else "MISSING"
            count = f" ({r.found()})" if ok and r.kind == "glob" else ""
            print(f"    {mark:8s} {n}{count}")
        print()

    # A full run over absent evidence is not a run that fails; it is a claim that cannot be made.
    # Exiting 2 here, before anything executes, is the whole point: there is no combination of green
    # rows below that could add up to a scientific pass without these.
    if profile == "full" and absent:
        print(f"  REFUSED: --profile full cannot be satisfied. {len(absent)} prerequisite(s) absent.\n")
        for n, r in absent:
            print(f"    {n}: {r.what}")
            print(f"      satisfy with: {r.how}")
            print(f"      until then:   {r.absent_means}\n")
        print("  Nothing was run. This is NOT a failure of the code -- the evidence a full")
        print("  verification is about is not in this checkout. Run --profile ci for the checks")
        print("  that do not need it; that is a real result, and a much smaller one.\n")
        return 2

    # ---------------------------------------------------------------- checks
    env = dict(os.environ)
    env["DENIMTWIN_PROFILE"] = profile
    # The suite writes its own counts, classified. verify.py used to scrape them out of pytest's
    # summary line with a regex, which review 7 found stale by 136 tests and which reported a
    # collection ERROR as zero of everything.
    suite_json = ROOT / "reports" / "suite.json"
    env["DENIMTWIN_SUITE_JSON"] = str(suite_json)

    rows, failed, unavailable = [], 0, 0
    for c in CHECKS:
        if profile not in c.profiles:
            rows.append((c.name, SKIP, 0.0, c.required, f"not part of --profile {profile}"))
            continue
        if c.name == "bench" and skip_bench:
            rows.append((c.name, SKIP, 0.0, c.required, "--no-bench")); continue
        miss = P.missing(c.needs) if c.needs else []
        if miss:
            unavailable += 1
            rows.append((c.name, UNAVAIL, 0.0, c.required,
                         f"needs {', '.join(miss)} | {P.RESOURCES[miss[0]].how}"))
            continue

        r, dt, argv = _run(c, profile, env)
        ok = r.returncode == 0
        if not ok and c.required:
            failed += 1
        tail = (r.stdout + r.stderr).strip().splitlines()
        rows.append((c.name, OK if ok else (FAIL if c.required else WARN), dt, c.required,
                     "" if ok else (c.meaning + " | " + (tail[-1][:110] if tail else "no output"))))

    # ---------------------------------------------------------------- table
    suite = {}
    if suite_json.exists():
        try:
            suite = json.loads(suite_json.read_text())
        except (OSError, ValueError):
            suite = {}

    w = max(len(r[0]) for r in rows)
    print()
    for name, status, dt, required, why in rows:
        tag = "" if required else " (advisory)"
        print(f"  {status:7s} {name:{w}s}{tag}  {dt:5.1f}s")
        if why:
            print(f"          {why}")

    # Tests that declared a prerequisite and did not get it are NOT RUN. They are reported here
    # because a suite that quietly did not exercise its evidence looks exactly like one that did.
    by_res = suite.get("unavailable_by_resource") or {}
    if by_res:
        print(f"\n  {suite.get('unavailable', 0)} test(s) NOT RUN -- declared evidence absent:")
        for res, n in sorted(by_res.items()):
            print(f"    {n:3d}  {res}: {P.RESOURCES[res].what}")
            print(f"         satisfy with: {P.RESOURCES[res].how}")

    unclassified = suite.get("unclassified_skips")
    if unclassified:
        print(f"\n  {unclassified} test(s) skipped WITHOUT declaring a prerequisite. That is a guard "
              f"that stopped\n  running for a reason no tool can check; "
              f"tests/test_guards_are_not_optional.py caps it.")

    n_required_run = sum(1 for r in rows if r[3] and r[1] in (OK, FAIL))
    print(f"\n  {'FAILED' if failed else 'OK'}: {failed} required check(s) failing of "
          f"{n_required_run} run"
          + (f"; {unavailable} check(s) NOT RUN (evidence absent)" if unavailable else "") + ".")

    # ---------------------------------------------------------------- what this proves
    # The most expensive mistake this repository has made is letting a green run be read as a
    # stronger claim than it was. So the run states its own scope, every time, in both directions.
    print(f"\n  {'-' * 68}")
    if profile == "ci":
        # Describe THIS run, not the run we hoped for. This paragraph used to assert "the tests pass
        # without torch, without the SAM checkpoint, without any photograph or mask" unconditionally
        # -- including on a maintainer's machine where the ci profile forces nothing absent, so torch
        # loads, the 375 MB checkpoint loads, and dozens of evidence-gated tests really execute. The
        # sentence was true of the CI job and false of the run that printed it, which is the same
        # category of error as everything else this file was rewritten to fix.
        # `network` is in this list on purpose. With DENIMTWIN_ALLOW_NETWORK=1 in the ambient
        # environment the socket block in tests/conftest.py does not install itself at all, so
        # "no outbound connection made from the suite" would be printed by a run that was free to
        # make them. The claim has to be conditioned on the same thing the block is.
        present = [n for n in ("torch", "segment_anything", "sam_checkpoint", "pair_masks",
                               "experiment_masks", "pair_images", "external_images", "network")
                   if P.available(n)]
        if present:
            head, tail = CI_PROVES.split("\n\n", 1)
            body = f"{head}\n\n{CI_NOT_HERMETIC.format(present=', '.join(present))}\n\n{tail}"
        else:
            body = CI_PROVES
    else:
        body = FULL_PROVES
    for line in body.splitlines():
        print(f"  {line}" if line else "")
    print()

    payload = {
        "profile": profile, "failed": failed, "unavailable_checks": unavailable,
        "required_run": n_required_run,
        "checks": [{"name": n, "status": s, "seconds": round(dt, 2), "required": req, "why": why}
                   for n, s, dt, req, why in rows],
        "prerequisites": {n: ok for n, ok, _ in audit},
        "suite": suite,
        "proves": ("repository-internal consistency only; no physical accuracy was validated"
                   if profile == "ci" else
                   "the repository's checks ran against real garment evidence"),
    }
    if a.json:
        Path(a.json).parent.mkdir(parents=True, exist_ok=True)
        Path(a.json).write_text(json.dumps(payload, indent=1) + "\n")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
