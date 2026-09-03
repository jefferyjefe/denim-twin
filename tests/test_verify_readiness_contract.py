"""What a verification profile claims to have run, and what it actually ran.

`tools/verify.py --profile full` calls itself "the scientific claim" and "everything, over real
evidence". Its `pilot` check ran `tools/pilot.py selftest` -- the ORDINARY self-test -- in both
profiles, and the ordinary self-test's three gate positive controls run on `_mini_spec`, a
four-shot fixture. The only thing that drives one garment through the real 424-frame plan and
asserts that all three gates OPEN, and the only place the sixteen single-fault negative controls
run, is `selftest --full`, and no profile threw that switch. So the strongest claim the repository
could make was made without the one proof that the plan an operator will actually shoot can be
satisfied at all.

The second thing here is smaller and worse. `main()` returned `1 if failed else 0`, and `failed`
only counts checks that RAN and exited non-zero. A REQUIRED check whose evidence was absent was
recorded UNAVAIL, printed as NOT RUN -- and the process still exited 0. No required check declares
a prerequisite today, so nothing was reaching it; it is the shape of the defect that matters,
because this file's whole subject is a verification that reports success while omitting what it
implies it ran. "We could not run this" and "this passed" already have different rows and different
prose. They now have different exit codes.

Both are checked against the REGISTERED CHECK GRAPH rather than against source text. A test that
greps for the string "--full" passes the day somebody renames the flag and stops running the proof.
"""
import importlib.util
import os
import subprocess
import sys
import textwrap

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))


