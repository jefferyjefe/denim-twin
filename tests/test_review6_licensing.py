"""Review 6 — the nine high-resolution controls were committed to git as image files.

Expected to FAIL.
"""
import json, os, subprocess

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _tracked(prefix):
    r = subprocess.run(["git", "-C", ROOT, "ls-files", prefix], capture_output=True, text=True)
    return [l for l in r.stdout.splitlines() if l.strip()]


def test_no_all_rights_reserved_image_file_is_committed():
    """data/external/README.md:1-7 states the policy — "Sources: Openverse (all CC licenses) and Wikimedia Commons
    (free licenses only) ... Download locally ... -> `images/` (gitignored)" — and .gitignore keeps every other
    image directory out of the repository: `data/external/images/`, `data/external/pair_images/`,
    `data/external/unpaired_images/`. tools/ingest_unpaired.py:6-8 restates it: "Nothing here is redistributed:
    images land in data/external/unpaired_images/ (gitignored) and only scale-free numbers enter the repo."

    observed: commit d5debb6 added nine .jpg files (7.2 MB) under data/external/control_images/ to the
              repository. data/external/control_candidates.jsonl records each one's terms, and all nine read
              "copyright / all rights reserved" — one of them quoting the store's own terms: "You agree not to
              reproduce, duplicate, copy, sell, resell or exploit any portion of the Service ... without express
              written permission by us". The measurements derived from them are already committed in
              reports/fringe_methods/controls_roughness.json, so the image files are not needed in git.
    expected: control images follow the same rule as every other harvested image — measured locally, gitignored."""
    tracked = _tracked("data/external/control_images")
    terms = {os.path.basename(json.loads(l)["image_url"].split("?")[0]): json.loads(l)["license_or_terms"]
             for l in open(os.path.join(ROOT, "data/external/control_candidates.jsonl")) if l.strip()}
    restricted = sorted(t for t in terms.values() if "all rights reserved" in t.lower())
    assert not tracked, (f"{len(tracked)} image files committed under data/external/control_images/ "
                         f"({len(restricted)} of {len(terms)} candidate records say 'all rights reserved')")


def test_the_control_image_directory_is_gitignored_like_every_other_image_directory():
    """.gitignore lists data/external/images/, data/external/pair_images/ and data/external/unpaired_images/ but
    not data/external/control_images/, which is why the nine files above could be added at all.

    expected: the new image directory is ignored on the same terms as the others."""
    ig = open(os.path.join(ROOT, ".gitignore")).read()
    assert "data/external/control_images/" in ig, (
        "data/external/control_images/ is not in .gitignore, unlike data/external/{images,pair_images,unpaired_images}/")
