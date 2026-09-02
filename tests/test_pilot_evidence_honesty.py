"""Four ways the navigator could have recorded something nobody observed.

Every test here fails on the code as it was, not on a hypothetical. Each one names the specific
keystroke or file that produced a fact the operator never established:

  1. holding Enter through `pilot.py setup` froze a rig -- camera, height, backdrop, room -- out of
     the prompts' own defaults, and answered all nine calibration readings "yes";
  2. the committable manifest carried a wall-clock float on every entry and the shutter's calendar
     date in EXIF, into a file that is deliberately not gitignored;
  3. `protocol_audit.py` could not see six of the protocol's nineteen open fields, so its one HARD
     rule stopped firing once the visible thirteen were filled;
  4. the capture watcher kept its processing state as st_mtime, which `touch` and `cp -p` both
     rewrite and `os.utime` can restore after an edit.
"""
import ast
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from denimtwin.pilot import gates as GATES                       # noqa: E402
from denimtwin.pilot import protocol_fields as PF                # noqa: E402
from denimtwin.pilot.manifest import EXIF_KEEP, Manifest, sanitise_exif   # noqa: E402


# -- 1. the rig freeze may not be built out of defaults -------------------------------------------

#: The eight fields whose value is a fact about physical hardware.
_PHYSICAL_SETUP_PROMPTS = (
    "camera_model", "mount_height_cm", "lens", "backdrop", "lighting", "leg_gap_cm",
    "exposure_locked", "room",
)


def _setup_prompt_calls():
    """Every `cfg[...] = _prompt(...)` in cmd_setup, as (field, default_node)."""
    tree = ast.parse((ROOT / "tools" / "pilot.py").read_text())
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "cmd_setup")
    out = {}
    for node in ast.walk(fn):
        if not (isinstance(node, ast.Assign) and isinstance(node.value, ast.Call)):
            continue
        call, tgt = node.value, node.targets[0]
        if not (isinstance(call.func, ast.Name) and call.func.id == "_prompt"):
            continue
        if not (isinstance(tgt, ast.Subscript) and isinstance(tgt.value, ast.Name)
                and tgt.value.id == "cfg"):
            continue
        key = tgt.slice
        key = key.value if isinstance(key, ast.Index) else key      # py<3.9 compatibility
        out[key.value] = call.args[1] if len(call.args) > 1 else None
    return out


def test_no_rig_field_is_offered_a_default_answer():
    """A default here is a measurement nobody took, hashed onto every photograph in the session.

    The prompts used to read `_prompt("camera / phone model", "iPhone")`, mount height 80.0,
    backdrop "dark green matte", room "studio". An operator who pressed Enter eight times got a
    fully populated, hash-attributed rig freeze describing hardware that may not exist, and
    validate_setup's emptiness check could never fire because a default is never empty.
    """
    calls = _setup_prompt_calls()
    missing = [f for f in _PHYSICAL_SETUP_PROMPTS if f not in calls]
    assert not missing, "cmd_setup no longer asks for %s" % ", ".join(missing)
    offered = {}
    for field, default in calls.items():
        if field not in _PHYSICAL_SETUP_PROMPTS:
            continue
        if default is not None and not (isinstance(default, ast.Constant) and default.value is None):
            offered[field] = ast.dump(default)
    assert not offered, (
        "these rig fields are pre-filled, so pressing Enter records hardware nobody looked at: %s"
        % ", ".join(sorted(offered)))


def test_the_calibration_confirmations_are_not_pre_answered_yes():
    """Nine y/n readings defaulting to "y" made a whole calibration one keystroke."""
    src = (ROOT / "tools" / "pilot.py").read_text()
    assert '_prompt("  %s? (y/n)" % question, "y", _bool)' not in src, (
        'the nine calibration readings default to "y"; holding Enter then records that the board '
        "was checked for coplanarity and the daylight excluded when neither was looked at")
    assert '_prompt("  %s? (y/n)" % question, None, _bool)' in src


def test_an_empty_rig_configuration_is_refused_by_the_shared_validator():
    with pytest.raises(ValueError) as e:
        GATES.validate_setup({})
    assert "camera_model" in str(e.value)


def test_both_front_doors_validate_the_rig_through_the_same_function():
    """The API validated REQUIRED_SETUP_FIELDS from the start and the CLI did not use it."""
    from denimtwin.pilot import webapp
    assert webapp.REQUIRED_SETUP_FIELDS is GATES.REQUIRED_SETUP_FIELDS
    with pytest.raises(webapp.BadInput):
        webapp.validate_setup({"camera_model": "x"})
    assert "GATES.validate_setup(cfg)" in (ROOT / "tools" / "pilot.py").read_text(), \
        "the CLI must freeze the rig through the same validator the API uses"


