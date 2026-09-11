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

**[CONFIRMED, pre-Phase-6 sanity check]** All four are buildable and load
on the current VM (Fedora 44, kernel 6.19); worth checking before Phase 6
itself, since a build failure discovered mid-benchmark is far more
disruptive than one discovered now:

- **EEVDF** — no setup, it's the state with no `sched_ext` scheduler
  loaded.
- **`scx_simple`** — no longer in this repo (moved to
  `sched-ext/scx-c-examples`, per Section 1's earlier finding). Cloned
  separately and built with `make scx_simple` (`~/scx-c-examples`).
  **That repo's own `meson.build` deliberately errors out** ("Meson
  builds are deprecated... switch to `cargo build`... `make` for C
  schedulers") — the opposite migration direction from this repo, worth
  knowing before assuming meson applies there just because it's a C
  scheduler collection. Attaches and detaches cleanly.
- **`scx_cms --tracker exact --mechanism none`** — already built and
  exercised throughout Section 9.
- **`scx_rusty`** and **`scx_lavd`** — both build via `cargo build -p
  <name>` in this repo, no extra setup. Both attach and detach cleanly.

One environment note this surfaced: `meson`/`ninja-build` were
deliberately removed from this repo's own VM setup (Section 6) since the
main `scx` tree is pure Cargo now — correct for that repo, but
`scx-c-examples` still needs `make` (and briefly, meson, before its
`meson.build` redirects you to `make`). Installed on the VM now
(`sudo dnf install meson ninja-build`, though only `make` ended up
mattering) for whoever picks up Phase 6 next.

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
5. [x] DONE, superseding the "still outstanding" note this item carried
   until now. The sketch is ported and runs on a real kernel;
   `--tracker exact|sketch` selects the counting method, and both are fed
   by one window clock so a comparison cannot be confounded by differing
   window boundaries. `--compare` feeds BOTH counters every wakeup and
   reports their divergence, which is the kernel-side equivalent of Phase
   1 feeding one event stream to both structures.

   Mechanisms were split one-per-file under `mechanisms/`, with a single
   registration point (`index.h`) and a build-time check that fails on a
   strategy file nobody listed. See Section 10.

   The targeted-collision replication per identity key (Section 9.4) and
   the identity-key decision that depended on it (PID/TGID over `comm`)
   are both done. So is the scheduling-manipulation question (9.5) and
   the seed-rotation mitigation test (9.6).

   [ ] TGID specifically was reasoned about (kernel-assigned, same
   argument as PID) but not measured directly — closing this now.
   [ ] `boost`'s reach and behavior under real load untested — closing
   this now.

   Original wording of this step, for reference: port the sketch-based
   version, testing both penalty and boost mechanism shapes (Section 2),
   AND all three identity-key candidates from step 2 — including a
   real-kernel replication of the targeted-collision attack (Section 7)
   per key candidate. Use these results to make the identity-key decision
   (Section 2) as a documented, evidence-based choice at this point, not
   before.
6. [~] IN PROGRESS. Round 1 done — see Section 12. All three obtained
   and confirmed working (`scx_simple` from `scx-c-examples` via `make`,
   `scx_cms --tracker exact --mechanism none`, `scx_lavd`), with a real
   first comparison against EEVDF on `schbench`. [ ] `cyclictest`,
   `hackbench`, and a mixed-workload benchmark (needed to test the
   `scx_lavd` finding's leading hypothesis) remain undone.
7. [x] DONE. The real targeted-collision attack (9.4), the
   scheduling-manipulation question (9.5), and the seed-rotation
   mitigation test (9.6) are all run on actual hardware/kernel (Fedora
   44, 6.19, via the Lima VM). [ ] The anomaly-triggered hard reset is
   the one piece of the Python-validated mitigation design still
   untested here — it needs a real rolling-baseline detector before it
   can be tested at all, since the Python version used a known-true-value
   oracle. Deliberately deferred as its own piece of work, not folded
   into this pass.

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

**Update: all three named levers have since been tested** (n=5 each, on
the fixed build -- confirmed via the scheduler binary's build timestamp
rather than assumed), and all remain null:

| lever | config | gap vs. exact+penalty |
|---|---|---|
| smaller sketch | width=32 (vs. 256) | -21.5% (wrong direction) |
| more CPUs | 8 (vs. 4) | +3.0% |
| combined | width=32, 8 CPUs, effectively uncapped adjustment | +11.4% |

Every gap was well within run-to-run noise. This substantially
strengthens the null finding rather than overturning it -- it now holds
across sketch width, CPU count, mechanism steepness, and their
combination, not just the original single configuration. Manipulation is
still not *proven* impossible (no finite set of configurations proves a
negative), but the specific candidate explanations for why the original
result might have been an artifact of one narrow setup have each been
tested directly and found not to change it.

The security claim the paper can currently support is therefore precise:
the *signal* is corruptible (demonstrated, 9.4), but a corrupted signal
translating into a corrupted *scheduling decision* is not demonstrated at
this scale, and is structurally resisted by the coupling between
corruption and load.


## 9.6 Seed rotation: effective at moderate volume, not at saturating volume

Whether `--seed-rotation` actually mitigates the collision attack on a
real kernel, per Phase 1's open question (delivery plan Section 1).
Harness: `attack/seed_rotation_attack.py`. Attackers replay identities
computed once, against the seeds live at attack start, sustained across
several window rotations -- Phase 1's "replay stale keys" variant, not
the "fire once and go silent" one. Samples are taken by polling
`cms_epoch` until it advances, not by sleeping a fixed duration; an
earlier version slept `window_ms` between samples and drifted out of
phase with the kernel's actual timer, producing a result (0%, 0%, then
rising to 787%) that looked like a finding and was measuring drift
instead. Caught by adding epoch logging to a diagnostic run before
trusting the number.

Two attacker-volume regimes, single run each:

| load | rotation OFF | rotation ON |
|------|-------------:|------------:|
| light: 8 @ 20/s (160 events/s) | 9.5%, 181.8%, 17.8%, 181.4% | **0.0%, 0.0%, 0.0%, 4.8%** |
| heavy: 64 @ 200/s (12,800 events/s) | 1,219-14,084% | 791-2,011% (~6x lower) |

**At light volume, rotation is close to a full mitigation.** At heavy
volume it only reduces damage, by roughly 6x, and does not clear it.

**Why, mechanistically, and it is not the same story as Phase 1's.**
Phase 1 characterized incomplete clearance as one window's carry-over lag
through the "previous" buffer. That still applies here, but at the heavy
setting a second, independent effect dominates: 12,800 events/s into a
256-column table is ~100 events per column per row per 2s window from
pure load, before any targeting is considered. Sustained volume at that
scale saturates the table regardless of whether an identity still hashes
to the intended column, which is a structural limit rotation cannot
address -- rotation invalidates *targeting*, not *volume*. This is
consistent with 9.4's separate finding that untargeted flooding alone
(`comm`/blind/256@1000/s) produced +5,450% with no seed knowledge at all.

**Caveats.** Single run per configuration, no repetition -- given how
often a single-run result has misled in this line of work (9.5's
+34.7%-that-became--1.7% is the most recent), treat the exact percentages
as illustrative, not precise, though the qualitative light-vs-heavy
split is large enough (near-zero vs. four figures) that it is unlikely to
be noise. Only the sustained-replay attack variant was tested, not
Phase 1's one-shot-then-silent variant. The light/heavy boundary was not
swept, so "how much load before rotation stops fully working" is known
only as "between 160 and 12,800 events/s," not pinned down.

## 9.7 Attempting a Phase-1-matched accuracy number surfaces a real gap

Earlier real-kernel accuracy figures (+11.0% under `hackbench`) were
flagged as not comparable to Phase 1's +31.9%, being both a different
churn level and a different statistic (aggregate ratio vs. one tracked
identity's error). This attempts an actual match: ~5,000 real churn
processes per window, each firing 1-20 wakeups, plus one persistent
tracked victim, measured via the probe -- Phase 1's exact setup, ported
to real processes.

Harness: `attack/phase1_matched_accuracy.py`.

| window length | mean overestimate (matched statistic) |
|---|---|
| 5s (Phase 1's implicit assumption: churn arrives and is measured near-instantly) | +277.3% |
| 15s (3x longer, to let real processes settle) | +98.9% |
| Phase 1 (Python, instantaneous synthetic events) | +31.9% |

**This did not converge, and that is itself the finding.** Tripling the
window brought the error down substantially, confirming that OS
scheduling contention among 5,000 concurrent short-lived processes on 4
real CPUs is a genuine contributing factor -- ruled out as a *fork-cost*
issue directly (5,000 raw `fork()`s measured at 0.33s wall time, not the
bottleneck). But it did not converge to Phase 1's figure even at 15s, so
contention is not the whole explanation either.

**Read this as: Phase 1's synthetic simulation likely understated
real-world sketch error, not that the real-kernel measurement is broken.**
A synthetic event has zero execution cost and arrives at a precisely
controlled instant; a real process competing for 4 real CPUs among
thousands of siblings does not, and that difference is structural, not a
bug to be tuned away. Chasing further convergence by continuing to extend
the window was deliberately not pursued -- past this point it would mean
tuning the experiment toward Phase 1's number rather than learning
something new, which is exactly the kind of iteration-toward-a-flattering-
result this project's methodology exists to avoid.

**Caveat:** two data points, one run each, no repetition. The direction
(real execution shows more error than synthetic simulation, and settles
toward but does not reach the synthetic figure as contention eases) is
plausible and mechanistically explained, but the specific magnitudes
should not be treated as precise.

## 9.8 A real concurrency bug found in the counters, partially fixed

Found while checking `--mechanism boost`'s behavior under `hackbench`
(originally a quick loose-end check, not a planned investigation): the
never-undercount guarantee -- Count-Min Sketch's one formal property,
verified clean at 52,316 samples earlier in this project -- was being
violated 633,000 times in a few seconds. That rate is far too high to be
a real algorithmic defect; it meant the port had a concurrency bug.

**Three distinct bugs found and fixed**, via direct diagnostic capture
(latching the first violation's raw internal state) after two wrong
guesses based on reasoning alone:

1. `(*cell)++` and `c->cur++` were plain non-atomic read-modify-writes.
   Under `--identity-key comm`, many threads sharing one identity (e.g.
   hackbench's workers) hammer the same map cell from multiple CPUs at
   once -- a textbook lost update. Fixed with `__sync_fetch_and_add`.
2. The "identity not seen before" path used `BPF_ANY`, which
   unconditionally overwrites. Two CPUs racing to create the same new
   identity's entry could both see the lookup miss; whichever insert
   lands second silently discards the first's `cur=1`. Fixed with
   `BPF_NOEXIST` plus a fallback to atomic increment on `EEXIST`.

Two wrong turns, kept in the code comments because they looked plausible
before being tested: an epoch consistency check, then a proper seqlock,
both aimed at a hypothesized read-side rotation race. Neither moved the
violation rate. Direct instrumentation showed the actual captured
violation happened at `cms_epoch=0` -- before any rotation had ever
occurred -- ruling out rotation timing entirely for the case that was
actually caught.

**Net effect: ~600k violations down to ~210k** on the same stress test.

**[CORRECTED] What remains is broader than first characterized here.**
Writing the regression suite (Section 9.9) immediately found it: with
each individual increment now atomic, `cms_track()`'s sequence of
incrementing exact, incrementing sketch, then reading both for
`--compare` is not atomic *as a unit*. A concurrent reader on another CPU
can still observe one structure mid-update relative to the other. This
was first attributed narrowly to `cms_roll()`'s three-field update
(`prev = cur; cur = 0; epoch = new`) tearing once real rotations start --
that race is real and still present, but it turns out to be one
manifestation of the broader issue, not the whole story: confirmed to
scale directly with concurrency (0/9/110 violations at 2/8/32 workers
sharing one identity) on a window long enough that no rotation ever
fired, which rules `cms_roll()` out specifically for that case.

Both are the same underlying problem and need the same fix: some form of
per-identity mutual exclusion, most naturally a `bpf_spin_lock`. **Still
deliberately deferred**, for the same reason as before -- no existing
`bpf_spin_lock` usage in this codebase to build from, and the risk of an
unbounded chase with no working reference judged too high. Both are now
tracked as explicit expected-failures in the regression suite rather than
left as a comment only, so the gap stays visible rather than being
forgotten a second time.

**Practical impact is still bounded, worth restating precisely now that
the scope is better understood.** It requires genuine concurrent access
to the *same* identity to trigger. Most measurements in this project's
attack harnesses do not sustain that at high intensity — each attacker is
typically its own process with its own identity, not many threads
hammering one shared identity the way `--identity-key comm` on a real
multi-threaded workload (hackbench, or `schbench`'s worker pool) can.

**A real build-system gap found while verifying fixes.** `build.rs` only
watched `src/bpf/main.bpf.c` directly, not the files it `#include`s.
Editing `tracker.bpf.c` without touching `main.bpf.c` produced a silent
0.12s no-op build reporting success without recompiling anything --
caught by the timing looking wrong, not by the tool telling us. Fixed by
watching the whole `src/bpf` tree. `scx_flow` and `scx_cidland` have the
identical gap; not specific to this scheduler.

**What this means for every earlier `--compare`-based number in this
project** (the collision attack in 9.4, seed rotation in 9.6, the
scheduling-manipulation measurements): all of them ran under lighter
concurrent-same-identity contention than this hackbench test deliberately
maximizes (many attacker *processes* with distinct or matched identities,
not hundreds of threads hammering one shared identity across every CPU
simultaneously). The qualitative findings are unlikely to flip from a bug
whose signature is occasional off-by-one undercounting. But the exact
figures now carry more uncertainty than they were reported with, and none
of them have been re-verified against the fixed build. **Re-running the
headline numbers (9.4's +8,824%, 9.6's light/heavy split, 9.5's null
result) against the current build is worth doing before those figures are
treated as final** -- not because they are expected to change materially,
but because "expected not to change" was exactly the assumption this bug
violated.

**9.4's headline re-verified**: +6,064.2% on the fixed build (comm,
white-box, 64 attackers), against the original +8,824.2%. Same order of
magnitude, same conclusion (`comm` severely exploitable) -- the
qualitative finding holds.

**9.5 re-verified**: +2.0% (steep penalty, low-rate victim, n=5), well
within noise (288us gap vs. 1,296us range) -- consistent with the
original n=15 result of -1.7%. The paper's central "no scheduling
manipulation detected" claim holds on the fixed build.

**9.6 re-verified, with a genuine scare worth recording.** Light volume:
0.0%, 11.1%, 93.0%, 0.0% -- noisier than the original 0.0%/0.0%/0.0%/4.8%
but the same qualitative picture (near-total mitigation). Heavy volume,
first run: 208.9%, 0.0%, 0.0%, 0.0% -- looked like the counter fix had
qualitatively changed the finding from "partial mitigation" to "near-full
clearance." A second heavy-volume run showed 815.6%, 1869.8%, 1936.4%,
1942.9% -- back to sustained high damage matching the original
790.5-2011.4% range. The first run was a fluke, not a fix-driven change;
**the original "partial mitigation only, not full clearance, at heavy
volume" finding holds**, confirmed across two runs on the fixed build.
Recorded as a reminder of exactly the trap 9.5 already caught once at n=5
vs n=15: a single run in the "interesting" direction is not evidence
until it survives a second look.

## 9.9 A regression suite now exists, and it immediately paid for itself

Section 5's original instruction -- build this before, not after,
starting the BPF work -- had gone unmet for the whole of the security
investigation in Sections 9.4-9.8. `tests/regression.py`
(`scheds/experimental/scx_cms/tests/`) closes that gap:

- `attach_detach_matrix` -- every tracker/mechanism combination loads
  and unloads cleanly.
- `window_rotation_advances` -- the timer-driven epoch actually
  increments over time.
- `mechanism_reach_reported` -- the core counters are present and
  readable.
- `concurrent_stress` -- many processes sharing one identity, hammering
  the same map cells concurrently. This is the test that would have
  caught all three of Section 9.8's lost-update bugs on its first run,
  had it existed before that investigation rather than after.
- `known_roll_race` -- the same load sustained across real window
  rotations, isolating the additional rotation-triggered exposure.

**It paid for itself immediately.** Running it against the already-fixed
build found the fourth, broader issue documented in the correction to
Section 9.8 above: `concurrent_stress` failed even with no rotation
involved, which is what revealed that the remaining problem is broader
than `cms_roll()` specifically. Both `concurrent_stress` and
`known_roll_race` are marked as expected failures (xfail) rather than
skipped or silently passing, so the known gap stays visible in every run
of the suite rather than depending on someone remembering a code
comment. The other three tests pass cleanly.

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

## 12. Phase 6: four-tier baseline comparison (round 1)

The comparison delivery plan Section 3 requires before any
scheduling-quality claim is credible. Round 1: `schbench` request-latency
P99/P999 only, one workload shape, on the 4-CPU Lima VM. `cyclictest`,
`hackbench`, `rt-app`, and the still-open workload-profile decision
(paper checklist item 10) are not yet part of this — see "what round 1
does not cover" below.

**Harness**: `benchmark/baseline_comparison.py`. Four tiers, 5 conditions
interleaved per repetition (matching the methodology established in
Sections 9.5/9.6): stock EEVDF, `scx_simple` (from `scx-c-examples`,
built via `make`), `scx_cms --tracker exact --mechanism none` (this
project's own scheduler with the sketch/mechanism questions already
answered in Section 9 switched off, isolating "does this project's own
scaffolding cost anything"), and `scx_lavd` (chosen over `scx_rusty` for
thematic alignment — both are fundamentally about tracking task behavior
to protect latency-sensitive work). Workload: `schbench -m2 -t4 -R100
-w3 -r10`, fixed across all four conditions.

### Result: consistent across all 5 repetitions, ranges do not overlap

| scheduler | p99 median | p99 range | vs. EEVDF | p999 median | vs. EEVDF |
|---|---:|---:|---:|---:|---:|
| EEVDF | 25,760us | 24,800-29,344 | 1.00x | 36,416us | 1.00x |
| `scx_simple` | 14,800us | 14,448-15,792 | **0.57x** | 16,416us | **0.45x** |
| `scx_cms` (exact) | 14,256us | 11,088-14,896 | **0.55x** | 15,472us | **0.42x** |
| `scx_lavd` | 42,176us | 35,008-45,760 | **1.64x** | 66,688us | **1.83x** |

Unlike every single-run scare this project has already caught and
discarded (9.5's +34.7%, 9.6's near-clearance fluke), this is not
borderline: every one of the 5 repetitions independently shows the same
ordering, and the ranges are cleanly separated -- `scx_lavd`'s worst run
(35,008us) still exceeds EEVDF's best (29,344us).

### `scx_simple` and `scx_cms` beating EEVDF is plausible and not
surprising: both are minimal global-vtime schedulers with none of
EEVDF's fairness/interactivity bookkeeping, on a synthetic benchmark
that rewards exactly that simplicity. `scx_cms`'s own scaffolding
(identity resolution, exact counter tracking, all running with
`--mechanism none` so nothing acts on what's tracked) costs nothing
detectable relative to `scx_simple` -- the two are statistically
indistinguishable here (0.55x vs. 0.57x, overlapping ranges).

### `scx_lavd` losing to EEVDF is the real finding, and it needed a
follow-up before writing it up as a flat claim. `scx_lavd` is a
power-aware scheduler (core compaction to save power on real hardware)
built for SteamOS's actual heterogeneous gaming/desktop workloads --
reporting "`scx_lavd` is 1.64x worse" without checking for an obvious
confound first would have been unfair to it.

**Confound tested directly**: `scx_lavd --performance` (disables core
compaction entirely). 3 reps each: default 44,480us median, `--performance`
37,568us median -- a real ~16% improvement, confirming power-saving
costs something here. But it does not close the gap: even in
`--performance` mode `scx_lavd` remains roughly 1.4x worse than EEVDF's
25,760us, well outside what core compaction alone explains.

**Plausible, NOT verified**: the remaining gap is most likely `scx_lavd`'s
task-criticality/interactivity classification -- designed to
differentiate real mixed workloads (foreground game thread vs.
background compositor vs. audio callback) -- providing no benefit on
`schbench`'s single, uniform task-type pattern while its overhead still
applies. This has not been tested directly (would need a mixed-workload
benchmark, which round 1 does not have) and must not be reported as
confirmed.

**What this does and does not establish.** It does NOT establish that
`scx_lavd` is a worse scheduler in any general sense -- a synthetic
single-workload-type benchmark on a virtualized 4-CPU machine is close
to the least representative environment for a scheduler built around
real hardware power/topology signals and heterogeneous task mixes,
exactly the caveat already recorded in Section 3.2's VM-justification
paragraph, now with a concrete illustration behind it rather than only
the abstract argument. It DOES establish, with real confidence given 5
non-overlapping repetitions, that on this specific workload and
environment, `scx_lavd` underperforms both EEVDF and two much simpler
schedulers, and that roughly a sixth of that gap is attributable to power
management specifically.

### What round 1 does not cover

- **Only `schbench` P99/P999.** `cyclictest` and `hackbench` (Section 4's
  tooling) have not been run against any of the four tiers yet --
  `hackbench` in particular matters, since it is the throughput
  regression check confirming a scheduler that wins on latency isn't
  quietly losing on general throughput.
- **Only one workload shape** (`schbench`'s uniform message/worker
  pattern at a fixed low RPS). The mixed-workload test that would
  actually probe the `scx_lavd` hypothesis above does not exist yet.
- **`rt-app` and the workload-profile decision** (paper checklist item
  10: audio-callback vs. periodic-deadline-task) remain unresolved,
  unchanged from before this round.
- **Single VM, single hardware configuration.** No cross-checking against
  a different CPU count or a non-VM environment.

## 13. Phase 6 round 2: mixed workload, and the first positive result

Round 1 compared schedulers on a workload where the mechanism had nothing
to do. Round 2 was built to answer the question the project actually
exists to answer, and which nothing before it had opened:

> **Does acting on the tracked wakeup count improve scheduling quality,
> and if so, does the sketch preserve that improvement?**

This decomposes into two comparisons, in strict order:

1. **`cms_exact_penalty` vs `cms_none`** -- the *gating* question. Same
   scheduler, same tracker, same overhead; the only difference is whether
   the mechanism acts on the count. If this shows nothing, the sketch
   question is meaningless, because there is no signal for the sketch to
   preserve or lose.
2. **`cms_sketch_penalty` vs `cms_exact_penalty`** -- the paper's
   hypothesis, interpretable *only* if (1) showed something.

### Building the instrument took six iterations, and that was the work

Every previous attempt to detect a mechanism effect (Section 9.5) found
nothing across every configuration tried. The honest reading of that was
never "the mechanism does nothing" -- it was "no instrument here can tell
the difference between *no effect* and *cannot detect an effect*." Round 2
therefore led with a **positive control**: the same victim measured with
the antagonist mostly removed (`--posctl-churn 8`). If the victim does not
improve when the pressure is lifted, the workload cannot detect scheduling
quality and every other row is void.

Six candidate workloads were built and rejected, each killed by the
positive control before a full matrix was ever run. Two findings came out
of that, both worth recording because both cost real time:

**`rt-app` is unusable as a victim on this VM.** It measures timer-driven
wakeups, and timer *delivery* under this VM's virtualised clock has a
floor around 1.7ms. Churn levels of 24, 4, and 0 tasks all produced a
victim latency of ~1700us -- indistinguishable, because the floor swamps
everything scheduling does. This resolves paper checklist item 10 in the
negative for this environment: the audio-callback profile cannot be
measured with `rt-app` here. `schbench`, which measures *task-to-task*
wakeups, has no such floor and works. Anyone reproducing this on bare
metal should re-test rather than inherit the conclusion.

**Victim latency is driven by runqueue depth, not CPU demand.** This was
the breakthrough that made the instrument work, and it is counter-
intuitive enough to state plainly:

| churn shape | CPU demand | victim degradation |
|---|---|---|
| 48 tasks, heavy (each burning a lot) | 19.2 CPUs | 6.23x |
| 128 tasks, light (each burning little) | 5.1 CPUs | **9.07x** |

A *quarter* of the CPU demand spread across *2.7x* the task count hurts
the victim substantially more. Wakeup latency is a queueing phenomenon:
what matters is how many runnable tasks sit between the victim and the
CPU, not how much work they represent. This is also precisely the regime a
wakeup-frequency mechanism should be able to exploit -- many small
frequent wakers are exactly what it is built to identify. The final
workload is therefore 128 CPU-light, wakeup-heavy churn tasks at 200
wakeups/s burning 200us each, against a `schbench` victim.

### Result: the gate opens, confirmed at n=15

The first matrix ran at n=5 and looked spectacular. Because two earlier
results in this project evaporated when N was raised (Section 9.6's
seed-rotation "near-clearance", and a +34.7% effect at n=5 that became
-1.7% at n=15), the headline conditions were re-run at n=15 before
anything was written down. Both numbers are given, because the movement
between them is itself evidence:

| condition | p99 @ n=5 | p99 @ n=15 | range @ n=15 |
|---|---|---|---|
| eevdf | 259,328us | 250,624us | 208,128-343,552 |
| cms_none | 87,424us | 82,304us | 63,808-165,632 |
| cms_exact_penalty | 9,104us | **12,016us** | 11,152-19,040 |
| cms_sketch_penalty | 9,200us | **13,456us** | 10,928-27,168 |

**The gating question is answered yes, for the first time in this
project.** `cms_exact_penalty` (11,152-19,040) against `cms_none`
(63,808-165,632): the ranges are nowhere near overlapping, across 15
repetitions, for a **6.8x** reduction in victim p99. Both conditions run
the same scheduler, the same tracker, and the same per-wakeup tracking
overhead, with `reach=100%` in both. The only difference is whether the
mechanism consults the count it already computed. Section 9.5's "no
effect on this scale" was a property of that workload, not of the
mechanism.

Note the effect *shrank* from 9.6x to 6.8x when N tripled. That is the
expected signature of a real effect that a small sample flattered, and
is more reassuring than a number that had not moved at all.

**The sketch comparison must be worded carefully.** Exact
(11,152-19,040) and sketch (10,928-27,168) overlap heavily, which by
this harness's own stated rule means *no difference was demonstrated*.
That is the direction the hypothesis wants, but it is not the same
claim, and the paper must not blur them:

> Supported: the sketch retained the benefit; no penalty relative to
> exact counting was detectable at n=15.
> NOT established: that the sketch is equivalent to exact counting.

Absence of a detected difference is not evidence of equivalence,
particularly here -- the sketch's upper tail (27,168us) runs above
exact's (19,040us), which is consistent with either noise or a real
worst-case cost the sample cannot resolve. Establishing equivalence
needs an equivalence test with a pre-declared margin, not a null from a
difference test. This is the same error the project already caught
itself making in Phase 1, where sketch and exact produced byte-identical
outcomes and the tempting reading was "the approximation is accurate
enough" when "the mechanism does not lean on the count hard enough" fit
equally well.

### The win is not bought by starving the background work

A mechanism that wins its target metric by wrecking everything else has
not won. The churn tasks completed a median 157,059 loops under
`cms_exact_penalty` against 157,095 under `cms_none` -- 0.02% apart,
inside run-to-run noise. The victim's 6.8x costs the antagonist nothing
measurable.

Caveat on that check's strength: the churn tasks are rate-limited at 200
wakeups/s, so this can detect a *regression* but could not observe a
throughput *gain*. As the regression check Section 4 asks for, it holds;
it is not a general throughput result, and `hackbench` across the tiers
is still unrun.

### The negative control: most of the 6.8x is NOT the tracking

`penalty` does two things simultaneously: it consults the tracked count,
and it perturbs vtime. Comparing it against `none` measures both at once.
If the improvement comes from the perturbation, the tracking is doing no
work and the result says nothing about this project's premise.

A `flat` mechanism was added (mechanisms/flat.bpf.c) applying an
identical vtime penalty to every task at every enqueue with no reference
to the count, swept across values chosen to be able to beat the
treatment rather than one convenient number:

| condition | p99 median | range | n |
|---|---|---|---|
| cms_none | 99,072us | 61,760-110,976 | 8 |
| **cms_exact_penalty** | **12,384us** | 11,568-15,120 | 8 |
| flat_2ms | 17,824us | 16,736-25,952 | 8 |
| flat_4ms | 17,248us | 15,440-20,128 | 8 |
| flat_8ms | 18,880us | 15,472-26,912 | 8 |

**A count-blind penalty captures 5.7x of the 8.0x.** On a log scale
roughly **84% of the effect is generic vtime perturbation**; only ~16%
is attributable to consulting the count. The correct statement of the
round 2 result is therefore:

> Acting on wakeup frequency improved victim p99 by ~1.4x over an
> equally strong count-independent penalty. The 6.8-8x figure against
> `cms_none` conflates the mechanism with vtime perturbation per se and
> must not be attributed to tracking.

The count-attributable margin is real but thin: exact (max 15,120)
against flat_4ms (min 15,440) clears by 320us, ~2% of the values, at
n=8. Non-overlapping against all three flat variants, but fragile
enough that it needs confirmation at higher N before it is reported.

**This undermines the sketch conclusion above, and that matters more.**
If only ~16% of the measured effect depends on the count, then
sketch-vs-exact comparisons run against `cms_none` have almost no
resolving power: both conditions are dominated by a component the
sketch cannot degrade. A sketch losing a large fraction of the
count-attributable signal would still land inside exact's range. The
overlap reported in the previous subsection is therefore much weaker
evidence than it appears.

The sketch comparison must be re-run with **`flat` as the baseline, not
`cms_none`**, isolating the count-attributable component. That is the
comparison the paper's hypothesis actually rests on and it has not yet
been made.

This is the third time in this project that a headline number shrank
under a control (Section 9.6's seed rotation, the n=5 to n=15 movement
above, and now this). The pattern is consistent enough to be worth
stating as method: every mechanism here does something besides the
thing being studied, and the control that isolates it has never once
been unnecessary.

### The memory saving is NOT demonstrated by round 2

Round 2 ran the sketch at defaults (2 x 256 x 4 cells x 4B = ~8 KB)
against the exact tracker's LRU hash provisioned at CMS_MAX_TRACKED =
16,384 entries (~800 KB). That looks like a ~100x saving and it is not
one: **the workload had only ~132 distinct identities**, under 1% of the
exact map's provisioned capacity. An exact map honestly sized for 132
tasks would be roughly 6 KB -- *smaller than the sketch.*

Round 2 demonstrates that approximate tracking preserves scheduling
quality. It demonstrates nothing whatsoever about memory, because the
identity count never approached the regime where bounded-memory
counting is worth anything. Reporting the 8 KB vs 800 KB comparison
from this experiment would be comparing a sketch at its natural size
against a provisioning ceiling the workload never used.

Demonstrating the memory claim needs a workload with thousands of
distinct short-lived identities, where exact counting genuinely must
allocate and the sketch's bounded footprint is the actual point. Until
that exists the paper has evidence for half its thesis.

### Re-run against `flat` at n=15: the p99 claim dies, a better one appears

The control above was n=8 and cleared by 2%. Re-run at n=15 with `flat`
as the baseline:

| condition | p50 median | p50 range | p99 median | p99 range |
|---|---|---|---|---|
| cms_none | 3,948us | 2,156-5,208 | 88,192us | 64,064-157,952 |
| cms_exact_penalty | 3,964us | 3,588-4,104 | 12,784us | 10,928-21,664 |
| cms_sketch_penalty | 4,012us | 3,676-6,008 | 12,880us | 10,576-32,288 |
| flat_4ms | **11,760us** | 11,120-12,624 | 16,544us | 15,344-29,600 |

**On the pre-declared metric the count-attributable effect is gone.**
exact (10,928-21,664) and flat_4ms (15,344-29,600) overlap heavily on
p99. At n=8 they cleared by 320us; at n=15 they do not clear at all. By
the criterion committed to in advance -- ranges overlapping means no
effect demonstrated -- there is no demonstrated p99 benefit from
consulting the count over an equally strong count-blind penalty. That is
the third headline number in this project to evaporate under a larger
sample.

**But p50 shows something the p99 comparison was blind to.** `flat`
penalises every task, the victim included, and its median wakeup latency
is 11,760us against ~3,950us for every other condition -- 3x worse,
ranges nowhere near overlapping. `cms_exact_penalty` achieves comparable
tail reduction while leaving p50 statistically identical to doing
nothing (3,964 vs cms_none's 3,948).

The count's value is therefore not "reduces the tail more than a flat
penalty does". It is:

> A count-blind penalty buys tail improvement by taxing every task,
> including the latency-sensitive one. A count-proportional penalty buys
> comparable tail improvement at no cost to the median, because it can
> tell the victim from the churn. Discrimination shows up as absence of
> collateral damage, not as a larger tail reduction.

**Why this is reported as provisional, not as the finding.** The
pre-declared primary metric was p99, and p99 is inconclusive. The effect
was located in p50 only after p99 disappointed, which is metric-shopping
regardless of p50 having been collected in every run since round 2
began. A paired sign test on p99 (the harness interleaves conditions
within each repetition, so the data is paired by design) gives exact <
flat in 12 of 15 pairs, one-sided p = 0.018 -- but that test was also
chosen after seeing the range criterion fail, and post-hoc test
selection is how the two false positives earlier in this project
happened.

What keeps it alive rather than discarded is that it is not a marginal
statistical rescue: it is a 3x non-overlapping gap whose mechanism was
predictable in advance (a count-blind penalty MUST hit the victim; a
count-proportional one mostly spares it). The hypothesis explains the
data instead of being fitted to it.

**Required before this is claimed:** a pre-registered run declaring p50
as the primary metric and the paired sign test as the analysis, before
any data is collected. Nothing above should reach the paper until that
run exists.

**Sketch caution.** `cms_sketch_penalty` overlaps exact on both metrics,
so no difference is demonstrated -- but its upper tails run high on
both (p50 6,008 vs exact's 4,104; p99 32,288 vs exact's 21,664). That
is the signature one would expect if the sketch occasionally mis-ranks a
task under collision. Not demonstrated, and specifically worth
instrumenting in round 3 rather than left as an impression.

## 14. Round 2c: the pre-registered test voids itself, and exposes an instability

Pre-registration committed at cc31180 before any data existed. Result at
n=20:

| condition | p50 median | p50 range | p99 median | p99 range |
|---|---|---|---|---|
| cms_exact_penalty | 3,836us | 3,444-4,012 | 11,712us | 10,352-14,000 |
| cms_sketch_penalty | 3,860us | 3,508-**11,120** | 12,912us | 10,032-24,224 |
| flat_4ms | 11,680us | 10,320-12,464 | 16,160us | 15,248-21,920 |

**Criterion 1 (gating) FAILED.** The p99 ranges were required to overlap,
confirming matched tail benefit. They do not: exact (10,352-14,000) sits
cleanly below flat (15,248-21,920). The pre-registration states that in
this case the primary comparison is void and must be re-registered.

Criteria 2 and 3 both passed emphatically -- paired sign test 20/20,
one-sided p = 9.5e-7, p50 ranges nowhere near overlapping. **They are
void anyway.** The precondition was written down precisely to prevent
accepting the favourable half of a result whose framing had already
failed, and it is being honoured.

### The real problem: two runs disagree about the system

| comparison | n=15 run | n=20 run (2c) |
|---|---|---|
| exact p99 range | 10,928-21,664 | 10,352-**14,000** |
| flat_4ms p99 range | 15,344-29,600 | 15,248-**21,920** |
| overlap? | **yes** | **no** |

Exact's upper bound fell from 21,664 to 14,000 while N *increased*.
Ranges do not narrow with more sampling; something uncontrolled differs
between the runs.

The leading hypothesis is condition-set composition. The n=15 matrix
included `cms_none`, whose p99 is ~88ms; 2c did not. If running a
pathological condition perturbs conditions measured after it -- residual
runqueue state, page cache, CPU frequency, or the harness's own
scheduler attach/detach path -- then **which conditions share a matrix
changes the numbers**, and every comparison in this project inherits
that confound, including those already written into the paper.

This must be resolved before any Phase 6 number is trusted. The check is
cheap: run exact and flat alone, then again with cms_none interleaved,
and see whether exact's range moves. Until then the correct status of
every round 2 comparison is *unstable, not reproduced*.

### The sketch has an occasional severe failure mode

Sketch p50 across the 20 repetitions:

```
3508 3588 3620 3684 3692 3732 3804 3780 3836 3828
3884 5240 3932 3932 3924 4052 11120 3948 3932 4020
```

Eighteen runs track exact closely. Two do not: 5,240us and 11,120us,
the latter essentially flat's median. Exact never exceeded 4,012us.

That is a ~10% severe-failure rate with a clear mechanism: a hash
collision places the victim in the same cell as heavy wakers, its
estimated wakeup count inflates, and the penalty intended for churn
lands on the task the user is waiting on. It is the scheduling-outcome
consequence of Section 9.4's collision attack, arriving here by
accident rather than by an adversary.

**This is the most policy-relevant sketch finding so far, and medians
hide it completely.** The sketch's cost is not a small average
degradation that a memory saving might justify; it is occasional
severe misranking of exactly the task the mechanism exists to protect.
For a scheduler that is arguably worse than uniform error, and it means
sketch-vs-exact must be reported as a failure-rate comparison, not a
median comparison.

## 15. Round 2d: randomised ordering, and what survives

First matrix run after the ordering fix (623762e), n=20, seed=1, all
four conditions. This is the first Phase 6 measurement not carrying the
fixed-order confound.

| condition | p50 median | p50 range | p99 median | p99 range |
|---|---|---|---|---|
| cms_none | 3,920us | 2,148-3,956 | 80,640us | 63,680-138,496 |
| cms_exact_penalty | 3,920us | 3,556-3,964 | 11,744us | 10,512-39,488 |
| cms_sketch_penalty | 3,928us | 3,524-4,872 | 12,880us | 10,832-22,304 |
| flat_4ms | 11,776us | 10,832-12,368 | 16,576us | 15,248-17,568 |

### Confirmed, and robust to randomisation

**The collateral-damage finding.** `flat` costs 3x median latency
(11,776us vs 3,920us) while `cms_exact_penalty` costs nothing -- its p50
is identical to `cms_none` to the microsecond. Ranges non-overlapping,
paired sign test 20/20, p = 9.5e-7. This is the project's positive
result and it is the one that survived every control applied to it.

**The gate.** Acting on the count beats `none` on p99: 20/20
non-overlapping, ~6.9x.

**The count-blind control.** Still ~82% of the p99 improvement is
generic vtime perturbation. The p50 column now shows what that
perturbation costs: `flat` makes the median **3x worse than doing
nothing at all**. It does not merely fail to help the typical case, it
actively harms it to buy a tail number. That sharpens rather than
weakens the original control finding.

### RETRACTED: the sketch's ~10% severe-failure rate

Section 14 reported 2 of 20 sketch runs at 5,240us and 11,120us p50 and
called it "the most policy-relevant sketch finding so far", with a
mechanism (collision places the victim in a cell with heavy wakers) and
an explicit prediction that it was the finding *least* likely to be an
ordering artifact.

It does not reproduce. Under randomised ordering, **0 of 20** sketch
runs exceeded 5,000us; the maximum was 4,872us against exact's 3,964us.
The earlier observation was fixed-order contamination or chance.

Recorded prominently rather than quietly deleted, because the error is
instructive: the same skepticism was applied to results that were
disappointing and not to one that was interesting. A plausible
mechanism was available for the interesting result, and having a
mechanism made it feel confirmed. That is the fourth headline number in
this project to fail replication, and the first where the failure was
caused by wanting it to be true.

### Unresolved

exact vs flat on p99: paired sign test strongly favours exact (19/20,
p = 2e-5) but ranges overlap on a single exact outlier at 39,488us
against a next-worst of ~14,000us. Probably real, not claimed.

sketch vs exact: no significant difference on either metric (exact
lower in 14/20 on p99, p ~ 0.058). The sketch neither clearly preserves
nor clearly degrades what the count contributes.

### Status of everything measured before 623762e

Unreproduced. Rounds 1, 2, 2b and 2c all carry the fixed-order
confound. Findings above are the ones re-established after the fix;
anything else from those rounds should be treated as provisional until
re-run.

## 16. Round 3: the memory question, answered against the hypothesis

Matched memory budgets, n=8, randomised condition order. `--max-tracked`
was added to size the exact hash, because both maps exist in the BPF
object whichever tracker is selected -- without it every condition
reported identical memory and the first sweep measured nothing.

Discrimination ratio = `flat` p50 / condition p50. It asks how well the
tracker separates the victim from churn, with the count-blind penalty as
the zero point. 1.0 means no discrimination at all.

| budget | exact | sketch | sketch map |
|---|---|---|---|
| 128 KB | **3.72x** | 3.71x | 128.3 KB |
| 32 KB | **3.62x** | 3.14x | 32.3 KB |
| 8 KB | **3.55x** | **0.83x** | 8.3 KB |
| 2 KB | **3.60x** | **0.97x** | 2.3 KB |

**Exact counting beats the sketch at every budget tested, and the gap
widens as memory shrinks. No crossover in the sketch's favour exists in
the range measured.** That range is the project's entire premise.

The sketch matches exact at 128 KB, slips at 32 KB, and by 8 KB has lost
all discrimination -- its p50 (17,056us) is worse than the count-blind
baseline (14,208us). At that width everything collides, every count is
inflated including the victim's, and the mechanism penalises the task it
exists to protect. Exact holds ~3.6x down to **21 entries** in a
workload containing thousands of distinct pids.

### Why: LRU is a better small-memory approximation than a sketch here

Scheduling needs the *active set*, not the full population. An LRU hash
under-provisioned by three orders of magnitude still holds the tasks
that are currently running, and forgets the rest -- which is precisely
the right thing to forget. A Count-Min Sketch retains every identity and
blurs all of them together.

When the budget is tight, precise-on-few beats imprecise-on-many, and
the sketch's never-undercount guarantee inverts from a feature into a
liability: guaranteed overestimation means the protected task's count is
inflated and it gets penalised as churn.

This is the substantive result of the project, and it is the opposite of
the hypothesis. It is also specific rather than vague -- the crossover
is between 32 KB and 8 KB on this workload, and the mechanism for the
failure is identified.

### Second finding: identity turnover defeats the mechanism

Every penalty variant is 2-3x **worse** than `flat` on p99 at every
budget (exact 2.15x-3.04x). With `--identity-key pid` and continuously
respawning churn, each churn task is a fresh identity at count 0, is
never penalised, and runs at full slice. Nothing controls the tail. The
count-blind penalty does better precisely because it does not need to
recognise anything.

So the mechanism's usefulness depends on **identity stability**, an
assumption never stated in the design. `--identity-key comm` should
recover it, since respawned churn shares a comm -- untested, and it is
the obvious next experiment.

### Third: the collateral-damage finding replicates

Exact holds ~3.6x discrimination at every budget in this workload, which
is structurally different from round 2d's (respawning tasks, different
scale, different identity turnover). A result that survives a change of
workload is considerably stronger than one confirmed only by more
repetitions of the same one.

## 17. Round 4: identity, boost, sketch shape, and a replication

### 17.1 Identity stability, and why `comm` is not the fix

n=10, respawning workload. Discrimination = flat p50 / row p50.

| condition | p50 | p99 | discrim |
|---|---|---|---|
| flat_ref | 14,336us | 30,752us | 1.00x |
| penalty_pid | 3,980us | 68,608us | 3.60x |
| penalty_comm | 12,416us | 28,032us | 1.15x |
| boost_pid | 4,000us | 115,456us | 3.58x |
| boost_comm | 4,004us | 100,608us | 3.58x |

`comm` recovered the tail (68,608 -> 28,032us, non-overlapping) exactly
as predicted, and destroyed discrimination doing it (3.60x -> 1.15x).
It is not a fix; it trades one failure for another, and `penalty_comm`
is `flat` with extra steps.

The mechanism is structural rather than a tuning problem: **a coarse
identity key aggregates a multithreaded latency-sensitive application
into the heaviest waker on the system.** The victim's four schbench
threads share one comm, so their wakeups sum to ~400/s against each
churn slot's 200/s. Under `comm` the task the mechanism exists to
protect becomes the single most-penalised identity present.

So the sharpened limitation is: the mechanism requires identity
stability, and **no identity-key choice rescues it when identities
churn** -- fine-grained keys cannot see the churn, coarse keys
mis-attribute the victim.

`boost` ran for the first time here, having existed since the mechanism
abstraction was built. It has good discrimination and the worst tails
measured anywhere in the project (100-115ms). Not a viable direction on
this evidence.

### 17.2 The sketch's best shot, at the budget where it collapsed

n=10, 8 KB, cells held constant so only the width/depth split varies.

| condition | p50 | p50 range | discrim |
|---|---|---|---|
| exact_ref | 4,012us | 3,988-4,136 | **3.67x** |
| sketch_d1_w512 | 7,512us | **2,884-19,168** | 1.96x |
| sketch_d2_w256 | 17,920us | 16,272-19,808 | 0.82x |
| sketch_d4_w128 | 17,184us | 15,824-18,784 | 0.86x |
| sketch_d8_w64 | 15,584us | 15,120-16,112 | 0.95x |
| sketch_d4_rotate | 17,184us | 16,544-17,952 | 0.86x |

**No shape reaches exact.** Best is depth-1 at 1.96x, barely half, and
four of five sit below 1.0x -- worse than not discriminating at all.

**Seed rotation does nothing** for accidental collisions: 0.86x with,
0.86x without. It moves collisions rather than creating room. Its
value against *adversarial* collisions (Section 9.6) is unaffected.

Depth 1 is a lottery: p50 from 2,884us (better than exact's best) to
19,168us. With one row there is no min-query, so the victim either gets
a clean cell or does not, per run. Excellent-or-unusable depending on
hash placement is not a viable scheduler design regardless of median.

This closes the "did you give the sketch its best shot" objection. Four
shapes plus rotation, at constant memory, at the deciding budget.

### 17.3 Replication of the collapse at n=20, different seed

| budget | exact n=8/s1 | exact n=20/s2 | sketch n=8/s1 | sketch n=20/s2 |
|---|---|---|---|---|
| 32 KB | 3.62x | **3.70x** | 3.14x | **3.53x** |
| 8 KB | 3.55x | **3.64x** | 0.83x | **0.86x** |

The collapse between 32 KB and 8 KB reproduces at a different sample
size and a different order seed. At 8 KB the p50 ranges are nowhere
near overlapping (exact 3,972-4,136us, sketch 16,048-17,504us).

Replicated across two sample sizes, two order seeds, and independently
supported by 17.2's shape sweep, this is the most solid result the
project has.

### 17.4 A tradeoff that holds across a continuous knob

Ordering 17.2's rows by discrimination against their p99:

```
3.67x (exact)  -> p99  98,432us
1.96x (d1)     -> p99  54,528us
0.86x (d4)     -> p99  31,008us
0.95x (d8)     -> p99  24,320us
```

Monotonic, or near enough. In this workload the blunter the instrument
the better the tail, because identity turnover means discrimination
mostly succeeds at penalising the victim. Scope matters: round 2d's
stable-identity workload had exact achieving good discrimination AND
good p99 (11,744us) simultaneously. The tradeoff is what identity churn
does to the mechanism, not a universal law.

## 18. Rounds 5 and 6: replacing inferences with instruments

Every finding in this section replaced something previously asserted.
That is the pattern worth noting: none of it came from more repetitions,
all of it came from adding a control or an instrument.

### 18.1 CONFIRMED: BPF LRU_HASH degenerates far below LRU semantics

The claim that exact counting's small-map collapse was BPF LRU behaviour
rather than capacity was raised as an explanation and never tested. A
`--plain-map` flag now backs the same tracker with BPF_MAP_TYPE_HASH:
identical capacity, no eviction. Stable workload, mean tracked count per
query:

| budget | entries | LRU_HASH | plain HASH |
|---|---|---|---|
| 8 KB | 85 | 184.2 | 192.4 |
| **4 KB** | **42** | **1.6** | **189.8** |
| 2 KB | 21 | 1.0 | 0.2 |

At 42 entries the LRU map reports a mean count of **1.6** where a plain
hash of the same size reports **189.8**. A true LRU holding 42 of the
~330 live identities should report roughly 48. BPF's LRU is therefore
about **30x worse than LRU semantics predict**, and the cliff falls
between 42 and 85 entries on this 4-CPU machine.

This is a property of the map type, not of exact counting, and it is
worth reporting on its own: any BPF program sizing an LRU_HASH in the
low tens of entries on a multi-core system is not getting an LRU.

It also revises Section 16. "Exact goes inert below ~32 KB" was
measuring a pathological map at the smallest budgets, not graceful
capacity-limited degradation.

Note the plain hash is not a fix, only a different failure. Its
histogram shows 83% of queries returning zero while a locked-in minority
accumulate counts in the thousands: first-come-first-served, with
everything after the map fills up invisible. Neither structure degrades
usefully; they simply degrade differently.

### 18.2 Conservative update: effective, and unusable in BPF

Conservative update reduces overestimation as theory says it should:

| condition | baseline | conservative | conservative+hash mix |
|---|---|---|---|
| churning 16 KB | 2.79x | 2.40x | **2.27x** |
| churning 8 KB | 4.30x | 3.59x | **2.78x** |
| stable 16 KB | 1.21x | **1.07x** | 1.08x |

A 15-35% improvement at no memory cost. It is still not usable, for a
reason specific to BPF rather than to the algorithm.

Conservative update must read all d cells, take the minimum and write
back as one atomic unit. Each cell needs its own bpf_map_lookup_elem,
and the verifier rejects a lock held across those calls outright:

    function calls are not allowed while holding a lock

So the implementation here is lock-free, using compare-and-swap with an
atomic-increment fallback. The race that leaves is not theoretical: at
stable 16 KB it produced **1,749 never-undercount violations against a
baseline of 116**, a 15x increase. Two CPUs observing the same minimum
and both writing min+1 lose an increment, and the guarantee that
justifies using a Count-Min Sketch at all is gone.

**Correct-and-slow is not available; only fast-and-wrong.** A locked
version would need the entire table restructured into a single map
value, which changes what is being measured.

### 18.3 The unexplained 3.4x model gap: closed

Section 3.4 of the paper recorded that the churning regime's mean
tracked count (220) missed the workload model's prediction (~64) by 3.4x
even after the identity population was measured. A count histogram shows
why -- the distribution is bimodal, not centred:

    churning 32 KB:  10-99 -> 101,606 queries    1k-10k -> 22,209 queries

Most queries see 10-99, matching the model. A minority of long-lived
identities carry counts in the thousands and drag the mean upward. The
model counted only churn tasks and ignored the persistent ones.

The lesson is narrow and practical: a mean tracked count is not a useful
summary of a workload with mixed identity lifetimes, and three rounds of
inference were spent on a number a histogram answered directly.

### 18.4 Hash mixing: confirmed at the predicted size

Adding a final avalanche before the power-of-two modulo improves the
sketch's overestimate by roughly 5-13% (churning 16 KB 2.79x -> 2.46x;
8 KB 4.30x -> 4.10x), matching the simulation estimate of <=13%. Real,
worth fixing, changes no conclusion.

## 19. Rounds 7-9: the thesis, supported

### 19.1 No throughput cost (Section 4's outstanding check)

hackbench and cyclictest across the tiers, n=5, randomised order. This
was specified in Section 3.3 and never run, and it matters here because
the mechanism works by *delaying* tasks -- an obvious route to buying
latency wins with throughput on a benchmark suite that only measures
latency.

| condition | hackbench | vs eevdf | cyclictest avg |
|---|---|---|---|
| eevdf | 1.05s | 1.00x | 124us |
| cms_none | 0.95s | 0.91x | 134us |
| flat | 1.00s | 0.95x | 117us |
| exact_penalty | 0.97s | 0.92x | 113us |
| sketch_penalty | 0.95s | 0.90x | 119us |

No regression anywhere; every scx variant matches or slightly beats
EEVDF. cyclictest shows no meaningful separation (its absolute values
are floored by this VM's timer delivery, so only the relative reading
is usable). The mechanism does not pay for its latency behaviour in
throughput.

### 19.2 The memory thesis holds in the stable-identity regime

Victim p99, stable workload, LRU map, n=8:

| budget | none | exact_penalty | sketch_penalty |
|---|---|---|---|
| 32 KB | 77,952us | **10,272us** | 13,200us |
| 16 KB | 77,824us | 42,240us | **9,888us** |
| 8 KB | 71,552us | 68,608us *(inert)* | **12,192us** |
| 2 KB | 72,704us | 67,456us *(inert)* | **13,184us** |

The sketch delivers a 5-7x tail improvement over taking no action at
**every** budget down to a 2.3 KB map. Exact matches it at 32 KB,
degrades at 16 KB, and is statistically indistinguishable from `none`
at 8 KB and below. At 8 KB the ranges do not overlap (sketch
7,640-17,376us, exact 58,048-86,656us).

**This is the claim the project set out to test**: approximate counting
delivering scheduling benefit at a memory budget where exact counting
cannot. Earlier rounds appeared to refute it because the discrimination
metric could not distinguish a working tracker from an inert one, and
because the churning regime -- where the mechanism fails for unrelated
reasons -- was treated as representative.

### 19.3 Exact's failure is not merely a BPF LRU artifact

The plain-hash control separates implementation from capacity:

| budget | exact (LRU_HASH) | exact (plain HASH) |
|---|---|---|
| 16 KB | 42,240us | **18,112us** |
| 8 KB | 68,608us | 66,400us |
| 2 KB | 67,456us | 72,960us |

At 16 KB the plain hash is 2.3x better, so Section 18.1's LRU pathology
reaches scheduling outcomes and not only tracked counts. But at 8 KB and
below **both map types are inert**. A better eviction policy postpones
the failure by roughly one budget step; it does not prevent it. Exact
counting's collapse under a hard entry bound is real, not an artifact
to be engineered away.

### 19.4 Churning regime: exact never works at any budget

With respawning identities, `exact_penalty` is statistically identical
to `none` at every budget tested (110,976 vs 111,872us at 32 KB;
124,032 vs 130,880us at 8 KB). The sketch does act (63,680 -> 35,456 ->
25,248us as the budget shrinks) but goes blunt, degrading p50 to
flat-like levels at narrow widths.

So the two regimes give different answers and both belong in the paper:
where identities persist, the sketch extends the usable memory range
well below exact's floor; where they churn, neither structure produces a
scheduler worth shipping.

### 19.5 Width beats depth, replicated on real hardware

Fixed 8 KB, stable regime, varying only the geometry:

| geometry | p50 | p99 |
|---|---|---|
| sketch d2 w256 | 3,932us | **11,456us** |
| sketch d1 w512 | 3,936us | 20,448us |
| sketch d4 w128 | 4,432us | 19,968us |
| sketch d8 w64 | 9,680us | 16,928us |
| sketch d4 + rotate | 4,054us | 15,248us |
| exact_ref | 3,904us | 63,232us *(inert)* |

Phase 1's synthetic finding that width buys more accuracy than depth at
a fixed budget **replicates on the kernel**. Depth 2 is optimal here,
depth 8 is blunt (its p50 collapses to near-flat), and every geometry
except depth 8 beats exact counting at this budget.

## 20. The result, at n=20

All rows below are n=20, randomised condition order, stable-identity
workload unless stated. This supersedes the n=8 figures in Section 19.

### 20.1 The headline: equivalent quality at 4.3x less memory

| tracker | map | p50 | p99 |
|---|---|---|---|
| exact, 341 entries | 35.6 KB | 3,932us | 10,096us |
| **sketch, depth 2 width 256** | **8.3 KB** | **3,900us** | **10,144us** |

Statistically equivalent on both metrics -- medians identical to within
1%, p99 ranges overlapping -- at **4.3x less memory**. Against taking no
action (p99 ~65,000us) both are a ~6.4x tail improvement with the
median untouched.

This is the claim the project set out to test, and it holds.

### 20.2 Where each structure stops working

| budget | exact p99 | sketch p99 (default d4) |
|---|---|---|
| 32 KB | 10,096us (6.4x) | 9,952us (6.5x) |
| 16 KB | 37,312us (1.75x) | 11,088us (5.9x) |
| 8 KB | 62,336us **inert** | 17,984us (3.65x) |
| 2 KB | 65,024us **inert** | 13,248us, but **blunt** |

Exact discriminates at 32 KB, degrades at 16 KB, and by 8 KB is
statistically indistinguishable from `mechanism=none`. The sketch
discriminates down to 8 KB.

**Correction to an earlier reading.** Section 19 claimed the sketch
"works down to 2.3 KB". The geometry sweep shows that is too generous:
at 2 KB every configuration is blunt, with p50 collapsing to the
count-blind baseline's level (~10,900us, discrimination 1.01-1.10x). It
still improves the tail, but by taxing every task rather than by
distinguishing them -- which is the count-blind mechanism, not the
tracked count. The usable range is 4.3x, not 15x.

### 20.3 Geometry is load-bearing, not a footnote

At a fixed 8 KB, varying only the width/depth split (n=20):

| geometry | p50 | p99 |
|---|---|---|
| **d2 w256** | **3,900us** | **10,144us** |
| d1 w512 | 3,900us | 12,208us |
| d4 w128 (default) | 4,008us | 18,624us |
| d8 w64 | 9,504us | 15,344us (blunt) |
| d4 w128 + seed rotation | 4,224us | 16,704us |

**The default geometry is 1.8x worse than the best at identical
memory.** Phase 1's synthetic finding that width buys more accuracy than
depth replicates on the kernel, and choosing depth 2 rather than 4 is
the difference between the sketch matching exact counting and falling
well short of it.

The tradeoff inverts at 2 KB: deeper gives a better p99 but a worse p50,
because once every cell is saturated additional rows only spread uniform
inflation. That is another way of seeing that the structure has run out
of room rather than degraded gracefully.

### 20.4 Churning regime, confirmed: neither structure carries information

| budget | none | exact | sketch |
|---|---|---|---|
| 16 KB | 116,480us | 98,688us (overlapping) | 41,856us, p50 18,112us |
| 8 KB | 118,912us | 112,768us (inert) | 30,784us, p50 17,696us |

Exact is inert. The sketch does improve the tail with non-overlapping
ranges, but its p50 is 17,696us against `none`'s 3,984us -- it has
become blunt, achieving the improvement the same way the count-blind
baseline does. Neither structure carries usable information when
identities turn over.

So the memory result is bounded to the regime where the technique works
at all, and that boundary belongs in the claim rather than in a
footnote.

## 21. The headline, measured in a single matrix

Section 20 paired `exact @ 32 KB` (from one run) against
`sketch @ 8 KB depth 2` (from another). That is a cross-run comparison,
and this project has already learned at some cost that figures from
separate matrices are not safely comparable -- fixed condition ordering
made the same configuration read 21,664us or 14,000us depending on what
preceded it.

So the comparison was re-run with every condition carrying its own
memory budget, interleaved in one randomised matrix, n=20. The grid
includes `exact_8k` and `sketch_32k_d2` so it is complete in both
directions rather than showing only the pairing that flatters the claim.

| condition | memory | p50 | p99 | p99 range |
|---|---|---|---|---|
| none_ref_32k | 35.6 KB | 3,912us | 65,440us | 61,376-635,904 |
| flat_ref_32k | 35.6 KB | 11,040us | 16,864us | 15,696-17,952 |
| **exact_32k** | **35.6 KB** | **3,892us** | **10,144us** | 9,520-22,816 |
| exact_8k | 9.6 KB | 3,908us | 63,680us | 56,640-100,736 |
| sketch_32k_d2 | 32.3 KB | 3,892us | 10,064us | 9,360-22,496 |
| **sketch_8k_d2** | **8.3 KB** | **3,924us** | **11,344us** | 8,720-29,088 |

**The claim holds.** `sketch_8k_d2` and `exact_32k` differ by 12% on
median p99 with heavily overlapping ranges, and their p50s agree within
1%. No difference is demonstrated between a sketch at 8.3 KB and exact
counting at 35.6 KB: **4.3x less memory for the same scheduling
outcome**, now measured within a single matrix.

The grid is coherent in both directions, which is what makes it
believable rather than merely favourable:

- At 32 KB the two structures match each other (10,144 vs 10,064us), so
  the sketch is not winning through some artefact of being approximate.
- At 8 KB exact is inert (63,680us against `none`'s 65,440us), so the
  comparison is not flattered by an exact configuration that had
  already failed at its own budget.
- The count-blind reference sits at 16,864us with a p50 of 11,040us,
  confirming within this same run that both working conditions are
  discriminating rather than merely perturbing.

### What this does and does not establish

**Does:** at these budgets, on this workload, in the stable-identity
regime, approximate counting delivers the same scheduling outcome as
exact counting at roughly a quarter of the memory, and the comparison
survives being run as a single interleaved matrix.

**Does not:** *equivalence*, in the statistical sense. Overlapping
ranges mean no difference was demonstrated, which is weaker than
demonstrating no difference exists. A formal equivalence test with a
pre-declared margin has not been run, and the p99 ranges here are wide
on both sides (to 22,816us and 29,088us).

**Consistency caveat.** The sketch is slightly less stable than exact:
its p50 reached 8,104us in one run of twenty, where exact's worst was
4,184us. That is one repetition where the sketch partially lost
discrimination, and it is the kind of occasional failure a median
conceals.

