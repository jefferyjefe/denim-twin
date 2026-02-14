#!/usr/bin/env python3
"""Ingest GitHub issues labelled 'pair-submission' into data/external/pairs.jsonl (source_type='submission').
Requires `gh` auth. Idempotent: skips issues already ingested (page_url = issue URL)."""
import json, re, subprocess, sys, datetime as dt
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; P = ROOT / "data/external/pairs.jsonl"
existing = {json.loads(l)["page_url"] for l in P.read_text().splitlines() if l.strip()} if P.exists() else set()
issues = json.loads(subprocess.run(["gh", "issue", "list", "-R", "jefferyjefe/denim-twin", "-l", "pair-submission", "-s", "all", "--json",
                                    "number,url,title,body,author,createdAt", "-L", "200"], capture_output=True, text=True, check=True).stdout)
IMG = re.compile(r"(https://(?:github\.com/user-attachments/assets|user-images\.githubusercontent\.com)/[^\s)\"]+|https?://[^\s)\"]+\.(?:jpe?g|png|webp)(?:\?[^\s)\"]*)?)", re.I)   # GitHub attachments or pasted image links
def section(body, heading):
    m = re.search(rf"### {re.escape(heading)}[^\n]*\n(.*?)(?=\n### |\Z)", body, re.S); s = m.group(1) if m else ""
    return "" if s.strip() == "_No response_" else s
new = 0
with P.open("a") as f:
    for it in issues:
        if it["url"] in existing: continue
        b = it["body"] or ""
        if "I took these photos" not in b or "[X]" not in b and "[x]" not in b: continue   # consent box unticked
        images = []
        for role, head in (("before", "BEFORE photo(s)"), ("after_cut", "AFTER CUTTING photo(s)"), ("after_wash", "AFTER WASHING photo(s)")):
            for u in IMG.findall(section(b, head)): images.append({"url": u, "role": role, "note": ""})
        if not any(i["role"] == "before" for i in images) or not any(i["role"].startswith("after") for i in images): continue
        scale = section(b, "Scale reference in the photos").strip()
        rec = dict(page_url=it["url"], title=it["title"], source_type="submission", garment_desc=section(b, "Care label").strip(),
                   images=images, wash_described=bool(section(b, "How was it washed").strip()), wash_notes=section(b, "How was it washed").strip(),
                   cut_notes=section(b, "How did you cut?").strip(),
                   scale_ref={"none": "none"}.get(scale, "ruler" if "ruler" in scale else "coin" if "coin" in scale else "known_object" if scale else "none"),
                   scale_detail=section(b, "Which coin / object?").strip(),
                   license_or_terms="CC BY 4.0 (contributor consent in issue)" + ("" if "Anonymous" in section(b, "Attribution") else f"; attribution: {it['author']['login']}"),
                   found_at=dt.date.today().isoformat())
        f.write(json.dumps(rec) + "\n"); new += 1
print(f"ingested {new} new submissions")