# -- 2. the committable manifest carries no clock -------------------------------------------------

def test_the_committable_manifest_has_no_wall_clock_and_no_exif_date(tmp_path):
    """`manifest.sanitised.json` is the one pilot file that is deliberately NOT gitignored.

    It used to carry a `ts` float on every entry -- a calendar date with the formatting removed --
    and the shutter's DateTimeOriginal string from the phone's EXIF. The literal values below are
    the fixture this test strips; they are the only place they appear.
    """
    m = Manifest(tmp_path / "pilot" / "manifest.jsonl", seed="DENIM_0001")
    m.append("capture", {"shot_id": "BEFORE.WHOLE.F00", "rep": 1,
                         "exif": {"DateTimeOriginal": "2026:09:02 14:33:01",
                                  "DateTime": "2026:09:02 14:33:01",
                                  "Model": "Pixel 8", "GPSLatitude": 51.5, "FNumber": 1.8}})
    m.append("measurement", {"name": "waist_cm", "readings": [97.0, 97.2]})

    private = (tmp_path / "pilot" / "manifest.jsonl").read_text()
    assert '"ts"' in private and "DateTimeOriginal" in private, \
        "the private log keeps both; it is gitignored and it is what makes a session debuggable"

    entries, problems = m.sanitised(tmp_path)
    assert problems == []
    blob = json.dumps(entries, sort_keys=True)
    assert '"ts"' not in blob
    assert "DateTimeOriginal" not in blob and "DateTime" not in blob
    assert "GPS" not in blob
    assert not re.search(r"\d{4}[-:]\d{2}[-:]\d{2}", blob), "a calendar date reached the commit form"
    assert not re.search(r"1[6-9]\d{8}\.\d+", blob), "an epoch timestamp reached the commit form"
    # What must survive: the ordering and the chain reference.
    assert [e["seq"] for e in entries] == [0, 1]
    assert all(e.get("chain") for e in entries)


def test_the_exif_subset_no_longer_lists_the_date_tags():
    assert "DateTimeOriginal" not in EXIF_KEEP and "DateTime" not in EXIF_KEEP
    assert "Model" in EXIF_KEEP, "rig-relevant tags still belong in the committable form"
    assert sanitise_exif({"DateTimeOriginal": "2026:09:02 14:33:01", "Model": "x"}) == {"Model": "x"}


# -- 3. the protocol audit can see every open field -----------------------------------------------

def test_every_fill_field_in_the_protocol_is_found_and_classified():
    """The old regex needed a backtick either side of the bracket.

    `[FILL] cm`, `[FILL] ml`, `[FILL] hours`, `[FILL] min`, `[FILL] mm` and the dryer's bare
    `[FILL]` all put the unit inside the code span, so none of them matched.
    """
    text = (ROOT / "protocol" / "PROTOCOL.md").read_text()
    found = PF.fields(text)
    old_regex = re.findall(r"`\[FILL[^\]]*\]`", text)
    assert len(found) > len(old_regex), \
        "the corrected scan must see more fields than the regex that missed six of them"
    assert PF.unclassified(text) == [], (
        "PROTOCOL.md has a [FILL] field protocol_fields.COVERAGE does not know how to answer; "
        "add it there rather than letting the audit under-report")
    counts = PF.summary(text)
    assert counts["unknown"] == 0
    assert sum(counts.values()) == len(found)


def test_prose_that_mentions_the_convention_is_not_counted_as_a_field():
    text = ("Fields marked `[FILL]` must be decided.\n"
            "> The `[FILL]` fields in this section are the standing defaults.\n"
            "- Detergent: `[FILL: brand]`, `[FILL] ml`\n")
    got = PF.fields(text)
    assert [f["raw"] for f in got] == ["[FILL: brand]", "[FILL]"], \
        "only the list item carries real fields; the two sentences describe the convention"


def test_a_field_written_with_the_unit_inside_the_code_span_is_found():
    text = "- Camera: `[FILL: phone model]`, overhead mount height `[FILL] cm`, locked WB.\n"
    assert len(PF.fields(text)) == 2


def test_the_audit_reports_the_open_fields_and_still_exits_zero_on_this_tree():
    """Strengthening the count must not turn today's soft findings into a failure."""
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "protocol_audit.py")],
                       capture_output=True, text=True, cwd=str(tmp_cwd()))
    assert r.returncode == 0, r.stdout + r.stderr
    text = (ROOT / "protocol" / "PROTOCOL.md").read_text()
    assert "%d unfilled [FILL] fields" % len(PF.fields(text)) in r.stdout
    assert "HARD:" not in r.stdout