def _verify_module():
    """Import tools/verify.py as a module so the check graph can be read as data."""
    spec = importlib.util.spec_from_file_location("_verify", os.path.join(ROOT, "tools", "verify.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


V = _verify_module()


def _check(name):
    for c in V.CHECKS:
        if c.name == name:
            return c
    raise AssertionError("tools/verify.py registers no check named %r; the checks it does register "
                         "are %s" % (name, sorted(c.name for c in V.CHECKS)))


def _argv(check, profile):
    """The argv this check would actually be run with under this profile."""
    return list(check.argv) + (list(check.full_args) if profile == "full" else [])


# ---------------------------------------------------------------- the real plan
def test_the_full_profile_drives_the_real_plan(): 
    """The scientific profile has to run the only proof that the production plan can be satisfied."""
    pilot = _check("pilot")
    assert "full" in pilot.profiles, "the full profile no longer runs the pilot check at all"
    argv = _argv(pilot, "full")
    assert "--full" in argv, (
        "tools/verify.py --profile full runs %r, which is the ordinary self-test. The three gate "
        "positive controls in that run are on a four-shot fixture; the real 424-frame plan, the "
        "three REAL PLAN positive controls and the single-fault negative controls only run behind "
        "--full. A profile that calls itself the scientific claim cannot omit the one proof that "
        "the plan the operator will shoot opens the gates." % (argv,))


def test_the_ci_profile_does_not_silently_take_the_hour_long_run():
    """The ordinary profile stays the ordinary profile; the two claims must not be confused."""
    argv = _argv(_check("pilot"), "ci")
    assert "--full" not in argv, (
        "the ci profile now runs the hour-long real-plan self-test. That is not a weaker claim than "
        "before, but it makes the hermetic profile something nobody will run, and the two claims "
        "this file exists to keep apart become one: %r" % (argv,))


def test_the_real_plan_proof_is_reachable_and_names_the_three_gates():
    """The switch has to reach a function that actually asserts all three gates open."""
    from denimtwin.pilot import selftest as ST
    assert hasattr(ST, "full_plan_scenarios"), (
        "selftest.py no longer exposes full_plan_scenarios, which is what --full reaches")
    src = ST.full_plan_scenarios.__doc__ or ""
    assert "real plan" in src.lower(), "full_plan_scenarios no longer describes itself as the real plan"
    import inspect
    body = inspect.getsource(ST.full_plan_scenarios)
    for gate in ("ready_to_cut", "ready_to_wash", "ready_to_finalize"):
        assert gate in body, (
            "the real-plan proof no longer opens %s. Every one of the three gates authorises an "
            "irreversible physical act and every one needs a positive control on the real plan."
            % gate)


def test_selftest_full_is_a_superset_of_the_ordinary_run():
    """--full must ADD to the ordinary scenarios, not replace them with a different set."""
    from denimtwin.pilot import selftest as ST
    import inspect
    body = inspect.getsource(ST.scenarios)
    assert "want_full" in body, "scenarios() no longer takes the --full switch"
    assert "full_plan_scenarios" in body, (
        "scenarios() no longer reaches full_plan_scenarios, so --full runs the ordinary set twice")


# ---------------------------------------------------------------- unavailable is not a pass
def test_an_unavailable_required_check_cannot_exit_zero(tmp_path):
    """A required check whose evidence is absent is NOT RUN, and NOT RUN is not success."""
    # Drive main() with one required check forced UNAVAIL, through the real code path rather than
    # through a re-implementation of it. The resource is a real registry entry forced absent by the
    # documented hook, so nothing here invents a status the tool cannot produce.
    script = textwrap.dedent("""
        import importlib.util, sys, os
        sys.argv = ["verify.py", "--profile", "ci", "--no-bench"]
        spec = importlib.util.spec_from_file_location("_v", %r)
        v = importlib.util.module_from_spec(spec); spec.loader.exec_module(v)
        # One required check, made unavailable by a prerequisite that is really absent.
        v.CHECKS = [c._replace(needs=("pair_masks",), required=True)
                    for c in v.CHECKS if c.name == "index"]
        sys.exit(v.main())
    """) % os.path.join(ROOT, "tools", "verify.py")
    env = dict(os.environ)
    env["DENIMTWIN_FORCE_ABSENT"] = "pair_masks"
    r = subprocess.run([sys.executable, "-c", script], cwd=ROOT, capture_output=True, text=True,
                       env=env)
    assert "UNAVAIL" in r.stdout, (
        "the check did not report UNAVAIL, so this test is not exercising what it claims:\n%s\n%s"
        % (r.stdout[-2000:], r.stderr[-2000:]))
    assert r.returncode != 0, (
        "a REQUIRED check was NOT RUN and tools/verify.py exited 0. 'we could not run this' and "
        "'this passed' are different sentences; they must not be the same exit code.\n%s"
        % r.stdout[-2000:])


def test_an_unavailable_advisory_check_still_exits_zero(tmp_path):
    """The rule is about REQUIRED checks. An advisory one that cannot run is not a failure."""
    script = textwrap.dedent("""
        import importlib.util, sys
        sys.argv = ["verify.py", "--profile", "ci", "--no-bench"]
        spec = importlib.util.spec_from_file_location("_v", %r)
        v = importlib.util.module_from_spec(spec); spec.loader.exec_module(v)
        v.CHECKS = [c._replace(needs=("pair_masks",), required=False)
                    for c in v.CHECKS if c.name == "index"]
        sys.exit(v.main())
    """) % os.path.join(ROOT, "tools", "verify.py")
    env = dict(os.environ)
    env["DENIMTWIN_FORCE_ABSENT"] = "pair_masks"
    r = subprocess.run([sys.executable, "-c", script], cwd=ROOT, capture_output=True, text=True,
                       env=env)
    assert "UNAVAIL" in r.stdout, r.stdout[-2000:]
    assert r.returncode == 0, (
        "an ADVISORY check that could not run failed the build. Advisory means advisory.\n%s"
        % r.stdout[-2000:])


def test_the_summary_payload_separates_not_run_from_passed():
    """The machine-readable summary must not fold NOT RUN into the pass count."""
    import inspect
    src = inspect.getsource(V.main)
    assert "unavailable_checks" in src, (
        "the JSON summary no longer reports how many checks were NOT RUN, so a consumer cannot "
        "tell a complete run from a partial one")
    # n_required_run must exclude UNAVAIL, or the denominator claims work that did not happen.
    assert "in (OK, FAIL)" in src or "in (V.OK, V.FAIL)" in src, (
        "the 'of N run' denominator no longer excludes checks that did not run")


# ---------------------------------------------------------------- what CI actually executes
WORKFLOW = os.path.join(ROOT, ".github", "workflows", "tests.yml")


def _jobs():
    import yaml
    with open(WORKFLOW) as fh:
        return yaml.safe_load(fh)["jobs"]


def _all_run_lines(job):
    out = []
    for step in job.get("steps") or []:
        if isinstance(step.get("run"), str):
            out.append(step["run"])
    return "\n".join(out)


def _invokes(job, *argv_prefixes):
    """Does some `run:` step of this job BEGIN a command line with one of these invocations?

    The first version of this file asked whether the string appeared anywhere in the job's run
    text, and the ordinary build's environment-check step mentions `--profile full` inside an error
    message. The test passed with the real-plan step deleted -- which is the exact shape of guard
    this file exists to refuse. An invocation is a line that starts with the command.
    """
    for line in _all_run_lines(job).splitlines():
        t = line.strip()
        if any(t.startswith(a) for a in argv_prefixes):
            return True
    return False


FULL_INVOCATIONS = ("python tools/pilot.py selftest --full", "python tools/verify.py --profile full")
CI_INVOCATIONS = ("python tools/verify.py --profile ci",)


def test_ci_executes_the_real_plan_proof_somewhere():
    """A documented claim that CI proves the production plan has to be a claim about a real job."""
    jobs = _jobs()
    runs_full = [name for name, job in jobs.items() if _invokes(job, *FULL_INVOCATIONS)]
    assert runs_full, (
        "no job in .github/workflows/tests.yml drives the real 424-frame plan. The ordinary "
        "self-test's three gate positive controls are on a four-shot fixture, so nothing in CI "
        "had ever shown the plan an operator will shoot opens the gates. Jobs present: %s"
        % sorted(jobs))


def test_the_real_plan_job_is_not_the_ordinary_build():
    """The two claims must stay separable: a green tick on one may not be quoted for the other."""
    jobs = _jobs()
    ordinary = [name for name, job in jobs.items() if _invokes(job, *CI_INVOCATIONS)]
    full = [name for name, job in jobs.items() if _invokes(job, *FULL_INVOCATIONS)]
    assert ordinary, "no job runs the hermetic profile any more"
    assert full, "no job runs the real-plan proof any more"
    assert not (set(ordinary) & set(full)), (
        "the same job runs both the hermetic profile and the hour-scale real-plan proof (%s). They "
        "prove different things and share one status check, so the weaker claim and the stronger "
        "one become one tick." % sorted(set(ordinary) & set(full)))


def test_the_real_plan_job_says_what_it_does_not_prove():
    """Every green result in this repository states its own scope. A new one is not exempt."""
    jobs = _jobs()
    for name, job in jobs.items():
        if not _invokes(job, *FULL_INVOCATIONS):
            continue
        text = _all_run_lines(job)
        low = text.lower()
        assert "does not prove" in low or "not prove" in low, (
            "job %r drives the real plan and prints no statement of what it does NOT prove. The "
            "most expensive mistake this repository has made is letting a green run be read as a "
            "stronger claim than it was." % name)
        assert "synthes" in low or "synthetic" in low, (
            "job %r does not say its frames were synthesised, which is the single fact that "
            "separates it from a claim about a real garment" % name)
