"""The per-garment capture manifest: append-only, hash-chained, and safe to interrupt.

A capture session is a long physical process interleaved with a phone, a laptop and a person
carrying a garment across a room. It WILL be interrupted. The manifest is the only record that the
evidence was collected under known conditions, so the failure modes that matter are the quiet ones:
a half-written line that parses; a photograph silently overwritten by a retake; a file that is
present but is not the file whose hash was recorded.

The choices here follow from those:

* APPEND-ONLY JSONL, not a rewritten JSON document. A rewritten document has a window in which the
  old record is gone and the new one is not yet there; an append has no such window, and a torn
  append damages exactly one line -- the last -- which `read()` detects and quarantines instead of
  silently dropping. A JSON document would also have to be re-serialised on every capture, which is
  the operation that loses the whole file when the laptop sleeps mid-write.

* A HASH CHAIN. Each entry carries `prev_chain` and `chain = sha256(prev_chain || canonical(entry))`.
  Editing or deleting an earlier line breaks every chain after it, so "the manifest was edited to
  make the gate pass" is detectable rather than deniable. This is tamper-EVIDENCE, not tamper-proof:
  anyone can recompute the whole chain. It is here because the failure it guards against is a person
  in a hurry fixing up a record, not an adversary.

* PHOTOGRAPHS ARE NEVER OVERWRITTEN. An incoming file is named by its own content hash, so a retake
  cannot land on the path of the shot it replaces, and re-ingesting the same bytes is idempotent
  rather than destructive. If a path somehow exists with different content, ingestion refuses.

* TWO COPIES OF THE TRUTH, one private and one committable. The local manifest carries absolute
  paths and full EXIF because that is what makes a session debuggable. `sanitised()` produces the
  form that may enter git: repo-relative paths only, and an EXIF subset with every GPS and location
  tag dropped. `data/external/README.md` and .gitignore already say photographs stay out of the
  repository; this keeps their coordinates out too.
"""
import hashlib
import json
import os
import shutil
import tempfile
import time
from pathlib import Path

SCHEMA_VERSION = "pilot-manifest/1"

#: EXIF tags kept in the committable form. Everything else -- and every GPS tag without exception --
#: is dropped. Lens/exposure survive because a deviation in them is a protocol deviation.
EXIF_KEEP = (
    "DateTimeOriginal", "DateTime", "Make", "Model", "LensModel", "LensMake",
    "ExposureTime", "FNumber", "ISOSpeedRatings", "PhotographicSensitivity",
    "FocalLength", "FocalLengthIn35mmFilm", "WhiteBalance", "ExposureMode",
    "Orientation", "ExifImageWidth", "ExifImageHeight", "SubjectDistance",
)
#: Dropped even if they somehow appear in EXIF_KEEP. Belt and braces: a location leak is not
#: recoverable once committed.
EXIF_FORBIDDEN_PREFIXES = ("GPS", "Geo", "Location")


class ManifestError(Exception):
    pass


def canonical(obj):
    """Serialisation a hash can be taken over: sorted keys, no whitespace drift, no NaN."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False,
                      ensure_ascii=True)


def sha256_file(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(str(path), "rb") as f:
        for b in iter(lambda: f.read(chunk), b""):
            h.update(b)
    return h.hexdigest()


def sha256_text(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def atomic_write_text(path, text):
    """Write via a temp file in the same directory, fsync, then rename. Survives power loss."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-", suffix=path.suffix)
    try:
        with os.fdopen(fd, "w") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, str(path))
        dfd = os.open(str(path.parent), os.O_RDONLY)
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def read_exif(path):
    """EXIF as a plain dict, or {} if it cannot be read. Never raises: a photograph without EXIF is
    a photograph, not an error -- but the absence is recorded so a check can refuse to rely on it."""
    try:
        from PIL import Image, ExifTags
    except Exception:
        return {}
    try:
        with Image.open(str(path)) as im:
            raw = im.getexif()
            if not raw:
                return {}
            names = {v: k for k, v in ExifTags.TAGS.items()}
            out = {}
            for tag_id, val in raw.items():
                name = ExifTags.TAGS.get(tag_id, str(tag_id))
                if isinstance(val, bytes):
                    try:
                        val = val.decode("utf-8", "replace")
                    except Exception:
                        val = repr(val)
                if isinstance(val, (int, float, str)) or val is None:
                    out[name] = val
                else:
                    out[name] = str(val)
            return out
    except Exception:
        return {}


