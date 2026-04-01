"""tools/editgarment_adapter.py: a gated dataset must stay gated, and a generated image must stay
labelled as one.

Two failure modes are being held off here, and they are opposites.

The first is legal. EditGarment is distributed under an access-controlled process, and the tempting
"convenience" is a fetch path -- a URL constant, a `--download` flag, a retry loop -- that quietly
turns a repository which is not licensed to redistribute anything into one that does. So this file
asserts the refusal is the DEFAULT and exits non-zero, and it reads the adapter's own imports to
assert it has no network capability at all. A promise in a docstring is not a control.

The second is scientific, and it is the one that would do the real damage. The "after" image in an
edit dataset is generated. If such a pair ever reached a physical-accuracy comparison, this project
would report that it had validated how cloth frays when what it had actually validated was an image
model's prior over pixels -- and the number would look exactly like a real one. Hence: every record
is checked to be `pair_type=synthetic_edit`, `excluded_from_physical_evaluation=true`, and stamped
`exact_garment=known_different`; and the stamp is checked to be UNCONDITIONAL, by feeding the
adapter a manifest that tries to claim otherwise and asserting the claim is ignored or refused.

Every fixture here is synthesised in tmp_path -- a handful of small PNGs written with numpy/PIL plus
hand-written JSON. No file from the real dataset is required, present, or reachable; this suite runs
identically on a machine that has never heard of EditGarment, which is the only way a test about an
access-controlled dataset can be honest.
"""
import ast
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "editgarment_adapter.py"
SRC = TOOL.read_text()

ACCESS_FLAG = "--i-have-dataset-access"
ACCESS_ENV = "DENIMTWIN_EDITGARMENT_ACCESS"


# ------------------------------------------------------------------ fixtures (synthesised only)
def _png(path, seed, size=(48, 32)):
    """A small deterministic image. Nothing here resembles a real photograph, and that is the point:
    the adapter is a bookkeeper over local files, so its tests need bytes, not garments."""
    rng = np.random.default_rng(seed)
    arr = rng.integers(0, 255, (size[1], size[0], 3), dtype=np.uint8)
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(arr).save(path)
    return path


def _dataset(tmp_path, n=2, name="ds"):
    """The documented local layout, built from scratch: a manifest plus source/edited PNG pairs."""
    root = tmp_path / name
    samples = []
    for i in range(n):
        sid = f"eg_{i:04d}"
        _png(root / "images" / f"{sid}_source.png", seed=100 + i)
        _png(root / "images" / f"{sid}_edited.png", seed=200 + i)
        samples.append({
            "sample_id": sid,
            "instruction": f"shorten the jeans to above the knee ({sid})",
            "edit_type": "length",
            "source_image": f"images/{sid}_source.png",
            "edited_image": f"images/{sid}_edited.png",
        })
    manifest = {
        "dataset": "EditGarment",
        "source_url": "https://example.invalid/editgarment-access-page",
        "retrieved_at": "2026-07-04",
        "generation_method": "an instruction-guided image editing model (per the dataset's paper)",
        "rights": {
            # A gated dataset is governed by a written agreement, not an SPDX licence. The adapter
            # carries that across as SPDX's LicenseRef- form, which is what
            # data/schemas/provenance.schema.json reserves for exactly this case, and keeps the
            # operator's original wording verbatim in license_statement.
            "license_id": "editgarment-research-use-agreement",
            "license_url": "https://example.invalid/editgarment-terms",
            "license_statement": "Research use only; no redistribution. Per the EditGarment usage agreement.",
            "attribution": "EditGarment authors, per the usage agreement",
            "rights_holder": "the EditGarment authors",
            "redistributable": False,
            "derivatives_allowed": True,
            "commercial_use_allowed": False,
        },
        "samples": samples,
    }
    (root / "editgarment_manifest.json").write_text(json.dumps(manifest, indent=1))
    return root, manifest


def _write_manifest(root, manifest):
    (root / "editgarment_manifest.json").write_text(json.dumps(manifest, indent=1))


def _run(root, out, *args, ack=True, env_ack=None):
    env = dict(os.environ)
    env.pop(ACCESS_ENV, None)
    if env_ack is not None:
        env[ACCESS_ENV] = env_ack
    argv = [sys.executable, str(TOOL), "--root", str(root), "--out", str(out), *args]
    if ack:
        argv.append(ACCESS_FLAG)
    return subprocess.run(argv, capture_output=True, text=True, env=env, cwd=str(root))


