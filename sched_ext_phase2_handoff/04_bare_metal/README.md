# Setting up a bare-metal measurement host

Everything in this project was measured in a VM on 4 aarch64 cores. That
environment invalidated one workload outright (`rt-app`, defeated by a
~1.7ms timer-delivery floor), hid an uncontrolled variable in every
result (the host moving vCPUs between performance and efficiency cores),
and could not measure energy at all.

This is how to build the machine that removes those limits.

## Before you buy or commit: does the machine qualify?

Two hard requirements, and one that is easy to get wrong.

**Intel RAPL needs Sandy Bridge (2nd gen, 2011) or later.** Nehalem and
Lynnfield -- the 1st-generation i5-7xx and i7-8xx -- have no RAPL, which
rules out energy work entirely. The year on the box is not reliable;
check the model number.

**`sched_ext` needs kernel 6.12 or later.** Fedora 44 ships 6.19.

**Avoid 12th-generation Intel and newer.** Those are hybrid, P-cores plus
E-cores, which reintroduces exactly the heterogeneity confound this
exercise exists to escape. 6th through 10th generation are homogeneous
and cheap secondhand.

## Buying secondhand: one question that matters more than the rest

Most cheap qualifying hardware is ex-corporate, and ex-corporate
machines frequently ship with a **BIOS supervisor password still set**.
That can block changing boot order, booting from USB, or disabling SMT,
and on many ThinkPads and business Dells it cannot be cleared without
replacing the mainboard.

Every other defect is recoverable after delivery. This one is not, so
ask before buying:

> 1. Is the BIOS supervisor password cleared?
> 2. What is the exact CPU model (i5-10210U, i5-8265U, and so on)?
> 3. Is the drive an SSD?
> 4. Is the charger included?

All four are lookups a seller can do from the BIOS screen or the
sticker. **Do not expect a seller to run diagnostic commands** -- they
will not, and there is no need: RAPL presence follows from the CPU
generation, so the exact model number answers it. The risk being managed
here is a mis-described listing, not uncertain hardware.

Buy from a seller offering returns. If it arrives mis-described or with
a locked BIOS, that is the remedy.

Verify on the machine before installing anything, from a live USB:

```bash
lscpu | grep -E 'Model name|^CPU\(s\)|Thread'
ls /sys/class/powercap/intel-rapl/            # must not be empty
perf stat -e power/energy-pkg/ sleep 1        # must return joules
cat /sys/devices/system/cpu/cpu0/cpuidle/state*/name
```

If RAPL is absent, the machine can still close the timer and
architecture gaps -- it just cannot answer the energy question.

## Which image

**Fedora Server 44, x86_64.**

- *Server*, not Workstation: a desktop session brings a compositor,
  indexers and background daemons onto a machine whose scheduling
  latency you are trying to measure. See `../../results/BENCHMARK_HOST.md`.
- *44*, matching the VM, so that when bare-metal results are compared
  against the existing archive the operating system is held constant and
  only the hardware has changed.
- *x86_64*, **not aarch64**. The VM is aarch64; the bare-metal candidates
  are Intel. Downloading the wrong architecture is an easy 2 GB mistake.

```
https://download.fedoraproject.org/pub/fedora/linux/releases/44/Server/x86_64/iso/Fedora-Server-dvd-x86_64-44-1.7.iso
```

## Writing the USB

On macOS, either **Fedora Media Writer** (point-and-click, verifies the
checksum) or:

```bash
diskutil list                          # identify the stick -- carefully
diskutil unmountDisk /dev/diskN
sudo dd if=Fedora-Server-dvd-x86_64-44-1.7.iso of=/dev/rdiskN bs=4m status=progress
```

`rdiskN` rather than `diskN` is substantially faster. Getting the disk
number wrong overwrites something you care about, so run `diskutil list`
twice.

## Booting it

**On a Mac:** hold **⌥ Option** during startup and choose the USB. This
happens in Apple firmware, before any OS loads, so a *Bluetooth keyboard
will not work* -- use the built-in one or a wired USB keyboard.

**On a ThinkPad:** F12 for the boot menu, or Enter then F12.

Nothing is written to disk until you explicitly run the installer, so
booting to test costs nothing.

## Install choices that matter

| choice | value | why |
|---|---|---|
| software selection | **Minimal Install** | no desktop; fewer processes competing with the measurement |
| partitioning | Automatic | nothing here needs a custom layout |
| network | **wired ethernet** | removes a wireless driver from the equation; a headless box with broken wireless cannot be reached to fix |
| root/user | any | you will type it once, then use SSH keys |
| SSH | **enable** | this machine should be headless |

On a laptop with damaged keys, choose a username and password composed
only of keys that work. It is typed once.

## After installation

```bash
# headless access
sudo systemctl enable --now sshd
ip a | grep 'inet '

# from the workstation, so passwords are never typed again
ssh-copy-id user@<ip>
```

Then apply `../../results/BENCHMARK_HOST.md` in full -- disabling the
periodic timers, pinning the CPU governor, masking the sleep targets,
and on a laptop stopping the lid from suspending it. That document
exists because a day was spent investigating a 240ms latency excursion
that turned out to be environmental.

## Building the scheduler

```bash
sudo dnf install -y git cargo rustc clang llvm bpftool libbpf-devel \
                    elfutils-libelf-devel zlib-devel pkgconf-pkg-config \
                    make jq tmux stress-ng perf

git clone https://github.com/sched-ext/scx.git
git clone <your scx-cms repo> scx/scheds/experimental/scx_cms
cd scx && cargo build -p scx_cms

uname -r                                   # confirm >= 6.12
cat /sys/kernel/sched_ext/state             # should exist
```

`scx_cms` does not build standalone -- it depends on `scx_utils` by
relative path and uses scx's BPF tooling, so it must sit inside an scx
checkout.

Workload tools: `schbench` and `rt-app`, both built from source.
`rt-app` matters here specifically -- it was unusable in the VM, and
bare metal is what makes the audio-callback workload testable at last.

## What to run first

Not the headline experiment. **Re-run the existing matrices and score the
predictions**, which are already written down and dated in the paper's
limitations section: the memory result should survive, absolute latencies
should shrink, the `LRU_HASH` cliff should stay put if this is also a
4-core machine, and the tail penalty is the one most at risk because it
rests on rare events in an environment that manufactures them.

A prediction that fails is more interesting than one that holds.

For energy, follow `../../benchmark/ENERGY_METHOD.md`, which starts with
instrument validation rather than with a comparison -- an instrument that
cannot detect a sledgehammer cannot detect the mechanism.

## Record what you built

Add the new machine to `../../results/ENVIRONMENT.md`: kernel, CPU model,
core count, whether RAPL is present, and what was disabled. Every
bare-metal number will be compared against the VM archive, and "what was
different about the machine" is unrecoverable after the fact.
