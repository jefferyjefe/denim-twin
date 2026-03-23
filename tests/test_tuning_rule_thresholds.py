"""Pin the heuristic thresholds the tuning rule governs (review 7).

docs/GATES.md: thresholds in canon/autolm.py, canon/hemfit.py, canon/upright.py and canon/warp.py
change only with >=5 usable pairs and tools/report_pairs.py output attached to the commit. Nothing
enforced that -- review 7 changed a hemfit threshold by 50% with the entire suite green.

This does not decide what the values should be. It makes changing one a deliberate act: the change
fails here, and the fix is to update the number below IN THE SAME COMMIT as the A/B report the rule
requires. A test that merely tracked the source would defeat the purpose.
"""
import inspect
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from denimtwin.canon import hemfit, warp, upright, autolm

ROOT = os.path.join(os.path.dirname(__file__), "..")

# module, callable, parameter -> value the tuning rule currently blesses
PINNED = [
    (hemfit.estimate_hems, "w", 6),
    (hemfit.estimate_hems, "solid_frac", 0.6),
    (hemfit.estimate_hems, "min_pts", 6),
    (hemfit.fabric_vs_fringe, "hem_zone_px", 80),
    (warp.CanonicalMap.__init__, "min_sep_frac", 0.01),
    (warp.CanonicalMap.__init__, "tol", 0.05),
    (warp.CanonicalMap.__init__, "iters", 6),
    (upright.upright, "deadband", 0.0),
]


def test_tuning_rule_thresholds_are_unchanged():
    wrong = []
    for fn, param, expected in PINNED:
        got = inspect.signature(fn).parameters[param].default
        if got != expected:
            wrong.append(f"{fn.__module__}.{fn.__qualname__}({param}): {expected} -> {got}")
    assert not wrong, (
        "A threshold under the docs/GATES.md tuning rule changed:\n  " + "\n  ".join(wrong) +
        "\n\nThat rule requires >=5 usable pairs and tools/report_pairs.py output attached to the "
        "commit. Update the pinned value here in the same commit as that report.")


def test_module_level_thresholds_are_unchanged():
    """Constants that are not function defaults."""
    assert upright.ISOTROPIC_ELONGATION == 1.2
    assert upright.UNRELIABLE_TILT_DEG == 5.0
    assert upright.max_correctable_tilt(2.0) == 80.0
    assert upright.max_correctable_tilt(1.5) == 30.0


def test_the_rule_still_names_these_modules():
    g = open(os.path.join(ROOT, "docs", "GATES.md")).read()
    for m in ("canon/autolm.py", "canon/hemfit.py", "canon/upright.py", "canon/warp.py"):
        assert m in g, f"{m} dropped out of the tuning rule"


def test_imported_code_matches_the_source_on_disk():
    """Detect a stale bytecode cache.

    `.venv/bin/python` here is macOS's system Python, which sets a `pycache_prefix` and writes
    bytecode to ~/Library/Caches/com.apple.python/<abs path>/ -- OUTSIDE the repository and outside
    any __pycache__. Review 7 hit this directly: a threshold was edited back to 0.6 on disk while the
    imported module kept reporting 0.9, and `rm -rf src/**/__pycache__` did not help. An experiment
    run in that state silently uses old code.

    This compares the defaults Python actually imported against the ones an AST parse of the file on
    disk reports, for the thresholds the tuning rule governs.
    """
    import ast
    import inspect as _i

    want = {}
    for fn, param, _ in PINNED:
        want.setdefault(_i.getfile(fn), set()).add((fn.__name__, param))

    mismatches = []
    for path, params in want.items():
        tree = ast.parse(open(path).read())
        on_disk = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                args = node.args.args
                defaults = node.args.defaults
                for a_, d_ in zip(args[len(args) - len(defaults):], defaults):
                    try:
                        on_disk[(node.name, a_.arg)] = ast.literal_eval(d_)
                    except (ValueError, TypeError):
                        pass
        for fn, param, _ in PINNED:
            if _i.getfile(fn) != path or (fn.__name__, param) not in params:
                continue
            imported = _i.signature(fn).parameters[param].default
            disk = on_disk.get((fn.__name__, param), imported)
            if imported != disk:
                mismatches.append(f"{fn.__name__}({param}): imported {imported}, on disk {disk}")

    assert not mismatches, (
        "Imported code does not match the source on disk:\n  " + "\n  ".join(mismatches) +
        "\n\nThis is almost certainly a stale bytecode cache. On macOS system Python it lives at\n"
        "  ~/Library/Caches/com.apple.python/<abs path to repo>/\n"
        "not in __pycache__. Remove that directory and re-run.")
