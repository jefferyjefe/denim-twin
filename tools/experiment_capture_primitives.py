#!/usr/bin/env python3
"""EXP_0043 -- what the pilot's three new capture checks can and cannot decide.

Every threshold in `denimtwin.pilot.qa_primitives` comes from this run, and this run needs no
photographs: the images are synthesised with a real ChArUco board at a scale the script sets, so the
error in a measured mm/px is known exactly rather than estimated against another measurement. That
makes the thresholds re-derivable in clean CI, which is the only kind of number this repository
allows to sit in a gate.

Three questions:

  A. TILT. `capture/board.mm_per_pixel` takes the median corner spacing. How wrong is that when the
     board is not fronto-parallel, and does `scale_range_ratio` see it coming?

  B. RELAY INDEPENDENCE. Can image similarity tell five independent re-lays from one photograph
     submitted five times? (Answer: no. That is the finding.)

  C. DUPLICATES. What similarity level is only ever produced by the same frame re-encoded?

    tools/experiment_capture_primitives.py [--out reports/pilot_qa_primitives.json] [--quick]

Exit 0 always unless the run itself fails; this measures, it does not gate.
"""
import argparse
import itertools
import json
import math
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import cv2                                        # noqa: E402
import numpy as np                                # noqa: E402
from denimtwin.capture.board import load_board, detect, mm_per_pixel   # noqa: E402
from denimtwin.pilot import qa_primitives as Q    # noqa: E402
from denimtwin.pilot.fixtures import synth_capture, reshoot  # noqa: E402


def part_a(board, spec, tmp, scales, seeds, warps, size):
    """Scale error vs scale_range_ratio, over a grid of image scales, seeds and keystone warps."""
    rows = []
    for mmpx in scales:
        for seed in seeds:
            for warp in warps:
                p = os.path.join(tmp, "a_%s_%s_%s.png" % (mmpx, seed, warp))
                truth = synth_capture(p, subject="jeans_front", mm_per_px=mmpx, size=size,
                                      tilt_deg=warp, seed=seed)
                gray = cv2.cvtColor(cv2.imread(p), cv2.COLOR_BGR2GRAY)
                corners, ids = detect(gray, board)
                os.remove(p)
                if corners is None:
                    rows.append({"mm_per_px": mmpx, "seed": seed, "warp_deg": warp,
                                 "detected": False})
                    continue
                srr = Q.scale_range_ratio(corners, ids, spec)
                est = mm_per_pixel(corners, ids, spec)
                err = abs(est - truth["mm_per_px"]) / truth["mm_per_px"]
                rows.append({"mm_per_px": mmpx, "seed": seed, "warp_deg": warp, "detected": True,
                             "n_corners": int(len(ids)), "scale_range_ratio": round(srr, 5),
                             "scale_error_frac": round(float(err), 5),
                             "verdict": Q.tilt_verdict(srr)[0]})
    det = [r for r in rows if r.get("detected")]
    level = [r for r in det if r["warp_deg"] == 0]
    ok = [r for r in det if r["scale_error_frac"] <= 0.05]
    bad = [r for r in det if r["scale_error_frac"] > 0.05]
    # The property the gate actually needs: nothing the tilt check calls PASS may carry a scale
    # error big enough to matter for a fray measurement.
    passed = [r for r in det if r["verdict"] == "PASS"]
    return rows, {
        "n": len(det),
        "level_srr_median": round(float(np.median([r["scale_range_ratio"] for r in level])), 5),
        "level_srr_max": round(max(r["scale_range_ratio"] for r in level), 5),
        "level_scale_error_max": round(max(r["scale_error_frac"] for r in level), 5),
        "max_srr_with_error_under_5pct": round(max(r["scale_range_ratio"] for r in ok), 5) if ok else None,
        "min_srr_with_error_over_5pct": round(min(r["scale_range_ratio"] for r in bad), 5) if bad else None,
        "worst_scale_error_among_PASS": round(max(r["scale_error_frac"] for r in passed), 5) if passed else None,
        "n_PASS": len(passed),
        "by_warp": [{"warp_deg": w,
                     "srr_median": round(float(np.median([r["scale_range_ratio"] for r in det if r["warp_deg"] == w])), 5),
                     "scale_error_median": round(float(np.median([r["scale_error_frac"] for r in det if r["warp_deg"] == w])), 5),
                     "scale_error_max": round(max(r["scale_error_frac"] for r in det if r["warp_deg"] == w), 5)}
                    for w in sorted({r["warp_deg"] for r in det})],
    }


