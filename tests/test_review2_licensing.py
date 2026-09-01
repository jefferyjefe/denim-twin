"""Review 2: licensing is recorded but never enforced for found (scraped) pairs."""
import os, sys, json, ast
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
ROOT = os.path.join(os.path.dirname(__file__), "..")

def test_validate_requires_license_field_and_fetch_gates_on_it():
    # tutorial_pairs.py:19-31 -- validate() never checks license_or_terms although the record schema (docstring)
    # lists it; fetch() downloads every image regardless. data/external/pairs.jsonl is currently ALL
    # 'copyright / all rights reserved' pages and run_pairs_batch.py consumes them with no flag.
    import tutorial_pairs as T
    rec = dict(page_url="https://x/y", source_type="blog", found_at="step",
               images=[{"url": "https://x/a.jpg", "role": "before"}, {"url": "https://x/b.jpg", "role": "after_cut"}])
    assert T.validate([rec]), "record without license_or_terms passes validation"
    src = ast.parse(open(os.path.join(ROOT, "tools", "tutorial_pairs.py")).read())
    fetch = next(n for n in src.body if isinstance(n, ast.FunctionDef) and n.name == "fetch")
    assert "license" in ast.unparse(fetch), "fetch() has no licence/terms gate"