def sanitise_exif(exif):
    """The committable EXIF subset. Drops every GPS/location tag, keeps rig-relevant ones."""
    out = {}
    for k, v in (exif or {}).items():
        if any(str(k).startswith(p) for p in EXIF_FORBIDDEN_PREFIXES):
            continue
        if k in EXIF_KEEP:
            out[k] = v
    return out


def exif_timestamp(exif):
    """DateTimeOriginal as epoch seconds, or None. Used only as corroboration, never as proof."""
    s = (exif or {}).get("DateTimeOriginal") or (exif or {}).get("DateTime")
    if not s:
        return None
    for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return time.mktime(time.strptime(str(s)[:19], fmt))
        except (ValueError, OverflowError):
            continue
    return None


class Manifest(object):
    """Append-only, hash-chained capture log for one garment."""

    GENESIS = "0" * 64

    def __init__(self, path):
        self.path = Path(path)

    # -- reading ------------------------------------------------------------------------------

    def read(self, verify=True):
        """Return (entries, problems). A torn final line is reported, never silently dropped.

        `problems` is the honest channel: a manifest that does not verify must not read as an empty
        manifest, because an empty manifest is what a fresh garment looks like and the gate treats
        those very differently.
        """
        entries, problems = [], []
        if not self.path.exists():
            return entries, problems
        raw = self.path.read_text(errors="replace").split("\n")
        for i, line in enumerate(raw):
            if not line.strip():
                continue
            try:
                entries.append(json.loads(line))
            except ValueError:
                if i == len(raw) - 1 or not any(x.strip() for x in raw[i + 1:]):
                    problems.append({"kind": "torn_final_line", "line_no": i + 1,
                                     "detail": "the last line is not valid JSON, which is what an "
                                               "interrupted append looks like. It is excluded from "
                                               "the entries and must be re-captured.",
                                     "raw_prefix": line[:120]})
                else:
                    problems.append({"kind": "corrupt_line", "line_no": i + 1,
                                     "detail": "unparseable line with valid lines after it -- this "
                                               "is not a torn append but damage.",
                                     "raw_prefix": line[:120]})
        if verify:
            problems.extend(self.verify_chain(entries))
        return entries, problems

    def verify_chain(self, entries=None):
        """Recompute the chain. Any break names the first entry that does not follow."""
        if entries is None:
            entries, _ = self.read(verify=False)
        problems, prev = [], self.GENESIS
        for e in entries:
            body = {k: v for k, v in e.items() if k != "chain"}
            want = sha256_text(prev + canonical(body))
            if e.get("prev_chain") != prev:
                problems.append({"kind": "chain_break", "seq": e.get("seq"),
                                 "detail": "prev_chain does not match the previous entry's chain; "
                                           "an entry was inserted, removed or reordered."})
            elif e.get("chain") != want:
                problems.append({"kind": "chain_mismatch", "seq": e.get("seq"),
                                 "detail": "the entry's contents were edited after it was written."})
            prev = e.get("chain") or want
        return problems

    def head_chain(self, entries=None):
        if entries is None:
            entries, _ = self.read(verify=False)
        return entries[-1]["chain"] if entries else self.GENESIS

    # -- writing ------------------------------------------------------------------------------

    def append(self, kind, payload, *, operator=None, setup_hash=None, now=None):
        """Append one chained entry and return it. fsync'd before returning."""
        entries, problems = self.read(verify=False)
        torn = [p for p in problems if p["kind"] == "torn_final_line"]
        if torn:
            # Repair before extending: appending after a torn line would chain onto nothing and
            # make the damage permanent. The torn bytes are kept beside the manifest as evidence.
            self._quarantine_torn()
            entries, _ = self.read(verify=False)
        prev = self.head_chain(entries)
        entry = {
            "schema": SCHEMA_VERSION,
            "seq": len(entries),
            "ts": float(now if now is not None else time.time()),
            "kind": str(kind),
            "operator": operator,
            "setup_hash": setup_hash,
            "payload": payload,
            "prev_chain": prev,
        }
        entry["chain"] = sha256_text(prev + canonical(entry))
        line = canonical(entry) + "\n"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(str(self.path), "a") as f:
            f.write(line)
            f.flush()
            os.fsync(f.fileno())
        return entry

    def _quarantine_torn(self):
        raw = self.path.read_text(errors="replace")
        lines = raw.split("\n")
        keep, bad = [], []
        for i, line in enumerate(lines):
            if not line.strip():
                continue
            try:
                json.loads(line)
                keep.append(line)
            except ValueError:
                bad.append(line)
        if bad:
            q = self.path.with_suffix(self.path.suffix + ".torn")
            with open(str(q), "a") as f:
                f.write("\n".join(bad) + "\n")
                f.flush()
                os.fsync(f.fileno())
        atomic_write_text(self.path, "".join(l + "\n" for l in keep))

    # -- committable form ---------------------------------------------------------------------

    def sanitised(self, repo_root):
        """The form that may enter git: repo-relative paths, EXIF subset, no GPS, no absolute path.

        Raises rather than emitting anything that still contains an absolute path: a leak here is
        not recoverable once pushed, so the failure must be loud and at write time.
        """
        repo_root = Path(repo_root).resolve()
        entries, problems = self.read()
        out = []
        for e in entries:
            c = json.loads(canonical(e))
            p = c.get("payload") or {}
            if isinstance(p, dict):
                if "exif" in p:
                    p["exif"] = sanitise_exif(p["exif"])
                for key in ("source_path", "abs_path", "src"):
                    p.pop(key, None)
                for key in ("path", "stored_path"):
                    v = p.get(key)
                    if isinstance(v, str) and os.path.isabs(v):
                        try:
                            p[key] = str(Path(v).resolve().relative_to(repo_root))
                        except ValueError:
                            raise ManifestError(
                                "manifest entry seq=%s has an absolute path outside the repository "
                                "(%r); it cannot be sanitised for commit." % (c.get("seq"), v))
            out.append(c)
        blob = canonical(out)
        if str(repo_root) in blob or "/Users/" in blob or "/home/" in blob:
            raise ManifestError("sanitised manifest still contains an absolute path")
        return out, problems


