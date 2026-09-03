"""The protocol audit has to be able to say its one HARD thing without crashing.

`tools/protocol_audit.py` has exactly one HARD finding of its own: a `[FILL]` field in
PROTOCOL.md that `protocol_fields.COVERAGE` does not classify, so the audit cannot say whether it
blocks a real run. That finding was appended to `hard` three lines before `hard` was bound. Every
ordinary run of the audit left the list of unknown fields empty, so the branch never executed and
the NameError was invisible -- until the owner did the thing docs/PILOT_OWNER_DECISIONS.md asks
them to do in two of its sections, which is to add a field. Then the only guard standing between
the pilot and an undecided protocol died with a traceback instead of a sentence.

`protocol` is an ADVISORY check in tools/verify.py, so the crash would have been a WARN row, not a
red build. A check that crashes when it has something to report is a check that cannot fail.

Driven through the real script, against a temporary tree, so the test exercises the file the
owner will actually run and not a re-implementation of it.
"""
import os
import runpy
import sys

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))

SCRIPT = os.path.join(ROOT, "tools", "protocol_audit.py")


def _run_audit_against(tmp_path, protocol_text, capsys):
    """Run tools/protocol_audit.py with ROOT pointed at a scratch tree holding `protocol_text`."""
    tree = tmp_path / "tree"
    (tree / "protocol").mkdir(parents=True)
    (tree / "data" / "garments").mkdir(parents=True)
    (tree / "tools").mkdir()
    (tree / "protocol" / "PROTOCOL.md").write_text(protocol_text)
    fake_file = str(tree / "tools" / "protocol_audit.py")
    # The script derives ROOT from __file__; give it one under the scratch tree. The real source
    # is what runs -- runpy reads SCRIPT -- only its idea of where it lives is changed.
    src = open(SCRIPT).read()
    code = compile(src, fake_file, "exec")
    g = {"__name__": "__main__", "__file__": fake_file}
    try:
        exec(code, g)
    except SystemExit as e:
        return int(e.code or 0), capsys.readouterr().out
    return 0, capsys.readouterr().out


def test_an_unclassified_fill_field_is_a_hard_finding_not_a_traceback(tmp_path, capsys):
    text = "# protocol\n\n- Something new the owner added: `[FILL]` widgets\n"
    try:
        rc, out = _run_audit_against(tmp_path, text, capsys)
    except NameError as e:                                   # the defect, verbatim
        pytest.fail("protocol_audit.py crashed with NameError (%s) on the one input its HARD "
                    "rule exists for: a [FILL] field COVERAGE does not classify" % e)
    assert rc == 1, "an unclassified [FILL] field must be a HARD finding (exit 1); got %d\n%s" % (rc, out)
    assert "does not classify" in out, out


def test_a_fully_classified_protocol_still_runs_clean_of_that_finding(tmp_path, capsys):
    """The same path with every field known: the HARD rule stays quiet and the exit is 0."""
    # One line COVERAGE knows about, taken from its own table so the test follows the module.
    from denimtwin.pilot import protocol_fields as PF
    needle = PF.COVERAGE[0][0]
    text = "# protocol\n\n%s `[FILL]` value\n" % needle
    rc, out = _run_audit_against(tmp_path, text, capsys)
    assert "does not classify" not in out, out
    assert rc == 0, out
