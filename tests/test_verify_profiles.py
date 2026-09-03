"""The profile split itself has to be guarded, or it becomes the next thing that quietly stops working.

Three claims are load-bearing and none of them is self-evident from reading the code:

  1. `--profile ci` is HERMETIC. If a resource that needs torch, a checkpoint, a photograph or a
     socket ever creeps into the ci set, clean CI stops being clean and the collection bug that
     started all this becomes invisible again -- it was invisible for exactly as long as nobody ran
     the suite without torch.
  2. A test that declares a prerequisite gets SKIPPED under ci and FAILS under full. That asymmetry
     is the whole mechanism by which "we had no evidence" cannot be reported as "this passed", and
     it is one `if` in a conftest hook.
  3. Every resource name written in a `@pytest.mark.needs(...)` is a real entry in the registry. A
     typo'd name would otherwise be a test that declares a dependency nobody can satisfy -- or,
     worse, one the runtime silently treats as absent.

The third is checked statically over the whole suite rather than at runtime, because a marker on a
test that never runs is exactly the marker most likely to be wrong.
"""
import ast
import glob
import os
import re
import subprocess
import sys
import textwrap

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
from denimtwin import prereqs as P


# ---------------------------------------------------------------- the registry
def test_every_resource_is_fully_described():
    """A resource with no remediation is a dead end for whoever hits it, and a resource with no
    `absent_means` cannot be printed instead of a result -- which is the one job it has."""
    for name, r in P.RESOURCES.items():
        # "exe" was added for `node`: the phone screen is JavaScript, and the test that runs the
        # real ui/app.js needs a runtime to run it in. The list stays hand-written rather than
        # derived from Resource._probe, because deriving it would make any future kind valid by
        # construction and this assertion exists to refuse exactly that.
        assert r.kind in ("module", "path", "glob", "optin", "exe"), \
            f"{name}: bad probe kind {r.kind}"
        assert r.targets, f"{name}: probes nothing"
        assert len(r.what) > 10, f"{name}: no description"
        assert len(r.how) > 10, f"{name}: no command that would satisfy it"
        assert len(r.absent_means) > 30, (
            f"{name}: no 'absent_means'. Every UNAVAILABLE row prints this sentence in place of a "
            f"result; without it the row says 'not run' and leaves the reader to guess what that "
            f"costs them.")


def test_probing_is_side_effect_free_and_never_touches_the_network():
    """The probes run inside a conftest before any test has started. One of them fetching something
    would make the act of *asking whether we may use the network* use the network."""
    src = open(os.path.join(ROOT, "src", "denimtwin", "prereqs.py")).read()
    tree = ast.parse(src)
    imported = {n.module.split(".")[0] for n in ast.walk(tree)
                if isinstance(n, ast.ImportFrom) and n.module}
    imported |= {a.name.split(".")[0] for n in ast.walk(tree)
                 if isinstance(n, ast.Import) for a in n.names}
    # Checked against the import graph rather than the source text: the file necessarily *talks*
    # about sockets and HTTP requests -- describing the network resource is half its job -- and a
    # substring scan flagged its own prose. What must be true is that it cannot perform any of it.
    for banned in ("socket", "urllib", "http", "requests", "httpx", "subprocess", "ssl", "ftplib"):
        assert banned not in imported, (
            f"prereqs.py imports {banned}; probing must be local, free and side-effect free -- it "
            f"runs inside a conftest before any test has started.")
    for heavy in ("numpy", "cv2", "torch", "skimage", "scipy"):
        assert heavy not in imported, (
            f"prereqs.py imports {heavy}. It is imported by tests/conftest.py at collection time and "
            f"by tools that must run in the hermetic environment; it has to stay stdlib-only.")


def test_the_ci_profile_is_hermetic():
    """The invariant the whole clean-CI story rests on."""
    forbidden = {"torch", "segment_anything", "open_clip", "sam_checkpoint", "network",
                 "pair_masks", "experiment_masks", "pair_cmp_metrics", "pair_predict_batch",
                 "pair_images", "external_images", "unpaired_images", "control_images",
                 "repeatability_masks", "garment_images"}
    leaked = sorted(P.CI_RESOURCES & forbidden)
    assert not leaked, (
        f"--profile ci declares {leaked}, which a clean clone cannot have. Either the resource is "
        f"genuinely committed (then it does not belong in this list) or the ci profile has stopped "
        f"being hermetic and clean CI is no longer testing what it claims to test.")
    unknown = sorted(set(P.CI_RESOURCES) | set(P.FULL_RESOURCES) - set(P.RESOURCES))
    assert not [u for u in unknown if u not in P.RESOURCES], f"undeclared resources: {unknown}"


