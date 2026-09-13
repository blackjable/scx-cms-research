> ## ⚠️ These instructions describe UTM. The measurements did not use UTM.
>
> Every result in this project was produced in a **Lima** VM, not UTM.
> UTM was the original plan and was abandoned early -- its VM creation is
> GUI-driven and awkward to script, and driving it from the command line
> was painful enough to be worth replacing.
>
> This matters more than a tooling preference. The virtualisation layer
> is part of the measurement environment: this project found that the
> guest's timer-delivery floor invalidated an entire workload, and that
> the host moved vCPUs between performance and efficiency cores with no
> visibility from inside. Reproducing on a different hypervisor is not
> reproducing.
>
> **The actual configuration is committed as
> [`lima-scx-fedora.yaml`](lima-scx-fedora.yaml)** -- 4 CPUs, 4 GiB,
> Fedora 44 cloud image, with the scx repo mounted through from the host.
> Recreate with:
>
> ```
> brew install lima
> limactl start --name=scx-fedora lima-scx-fedora.yaml
> limactl shell scx-fedora
> ```
>
> The sections below are kept because the reasoning about *why Fedora*
> still applies, and because the UTM detour is part of the record. The
> UTM-specific mechanics are superseded.

# macOS sched_ext Dev Environment Setup

Sets up a sched_ext development environment on macOS via a Fedora Linux
VM (UTM). No Raspberry Pi, no cross-compiling, no kernel building — as
of 2026, Fedora ships a sched_ext-enabled kernel by default.

Companion to `sched_ext_embedded_research.md` (the research project
definition) and a replacement for the earlier Pi-based scripts, per the
decision to use a memory-constrained VM/cgroup instead of physical
embedded hardware.

## Why Fedora, why UTM

- **Fedora**: confirmed to ship `CONFIG_SCHED_CLASS_EXT` enabled by
  default as of 2026 (along with Arch, CachyOS, NixOS unstable, openSUSE
  Tumbleweed). No kernel config patching or building required.
- **UTM**: free, native macOS virtualization (Apple's Hypervisor
  framework under the hood), works on both Apple Silicon and Intel
  Macs, no licensing friction unlike some alternatives.

## Order of operations

### 1. `01_macos_host_setup.sh` — run on macOS, in Terminal
Installs UTM via Homebrew and downloads a Fedora Server image matching
your Mac's architecture (Apple Silicon vs Intel, auto-detected).
Requires Homebrew already installed (https://brew.sh if not).

After this script finishes, there's a **manual, one-time step**: create
the actual VM in UTM's GUI pointing at the downloaded image. The script
prints the specific settings to use (RAM, CPU cores, etc.) — this isn't
automatable cleanly since UTM's VM creation is GUI-driven.

### 2. `02_fedora_vm_setup.sh` — run INSIDE the Fedora VM
Verifies sched_ext is actually available in the running kernel (checks
`/sys/kernel/sched_ext`), installs build dependencies, clones and builds
`sched-ext/scx`. Ends with a sanity check running `scx_simple`.

### 3. `03_memory_constrain.sh` — run INSIDE the Fedora VM, per-experiment
This is your actual "resource-constrained device" simulation. Wraps any
command in a memory-capped cgroup (v2), giving you a genuine enforced
memory ceiling for testing the sketch-vs-exact-counter hypothesis
without needing physical embedded hardware.

Usage:
```bash
./03_memory_constrain.sh 512M ./build/scheds/c/scx_simple
```

Adjust the memory limit (`512M`, `256M`, `128M`, etc.) to match whatever
constraint level you want to test against. Running your future custom
scheduler binary the same way lets you directly compare sketch-based vs.
exact-counter memory behavior under a controlled, repeatable ceiling —
arguably a *more* controlled experiment than real hardware, since you
can sweep the memory limit precisely across runs.

## Notes and honest caveats

- **File transfer between macOS and the VM**: easiest via UTM's shared
  directory feature (enable in VM settings) or plain `scp`/`rsync` over
  the VM's network interface. Not scripted here since it's a one-time
  UTM config choice, not a repeated setup step.
- **This setup gives you real x86_64 or ARM64 Linux kernel behavior**
  (matching your Mac's own architecture) — genuinely more trustworthy
  for latency measurements than the QEMU ARM64 emulation route
  discussed earlier, since there's no instruction-set emulation layer
  involved regardless of which Mac you have.
- **Fedora release numbers change.** If the image URL in
  `01_macos_host_setup.sh` 404s, check
  https://fedoraproject.org/server/download for the current release and
  update the script.
- If you later do want to validate on real embedded hardware (e.g. once
  the core VM-based result holds), the Pi-based scripts from earlier are
  still valid for that follow-up phase — this setup doesn't replace
  them, it lets you start now without waiting on hardware.
