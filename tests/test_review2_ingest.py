"""Review 2: ingest_submissions.py against a GitHub issue-form body. Runs a copy of the script with a fake `gh`."""
import os, sys, json, shutil, subprocess, tempfile, stat
ROOT = os.path.join(os.path.dirname(__file__), "..")
BODY = """### BEFORE photo(s) — jeans laid flat, before cutting

![before](https://github.com/user-attachments/assets/aaaaaaaa-1111)

### AFTER CUTTING photo(s) — before any wash

_No response_

### AFTER WASHING photo(s) — the frayed hem

![after](https://github.com/user-attachments/assets/bbbbbbbb-2222)

### Care label (fiber content, e.g. "99% cotton 1% elastane")

_No response_

### Scale reference in the photos

none

### Which coin / object?

_No response_

### How did you cut? (scissors/rotary, flat or worn, both legs together?)

_No response_

### How was it washed and dried? (machine cycle, temperature, dryer or hang; how many washes)

_No response_

### Attribution

Anonymous

### Consent

- [X] I took these photos and agree to their release under CC BY 4.0 for research.
"""

def _run(body):
    d = tempfile.mkdtemp(); os.makedirs(f"{d}/tools"); os.makedirs(f"{d}/bin"); os.makedirs(f"{d}/data/external")
    shutil.copy(os.path.join(ROOT, "tools", "ingest_submissions.py"), f"{d}/tools/")
    issues = [{"number": 1, "url": "https://github.com/x/y/issues/1", "title": "[pair] t", "body": body, "author": {"login": "u"}, "createdAt": "2026-01-01"}]
    gh = f"{d}/bin/gh"; open(gh, "w").write("#!/bin/sh\ncat <<'EOF'\n" + json.dumps(issues) + "\nEOF\n"); os.chmod(gh, 0o755)
    env = {**os.environ, "PATH": f"{d}/bin:" + os.environ["PATH"]}
    subprocess.run([sys.executable, f"{d}/tools/ingest_submissions.py"], env=env, check=True, capture_output=True)
    p = f"{d}/data/external/pairs.jsonl"
    return [json.loads(l) for l in open(p)] if os.path.exists(p) else []

def test_no_response_placeholders_are_not_treated_as_content():
    # ingest_submissions.py:24-28 -- GitHub writes '_No response_' for empty optional fields; the script stores it
    # verbatim (garment_desc, cut_notes, scale_detail) and sets wash_described=True from it.
    recs = _run(BODY); assert len(recs) == 1; r = recs[0]
    assert r["wash_described"] is False, r["wash_notes"]
    assert "_No response_" not in (r["garment_desc"], r["cut_notes"], r["scale_detail"])