def test_the_network_is_never_available_by_accident():
    """It is opt-in by a human, for one command, and no verification profile sets it."""
    assert P.RESOURCES["network"].kind == "optin"
    assert "network" not in P.CI_RESOURCES and "network" not in P.FULL_RESOURCES
    # What matters is that verify.py never SETS the variable, not that it never names it. The first
    # version of this test banned the string outright, which also banned the comment explaining why
    # the variable is consulted -- and a rule that forbids code from documenting itself gets worked
    # around rather than obeyed. Checked against assignments and mutations instead.
    src = open(os.path.join(ROOT, "tools", "verify.py")).read()
    grants = re.findall(
        r"(?:os\.environ|env)\s*(?:\[\s*[\"']DENIMTWIN_ALLOW_NETWORK[\"']\s*\]\s*=|"
        r"\.setdefault\(\s*[\"']DENIMTWIN_ALLOW_NETWORK|"
        r"\.update\([^)]*DENIMTWIN_ALLOW_NETWORK)", src)
    assert not grants, f"verify.py grants itself network access: {grants}"
    # ...and it must not be able to inherit it silently either: the ci summary names `network` among
    # the things whose presence makes a run non-hermetic, so an ambient opt-in is reported, not hidden.
    assert '"network")' in src or "'network')" in src, (
        "verify.py must consult the network resource so an ambient DENIMTWIN_ALLOW_NETWORK=1 is "
        "reported rather than silently invalidating the 'no outbound connection' line")


# ---------------------------------------------------------------- the markers
def _declared_needs():
    """Every resource name written in a @pytest.mark.needs(...) anywhere in the suite."""
    out = []
    for f in sorted(glob.glob(os.path.join(ROOT, "tests", "test_*.py"))):
        tree = ast.parse(open(f).read(), filename=f)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            if (isinstance(fn, ast.Attribute) and fn.attr == "needs"
                    and isinstance(fn.value, ast.Attribute) and fn.value.attr == "mark"):
                for arg in node.args:
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        out.append((os.path.basename(f), arg.value))
    return out


def test_every_declared_prerequisite_exists_in_the_registry():
    declared = _declared_needs()
    assert declared, "no test declares a prerequisite; the marker mechanism is not in use"
    bad = sorted({(f, n) for f, n in declared if n not in P.RESOURCES})
    assert not bad, (
        f"@pytest.mark.needs names that are not in src/denimtwin/prereqs.py: {bad}. "
        f"A misspelt resource is a dependency nobody can satisfy.")


def test_the_marker_skips_under_ci_and_fails_under_full():
    """The asymmetry, end to end, through a real pytest run.

    This is the mechanism that stops absent evidence being reported as a scientific result, so it is
    checked by running it rather than by reading it, in a real subprocess.

    `pair_masks` is the absent resource, forced absent through DENIMTWIN_FORCE_ABSENT so the test is
    deterministic on a machine that has the evidence and on one that does not. It cannot be `network`:
    network is opt-in and is deliberately never escalated to a failure, since a full verification is
    a claim about garment evidence and has to stay completable offline.
    """
    import shutil
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        pkg = os.path.join(td, "tests")
        os.makedirs(pkg)
        shutil.copy(os.path.join(ROOT, "tests", "conftest.py"), os.path.join(pkg, "conftest.py"))
        open(os.path.join(pkg, "test_probe.py"), "w").write(textwrap.dedent('''
            import pytest

            @pytest.mark.needs("pair_masks")
            def test_needs_something_absent():
                assert False, "this body must never run; the prerequisite is absent"

            @pytest.mark.needs("pair_runs")
            def test_needs_something_committed():
                pass
        '''))
        env = dict(os.environ)
        # conftest.py resolves the package from its own location, so point it at the real one.
        env["PYTHONPATH"] = os.path.join(ROOT, "src") + os.pathsep + env.get("PYTHONPATH", "")
        env.pop("DENIMTWIN_SUITE_JSON", None)
        env.pop("DENIMTWIN_ALLOW_NETWORK", None)
        env["DENIMTWIN_FORCE_ABSENT"] = "pair_masks"

        def run(profile):
            env["DENIMTWIN_PROFILE"] = profile
            return subprocess.run([sys.executable, "-m", "pytest", pkg, "-q", "-rs", "-p", "no:cacheprovider"],
                                  capture_output=True, text=True, cwd=td, env=env)

        ci = run("ci")
        assert ci.returncode == 0, f"--profile ci should not fail on absent evidence:\n{ci.stdout}"
        assert "1 passed" in ci.stdout and "1 skipped" in ci.stdout, ci.stdout
        assert "UNAVAILABLE[pair_masks]" in ci.stdout, (
            f"the skip reason must name the resource so verify.py can count it:\n{ci.stdout}")

        full = run("full")
        assert full.returncode != 0, (
            f"--profile full must FAIL when declared evidence is absent -- a scientific pass may not "
            f"be issued over data that is not there:\n{full.stdout}")
        assert "UNAVAILABLE[pair_masks]" in full.stdout, full.stdout
        assert "this body must never run" not in full.stdout, (
            "the test body executed under --profile full; the prerequisite gate must run first")