def tmp_cwd():
    """The audit must give the same answer from a foreign working directory."""
    return Path(os.environ.get("TMPDIR", "/tmp"))


# -- 4. the watcher remembers content, not a modification time ------------------------------------

def test_the_capture_watcher_keys_its_state_on_content_not_mtime():
    src = (ROOT / "tools" / "capture_watch.py").read_text()
    body = "\n".join(l for l in src.splitlines() if not l.strip().startswith('"""'))
    assert "f.stat().st_mtime" not in body, (
        "state keyed on st_mtime is rewritten by touch, cp -p and a backup restore, and can be "
        "put back by os.utime after the bytes were changed")
    assert "sha256_file(f)" in src
    assert "write_state_atomically" in src, "an interrupted write must not leave half a state file"


def test_the_watcher_state_write_is_atomic_and_survives_interruption(tmp_path):
    sys.path.insert(0, str(ROOT / "tools"))
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "_cw_probe", str(ROOT / "tools" / "capture_watch.py"))
    # Importing the module runs the watcher; read the two helpers out of the source instead.
    ns = {}
    src = (ROOT / "tools" / "capture_watch.py").read_text()
    tree = ast.parse(src)
    wanted = {"sha256_file", "write_state_atomically"}
    picked = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in wanted]
    assert {n.name for n in picked} == wanted
    exec(compile(ast.Module(body=picked, type_ignores=[]), "<probe>", "exec"),
         {"hashlib": __import__("hashlib"), "json": json, "os": os,
          "tempfile": __import__("tempfile")}, ns)

    p = tmp_path / "state.json"
    ns["write_state_atomically"](p, {"a": 1})
    assert json.loads(p.read_text()) == {"a": 1}
    ns["write_state_atomically"](p, {"a": 2})
    assert json.loads(p.read_text()) == {"a": 2}
    assert not [f for f in tmp_path.iterdir() if f.name.endswith(".tmp")], \
        "the temporary file must not be left behind"

    f = tmp_path / "img.bin"
    f.write_bytes(b"one")
    first = ns["sha256_file"](f)
    os.utime(str(f), (1_000_000, 1_000_000))
    assert ns["sha256_file"](f) == first, "touching a file must not change its identity"
    f.write_bytes(b"two")
    os.utime(str(f), (1_000_000, 1_000_000))
    assert ns["sha256_file"](f) != first, \
        "an edit whose mtime was restored must still read as a new file"


# -- 5. a stuck digit may not size the plan the CLI builds ----------------------------------------

def test_every_cli_plan_is_sized_through_the_same_screen_the_gate_uses():
    """`plan_safe_measurements` exists because the plan runs BEFORE the gate that refuses the value.

    The web app screened its two call sites from the day a phone keypad turned 40.0 into 4000. The
    CLI's seven passed the raw reading, so `status`, `plan`, `next`, `add`, `reuse`, `confirm` and
    `intake` each expanded a hem series quadratically from a number the gate would refuse.
    """
    src = (ROOT / "tools" / "pilot.py").read_text()
    calls = re.findall(r"PLAN\.activate\((.*?)\)", src, re.S)
    assert len(calls) == 7, "expected the seven CLI plan sites, found %d" % len(calls)
    unscreened = [c for c in calls if "plan_safe_measurements" not in c]
    assert not unscreened, (
        "these CLI call sites size a plan from an unscreened measurement: %r" % unscreened)


def test_an_absurd_leg_opening_does_not_expand_the_plan():
    from denimtwin.pilot import plan as PLAN, spec as SPEC
    spec = SPEC.load(ROOT / "protocol" / "shotplan" / "shotplan.json")
    feats = {}
    for _ in range(60):                       # answer whatever the plan says it needs
        try:
            PLAN.activate(spec, feats, {})
            break
        except PLAN.PlanError as e:
            for name in str(e).split(":", 1)[1].split(","):
                if name.strip():
                    feats[name.strip()] = False

    def frames(value):
        st = {"measurements": {"leg_opening_cm":
                               {"readings": [value, value], "mean": value, "unit": "cm"}}}
        return len(PLAN.activate(spec, feats, GATES.plan_safe_measurements(st))[0])

    sane = frames(40.0)
    assert frames(4000.0) <= sane, \
        "a leg opening of 4000 cm must not size a larger plan than a real one"
    assert frames(10.0 ** 7) <= sane