def _tree(p):
    return {str(q.relative_to(p)): (q.stat().st_size, q.stat().st_mtime_ns)
            for q in sorted(p.rglob("*")) if q.is_file()}


def _records(out, fmt="jsonl"):
    text = Path(out).read_text()
    if fmt == "jsonl":
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    return json.loads(text)


# ------------------------------------------------------------------ the refusal is the default
def test_without_the_rights_acknowledgement_it_refuses_and_exits_non_zero(tmp_path):
    """The whole point of an access-controlled dataset is that consent is stated, not assumed."""
    root, _ = _dataset(tmp_path)
    out = tmp_path / "records.jsonl"
    r = _run(root, out, ack=False)
    assert r.returncode != 0, f"a run with no acknowledgement succeeded:\n{r.stdout}"
    assert not out.exists(), "records were written despite the refusal"
    msg = (r.stderr + r.stdout).lower()
    for token in ("access", "editgarment", ACCESS_FLAG, ACCESS_ENV.lower(), "docs/editgarment.md"):
        assert token.lower() in msg, f"the refusal never mentions {token!r}:\n{r.stderr}"
    assert "does not automate" in msg and "does not distribute" in msg, (
        "the refusal must say plainly that this repository neither distributes the dataset nor "
        f"automates its access process:\n{r.stderr}")


def test_the_environment_variable_is_an_acknowledgement_only_when_it_says_exactly_one(tmp_path):
    """`DENIMTWIN_EDITGARMENT_ACCESS=0` is a person saying no. A truthiness test would read it as yes."""
    root, _ = _dataset(tmp_path)
    for value in ("", "0", "no", "false", "true"):
        out = tmp_path / f"records_{value or 'empty'}.jsonl"
        r = _run(root, out, ack=False, env_ack=value)
        assert r.returncode != 0, f"{ACCESS_ENV}={value!r} was accepted as an acknowledgement"
        assert not out.exists()
    out = tmp_path / "records_one.jsonl"
    r = _run(root, out, ack=False, env_ack="1")
    assert r.returncode == 0, r.stderr
    assert _records(out), "the env-var acknowledgement produced no records"


def test_the_adapter_declares_no_default_root_so_it_cannot_point_at_a_download(tmp_path):
    r = subprocess.run([sys.executable, str(TOOL), "--out", str(tmp_path / "x.jsonl"), ACCESS_FLAG],
                       capture_output=True, text=True)
    assert r.returncode != 0, "the tool ran with no --root; something is supplying a default location"
    assert "--root" in r.stderr


# ------------------------------------------------------------------ it cannot reach the network
NETWORK_MODULES = {"urllib", "urllib.request", "requests", "httpx", "aiohttp", "socket", "http",
                   "http.client", "ftplib", "telnetlib", "subprocess", "asyncio"}


def test_the_adapter_imports_nothing_that_could_fetch_the_dataset():
    """Static, because a fetch path added later would not fail any behavioural test on a machine
    with no dataset -- it would just start working, quietly, on someone's laptop."""
    tree = ast.parse(SRC)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    bad = sorted(m for m in imported if m.split(".")[0] in {n.split(".")[0] for n in NETWORK_MODULES})
    assert not bad, f"tools/editgarment_adapter.py imports network-capable modules: {bad}"
    for token in ("urlopen", "requests.get", "urlretrieve", "curl ", "wget "):
        assert token not in SRC, f"the adapter contains a fetch idiom: {token!r}"


def test_the_adapter_hardcodes_no_dataset_download_location():
    """It may quote http(s) only as scheme checks; it must not carry a URL to the data itself."""
    urls = [tok for tok in SRC.replace("'", '"').split('"')
            if tok.startswith(("http://", "https://")) and len(tok) > len("https://")]
    assert not urls, f"the adapter embeds URLs: {urls}"


# ------------------------------------------------------------------ what it emits
def test_it_emits_one_record_per_sample_when_access_is_acknowledged(tmp_path):
    root, manifest = _dataset(tmp_path, n=3)
    out = tmp_path / "records.jsonl"
    r = _run(root, out)
    assert r.returncode == 0, r.stderr
    recs = _records(out)
    assert len(recs) == len(manifest["samples"]) == 3
    assert [x["record_id"] for x in recs] == ["editgarment:eg_0000", "editgarment:eg_0001",
                                              "editgarment:eg_0002"]
    assert json.loads(r.stdout)["records"] == 3