def test_an_undeclared_resource_name_is_an_error_not_a_free_pass():
    """A typo must not read as 'available'."""
    assert "no_such_resource_at_all" not in P.RESOURCES
    with pytest.raises(KeyError):
        P.missing(["no_such_resource_at_all"])


# ---------------------------------------------------------------- verify.py
def test_verify_declares_a_profile_for_every_check():
    src = open(os.path.join(ROOT, "tools", "verify.py")).read()
    assert "--profile" in src and "ci" in P.PROFILES and "full" in P.PROFILES
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import verify
    assert verify.CHECKS, "verify.py has no checks"
    for c in verify.CHECKS:
        assert c.profiles, f"{c.name} runs in no profile"
        assert set(c.profiles) <= set(P.PROFILES), f"{c.name}: unknown profile in {c.profiles}"
        assert set(c.needs) <= set(P.RESOURCES), f"{c.name}: undeclared resource in {c.needs}"
        assert c.meaning, f"{c.name}: a failure must say what it means"


def test_the_bench_cannot_run_in_the_ci_profile():
    """It reads pair artefacts that a clean clone does not have, and it is the slowest thing here."""
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import verify
    bench = [c for c in verify.CHECKS if c.name == "bench"]
    assert bench, "the bench is no longer a check"
    assert "ci" not in bench[0].profiles, "the bench must not run in the hermetic profile"
    assert bench[0].needs, "the bench must declare the evidence it needs"


def test_a_ci_run_states_that_it_proves_nothing_about_physical_accuracy():
    """The most expensive mistake this repository has made is a green run being read as a stronger
    claim than it was. The disclaimer is part of the output contract, so it is asserted."""
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import verify
    # Whitespace-collapsed: the sentence is line-wrapped across print() calls, and a literal
    # substring check broke the moment it was reworded. What must hold is that the words are there.
    # Asserted against the constants themselves, not against the file's source text. Spread over a
    # run of print() calls, "anything whatsoever about physical prediction accuracy" was not a
    # substring of verify.py at all -- so the test that claimed to check for it was matching nothing.
    proves = " ".join(verify.CI_PROVES.split())
    assert "physical prediction accuracy" in proves
    assert "What a clean-CI pass proves" in proves
    assert "No garment was measured" in proves
    src = " ".join(open(os.path.join(ROOT, "tools", "verify.py")).read().split())
    # ...and that the disclaimer describes THIS run rather than an idealised one. verify.py used to
    # assert the suite ran "without torch, without the SAM checkpoint, without any photograph or
    # mask" unconditionally -- false on any machine that has them, which is every machine that can
    # run --profile full. The claim is now conditioned on the actual prerequisite probe.
    caveat = " ".join(verify.CI_NOT_HERMETIC.split())
    assert "was NOT hermetic" in caveat and "{present}" in caveat, (
        "the ci-profile caveat must name what was actually present on this machine")
    assert "P.available(n)" in src, (
        "the caveat must be driven by the real prerequisite probe, not printed unconditionally")
    full = " ".join(verify.FULL_PROVES.split())
    assert "NOT a claim about a controlled physical capture" in full, (
        "a full pass must not read as a claim about a controlled capture that does not exist yet")
    assert verify.UNAVAIL != verify.FAIL != verify.OK


