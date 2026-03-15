"""tools/verify.py is the single gate, and CI actually enforces it.

Three checks used to run in CI as `... || true`, so they could not fail the build. scope_check
spent months flagging the line that declares its own ban and nobody saw it, because a check that
cannot fail is not a check.
"""
import os, re
import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")


def test_verify_exists_and_lists_the_required_checks():
    src = open(os.path.join(ROOT, "tools", "verify.py")).read()
    for name in ("tests", "claims", "scope", "sentinel"):
        assert f'("{name}"' in src, f"{name} is no longer a check in verify.py"
    assert 'CHECKS' in src


def test_ci_runs_verify_and_does_not_swallow_failures():
    wf = open(os.path.join(ROOT, ".github", "workflows", "tests.yml")).read()
    assert "tools/verify.py" in wf, "CI no longer runs the verification gate"
    runs = re.findall(r"^\s*- run: (.+)$", wf, re.M)
    swallowed = [r for r in runs if "|| true" in r]
    assert not swallowed, f"CI steps that cannot fail: {swallowed}"


def test_scope_check_is_line_based_with_an_auditable_optout():
    """A file-wide regex condemned any file that so much as named a banned treatment, including
    the one declaring the ban. The opt-out must be an explicit marker, not a blanket skip."""
    src = open(os.path.join(ROOT, "tools", "scope_check.py")).read()
    assert "scope-ok:" in src
    assert "for i, line in enumerate(" in src


def test_every_scope_optout_states_a_reason():
    """`scope-ok:` with nothing after it would be a silent bypass."""
    import subprocess
    files = subprocess.run(["git", "ls-files", "src"], cwd=ROOT,
                           capture_output=True, text=True).stdout.split()
    for f in files:
        if not f.endswith(".py"):
            continue
        for i, line in enumerate(open(os.path.join(ROOT, f), errors="ignore"), 1):
            if "scope-ok:" in line:
                reason = line.split("scope-ok:", 1)[1].strip()
                assert len(reason) > 10, f"{f}:{i} opts out of the scope check without a reason"
