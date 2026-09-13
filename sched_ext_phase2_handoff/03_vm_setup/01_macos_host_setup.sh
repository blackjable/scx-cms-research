#!/usr/bin/env bash
#
# ⚠️ SUPERSEDED. This script installs UTM. The measurements in this
# project were made in a Lima VM, not UTM -- see README.md and
# lima-scx-fedora.yaml for the configuration that was actually used.
# Kept for the record; do not follow it to reproduce results.
#
# 01_macos_host_setup.sh
#
# RUN THIS ON YOUR MAC (in Terminal), not inside any VM.
#
# Installs UTM (a free, native macOS virtualization app — works on both
# Apple Silicon and Intel Macs) via Homebrew, and downloads a Fedora
# cloud image to use as the base for your sched_ext dev VM.
#
# Fedora is chosen because, as of 2026, it ships a sched_ext-enabled
# kernel by default — no kernel building or config patching required,
# unlike the earlier Raspberry Pi path.

set -euo pipefail

echo "==> Checking for Homebrew"
if ! command -v brew &>/dev/null; then
    echo "Homebrew not found. Install it first: https://brew.sh"
    echo "Then re-run this script."
    exit 1
fi

echo "==> Installing UTM"
brew install --cask utm

echo "==> Detecting Mac architecture"
ARCH="$(uname -m)"
echo "    Detected: ${ARCH}"

DOWNLOAD_DIR="${HOME}/Downloads/sched-ext-vm"
mkdir -p "${DOWNLOAD_DIR}"
cd "${DOWNLOAD_DIR}"

if [ "${ARCH}" = "arm64" ]; then
    echo "==> Apple Silicon detected — downloading Fedora Server aarch64 image"
    IMAGE_URL="https://download.fedoraproject.org/pub/fedora/linux/releases/44/Server/aarch64/images/Fedora-Server-Guest-Generic-44-1.7.aarch64.qcow2"
else
    echo "==> Intel Mac detected — downloading Fedora Server x86_64 image"
    IMAGE_URL="https://download.fedoraproject.org/pub/fedora/linux/releases/44/Server/x86_64/images/Fedora-Server-Guest-Generic-44-1.7.x86_64.qcow2"
fi

echo "    NOTE: Fedora release numbers change over time. If this URL"
echo "    404s, check https://fedoraproject.org/server/download for the"
echo "    current release and update IMAGE_URL above."

if [ ! -f "$(basename "${IMAGE_URL}")" ]; then
    curl -L -O "${IMAGE_URL}"
else
    echo "    Image already downloaded, skipping."
fi

echo ""
echo "==> Done. Image downloaded to: ${DOWNLOAD_DIR}"
echo ""
echo "Next steps (manual, one-time, via UTM's GUI):"
echo "  1. Open UTM"
echo "  2. Create a new VM -> 'Virtualize' -> Linux"
echo "  3. Point it at the downloaded .qcow2 image as the boot disk"
echo "  4. Allocate at least 4GB RAM and 2 CPU cores for comfortable"
echo "     building (you'll deliberately constrain memory for actual"
echo "     experiments later — this is just for setup/build comfort)"
echo "  5. Enable 'Share directory' in UTM's VM settings if you want to"
echo "     share a folder between macOS and the VM (optional but handy"
echo "     for moving files without scp)"
echo "  6. Boot the VM, complete Fedora's first-boot setup"
echo ""
echo "Once the VM is booted and you can SSH or use its terminal, run"
echo "02_fedora_vm_setup.sh INSIDE the VM."