def test_every_emitted_record_is_a_synthetic_edit_excluded_from_physical_evaluation(tmp_path):
    """The scientific load-bearing assertion of this file. A generated 'after' frame may never be
    scored as though a real garment had been cut and washed, so the exclusion must be present, true,
    machine-readable, and argued for in the record itself."""
    root, _ = _dataset(tmp_path, n=2)
    out = tmp_path / "records.jsonl"
    assert _run(root, out).returncode == 0
    recs = _records(out)
    assert recs
    for rec in recs:
        # The exclusion is carried by pair_type, which the eligibility rule in
        # tools/validate_provenance.py refuses unconditionally -- not by a boolean the record sets
        # about itself. It WAS such a boolean, and because the field did not exist in
        # data/schemas/provenance.schema.json the gate rejected the whole record as invalid, which
        # excluded it from nothing: an unreadable record is not a refused one.
        assert rec["pair_type"] == "synthetic_edit", rec["record_id"]
        assert rec["exact_garment"] == "known_different", (
            "a generated frame is not a photograph of any garment; 'not_verified' would imply some "
            "later check could promote it to 'verified', and none can")
        assert len(rec["exact_garment_basis"]) > 30
        # ... and the reason is still stated, in the field the schema keeps for it.
        assert len(rec["provenance"]["notes"]) > 30, "the exclusion carries no stated reason"
        assert rec["synthetic"]["generator"], "a synthetic record must name what generated it"


def test_the_exclusion_stamp_cannot_be_talked_out_of_the_records_by_the_input(tmp_path):
    """A manifest is a local file the operator writes. If it could set pair_type, or clear the
    exclusion, the label would be a suggestion rather than a control."""
    root, manifest = _dataset(tmp_path, n=2)
    manifest["pair_type"] = "real_pair"
    manifest["excluded_from_physical_evaluation"] = False
    manifest["exact_garment"] = "verified"
    for sample in manifest["samples"]:
        sample["pair_type"] = "real_pair"
        sample["excluded_from_physical_evaluation"] = False
        sample["exact_garment"] = "verified"
    _write_manifest(root, manifest)
    out = tmp_path / "records.jsonl"
    assert _run(root, out).returncode == 0
    for rec in _records(out):
        assert rec["pair_type"] == "synthetic_edit"
        assert rec["exact_garment"] == "known_different"
        assert "excluded_from_physical_evaluation" not in rec, (
            "the exclusion must not be a self-declared boolean. It was one, and because the field "
            "was not in data/schemas/provenance.schema.json the whole record was rejected by "
            "tools/validate_provenance.py -- so the flag excluded the sample from nothing. What "
            "excludes it is pair_type synthetic_edit, which the eligibility rule refuses.")


def test_no_record_asserts_its_own_training_eligibility(tmp_path):
    """Eligibility is a decision made downstream against a policy, not a claim a dataset adapter
    gets to make about itself."""
    root, _ = _dataset(tmp_path)
    out = tmp_path / "records.jsonl"
    assert _run(root, out).returncode == 0

    def keys(obj):
        if isinstance(obj, dict):
            return set(obj) | {k for v in obj.values() for k in keys(v)}
        if isinstance(obj, list):
            return {k for v in obj for k in keys(v)}
        return set()
    for rec in _records(out):
        assert "training_eligible" not in keys(rec), f"{rec['record_id']} self-asserts eligibility"


def test_records_carry_the_rights_and_provenance_fields_a_provenance_schema_requires(tmp_path):
    root, manifest = _dataset(tmp_path)
    out = tmp_path / "records.jsonl"
    assert _run(root, out).returncode == 0
    for rec in _records(out):
        for field in ("record_id", "pair_type", "rights", "provenance", "exact_garment"):
            assert field in rec, f"{field} missing from {rec['record_id']}"
        # Copied verbatim, with one documented exception: license_id is normalised to SPDX's
        # LicenseRef- form so the record can pass data/schemas/provenance.schema.json, and the
        # operator's original wording survives untouched in license_statement.
        expected = dict(manifest["rights"])
        expected["license_id"] = "LicenseRef-editgarment-research-use-agreement"
        assert rec["rights"] == expected, "rights were not copied verbatim from the grant"
        assert manifest["rights"]["license_statement"] == rec["rights"]["license_statement"]
        assert rec["rights"]["redistributable"] is False
        prov = rec["provenance"]
        assert prov["source"] == "EditGarment"
        assert prov["source_url"] == manifest["source_url"]
        assert prov["retrieved_at"] == manifest["retrieved_at"]
        assert "editgarment_adapter.py" in prov["method"] and "access process" in prov["method"]


