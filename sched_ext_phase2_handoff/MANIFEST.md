# START HERE — Phase 2 Handoff Manifest

Point Claude Code at this folder. This file tells it what everything
else is and what order to read it in. Nothing outside this folder is
needed; nothing inside it is obsolete filler — every file here earned
its place through the Phase 1 research process.

## Suggested first prompt to Claude Code

> "Read 00_orientation/paper_sections_2_to_6_draft.md in full, then
> 01_delivery_plan/phase2_delivery_plan_update.md. Summarize the
> current state and the next concrete action per the delivery plan's
> 'suggested order of operations' section, before writing any code."

This forces a comprehension check before any action — cheap insurance
against acting on stale or partial assumptions, which caused real
problems earlier in this project (see the paper's audit sections).

**Not sure Claude Code is actually set up and pointed at this folder
yet?** See `00_orientation/SETUP_CLAUDE_CODE.md` first — installation,
VS Code extension, and (the step that's easy to miss) how to actually
open this specific folder so Claude Code can see everything in it.

## Folder-by-folder guide

### `00_orientation/` — read first, in this order

1. `SETUP_CLAUDE_CODE.md` — how to actually get Claude Code installed
   and pointed at THIS folder (the one thing this bundle was missing
   until it was pointed out). Skip if Claude Code is already open on
   this folder.
2. `sched_ext_contribution_context.md` — why this project exists at
   all: general sched_ext contribution background, dev environment
   basics.
3. `sched_ext_embedded_research.md` — why resource-constrained/mobile
   scheduling specifically: LPC 2026 citations, the real gaps this
   targets, why they're real (not assumed).
4. `paper_sections_2_to_6_draft.md` — **the primary reference for
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

**Before porting to BPF**: build a small pytest regression suite
against this code at a fixed seed first (see delivery plan Section 5).
This code has already survived multiple rounds of silent-drift bugs
during Phase 1 — protect the upcoming BPF port from the same failure
mode rather than relying on manual re-verification again.

### `03_vm_setup/` — kernel/BPF development environment

Read `README.md` inside this folder first. Order: `01_macos_host_setup.sh`
(run on your Mac) → manual UTM VM creation (one-time, GUI, documented
in the README) → `02_fedora_vm_setup.sh` (run inside the VM) →
`03_memory_constrain.sh` (per-experiment, for the memory-capped
"resource-constrained device" simulation).

**Before running**: two things the delivery plan flags that these
scripts don't yet handle —
1. The Fedora release pinned in `01_macos_host_setup.sh` will go
   stale; check https://fedoraproject.org/server/download for the
   current release first.
2. These scripts install C/BPF build tools only. Add `schbench`,
   `cyclictest`, `hackbench`, and `rt-app` (see delivery plan Section
   4) before running any real benchmark — they're required for the
   four-tier baseline comparison and aren't installed by anything
   here yet.

## What's deliberately NOT in this folder

An earlier phase of this project explored building a custom Linux
kernel for a Raspberry Pi. That path was abandoned (no Pi hardware
available, and a memory-capped VM turned out to be a better-controlled
substitute for "resource-constrained device" anyway — see the paper
and delivery plan for why). Those Pi-specific scripts are excluded
here on purpose, not by oversight — loading them would risk suggesting
a path already correctly rejected.
