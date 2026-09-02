#!/usr/bin/env python3
"""Local capture-QA watcher: scans data/garments/*/images/**, runs quality checks on new files,
writes <garment>/qa_report.md, and prints/notifies failures. Run via launchd every 5 minutes."""
import hashlib, json, os, subprocess, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
from denimtwin.capture.board import load_board
from denimtwin.capture.quality import check_image
board, spec = load_board(ROOT / "protocol/charuco_board.json")
state_p = ROOT / "data/.capture_qa_state.json"; state = json.loads(state_p.read_text()) if state_p.exists() else {}


def sha256_file(path):
    """Content identity. The watcher used to remember st_mtime instead, which is wrong in both
    directions: `cp -p`, a restore from backup, a sync client and `touch` all reset it without the
    pixels changing (the shot is re-checked, and the report grows a duplicate row), and a file
    edited in place and then stamped back -- os.utime is public -- keeps its mtime while its
    contents change, so the replacement is never checked at all. State keyed on what is in the file
    cannot be told either lie."""
    h = hashlib.sha256()
    with open(str(path), "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_state_atomically(path, obj):
    """Interrupted here, the watcher must find its old state, not half of a new one."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".capture_qa_state.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as fh:
            json.dump(obj, fh)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, str(path))
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
EXT = {".jpg", ".jpeg", ".png", ".heic", ".tif", ".tiff"}
for gd in sorted(ROOT.glob("data/garments/DENIM_*")):
    new = []
    for f in sorted((gd / "images").rglob("*")):
        if f.suffix.lower() not in EXT: continue
        k = str(f.relative_to(ROOT)); m = sha256_file(f)
        # A previous run's state stored a float mtime under this key. Anything that is not a
        # 64-character hex digest is from that format and means "not yet checked by content".
        if isinstance(state.get(k), str) and len(state[k]) == 64 and state[k] == m: continue
        r = check_image(f, board, spec); state[k] = m
        new.append((k, r))
    if not new: continue
    rep = gd / "qa_report.md"; lines = [f"| shot | ok | reasons | blur | board | mm/px |", "|---|---|---|---|---|---|"]
    fails = []
    for k, r in new:
        lines.append(f"| {Path(k).name} | {'✅' if r.ok else '❌'} | {'; '.join(r.reasons)} | {r.blur_score:.0f} | {r.board_corners} | {r.mm_per_px or ''} |")
        if not r.ok: fails.append(f"{Path(k).name}: {'; '.join(r.reasons)}")
        if r.mm_per_px and r.ok:
            rp = gd / "record.json"; rec = json.loads(rp.read_text())
            if rec.get("capture_mm_per_px") is None:
                rec["capture_mm_per_px"] = round(r.mm_per_px, 5); rec["capture_board_corners"] = r.board_corners; rp.write_text(json.dumps(rec, indent=2) + "\n")
    rep.open("a").write(f"\n### new shots\n" + "\n".join(lines) + "\n")
    msg = f"{gd.name}: {len(new)} new shots, {len(fails)} failed" + ("\nRETAKE: " + " | ".join(fails) if fails else "")
    print(msg)
    if sys.platform == "darwin":
        subprocess.run(["osascript", "-e", f'display notification "{msg[:200].replace(chr(34), "")}" with title "denim-twin capture QA"'])
write_state_atomically(state_p, state)