def part_bc(board, spec, tmp, n_relays, size, mmpx):
    """Genuine re-lays vs the same lay re-shot vs the same file, on similarity AND on displacement."""
    kw = dict(subject="jeans_front", mm_per_px=mmpx, size=size)
    base = os.path.join(tmp, "base.png")
    tb = synth_capture(base, seed=7, relay=0, **kw)
    rect = tb.get("board_rect")

    def img(p):
        return cv2.imread(p)

    def pose(p):
        return Q.garment_pose(img(p), rect)

    cases = {}
    p = os.path.join(tmp, "copy.png"); shutil.copy(base, p); cases["identical_file_copy"] = p
    p = os.path.join(tmp, "reenc.jpg")
    cv2.imwrite(p, img(base), [int(cv2.IMWRITE_JPEG_QUALITY), 88]); cases["reencoded_jpeg_q88"] = p
    p = os.path.join(tmp, "bright.png")
    cv2.imwrite(p, np.clip(img(base).astype(int) * 1.04, 0, 255).astype(np.uint8))
    cases["same_frame_brightened_4pct"] = p
    # What photographing the SAME LAY again actually produces: the same render, new sensor noise,
    # a pixel or two of shake. Modelling it as a fresh render with a new texture seed changed the
    # cloth's own micro-texture -- the one thing that does NOT change when nobody touches the
    # garment -- and flattered the check by exactly that amount.
    for k, sig in enumerate((1.0, 3.0, 5.0)):
        p = os.path.join(tmp, "samelay%d.png" % k)
        reshoot(base, p, sensor_sigma=sig, shake_px=1.5, seed=100 + k)
        cases["same_lay_reshot_%d" % k] = p
    relays = []
    for i in range(1, n_relays + 1):
        p = os.path.join(tmp, "relay%d.png" % i)
        synth_capture(p, seed=7 + i, relay=i, **kw)
        cases["genuine_relay_%d" % i] = p
        relays.append(p)

    base_pose, base_sha, base_img = pose(base), Q.content_sha256(base), img(base)
    rows = []
    for name, p in cases.items():
        q = pose(p)
        n = Q.ncc(base_img, img(p))
        interior = Q.registered_interior_ncc(base_img, img(p), base_pose, q)
        dh = Q.hamming(Q.dhash_bits(base_img), Q.dhash_bits(img(p)))
        d_mm = d_rot = None
        if q and base_pose:
            d_mm = math.hypot(q["cx"] - base_pose["cx"], q["cy"] - base_pose["cy"]) * mmpx
            d_rot = Q._angle_delta(q["angle_deg"], base_pose["angle_deg"])
        rows.append({"case": name, "ncc": round(n, 6) if n is not None else None,
                     "interior_ncc": round(interior, 6) if interior is not None else None,
                     "dhash_distance": dh,
                     "same_sha256": Q.content_sha256(p) == base_sha,
                     "centroid_shift_mm": round(d_mm, 4) if d_mm is not None else None,
                     "rotation_delta_deg": round(d_rot, 4) if d_rot is not None else None,
                     "relay_verdict": Q.relay_verdict(base_pose, q, mmpx, interior_ncc=interior,
                                                      seconds_apart=120,
                                                      operator_confirmed=True)[0]})

    gen = [r for r in rows if r["case"].startswith("genuine_relay")]
    notmoved = [r for r in rows if r["case"] in ("identical_file_copy", "reencoded_jpeg_q88",
                                                 "same_frame_brightened_4pct")
                or r["case"].startswith("same_lay_reshot")]
    # relay-vs-relay, not just vs base: the five repeats are compared to each other in practice
    pair_ncc, pair_mm, pair_int = [], [], []
    poses = {p: pose(p) for p in relays}
    for a, b in itertools.combinations(relays, 2):
        pair_ncc.append(Q.ncc(img(a), img(b)))
        pair_int.append(Q.registered_interior_ncc(img(a), img(b), poses[a], poses[b]))
        pa, pb = poses[a], poses[b]
        pair_mm.append(math.hypot(pa["cx"] - pb["cx"], pa["cy"] - pb["cy"]) * mmpx)
    samelay = [r for r in rows if r["case"].startswith("same_lay_reshot")]

    return rows, {
        "crease_band_sigma_px": [Q.CREASE_LOW_SIGMA_PX, Q.CREASE_HIGH_SIGMA_PX],
        "interior_ncc_genuine_relay_max": round(max([r["interior_ncc"] for r in gen] + pair_int), 6),
        "interior_ncc_same_lay_min": round(min(r["interior_ncc"] for r in samelay), 6),
        "interior_ncc_separates_relay_from_same_lay": bool(
            max([r["interior_ncc"] for r in gen] + pair_int) < min(r["interior_ncc"] for r in samelay)),
        "interior_ncc_margin": round(min(r["interior_ncc"] for r in samelay)
                                     - max([r["interior_ncc"] for r in gen] + pair_int), 6),
        "genuine_relay_ncc_max": round(max(r["ncc"] for r in gen), 6),
        "genuine_relay_ncc_min": round(min(r["ncc"] for r in gen), 6),
        "same_lay_reshot_ncc_max": round(max(r["ncc"] for r in rows
                                             if r["case"].startswith("same_lay_reshot")), 6),
        "relay_pair_ncc_max": round(max(pair_ncc), 6),
        "relay_pair_ncc_min": round(min(pair_ncc), 6),
        "similarity_separates_relay_from_same_lay": bool(
            min(r["ncc"] for r in gen) > max(r["ncc"] for r in rows
                                             if r["case"].startswith("same_lay_reshot"))),
        "genuine_relay_centroid_shift_mm_min": round(min(r["centroid_shift_mm"] for r in gen), 4),
        "genuine_relay_centroid_shift_mm_max": round(max(r["centroid_shift_mm"] for r in gen), 4),
        "relay_pair_centroid_shift_mm_min": round(min(pair_mm), 4),
        "not_moved_centroid_shift_mm_max": round(max(r["centroid_shift_mm"] for r in notmoved), 4),
        "displacement_separates_relay_from_not_moved": bool(
            min(r["centroid_shift_mm"] for r in gen) > max(r["centroid_shift_mm"] for r in notmoved)),
        "near_duplicate_ncc_min_observed": round(min(r["ncc"] for r in rows
                                                     if r["case"] in ("identical_file_copy",
                                                                      "reencoded_jpeg_q88",
                                                                      "same_frame_brightened_4pct")), 6),
        "all_not_moved_rejected": bool(all(r["relay_verdict"] == "RETAKE_REQUIRED" for r in notmoved)),
        "all_genuine_relays_accepted": bool(all(r["relay_verdict"] == "PASS" for r in gen)),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "reports" / "pilot_qa_primitives.json"))
    ap.add_argument("--quick", action="store_true", help="smaller grid, for a smoke run")
    a = ap.parse_args()

    board, spec = load_board(ROOT / "protocol" / "charuco_board.json")
    scales = (0.4, 0.6) if a.quick else (0.3, 0.45, 0.7)
    seeds = range(2) if a.quick else range(4)
    warps = (0, 4, 10) if a.quick else (0, 1, 2, 3, 4, 6, 8, 12, 18)
    size = (1400, 1050) if a.quick else (1900, 1425)

    tmp = tempfile.mkdtemp(prefix="exp0043_")
    try:
        a_rows, a_sum = part_a(board, spec, tmp, scales, seeds, warps, size)
        bc_rows, bc_sum = part_bc(board, spec, tmp, 5 if a.quick else 8, size, scales[0])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    out = {
        "experiment": "EXP_0043",
        "what": "what the pilot's tilt, relay-independence and duplicate checks can decide",
        "grid": {"scales_mm_per_px": list(scales), "n_seeds": len(list(seeds)),
                 "warps_deg": list(warps), "image_size": list(size), "quick": bool(a.quick)},
        "thresholds_in_code": {
            "SRR_PASS": Q.SRR_PASS, "SRR_RETAKE": Q.SRR_RETAKE,
            "RELAY_MIN_CENTROID_MM": Q.RELAY_MIN_CENTROID_MM,
            "RELAY_MIN_ROT_DEG": Q.RELAY_MIN_ROT_DEG,
            "NEAR_DUPLICATE_NCC": Q.NEAR_DUPLICATE_NCC,
            "DISTINCT_NCC_MAX": Q.DISTINCT_NCC_MAX,
        },
        "tilt": a_sum, "relay_and_duplicates": bc_sum,
        "rows": {"tilt": a_rows, "relay": bc_rows},
    }
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
    print("wrote", a.out)
    print("  tilt: level srr median %(level_srr_median)s max %(level_srr_max)s; "
          "worst scale error among PASS %(worst_scale_error_among_PASS)s" % a_sum)
    print("  whole-image similarity separates relay from same-lay: "
          "%(similarity_separates_relay_from_same_lay)s" % bc_sum)
    print("  registered-interior correlation separates them: "
          "%(interior_ncc_separates_relay_from_same_lay)s (margin %(interior_ncc_margin)s)" % bc_sum)
    print("  displacement separates relay from not-moved: %(displacement_separates_relay_from_not_moved)s" % bc_sum)
    return 0


if __name__ == "__main__":
    sys.exit(main())
