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
5. [~] IN PROGRESS. The sketch is ported and runs on a real kernel;
   `--tracker exact|sketch` selects the counting method, and both are fed
   by one window clock so a comparison cannot be confounded by differing
   window boundaries. `--compare` feeds BOTH counters every wakeup and
   reports their divergence, which is the kernel-side equivalent of Phase
   1 feeding one event stream to both structures -- without it, sketch
   error would have to be compared across two runs with different
   workloads and the two effects could not be separated.

   Mechanisms were also split one-per-file under `mechanisms/`, with a
   single registration point (`index.h`) and a build-time check that
   fails on a strategy file nobody listed. See Section 10.

   Real-kernel results so far are in Section 9. Still outstanding for
   this step: the targeted-collision replication per identity key, and
   the identity-key decision that depends on it. Also untested: both
   mechanism shapes under a workload where the mechanism actually
   reaches most dispatches (see Section 9's reach finding), and the
   other two identity-key candidates.

   Original wording of this step, for reference: port the sketch-based
   version, testing both penalty and boost
   mechanism shapes (Section 2), AND all three identity-key candidates
   from step 2 — including a real-kernel replication of the
   targeted-collision attack (Section 7) per key candidate. Use these
   results to make the identity-key decision (Section 2) as a
   documented, evidence-based choice at this point, not before.
6. [ ] Obtain/build the remaining three baseline tiers.
7. [ ] Run the real targeted-collision and mitigation tests on actual
   hardware/kernel (Section 7) before trusting the Python-validated
   mitigation design.

## 9. Real-kernel findings so far (step 5, partial)

Three results from the first kernel-side measurements. None is a
scheduling-quality outcome -- Section 4.2 of the paper is still unrun --
but all three bear directly on how those outcomes must be measured.

### 9.1 The mechanism reaches almost nothing on an idle machine

`select_cpu` dispatches straight to the local queue whenever it finds an
idle CPU, bypassing `enqueue` -- which is where a mechanism adjusts
vtime -- entirely. The share of dispatches a mechanism can influence at
all is therefore load-dependent, and on an unloaded system it is
approximately zero:

| condition | local | global | mechanism reach |
|-----------|------:|-------:|----------------:|
| idle VM   | 6,976 |     54 | **0.8%** |
| `hackbench -l 2000 -g 12` | 7,381 | 44,927 | **85.9%** |

This matters more than it first appears. **A null result from an idle or
lightly loaded system is uninterpretable**: "the sketch made no
difference to scheduling" and "the mechanism never ran" produce identical
output. Every reported result must state its reach alongside it, and the
scheduler now prints it on every stats line for that reason.

It is also a candidate explanation for Phase 1's own null result (paper
Section 4.2.1), where penalty-based tracking showed no sketch-vs-exact
difference and the simulation could not say why. If the analogous
condition held there, the mechanism may simply not have been exercised.
That is now a testable hypothesis rather than an open shrug.

### 9.2 Sketch error is load-dependent, and zero on an idle system

Measured with `--compare`, so both counters see one identical event
stream:

| condition | exact mean | sketch mean | overestimate | max overshoot |
|-----------|-----------:|------------:|-------------:|--------------:|
| idle VM   | 1,134 | 1,134 | **+0.0%** | 0 |
| `hackbench` | 153.0 | 169.8 | **+11.0%** | 836 |

The idle figure is not a finding about the sketch; an idle VM has on the
order of 50-100 distinct pids, and 256 columns across 4 rows with a
minimum taken across them simply does not collide at that scale. Phase
1's +31.9% came from ~5,000 churn identities per window.

This was verified rather than assumed: at `--sketch-width 4
--sketch-depth 1`, where collisions are unavoidable, error appears
immediately (+7.2%, max overshoot 1,754). A sketch silently falling
through to the exact path would have shown zero there too.

**The +11.0% is not comparable to Phase 1's +31.9%** and must not be
reported as though it were. Different churn level, and a different
statistic: this is a ratio of sums across every queried identity, whereas
Phase 1's headline was the error on one tracked latency-sensitive task.
Both are meaningful; conflating them is not.

### 9.3 The never-undercount guarantee holds on real kernel data

Count-Min's one formal guarantee is that it never undercounts. Checked
continuously in compare mode against a live event stream: **zero
violations in 52,316 samples**. This is the kernel-side counterpart of
the Python invariant check in paper Section 4.1.2, and it is a real
validation of the port rather than a formality -- had it failed, every
accuracy figure above would be void.

## 9.4 The targeted-collision attack replicates on a real kernel

Harness: `attack/collision_attack.py` in this repo. Victim and attackers
are real processes; both counts come from the kernel's own query via a
probe map rather than from a userspace reimplementation of the hash,
because a divergent reimplementation is how Phase 1 once produced a false
"this hash is immune" result (paper 4.1.3).

Sketch at 256x4, single run per condition, victim waking at 20/s:

| identity | seeds | attackers | inflation of victim's estimate |
|----------|-------|-----------|-------------------------------:|
| `comm` | known | 64 @ 200/s | **+8,824%** |
| `comm` | unknown | 64 @ 200/s | **+0.0%** |
| `comm` | unknown | 256 @ 1000/s | **+5,450%** |
| `pid` | known | 64 @ 200/s | **+0.0%** (attack unavailable) |
| `pid` | unknown | 256 @ 1000/s | **+1,439%** |

**The attack transfers.** Phase 1's finding was not an artifact of
simulation: an adversary who knows the seeds and can choose its own
identity inflates a victim's estimated wakeup count by orders of
magnitude, with modest resources.

**Magnitude is a function of attacker volume, not a property of the
sketch.** The +8,824% here is not comparable to Phase 1's +440%; it
reflects the attacker-to-victim volume ratio chosen for this run. The
observed estimate matched what the attacker volume predicts almost
exactly (16 attackers per row x 200 wakes/s x 2s window ~ 6,400 against
an observed 6,282 in an earlier run), which is the check that this is
mechanistically real rather than an artifact.

**Seed knowledge buys efficiency, not access.** At identical volume,
knowing the seeds is the difference between +8,824% and nothing at all.
But volume alone still does severe damage without any seed knowledge
(+5,450%). An early reading of this as "blind attacks are harmless" was
wrong and was corrected by testing at higher volume -- worth recording,
because the first blind result looked like a reassuring finding.

### A correction to the paper's threat model

Paper Section 5 states the attack requires "only knowledge of the hash
function and per-row seeds (not privileged system access)". On a real
kernel that understates the precondition: the seeds are generated by
`bpf_get_prandom_u32()` and live in a BPF map, so **reading them requires
privilege**. An unprivileged co-located process cannot mount the targeted
attack at all. It can still flood.

This does not make the finding less serious, but it does change who the
adversary is: an insider, a leak, or a system with predictable seeds --
not any co-tenant process.

### This decides the identity key

`comm` is settable by the task itself, so an attacker can construct an
identity that lands in a victim's cells. A pid or tgid is assigned by the
kernel, so no amount of seed knowledge lets an attacker steer into a
victim -- the targeted attack is structurally unavailable, which is why
that row reads +0.0% rather than "a smaller number".

That is a qualitative difference, not a tuning difference, and it
confirms the lean recorded in Section 2 with evidence rather than
assumption: **use PID or TGID, not `comm`.**

Caveats, stated rather than buried:

- Single run per condition. No variance or repetition yet, so the
  `pid`-vs-`comm` gap under blind flooding (+1,439% vs +5,450%) should
  NOT be read as a real effect -- one measurement each, and no mechanism
  established for why they would differ under an untargeted attack.
- TGID was not tested. The structural argument applies to it equally
  (kernel-assigned), but that is reasoning, not measurement.
- Identity choice mitigates *targeting*, not *flooding*. Both keys took
  heavy damage from blind volume, so this decision does not make the
  sketch safe; it removes the cheapest and most precise attack.

## 9.5 Does the corrupted signal actually manipulate scheduling? NO (not on this scale)

The attack corrupts the tracked count (9.4). Whether that corrupts a
scheduling *decision* is a separate claim, and the answer here, across
every regime tested, is that no manipulation is detectable -- with a
structural reason why it is hard, and explicit conditions under which it
might still occur.

### Method

Harness: `attack/schbench_attack.py`. The victim is `schbench` in
fixed-rps mode, the instrument the delivery plan specifies (Section 3.3)
because it measures scheduling latency directly. Its threads all share
the comm "schbench", so under `--identity-key comm` the victim is one
identity the attacker collides with. Attacker load is held identical
across three conditions; only the counter the mechanism reads changes:

| condition | isolates |
|-----------|----------|
| sketch + penalty | mechanism reads the corruptible count |
| exact + penalty | mechanism reads the true count, same load |
| sketch + none | count corrupted, nothing acts on it |

Manipulation would show as sketch+penalty degrading the victim more than
exact+penalty at matched load. Metric is `schbench` request-latency p99
(~1000 samples, stable); wakeup-latency percentiles are unusable in rps
mode (~17 samples, tail pinned to a ~900ms histogram-ceiling artifact).

### Result: no effect, confirmed across configurations

| config | sketch+penalty p99 | exact+penalty p99 | gap | verdict |
|--------|-------------------:|------------------:|----:|---------|
| gentle penalty, high-rate victim, n=5 | 25,184us | 24,544us | +2.6% | within noise |
| steep penalty, low-rate victim, n=5 | 14,896us | 11,056us | +34.7% | within noise, but suggestive |
| steep penalty, low-rate victim, n=15 | 15,184us | 15,440us | -1.7% | no effect |

