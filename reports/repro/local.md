# Reproducibility check (local fresh clone, this step)

Fresh `git clone` into a scratch dir, new venv, `pip install numpy opencv-contrib-python pillow pyyaml jsonschema scikit-image scipy pytest`
(heavy ML deps torch / segment-anything / open_clip_torch deliberately skipped — tests must not need them).

| step | result |
|---|---|
| python3 --version | 3.9.6 |
| pytest -q tests | **43 passed, 1 skipped** (Openverse network test) in 26 s |
| tools/sentinel.py | OK |
| tools/scope_check.py | OK (gate_0 only) |

Note: the cloud reproducibility routine has never executed (environment stalls); this local check stands in for it.