def ingest_photo(src, dest_dir, shot_id, rep, *, state=None, move=False):
    """Copy a capture into the garment tree under a content-addressed name. Never overwrites.

    Returns (dest_path, sha, was_already_present). Re-ingesting identical bytes is a no-op that
    reports itself, which is what makes an interrupted upload safe to retry: the retry either
    completes the copy or discovers the copy already completed.
    """
    src = Path(src)
    if not src.exists():
        raise ManifestError("source does not exist: %s" % src)
    sha = sha256_file(src)
    ext = src.suffix.lower() or ".jpg"
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    safe_shot = "".join(ch if (ch.isalnum() or ch in "._-") else "_" for ch in str(shot_id))
    dest = dest_dir / ("%s__r%02d__%s%s" % (safe_shot, int(rep), sha[:12], ext))
    if dest.exists():
        if sha256_file(dest) == sha:
            return dest, sha, True
        raise ManifestError(
            "refusing to overwrite %s: it exists with different content. A photograph is never "
            "replaced in place; capture it under a new repetition." % dest)
    fd, tmp = tempfile.mkstemp(dir=str(dest_dir), prefix=".ingest-", suffix=ext)
    os.close(fd)
    try:
        shutil.copy2(str(src), tmp)
        with open(tmp, "rb") as f:
            os.fsync(f.fileno())
        if sha256_file(tmp) != sha:
            raise ManifestError("copy of %s does not match its source hash (torn read?)" % src)
        os.replace(tmp, str(dest))
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    if move:
        try:
            os.unlink(str(src))
        except OSError:
            pass
    return dest, sha, False
