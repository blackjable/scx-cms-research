#!/usr/bin/env bash
#
# 02_fedora_vm_setup.sh
#
# RUN THIS INSIDE THE FEDORA VM (not on macOS).
#
# Verifies sched_ext is available in the running kernel, installs build
# dependencies, and builds the scx workspace -- specifically scx_cms,
# the swappable-identity-key scheduler scaffolded in Phase 2 step 2.
#
# REVISED from the original version of this script: the original used
# `meson setup`/`meson compile` and cloned a fresh copy of scx from
# GitHub. Both are stale -- as of this repo's current state, the C
# schedulers (and meson) were removed entirely; the project builds
# exclusively via `cargo` now (see CARGO_BUILD.md at the repo root).
# This script also builds the LOCAL repo (rsync'd in from the Mac host,
# expected at ~/scx) rather than a fresh GitHub clone, since a fresh
# clone would not contain the scx_cms scaffolding already done.

set -euo pipefail

echo "==> Kernel version check"
uname -r

echo "==> Checking for sched_ext support"
if [ -d /sys/kernel/sched_ext ]; then
    echo "    /sys/kernel/sched_ext exists — sched_ext is available. Good."
else
    echo "    WARNING: /sys/kernel/sched_ext does not exist."
    echo "    This Fedora kernel may not have CONFIG_SCHED_CLASS_EXT enabled,"
    echo "    or you're on an older release. Check 'fedoraproject.org' for"
    echo "    the current recommended release, or run:"
    echo "        sudo dnf update kernel"
    echo "    and reboot, then re-run this script."
fi

echo "==> Installing build dependencies"
sudo dnf install -y \
    clang llvm \
    elfutils-libelf-devel \
    zlib-devel libzstd-devel \
    libbpf-devel bpftool \
    pkgconf-pkg-config \
    git \
    dwarves \
    make gcc

BUILD_DIR="${HOME}/scx"

if [ ! -d "${BUILD_DIR}" ]; then
    echo "==> ${BUILD_DIR} not found."
    echo "    This script expects the repo to be rsync'd in from the Mac"
    echo "    host first (it builds the LOCAL working tree, including"
    echo "    scx_cms, not a fresh GitHub clone). From the host:"
    echo ""
    echo "        rsync -az --exclude target --exclude .git \\"
    echo "            /Users/jamieblack/sched_ext/repo/ jblack@<vm-ip>:~/scx/"
    echo ""
    echo "    Then re-run this script."
    exit 1
fi

cd "${BUILD_DIR}"

echo "==> Installing Rust toolchain (rustup, matching rust-toolchain.toml)"
if ! command -v rustup &>/dev/null; then
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
fi
# shellcheck disable=SC1091
source "${HOME}/.cargo/env"

echo "==> Building scx_cms (the scheduler scaffolded in Phase 2 step 2)"
cargo build -p scx_cms

echo ""
echo "==> Build complete: target/debug/scx_cms"
echo ""
echo "Quick sanity check — run scx_cms and confirm it loads:"
echo "    sudo ./target/debug/scx_cms --stats 1"
echo ""
echo "In another terminal (or another SSH session), verify it's active:"
echo "    cat /sys/kernel/sched_ext/state       # should print 'enabled'"
echo "    cat /sys/kernel/sched_ext/*/ops       # should print 'cms'"
echo ""
echo "Stop it with Ctrl-C in the first terminal; the system reverts to"
echo "the default scheduler automatically."
echo ""
echo "Next: run 03_memory_constrain.sh to set up the memory-capped cgroup"
echo "you'll use for the actual sketch-vs-exact-counter experiments."
