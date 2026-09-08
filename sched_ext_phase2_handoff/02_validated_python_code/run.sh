#!/usr/bin/env bash
#
# run.sh
#
# One-command way to build and run the CMS prototype in Docker.
# No VM, no kernel, no GUI steps — this validates the core hypothesis
# in plain Python first, before any BPF/kernel work.
#
# Usage:
#   ./run.sh              # run the experiment once, print report
#   ./run.sh --plot        # also generate a memory-growth chart
#
# Edit experiment.py locally between runs — it's mounted live, not
# baked into the image, so there's no rebuild step for code changes.

set -euo pipefail

IMAGE_NAME="cms-prototype"

echo "==> Building image (only slow the first time)"
docker build -t "${IMAGE_NAME}" .

echo "==> Running experiment"
docker run --rm \
    -v "$(pwd)":/work \
    "${IMAGE_NAME}" \
    python experiment.py "$@"
