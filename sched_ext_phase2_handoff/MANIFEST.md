# START HERE — Phase 2 Handoff Manifest

Start here. This file explains what everything else is and what order
to read it in. Nothing outside this folder is
needed; nothing inside it is obsolete filler — every file here earned
its place through the Phase 1 research process.

## Suggested reading order

Read `00_orientation/paper_sections_2_to_6_draft.md` in full, then
`01_delivery_plan/phase2_delivery_plan_update.md`, and establish the
current state and the next concrete action before writing any code.

That ordering is deliberate: acting on stale or partial assumptions
caused real problems earlier in this project (see the paper's audit
sections, and `results/REVISIONS.md`).

## Folder-by-folder guide

### `00_orientation/` — read first, in this order

1. `sched_ext_contribution_context.md` — why this project exists at
   all: general sched_ext contribution background, dev environment
   basics.
2. `sched_ext_embedded_research.md` — why resource-constrained/mobile
   scheduling specifically: LPC 2026 citations, the real gaps this
   targets, why they're real (not assumed).
3. `paper_sections_2_to_6_draft.md` — **the primary reference for
   everything**. Every design decision, number, bug found and fixed,
   and piece of reasoning from Phase 1 lives here, organized by
   section (2 = approach, 3 = methodology, 4 = results/findings,
   5 = limitations, 6 = conclusion, plus a consolidated checklist at
   the end). When any other file conflicts with this one, this one
   wins — it's the most current and most detailed.

### `01_delivery_plan/` — read second

- `phase2_delivery_plan_update.md` — the delta between what was
  originally planned for Phase 2 and what Phase 1 actually taught us:
  resolved design decisions (windowing scheme, hash function,
  mitigation approach), the four-tier baseline requirement (not just
  one narrow comparison), tooling gaps, and open questions to resolve
  FIRST (identity key choice, penalty-vs-boost mechanism design).
  Points back into the paper draft for detail on each item — read
  that first if anything here is unclear.

### `02_validated_python_code/` — the logic that gets ported to BPF

This is Phase 1's actual output: a Count-Min Sketch vs. exact-counter
comparison, stress-tested across many rounds of deliberate bug-hunting.
Read `README.md` inside this folder first for how to run it (one
command via Docker, no VM needed: `./run.sh`).

- `sketch_lib.py` — **the canonical implementation**. Count-Min
  Sketch, exact counter, rotating dual-buffer windowing, churn
  distributions, pluggable hash functions. This is what gets ported.
- `experiment.py` — basic demo/sanity-check script.
- `sweep_experiment.py` — multi-seed variance, parameter sweeps,
  adversarial distribution testing.
- `strict_tests.py` — reproducibility verification, formal invariant
  checking, the targeted-collision attack (the project's most
  important negative finding).
- `expanded_findings_experiment.py` — width/depth tradeoff, seed
  rotation as a defense, hash function comparison (blake2b vs.
  FNV-1a), multi-window attack decay, anomaly-triggered mitigation.
- `savage_audit.py` — real memory measurement (replacing a guessed
  constant), exact L1 norm verification, extended invariant coverage,
  formal statistical significance testing, edge-case fuzzing,
  collision-search verification.
- `scheduler_policy_simulation.py` — early, pure-Python scheduling
  POLICY comparison. Explicitly NOT a preview of real kernel behavior
  — read its own docstring before drawing any conclusion from it, and
  see paper Section 4.2.1 for the full honest writeup including three
  real bugs found and fixed during this exercise.
- `requirements.txt` / `Dockerfile` / `run.sh` — how to actually run
  any of the above. Dependencies were directly audited against real
  imports (an earlier version had this wrong — unused `numpy` listed,
  required `scipy` missing — fixed and verified).
- `*.png` — result charts from the above scripts, for reference only,
  not needed to run anything.

**The BPF port is done** — see `scx_cms`, in its own repository at
`github.com/blackjable/scx-cms`. The regression suite this section asked
for exists on both sides: `test_sketch_lib.py` here, and `tests/` in the
scheduler repo, which found a real gap the moment it was written and
carries the known increment-then-read atomicity bug as an expected
failure.

### `03_vm_setup/` — kernel/BPF development environment

Read `README.md` inside this folder first — it opens with a banner
explaining that these instructions describe **UTM and the measurements
did not use UTM**.

Every result in this project was produced in a **Lima** VM. UTM was the
original plan and was abandoned early: its VM creation is GUI-driven,
its console blocks paste, and SSH and sudo have to be set up by hand,
none of which suits scripted use. `lima-scx-fedora.yaml` in that folder
is the configuration that actually produced the measurements — 4 CPUs,
4 GiB, Fedora 44 — and is the thing to use.

`01_macos_host_setup.sh` (which installs UTM) and the UTM-specific parts
of the README are superseded and carry banners saying so. They are kept
because the reasoning about *why Fedora* still applies and because the
detour is part of the record. `02_fedora_vm_setup.sh` and
`03_memory_constrain.sh` are guest-side and unaffected by the host
tooling change.

**Still worth knowing**: the Fedora release pinned in the setup script
will go stale — check https://fedoraproject.org/server/download for the
current release. The scripts install C/BPF build tools only; `schbench`,
`cyclictest`, `hackbench` and `rt-app` are separate (delivery plan
Section 4). All four were obtained and used, and `rt-app` was then found
unusable in this VM for a reason no install step fixes: a ~1.7ms
timer-delivery floor that exceeds the differences under study.

### `04_bare_metal/` — the environment this one could not be

How to build and qualify a physical measurement host: what makes a
machine eligible (RAPL needs Sandy Bridge or later; avoid 12th-gen
hybrid parts), what to ask a secondhand seller, which Fedora image,
what to disable, and — importantly — **what to run first**, which is the
existing matrices scored against predictions already written down and
dated, not the headline experiment.

Bare metal is what removes the three limits this VM imposed: the timer
floor that invalidated `rt-app`, the host moving vCPUs between
performance and efficiency cores mid-run, and the absence of any energy
counter. The method for the last of those is written up in advance in
`../benchmark/ENERGY_METHOD.md`.

## What's deliberately NOT in this folder

An earlier phase of this project explored building a custom Linux
kernel for a Raspberry Pi. That path was abandoned (no Pi hardware
available, and a memory-capped VM turned out to be a better-controlled
substitute for "resource-constrained device" anyway — see the paper
and delivery plan for why). Those Pi-specific scripts are excluded
here on purpose, not by oversight — loading them would risk suggesting
a path already correctly rejected.
