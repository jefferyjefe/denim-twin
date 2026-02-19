"""Review 3: ingest_submissions.py treats the issue body as trusted."""
import os, re
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = open(os.path.join(ROOT, "tools/ingest_submissions.py")).read()

import sys, importlib.util
_spec = importlib.util.spec_from_file_location("ingest_submissions", os.path.join(ROOT, "tools/ingest_submissions.py")); _m = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_m)
consent_ok = _m.consent_ok

def test_unticked_consent_passes_if_any_checkbox_text_appears_anywhere():
    # ingest_submissions.py:19 -- consent = the label text present (it always is: the template renders the label even
    # when unticked as "- [ ] I took these photos ...") AND "[x]" ANYWHERE in the body. A submission with the consent box
    # UNTICKED but "[x]" typed into any free-text field (cut notes, wash notes) is ingested with "contributor consent".
    body = ("### BEFORE photo(s)\nhttps://x/b.jpg\n### AFTER WASHING photo(s)\nhttps://x/a.jpg\n"
            "### How did you cut?\nscissors [x] flat\n### Consent\n- [ ] I took these photos and agree to their release under CC BY 4.0 for research.\n")
    assert not consent_ok(body)