def test_the_record_carries_derived_numbers_about_the_images_and_no_pixels(tmp_path):
    """Only derived NUMBERS enter this repository (data/external/README.md). The record may say how
    big a local file is and what it hashes to; it may not carry the file."""
    root, manifest = _dataset(tmp_path, n=1)
    out = tmp_path / "records.jsonl"
    assert _run(root, out).returncode == 0
    rec = _records(out)[0]
    for key, rel in (("source_image", manifest["samples"][0]["source_image"]),
                     ("edited_image", manifest["samples"][0]["edited_image"])):
        facts = rec["sample"][key]
        assert facts["path_relative_to_root"] == rel
        assert (facts["width"], facts["height"]) == (48, 32)
        assert facts["sha256"] == hashlib.sha256((root / rel).read_bytes()).hexdigest()
    blob = Path(out).read_text()
    assert "\\u0089PNG" not in blob and "iVBORw0" not in blob, "image bytes leaked into the record"


def test_limit_truncates_and_the_json_array_format_is_a_list_of_the_same_records(tmp_path):
    root, _ = _dataset(tmp_path, n=3)
    out = tmp_path / "two.json"
    assert _run(root, out, "--limit", "2", "--format", "json").returncode == 0
    recs = _records(out, fmt="json")
    assert isinstance(recs, list) and len(recs) == 2
    assert all(x["pair_type"] == "synthetic_edit" for x in recs)


# ------------------------------------------------------------------ malformed local input
def _break(manifest, mutate):
    mutate(manifest)
    return manifest


MALFORMED = [
    ("no_manifest", lambda root, m: (root / "editgarment_manifest.json").unlink(), "editgarment_manifest.json"),
    ("not_json", lambda root, m: (root / "editgarment_manifest.json").write_text("{ not json"), "not valid json"),
    ("manifest_is_a_list", lambda root, m: (root / "editgarment_manifest.json").write_text("[]"), "json object"),
    ("no_rights", lambda root, m: _write_manifest(root, _break(m, lambda d: d.pop("rights"))), "rights"),
    ("rights_field_missing",
     lambda root, m: _write_manifest(root, _break(m, lambda d: d["rights"].pop("attribution"))), "rights.attribution"),
    ("rights_bool_is_a_string",
     lambda root, m: _write_manifest(root, _break(m, lambda d: d["rights"].update(redistributable="no"))),
     "rights.redistributable"),
    ("claims_redistribution_rights",
     lambda root, m: _write_manifest(root, _break(m, lambda d: d["rights"].update(redistributable=True))),
     "redistributable"),
    ("no_source_url", lambda root, m: _write_manifest(root, _break(m, lambda d: d.pop("source_url"))), "source_url"),
    ("source_url_is_not_a_url",
     lambda root, m: _write_manifest(root, _break(m, lambda d: d.update(source_url="ask me"))), "source_url"),
    ("retrieved_at_is_not_a_date",
     lambda root, m: _write_manifest(root, _break(m, lambda d: d.update(retrieved_at="last summer"))), "retrieved_at"),
    ("no_samples", lambda root, m: _write_manifest(root, _break(m, lambda d: d.update(samples=[]))), "samples"),
    ("duplicate_sample_id",
     lambda root, m: _write_manifest(root, _break(m, lambda d: d["samples"].append(dict(d["samples"][0])))),
     "duplicate"),
    ("sample_id_is_a_path",
     lambda root, m: _write_manifest(root, _break(m, lambda d: d["samples"][0].update(sample_id="../../etc/passwd"))),
     "sample_id"),
    ("image_path_escapes_root",
     lambda root, m: _write_manifest(root, _break(m, lambda d: d["samples"][0].update(source_image="../outside.png"))),
     "escapes --root"),
    ("image_path_is_absolute",
     lambda root, m: _write_manifest(root, _break(m, lambda d: d["samples"][0].update(edited_image="/etc/hosts"))),
     "absolute"),
    ("image_missing", lambda root, m: (root / m["samples"][0]["edited_image"]).unlink(), "does not exist"),
    ("image_is_not_an_image",
     lambda root, m: (root / m["samples"][1]["source_image"]).write_text("this is not a PNG"),
     "not a readable image"),
    ("instruction_missing",
     lambda root, m: _write_manifest(root, _break(m, lambda d: d["samples"][0].update(instruction=""))),
     "instruction"),
]