The n=5 steep-penalty run looked like an effect: +34.7% in the predicted
direction, and unlike an earlier Python-harness attempt the direction did
not flip between runs. At n=15 it collapsed to -1.7%. **This is the
project's own recurring lesson, caught again: a suggestive small-sample
result in the hoped-for direction must be confirmed at higher N before it
is believed.** It was nearly written up as a positive finding.

### Why manipulation is hard here: inflation and load are coupled

A cell's inflation equals the number of colliding wakeups landing in it
per window -- which is exactly the load those attackers add. Measured
directly:

| attacker load | victim inflation | victim latency |
|---------------|-----------------:|----------------|
| 64 @ 200/s | ~89x (9.4) | saturated (~900ms, histogram ceiling) |
| 16 @ 20/s, high-rate victim | 1.8x | measurable (~24ms p99) |
| 16 @ 20/s, low-rate victim | 3.0x | measurable |

Large corruption requires heavy colliding load, and heavy load saturates
the victim's latency on its own -- independent of any mechanism -- which
drowns any manipulation effect. At load light enough to measure latency
cleanly, the achievable corruption is only 2-3x, a count difference too
small to move scheduling even under a steep penalty. The corruption-heavy
and latency-measurable regimes do not overlap on this 4-CPU machine.

A lower-rate victim raises the inflation *ratio* (a task that mostly
sleeps has a tiny baseline count), which is why 3.0x beat 1.8x -- but not
enough to escape the coupling.

### What this does and does not establish

Establishes: on this hardware and configuration, an attacker who corrupts
the wakeup signal does not thereby measurably worsen the victim's
scheduling, because the corrupting regime is also the self-saturating
regime.

Does NOT establish that manipulation is impossible. Untested levers that
could change it, each a candidate for future work:

- **More CPUs.** On a large machine the attacker's raw load is absorbed
  across many cores while the collisions still land, potentially
  separating the two regimes. This 4-CPU VM is the worst case for the
  attacker's load being absorbed and may be the best case for the
  defender.
- **A smaller sketch.** Fewer columns means more collisions per unit
  load, raising inflation-per-load -- the same reason a small sketch is
  less accurate makes it easier to poison cheaply.
- **A steeper or uncapped mechanism.** The vulnerability's expression
  depends on how hard the scheduler leans on the count. The values here
  cap any adjustment at one region of vtime; a mechanism that weights the
  count more aggressively would amplify a given corruption further.

The security claim the paper can currently support is therefore precise:
the *signal* is corruptible (demonstrated, 9.4), but a corrupted signal
translating into a corrupted *scheduling decision* is not demonstrated at
this scale, and is structurally resisted by the coupling between
corruption and load.


## 10. Leaky edges in the mechanism abstraction

Recorded because each is a place where a future change could produce a
quietly wrong experiment rather than an obvious failure.

- **Most dispatches bypass it entirely** on an idle system (Section 9.1).
  Deliberately not "fixed": routing everything through `enqueue` would
  distort the baseline scheduler to make the mechanism fire, which is
  worse than reporting reach honestly. The evaluation workload must
  instead be one that actually saturates CPUs.
- **`--fifo` silently disabled mechanisms.** FIFO takes a different
  branch in `enqueue` and never consults them. Now warns at startup;
  previously it would have produced a full run's worth of data from a
  scheduler that was never applying the requested mechanism.
- **The accumulated-budget clamp is the caller's job.** A boost that
  escaped it could hand a task unbounded credit; the mechanism documents
  the requirement but cannot enforce it. There is exactly one caller
  today.
- **A mechanism can only shift queue position.** It cannot extend a
  slice or preempt, which bounds what strategies are expressible at all.

## 11. Implementation departures from the Python prototype

Forced by what BPF can do cheaply. Recorded because they are semantic
decisions, not incidental coding details.

### Sketch (step 5)

- **The table is sized at load time to exactly `2 * width * depth`
  cells**, not to a compiled-in maximum. The sketch's entire claim is a
  small fixed footprint; an over-allocated table would make the memory it
  occupies disagree with the memory it reports, which would quietly
  undermine the headline number. At the Phase 1 reference parameters this
  is 8,192 bytes, matching that work exactly.
- **Identities are hashed as u64, not as strings.** The prototype hashed
  identity strings; here an identity is already a u64 (a pid, tgid, or
  hashed comm), so the same FNV-1a construction runs over its eight
  bytes. Seed mixing and table structure are unchanged, so the collision
  behaviour Section 4.1.3 found to be structural rather than
  hash-specific is preserved.
- **Each buffer carries its own seeds**, as in the prototype. This is
  what makes seed rotation coherent: a recycled buffer can take fresh
  seeds while the surviving buffer is still read with the seeds its
  counts were written under. The seeds are readable from userspace, which
  the collision replication needs in order to play the adversary.
- **Rotation zeroes the discarded buffer for real**, unlike the exact
  tracker's lazy per-entry roll. There is nowhere to hang a per-entry
  epoch without adding a field to every cell, which would inflate the
  very footprint under measurement.

### Exact counter (step 4)

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
