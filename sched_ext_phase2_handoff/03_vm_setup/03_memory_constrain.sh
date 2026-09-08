#!/usr/bin/env bash
#
# 03_memory_constrain.sh
#
# RUN THIS INSIDE THE FEDORA VM.
#
# Creates a memory-limited cgroup (v2) to simulate a resource-constrained
# device for the actual research experiments — this is the practical
# stand-in for "real embedded hardware" discussed earlier: it gives you
# a genuine, enforced memory ceiling without needing physical hardware.
#
# Usage:
#   ./03_memory_constrain.sh <memory_limit> <command...>
#
# Example:
#   ./03_memory_constrain.sh 512M ./build/scheds/c/scx_simple
#
# This runs the given command inside a cgroup capped at the given memory
# limit. Any child processes it spawns (e.g. your test workload
# generator) inherit the same limit.

set -euo pipefail

if [ "$#" -lt 2 ]; then
    echo "Usage: $0 <memory_limit e.g. 512M> <command...>"
    exit 1
fi

MEM_LIMIT="$1"
shift

CGROUP_NAME="sched-ext-research"
CGROUP_PATH="/sys/fs/cgroup/${CGROUP_NAME}"

if [ ! -d "${CGROUP_PATH}" ]; then
    echo "==> Creating cgroup: ${CGROUP_PATH}"
    sudo mkdir -p "${CGROUP_PATH}"
fi

echo "==> Setting memory limit: ${MEM_LIMIT}"
echo "${MEM_LIMIT}" | sudo tee "${CGROUP_PATH}/memory.max" > /dev/null

echo "==> Setting memory.high to 90% of max as an early-warning threshold"
# memory.high triggers reclaim pressure before the hard memory.max limit
# is hit — useful for observing degradation rather than a hard OOM kill.
# This is a simple heuristic; adjust if you want harder/softer behaviour.
echo "==> (leaving memory.high unset for now — add manually if you want"
echo "    graduated pressure instead of a hard cutoff at memory.max)"

echo "==> Adding current shell to the cgroup, then running command"
echo "$$" | sudo tee "${CGROUP_PATH}/cgroup.procs" > /dev/null

echo "==> Running: $*"
echo "    (constrained to ${MEM_LIMIT} via cgroup ${CGROUP_NAME})"
exec "$@"