@pytest.mark.parametrize("name,mutate,expect", MALFORMED, ids=[m[0] for m in MALFORMED])
def test_malformed_local_input_is_refused_with_a_reason_and_writes_nothing(tmp_path, name, mutate, expect):
    """Rejection must name what is wrong. A generic 'invalid input' sends the operator back to a
    dataset they cannot re-download on a whim."""
    root, manifest = _dataset(tmp_path, n=2)
    mutate(root, manifest)
    out = tmp_path / "records.jsonl"
    r = _run(root, out)
    assert r.returncode != 0, f"[{name}] malformed input was accepted:\n{r.stdout}"
    assert not out.exists(), f"[{name}] records were written from malformed input"
    assert expect.lower() in (r.stderr + r.stdout).lower(), \
        f"[{name}] the refusal does not say what was wrong (wanted {expect!r}):\n{r.stderr}"


def test_one_bad_sample_refuses_the_whole_run_rather_than_emitting_the_rest(tmp_path):
    """Silently dropping the unreadable sample would leave a shorter file that looks complete."""
    root, manifest = _dataset(tmp_path, n=3)
    (root / manifest["samples"][1]["edited_image"]).unlink()
    out = tmp_path / "records.jsonl"
    r = _run(root, out)
    assert r.returncode != 0
    assert not out.exists(), "a partial record set was emitted from a partly-broken manifest"


# ------------------------------------------------------------------ where it writes
def test_nothing_is_written_anywhere_but_the_out_path(tmp_path):
    root, _ = _dataset(tmp_path, n=2)
    out = tmp_path / "elsewhere" / "records.jsonl"
    before = _tree(tmp_path)
    r = _run(root, out)
    assert r.returncode == 0, r.stderr
    after = _tree(tmp_path)
    new = set(after) - set(before)
    assert new == {str(out.relative_to(tmp_path))}, f"unexpected files appeared: {sorted(new)}"
    changed = [f for f in before if after.get(f) != before[f]]
    assert not changed, f"the local dataset copy was modified in place: {changed}"


def test_it_refuses_to_write_into_the_repositorys_tracked_trees(tmp_path):
    """A gated dataset's derivatives must not land where the next `git add -A` would publish them."""
    root, _ = _dataset(tmp_path)
    for tree in ("data", "reports", "experiments"):
        out = os.path.join(str(ROOT), tree, "editgarment_records_should_never_exist.jsonl")
        r = _run(root, out)
        assert r.returncode != 0, f"the tool wrote into tracked {tree}/"
        assert not os.path.exists(out), f"a file was created under tracked {tree}/"
        assert tree in r.stderr


def test_it_refuses_to_clobber_an_existing_output_without_being_told_to(tmp_path):
    root, _ = _dataset(tmp_path)
    out = tmp_path / "records.jsonl"
    out.write_text("previous run, not to be silently destroyed\n")
    r = _run(root, out)
    assert r.returncode != 0 and "overwrite" in r.stderr
    assert out.read_text().startswith("previous run")
    assert _run(root, out, "--overwrite").returncode == 0
    assert _records(out), "--overwrite did not produce records"


# ------------------------------------------------------------------ the documentation is the process
def test_the_documentation_states_the_exclusion_and_disclaims_automating_access():
    doc = (ROOT / "docs" / "EDITGARMENT.md").read_text()
    low = doc.lower()
    for phrase in ("synthetic", "excluded", "physical", ACCESS_FLAG, "editgarment_manifest.json"):
        assert phrase.lower() in low, f"docs/EDITGARMENT.md never mentions {phrase!r}"
    assert "does not distribute" in low and "does not automate" in low, \
        "the document must say plainly that this repository neither distributes the dataset nor " \
        "automates its access process"


def test_the_records_are_refused_by_the_projects_own_eligibility_gate(tmp_path):
    """The exclusion, enforced rather than asserted.

    docs/PROJECT_STATUS.md claims these samples are excluded from physical-accuracy evaluation "by
    the eligibility rule, not by convention". That sentence was false for as long as the adapter
    emitted field names of its own: tools/validate_provenance.py rejected every record as
    schema-invalid, which is not the same as deriving it ineligible -- an invalid record is one the
    gate could not read, and a gate that cannot read a record is not excluding it. This runs the
    real gate over real adapter output and requires BOTH halves: the records validate, and the rule
    refuses them for being synthetic."""
    root, _ = _dataset(tmp_path, n=2)
    out = tmp_path / "records.jsonl"
    assert _run(root, out).returncode == 0
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools/validate_provenance.py"),
                        "--manifest", str(out)], capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 0, f"adapter output does not validate:\n{r.stdout}{r.stderr}"
    assert "0 training-eligible" in r.stdout, (
        f"a synthetic edit was derived training-eligible:\n{r.stdout}")
    assert "synthetic_edit" in r.stdout and "refused for" in r.stdout, r.stdout
