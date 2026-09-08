# Phase 2 Delivery Plan — Updated After Phase 1

This supersedes/supplements the original setup docs
(`sched_ext_contribution_context.md`, `sched_ext_embedded_research.md`,
`macos-sched-ext-setup/`) with concrete design decisions and
requirements that only became clear during Phase 1's Python research.
Load this alongside those files in Claude Code — it doesn't replace
them, it tells you what changed.

## 1. Design decisions to port directly (already validated in Python)

- **Windowing scheme**: rotating dual-buffer (current + previous),
  swap-and-clear on rotation. Validated extensively; do not
  reintroduce the exponential-decay approach (tried and rejected —
  see paper Section 2.3.1 for why).
- **Hash function**: use **FNV-1a**, not a cryptographic hash. Tested
  against the targeted-collision attack (paper Section 4.1.3) — both
  blake2b and FNV-1a showed identical vulnerability, so there's no
  security reason to pay a cryptographic hash's cost, and BPF favors
  the cheapest correct option for a hot-path hash anyway.
- **Mitigation, built in from the start, not bolted on later**:
  - Seed rotation on every window rotation.
  - Anomaly-triggered hard reset: if a query result exceeds ~3x an
    expected baseline, discard both buffers immediately rather than
    letting poisoned data carry into the next window. Validated to
    take attack damage from +200% to +0% (paper Section 4.1.4).
  - **Known gap**: the validated version used a known-true-value
    oracle for anomaly detection. A real implementation needs a
    rolling baseline estimate instead — this needs designing in
    Phase 2, not assumed to transfer directly.

## 2. Decisions still open — resolve these FIRST in Phase 2

- **Identity key**: PID vs. TGID vs. `comm` string. **Do not hardcode
  this up front.** Implement identity-key extraction in the BPF
  scheduler as a single swappable point (e.g. one `task_identity()`
  helper feeding the sketch/exact-counter increment calls, selectable
  via a build-time constant or config, not the choice threaded
  throughout the tracking logic). This is higher-stakes than a
  granularity tradeoff — `comm` is self-settable by a process, and we
  have a demonstrated targeted-collision attack (paper Section
  4.1.1) — which is exactly why it should be an evidence-based
  decision, not a guess made before Phase 2's real constraints exist.
  Resolve it using: (a) what's actually cheap/ergonomic to read in the
  `runnable` callback under real BPF verifier constraints, and (b) the
  real-kernel replication of the targeted-collision attack (Section 7)
  — run it against each candidate key before picking one. Current lean
  (PID/TGID over `comm`, for security) is a hypothesis this evidence
  should confirm or overturn, not a conclusion to bake in now.
- **Penalty vs. boost mechanism**: the Phase 1 scheduler-policy
  simulation (paper Section 4.2.1) found that a penalty-based design
  ("deprioritize high-frequency wakers") showed NO measurable
  difference between sketch and exact tracking, while a boost-based
  design (directly favoring the latency-sensitive task) was not
  properly tested (the one boost-style comparison policy turned out
  to be cheating with oracle knowledge, and collapsed to no advantage
  once fixed). **Test both mechanism shapes in the real BPF
  scheduler** rather than assuming penalty-based is right — the
  Python simulation didn't resolve this.

## 3. Baseline requirement — four tiers, not one

The original plan only had one baseline ("same scheduler, exact
counters instead of sketch"). This is insufficient on its own. Build
or obtain all four before any Phase 2 result is reported:

1. Stock EEVDF, unmodified.
2. `scx_simple`, unmodified (already studied in Phase 1).
3. This project's scheduler with exact counters (the original
   isolation-only plan) — isolates the sketch's specific effect.
4. An established production sched_ext scheduler — `scx_rusty` or
   `scx_lavd` — shows how this compares to what people actually run.

Report every result as a **relative multiplier against EEVDF**, not
just relative to this project's own variants (matches the convention
used in the "Towards Agentic OS" precedent cited in the paper).

## 4. Tooling needed on the Fedora VM [INSTALLED]

- `schbench` — primary metric source (P99/P999 wakeup latency).
  Directly matches this project's own tracked signal.
- `cyclictest` — secondary scheduling-latency measurement.
- `hackbench` — throughput/stress regression check (confirm the new
  scheduler doesn't hurt general throughput even if it helps the
  targeted metric).
- `rt-app` — for modeling the latency-sensitive workload via JSON
  config, rather than hand-rolling a synthetic task.

None of these were in the original VM setup scripts. All four are now
installed on the Lima VM:

- `cyclictest` and `hackbench` — both ship in Fedora's `realtime-tests`
  package (the rt-tests suite, renamed). `dnf install cyclictest
  hackbench` resolves to it; ~1.1MB. Note `dnf install rt-tests` matches
  something else entirely and pulls 422 packages — don't use that name.
- `schbench` — not packaged; built from source
  (`github.com/masoncl/schbench`, `~/schbench/schbench`). Verified
  producing P50/P99/P99.9 wakeup-latency output.
- `rt-app` — not packaged; built from source
  (`github.com/scheduler-tools/rt-app`, `~/rt-app/src/rt-app`).
  Build deps: `json-c-devel numactl-devel automake autoconf libtool`.

### Measurement hygiene, learned the hard way

`scxtop` (this repo's own `sched_ext` observability tool, `tools/scxtop`)
is genuinely useful for understanding *why* a scheduling number looks the
way it does — it produces Perfetto traces and has an MCP server for
querying them. It must **not** be running during any benchmark whose
number gets reported.

In a 5-second trace of `scx_cms`, `scxtop`'s own tokio worker threads
were the top CPU consumers (one at ~90% of a core), and its analyzer
flagged max-severity context-switch-rate bottlenecks on all four CPUs
that were entirely its own overhead — `scx_cms` did not appear in the top
15 processes by runtime. Stated precisely: what was observed is that the
tracer dominates the traced workload. How much it would distort a
specific `schbench` P99 figure has **not** been measured; if that number
is ever wanted, measure it by running the same benchmark bare and under
trace rather than estimating.

Practical split: `schbench`/`cyclictest`/`hackbench`/`rt-app` produce the
reported numbers, run with nothing else attached. `scxtop` is for
separate, disposable debugging runs. `scx_cms --stats N` costs a few
atomic increments and is cheap enough to leave on during a real
benchmark.

## 5. Before porting to BPF: build a regression test suite

Phase 1's Python code went through multiple silent-staleness bugs — a
fix applied in one file didn't propagate to another for several turns
of work, and was only caught by a dedicated audit pass (paper Section
4.1's audit note, and 4.1.5). Before porting the validated logic into
BPF, add a small pytest suite asserting known-good values for the
Python prototype at a fixed seed. This protects the *next* refactor
(the BPF port itself, which will touch every file) from the same
silent-drift failure mode. This is checklist item 20/21 in the paper
draft — do this before, not after, starting the BPF work.

## 6. Sanity checks before running any VM setup script [SUPERSEDED]

The VM is now provisioned via Lima (see step 3 above), which pins its own
image digest and removes most of this section's risk. Kept for the
general lesson, which held: **both** pinned assumptions were stale.

- Fedora was pinned at 42; current is 44. Beyond the version, the image
  filename convention had also changed
  (`Fedora-Server-42-1.1.aarch64.qcow2` →
  `Fedora-Cloud-Base-Generic-44-1.7.aarch64.qcow2`), so bumping the
  number alone would still have 404'd. Check the actual mirror directory
  listing, not just the release number.
- `CONFIG_SCHED_CLASS_EXT` confirmed still enabled by default:
  `/sys/kernel/sched_ext` is present on Fedora 44, kernel 6.19.
- Also stale, and worth the same suspicion: the build system. The
  original `02_fedora_vm_setup.sh` used `meson setup`/`meson compile`
  and expected binaries under `build/scheds/c/`. There is no `meson.build`
  anywhere in this repo any more — it is a pure Cargo workspace (see
  `CARGO_BUILD.md`). The script has been rewritten accordingly.

## 7. What Phase 2 must additionally test, beyond the original scope

- A real-kernel replication of the targeted-collision attack (paper
  Section 4.1.1) — not just the benign-case comparison. If the
  vulnerability doesn't translate into an actual exploitable
  scheduling-decision manipulation, that's an important, different
  finding from "the tracking is inaccurate under attack."
- Whether the mitigation (seed rotation + hard reset) still works
  once anomaly detection uses a real rolling baseline instead of the
  oracle used in Python validation.

## Suggested order of operations

1. [x] Build the pytest regression suite for the validated Python logic
   (Section 5 above) — cheap insurance before the big refactor. DONE —
   `02_validated_python_code/test_sketch_lib.py`, 27 tests, passing
   both locally and in the project's Docker environment.
2. [x] Build the identity-key extraction as a swappable abstraction
   (Section 2) — do NOT resolve PID vs. TGID vs. `comm` now; wire the
   scheduler so any of the three can be dropped in without touching
   the tracking logic. DONE — `scheds/experimental/scx_cms/`,
   `src/bpf/identity.bpf.c`, selectable at run time via
   `--identity-key pid|tgid|comm`. The choice is a `const volatile` set
   from userspace before load, so switching candidates needs no rebuild.
   **The decision itself remains deliberately unmade**, pending step 5.

   Note a stale assumption corrected here: this plan and the paper both
   describe forking `scx_simple.bpf.c` from this repo. That file no
   longer exists here — the C schedulers were moved out to
   `sched-ext/scx-c-examples`, and everything remaining is Rust
   userspace + BPF. `scx_cms` is therefore a port of `scx_simple`'s
   policy (recovered from this repo's own git history at `d1810e62~1`)
   into the current Rust+BPF crate layout, not a fork of a live file.
3. [x] Set up the Fedora VM with the additional tooling (Section 4).
   DONE, with two deviations from `03_vm_setup/`:
   - **Lima, not UTM.** UTM's VM creation is GUI-driven, its console
     rejects paste, and it required manual sudo/SSH setup. Lima is
     CLI-only, ships a digest-pinned `fedora-44` template, injects SSH
     keys and passwordless sudo via cloud-init, and mounts the host
     repo directly into the guest (no rsync). `limactl shell scx-fedora`
     is the entry point; the instance config lives in
     `~/.lima/scx-fedora/lima.yaml` (the repo mount is marked writable
     there, which Cargo needs for `Cargo.lock`).
   - **Fedora 44, not 42**, and the image filename convention changed
     too (`Fedora-Server-42-1.1.*` → `Fedora-Cloud-Base-Generic-44-1.7.*`),
     so a naive version bump would have 404'd. Kernel 6.19 with
     `/sys/kernel/sched_ext` present, confirmed.
4. [x] Build the exact-counter isolation-baseline scheduler first
   (Section 3, tier 3) — closest to what's already validated in Python.
   DONE — `scx_cms/src/bpf/tracker.bpf.c` (rotating dual-buffer exact
   counter) and `mechanism.bpf.c` (`--mechanism none|penalty|boost`).
   Verified loading and running on the real kernel; window rotation,
   lazy roll-forward and buffer discard confirmed against live map
   dumps. See Section 8 below for implementation departures.
5. [ ] Port the sketch-based version, testing both penalty and boost
   mechanism shapes (Section 2), AND all three identity-key candidates
   from step 2 — including a real-kernel replication of the
   targeted-collision attack (Section 7) per key candidate. Use these
   results to make the identity-key decision (Section 2) as a
   documented, evidence-based choice at this point, not before.
6. [ ] Obtain/build the remaining three baseline tiers.
7. [ ] Run the real targeted-collision and mitigation tests on actual
   hardware/kernel (Section 7) before trusting the Python-validated
   mitigation design.

## 8. Implementation departures from the Python prototype (step 4)

Both forced by what BPF can do cheaply. Recorded here because they are
semantic decisions, not incidental coding details.

- **Rotation is lazy and per-entry, not a buffer swap-and-clear.**
  Clearing a hash map from a BPF program means iterating and deleting
  every entry; nothing else in this repo does that. Instead one LRU hash
  map holds `{epoch, cur, prev}` per identity, a BPF timer bumps a global
  epoch every window, and an entry is rolled forward on next access
  (one window missed → `cur` becomes `prev`; two or more → both
  discarded). Observable semantics are identical to the validated
  scheme: a query sums current + previous, older data is gone.

  A simpler single-counter epoch scheme was considered and rejected: it
  would have silently dropped the "previous window" term, changing the
  ground truth the Phase 1 results are defined against.

  **Trap for anyone reading `cms_counts` from userspace** (e.g. the
  upcoming exact-vs-sketch comparison): stale entries keep their old
  epoch and old counts until touched again, so a raw read reports a
  window that closed long ago. Apply the roll logic against the live
  `cms_epoch` — the true value for a stale entry is usually zero. This
  is the same silent-staleness failure mode that corrupted the Section
  4.1 figures in Phase 1, so it is called out in the code as well.

- **The map is an LRU hash.** The Python model needed no eviction
  because it rebuilt buffers wholesale. Here, churned-away identities
  would occupy slots forever; LRU reclaims exactly those. Capacity is
  `CMS_MAX_TRACKED` (16384).

- **`boost` is a first attempt, not a port.** There is no validated
  boost design to port — paper Section 4.2.1 records that Phase 1's
  boost-style policy was relying on oracle knowledge of which task was
  latency-sensitive and collapsed to no advantage once corrected. With
  only a wakeup count available, the implemented stand-in favours tasks
  below a count threshold. Whether that proxy is useful at all is an
  open question for step 5; it must not be reported as inheriting Phase
  1's validation.
