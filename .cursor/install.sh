#!/usr/bin/env bash
# Cloud Agent install: reproduce the hermetic-core development environment.
#
# This is the environment CI runs in (see .github/workflows/tests.yml and
# docs/REPRODUCIBILITY.md): CPython 3.11 + requirements-ci.txt, with NO torch,
# no SAM checkpoint and no photographs. It runs the whole test suite, every
# verification gate (tools/verify.py --profile ci) and the Pilot Capture
# Navigator (tools/pilot.py, including its web app).
#
# The heavy optional extras in requirements.txt (torch, torchvision,
# segment-anything, open_clip_torch) are deliberately NOT installed here:
#   * constraints.txt pins click==8.1.8, but open_clip_torch -> typer==0.23.2
#     requires click>=8.2.1 on Python >= 3.10, so `pip install -r
#     requirements.txt` cannot be satisfied on CPython 3.11 (Linux). This is the
#     Linux/3.11 reproducibility hole constraints.txt already documents (its
#     closure was computed on macOS + CPython 3.9).
#   * The code paths that need them (tools/predict.py from an image, and
#     tools/verify.py --profile full) also require the 375 MB SAM checkpoint and
#     the all-rights-reserved garment photographs, none of which live in the
#     repository. See src/denimtwin/prereqs.py.
# To work on the segmentation path, a developer can add it explicitly on top:
#   .venv/bin/pip install torch torchvision segment-anything
#
# The script is idempotent: it may run repeatedly against a prepared snapshot.
set -euo pipefail

cd "$(dirname "$0")/.."

# --- Python 3.11 -------------------------------------------------------------
# Match CI. Ubuntu 24.04 ships CPython 3.12; 3.11 comes from the deadsnakes PPA.
if ! command -v python3.11 >/dev/null 2>&1; then
  sudo add-apt-repository -y ppa:deadsnakes/ppa
  sudo apt-get update -qq
  sudo apt-get install -y python3.11 python3.11-venv python3.11-dev
fi

# --- the hermetic core, in a venv -------------------------------------------
if [ ! -x .venv/bin/python ]; then
  python3.11 -m venv .venv
fi
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements-ci.txt

echo
echo "denim-twin environment ready. Activate with:  source .venv/bin/activate"
echo "Verify the repository:                        python tools/verify.py --profile ci --no-bench"