def test_the_force_absent_hook_can_only_remove_a_resource():
    """The test affordance above must not be a way to manufacture a pass.

    It is one-directional on purpose: naming a resource makes it look ABSENT, and there is no
    spelling that makes an absent photograph look present. So the worst it can do is make a
    verification refuse a claim it would otherwise have made."""
    src = open(os.path.join(ROOT, "src", "denimtwin", "prereqs.py")).read()
    assert "return False" in src.split("_forced_absent()")[-1][:200], (
        "the force-absent hook must return False (absent); if it can ever return True it becomes a "
        "way to fake evidence and this whole mechanism is worthless")
    env = dict(os.environ)
    env["DENIMTWIN_FORCE_ABSENT"] = "pair_runs"
    env["PYTHONPATH"] = os.path.join(ROOT, "src") + os.pathsep + env.get("PYTHONPATH", "")
    r = subprocess.run(
        [sys.executable, "-c",
         "from denimtwin import prereqs as P; print(P.available('pair_runs'))"],
        capture_output=True, text=True, env=env)
    assert r.stdout.strip() == "False", f"force-absent did not take effect: {r.stdout}{r.stderr}"

    env["DENIMTWIN_FORCE_ABSENT"] = "network"
    r = subprocess.run(
        [sys.executable, "-c",
         "from denimtwin import prereqs as P; print(P.available('network'))"],
        capture_output=True, text=True, env=env)
    assert r.stdout.strip() == "False", "naming a resource must never make it available"


@pytest.mark.parametrize("tool,fn", [
    ("tools/harvest_images.py", "get"),
    ("tools/tutorial_pairs.py", "fetch"),
    ("tools/ingest_unpaired.py", "fetch"),
])
def test_no_tool_can_fetch_without_a_deliberate_opt_in(tool, fn):
    """The documented guarantee, actually enforced.

    src/denimtwin/prereqs.py has described DENIMTWIN_ALLOW_NETWORK=1 as the way to permit an outbound
    request since it was written, and for a while nothing implemented it: these three tools would
    fetch for anyone who ran them, including an unattended scheduled job. What they fetch is
    photographs this project is not licensed to redistribute, so refusing is the correct default and
    a documented guarantee nobody enforces is worse than none -- people plan around it.

    Checked by calling the fetch entry point directly with the opt-in absent and requiring a refusal,
    rather than by grepping for the call: a guard that is present but unreachable is the failure mode
    this repository keeps finding.
    """
    import importlib
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    mod = importlib.import_module(os.path.basename(tool)[:-3])
    env_was = os.environ.pop("DENIMTWIN_ALLOW_NETWORK", None)
    try:
        P.reset_cache()
        with pytest.raises(SystemExit) as e:
            if fn == "get":
                mod.get("https://example.invalid/")
            elif tool.endswith("tutorial_pairs.py"):
                mod.fetch([], 1)
            else:
                mod.fetch({"image_url": "https://example.invalid/x.jpg"})
        assert "DENIMTWIN_ALLOW_NETWORK=1" in str(e.value), (
            f"{tool} refused, but without telling the caller how to proceed deliberately")
    finally:
        if env_was is not None:
            os.environ["DENIMTWIN_ALLOW_NETWORK"] = env_was
        P.reset_cache()


def test_the_fetch_guard_is_at_the_fetch_site_not_at_import():
    """Reading a manifest, validating records and printing a plan must all keep working offline."""
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import importlib
    for name in ("harvest_images", "tutorial_pairs", "ingest_unpaired"):
        importlib.import_module(name)   # importing must not refuse


def test_the_full_profile_pre_checks_every_resource_the_suite_declares():
    """The gap that made --profile full report absent evidence as a regression.

    verify.py refuses the profile up front by consulting P.FULL_RESOURCES, a hand-written list. The
    suite declares its needs separately, in markers. When the two disagreed -- experiment_masks and
    external_images were declared by four tests and missing from the list -- verify.py printed a
    prerequisite audit in which everything was present, ran the suite anyway, and reported
    `FAIL tests | a behaviour changed or a guard test caught a regression`. That is exactly the
    confusion this session set out to remove, reintroduced one level above where it was fixed.

    Derived from the suite rather than restated, so the list cannot silently fall behind a marker."""
    declared = {n for _, n in _declared_needs()}
    # Opt-in resources are excluded by design: --profile full is a claim about garment evidence and
    # must stay completable offline. See tests/conftest.py.
    blocking = {n for n in declared if P.RESOURCES[n].kind != "optin"}
    missing = sorted(blocking - set(P.FULL_RESOURCES))
    assert not missing, (
        f"tests declare {missing} but --profile full does not pre-check them, so their absence "
        f"reaches the suite as a test FAILURE rather than a refusal. Add them to FULL_RESOURCES in "
        f"src/denimtwin/prereqs.py.")
