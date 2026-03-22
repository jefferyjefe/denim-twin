"""The experiment index must exist, be current, and flag superseded notes (EXP index)."""
import os, re, subprocess, sys
import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
IDX = os.path.join(ROOT, "experiments", "README.md")


def test_index_is_up_to_date():
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "experiment_index.py"), "--check"],
                       capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 0, r.stdout + r.stderr


def test_every_experiment_dir_is_listed():
    idx = open(IDX).read()
    dirs = [d for d in os.listdir(os.path.join(ROOT, "experiments"))
            if d.startswith("EXP_") and os.path.exists(os.path.join(ROOT, "experiments", d, "NOTE.md"))]
    missing = [d for d in dirs if d not in idx]
    assert not missing, f"experiments missing from the index: {missing}"


def test_a_supersession_pointer_is_never_self_referential():
    """The first pass pointed every flagged note at its own number, which is no pointer at all."""
    for line in open(IDX):
        m = re.search(r"\*\*(\d{4})\*\*.*\(see (EXP_\d{4})\)", line)
        if m:
            assert m.group(2) != f"EXP_{m.group(1)}", f"self-referential pointer: {line.strip()}"


def test_the_voided_croponly_notes_all_point_at_exp_0034():
    """EXP_0034 voided the crop-only comparison. Every note that still states it must say so --
    a superseded conclusion left unflagged is worse than no conclusion."""
    base = os.path.join(ROOT, "experiments")
    for d in sorted(os.listdir(base)):
        p = os.path.join(base, d, "NOTE.md")
        if not d.startswith("EXP_") or not os.path.exists(p):
            continue
        t = open(p).read()
        if d >= "EXP_0034":
            continue
        if "dead heat" in t or "crop-only null" in t:
            assert "EXP_0034" in t, f"{d} states the voided crop-only comparison with no pointer"


def test_the_word_correction_alone_does_not_flag_a_note():
    """'tilt correction' is a noun. Keying supersession on the word flagged EXP_0022 falsely."""
    src = open(os.path.join(ROOT, "tools", "experiment_index.py")).read()
    assert "RETRACTED_TITLE" in src and "BANNER" in src
    idx = open(IDX).read()
    line = next((l for l in idx.splitlines() if "**0022**" in l), "")
    assert "superseded" not in line, "EXP_0022 is falsely flagged again"
