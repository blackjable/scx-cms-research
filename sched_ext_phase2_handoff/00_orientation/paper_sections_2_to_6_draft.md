# Paper Draft — Sections 2–6

Companion to `paper_abstract_and_section_1.md`, which supersedes the
earlier separately-drafted introduction -- that one framed the work as
proposing an approach, which no longer matches the outcome.

Phase 2 is complete and these sections carry its results. Remaining
`[NEEDS:` markers are author decisions, deferred hardware validation,
and one item blocked on LPC 2026 talks being published -- not
unfinished experiments.

---

## 2. Approach

### 2.1 Count-Min Sketch construction

We use a standard Count-Min Sketch (CMS) as the approximate counting
structure, parameterized by width `w` and depth `d`, giving a fixed
memory footprint of `w × d × sizeof(counter)` regardless of the number
of distinct task identities inserted. Each of the `d` rows uses an
independent hash function to map a task identity to one of `w` counter
slots; incrementing a key increments all `d` corresponding slots, and
querying a key's estimated count returns the minimum value across its
`d` slots — the standard CMS guarantee that this minimum never
underestimates the true count, with overestimation bounded
probabilistically by `w` and `d`.

**[RESOLVED]** Citation and formal error bound:

> G. Cormode and S. Muthukrishnan. "An Improved Data Stream Summary:
> The Count-Min Sketch and its Applications." *Journal of Algorithms*,
> 55(1):58–75, 2005.

Formal guarantee (Cormode & Muthukrishnan, 2005): given parameters
`ε > 0` and `δ ∈ (0,1)`, setting sketch width `w = ⌈e/ε⌉` and depth
`d = ⌈ln(1/δ)⌉`, the estimate `f̂(j)` for true frequency `f(j)`
satisfies `f(j) ≤ f̂(j)` always (never underestimates), and with
probability at least `1 − δ`:

  `f̂(j) ≤ f(j) + ε‖f‖₁`

where `‖f‖₁` is the sum of all frequencies (total event count). This
bound should be used directly in Section 3.1's parameter sweep design
— i.e., choose `w` and `d` from a target `(ε, δ)` rather than picking
arbitrary values, and report results in terms of the achieved `(ε, δ)`
for reproducibility.

In our prototype implementation (Python, validated in isolation before
any kernel integration — see Section 3.1), task identity is represented
as a string; in the eventual BPF implementation this would map to a
PID, TGID, or `comm`-derived identifier depending on which identity
notion best matches the churn pattern being tracked.

**[RESOLVED] Identity key: PID or TGID, not `comm`.** The candidates
were PID (churns fastest, arguably the wrong granularity), TGID, and
the `comm` string (coarser, survives PID reuse, but collides across
unrelated processes sharing a binary name). The decision was
deliberately deferred until Phase 2 could produce evidence, on the
grounds that a self-settable identity is a security choice rather than
only a granularity one.

The evidence (checklist item 27) settles it. Against a real kernel, a
targeted-collision attack on `comm` inflated a victim's estimated
wakeup count by +8,824% using 64 processes; the same attack against
PID produced no measurable effect, because a task cannot choose its own
pid and therefore cannot construct an identity that lands in a victim's
cells. The attack is not harder against PID, it is structurally
unavailable — a qualitative difference.

Two caveats: TGID was not measured directly, though being
kernel-assigned the same argument applies to it; and this choice
removes the *targeted* attack only. Untargeted volume flooding needs no
control over identity and damaged both candidates.

### 2.1.1 Reproducibility bug and fix [RESOLVED]

An early version of the Phase 1 implementation used Python's built-in
`hash()` for mapping task identity strings to sketch slots. This was
found, during rigor testing, to be a real reproducibility defect:
Python randomizes string hashing per-process by default
(`PYTHONHASHSEED`, a security feature since Python 3.3 against
hash-flooding denial-of-service attacks), meaning `hash("some_key")`
returns a *different* value on every new process invocation — even
with identical code and an identical simulation seed. Every result
generated before this was caught was only internally consistent
*within a single script invocation*; re-running the exact same
experiment in a new process would silently produce different absolute
numbers. This was not caught by code review — it was only discovered
by deliberately testing reproducibility across separate process
invocations (see Section 4, Test A).

**Fix**: replaced Python's `hash()` with an explicit, seeded
`blake2b`-based hash (see `sketch_lib.stable_hash`), which has no
process-level randomization and is deterministic across machines and
runs. Verified fixed by re-running the identical configuration in two
genuinely separate subprocesses and confirming identical output (see
Section 4, Test A) — the fix is not merely asserted, it is tested.

This is documented in detail because it is a general lesson, not a
one-off mistake specific to this project: **any simulation or
prototype using Python's built-in `hash()` on strings for anything
claiming reproducibility is silently broken unless `PYTHONHASHSEED` is
pinned or a stable hash function is used instead.** This should be
treated as a checklist item for any future Python-based prototyping in
this line of work, not just fixed once and forgotten.

### 2.2 Baseline: exact per-identity counters

As a baseline, we implement an exact counter using a hash map from task
identity to count. This represents the naive approach assumed implicitly
by existing sched_ext example schedulers, none of which currently
perform this class of historical behavioral tracking at all (see Related
Work, Section 2.4).

**[AMENDED after implementation]** This section originally specified the
map as having *no eviction*, so that memory would grow monotonically
with the number of distinct identities ever observed. The BPF
implementation uses `BPF_MAP_TYPE_LRU_HASH` instead, because a map that
never evicts either grows without bound or refuses new identities once
full, and neither is a fair baseline under process churn. The
consequence for the evaluation is that the exact tracker has a hard
entry bound and a capacity cliff rather than unbounded growth, which is
what Section 4.2.2 measures. A plain non-evicting hash was added later
as a control (`--plain-map`) and is reported in Section 4.2.4.

### 2.3 Integration into the sched_ext callback model

sched_ext schedulers implement policy via a fixed set of callbacks on
`struct sched_ext_ops`, invoked by the kernel at defined points in a
task's lifecycle (see `scx_simple.bpf.c` for a minimal reference
implementation). Wakeup-frequency tracking maps naturally onto two
existing callbacks:

- **`runnable`**: invoked when a task transitions from sleeping to
  runnable — i.e., a wakeup event. This is where the counter (sketch or
  exact) would be incremented.
- **`quiescent`**: invoked when a task becomes non-runnable (blocks,
  exits). Could be used to finalize or decay per-window statistics.

**[RESOLVED] This integration is now implemented** as `scx_cms`
(`scheds/experimental/scx_cms/` in the scx tree), and runs on Fedora 44,
kernel 6.19. The CMS is a `BPF_MAP_TYPE_ARRAY` counter table sized at
load time to exactly `2 x width x depth` cells, with the increment
wired into `runnable` as designed here. Verifier constraints did not
require restructuring the hashing logic; the loops are bounded by the
configured depth and width, and the FNV-1a construction ports directly.

Two things did have to change, neither anticipated here. The scheduler
could not fork `scx_simple.bpf.c` because that file no longer exists in
the scx repository — the C schedulers were moved out to
`scx-c-examples`, so the policy was recovered from repository history
instead. And window rotation for the *exact* counter could not clear a
hash map wholesale, since iterating and deleting every entry from a BPF
program is not something the surrounding codebase does; entries are
rolled forward lazily against an epoch instead, which is observably
equivalent. The sketch, having a fixed table, does clear for real.

### 2.3.1 Forgetting mechanism: design history [RESOLVED]

A vanilla Count-Min Sketch never forgets — every increment is
permanent (confirmed against existing literature: Redis's own writeup
on CM sketch states plainly that "CM sketch never forgets," contrasted
with decay-based alternatives). Under process churn, this is a real
correctness problem, not a cosmetic one: without a forgetting
mechanism, both the sketch and a naive exact counter would answer
"what has this task's LIFETIME wakeup total been since boot," not "is
this task CURRENTLY a heavy waker" — the latter being the actually
useful signal for a scheduling decision. This gap was identified via a
direct challenge during project review and is documented here in full
because the first fix attempted was itself flawed in an instructive
way.

**First attempt (rejected): periodic global halving.** The initial fix
implemented the same decay mechanism TinyLFU uses for its CMS-based
frequency tracking — periodically halve every counter. Running this
surfaced a subtle problem: halving every period implements
**exponential decay**, which produces a geometrically-weighted sum of
*all* history (`true_per_period × (1 + ½ + ¼ + ...) → 2 × true_per_period`
at steady state), never fully forgetting old data — it only
down-weights it. This is mathematically correct behavior for that
mechanism, but it means comparing the decayed estimate against a raw
"this period's count" ground truth is comparing against the wrong
target entirely, and produces a misleading, non-zero "error" for both
the sketch AND the exact-counter baseline, even though the exact
counter was tracking its (geometrically-weighted) target correctly.
This was caught empirically by running the corrected prototype and
noticing both structures converged to a stable value roughly double
the true per-period count, rather than by reasoning about it in
advance — worth stating plainly as an example of why running an
experiment, even a synthetic one, surfaces real design flaws that
pure design review can miss.

**Final design (implemented): rotating dual-buffer (tumbling window).**
Two buffers — "current" and "previous" — are maintained. All inserts
go to "current." A query sums current + previous (for the sketch: the
underlying tables are summed cell-wise before the standard min-query
is applied — mathematically exact, since two Count-Min Sketches built
with identical hash functions can be merged by summing their tables,
equivalent to having inserted all events into one sketch). At each
window boundary, "previous" is discarded, "current" becomes
"previous," and a fresh "current" begins.

This gives an unambiguous ground truth (current+previous holds exactly
the true event counts from the current and prior window — a hard,
statable number, not an infinite geometric series), at the cost of 2x
memory instead of 1x (still fixed and bounded — a larger constant, not
unbounded growth) and a discontinuity at rotation boundaries (a real
tradeoff versus exponential decay's smoothness, stated here rather
than hidden).

**Validated result (Python prototype, `cms-prototype/experiment.py`):**
at `width=256, depth=4`, ~5,000 churn identities per window (each
generating 1–20 wakeup events), the exact-counter baseline shows
**zero error** against the true window count (as expected — no
approximation involved), while the sketch shows a consistent,
stable **~35% overestimate** (average +357 error on a true value of
1,000, measured over epochs 2–19 to exclude the partial-window edge
case at epoch 0). This is a real, reproducible accuracy cost of
approximation at these specific parameters — not measurement noise —
and is the correct starting point for the parameter sweep described in
Section 3.1, which should search for a `(width, depth)` combination
achieving an acceptable accuracy/memory tradeoff using the formal
`(ε, δ)` bound from Section 2.1.

Citations for the design alternatives considered and rejected/adopted:

- Papapetrou, Garofalakis, Deligiannakis. "Sketch-based Querying of
  Distributed Sliding-Window Data Streams" (ECM-Sketch) — per-counter
  sliding-window sub-structures; more theoretically precise than the
  approach adopted here, but adds real per-counter overhead that works
  against the fixed-minimal-footprint goal of this project. Considered
  and set aside for that reason.
- Einziger, Friedman, Manes. "TinyLFU: A Highly Efficient Cache
  Admission Policy," *ACM Transactions on Storage*, 13(4), 2017 —
  source of the (ultimately rejected, for this project's ground-truth
  needs) periodic-halving approach.
- A patent for SSD hot/cold data tiering uses dual Count-Min Sketches
  with a temporal-proximity decay function for tier-promotion
  decisions — a real-world precedent for the general
  "approximate-frequency-plus-recency drives a resource allocation
  decision" pattern, structurally similar to this project's use case.

### 2.4 Related work

**[RESOLVED]** An informal scan first found two starting points, both
later confirmed by a proper literature search rather than left as
web-search impressions: no existing `sched_ext` scheduler applies
probabilistic/approximate data structures for behavioral tracking (see
`sched_ext_embedded_research.md` for the specific searches run), and a
proposed LPC 2026 talk ("Amortizing CPU wakeup costs with lazy wakeups,"
Samuel Wu, Google) addresses a related but distinct problem — detecting
wakeup-heavy tasks to reduce idle-transition energy cost — without, as
far as the published abstract indicates, addressing the memory-scaling
problem of the tracking mechanism itself. [NEEDS: revisit after LPC 2026
(5–7 Oct) once slides/recording are published, to properly cite or
differentiate — this is the one part of this section still blocked on an
event outside the project's control, not on further search effort.]

The literature search itself (see search queries logged in project
history) confirms and extends both starting points. Findings:

- Bloom filters and Count-Min Sketches are well-established in
  **networking** (flow tracking / heavy-hitter detection in data-plane
  telemetry — e.g. Cormode et al.'s own follow-on work, and surveys
  such as "Compact Data Structures for Network Telemetry") and
  **database systems** (Cassandra, HBase use Bloom filters for SSTable
  existence checks) for analogous "track approximately, bounded
  memory" problems.
- **No paper or system was found applying Count-Min Sketch or Bloom
  filters to CPU scheduling decisions specifically** — this appears to
  be genuinely unaddressed territory, consistent with the earlier
  finding that no sched_ext scheduler does this either.
- **Closest conceptual precedent found: TinyLFU** (Einziger, Friedman,
  Manes — "TinyLFU: A Highly Efficient Cache Admission Policy"), which
  uses a Count-Min Sketch to estimate item access frequency for
  **cache admission/eviction decisions**. This is a strong analog worth
  citing directly: it is the same technique (CMS-based frequency
  estimation) applied one layer over — to a different resource
  allocation decision (cache admission) rather than CPU scheduling —
  and demonstrates the general pattern ("use CMS to make an approximate
  resource-allocation decision under memory constraints") is
  established and successful elsewhere, even though scheduling itself
  is untouched. This paper's contribution can be framed as extending
  the TinyLFU-style pattern to a new domain (CPU scheduling) rather
  than inventing the pattern itself — a more honest and better-situated
  framing than claiming pure novelty of technique.
- Citation: Einziger, G., Friedman, R., and Manes, B. "TinyLFU: A
  Highly Efficient Cache Admission Policy." *ACM Transactions on
  Storage*, 13(4), 2017.

---

## 3. Methodology

### 3.1 Phase 1: Algorithmic validation (synthetic, no kernel)

Before kernel integration, the sketch-vs-exact tradeoff was validated
in isolation using a Python simulation (see accompanying
`cms-prototype/` code). This simulates:

- `N` short-lived "churn" task identities, each generating a random
  number of wakeup events in a fixed range, standing in for embedded
  process churn.
- One persistent "latency-sensitive" task identity generating a fixed
  number of wakeup events, representing the task whose accurate
  tracking matters most.

Memory footprint (sketch: fixed `w × d × 4` bytes; exact: grows with
distinct identities) and estimation accuracy for the latency-sensitive
task are recorded.

**Result (rotating dual-buffer, corrected methodology)**: at
`w=256, d=4`, ~5,000 churn identities per window, over 20 simulated
windows: the exact-counter baseline achieved **zero error** against
the true window count. The sketch showed a stable, reproducible
**~35% overestimate** (average +357 error on a true value of 1,000,
epochs 2–19). Memory: sketch fixed at 8,192 bytes (2x single-buffer
size, per the rotating-window design); exact counter's real, measured
footprint (see Section 4.1's memory-measurement audit note — the
figure here was originally computed with a since-corrected guessed
constant) at ~537,901 bytes at steady state (65.7x the sketch's
footprint) — bounded now by per-window churn rather than growing
unboundedly with lifetime churn, since the windowing scheme discards
data older than one rotation.

This superseded an earlier single data point (61x memory savings [also
later corrected to 65.7x — see Section 4.1], 37% accuracy
overestimate) that used a flawed non-windowed methodology — see
Section 2.3.1 for the full design history, including a rejected
exponential-decay approach that produced misleading accuracy numbers
against the wrong ground truth.

[RESOLVED] This was one data point rather than a result, and a proper
methodology required sweeping `w`, `d` and `N` and reporting curves. The
width sweep is in Section 4.1, the joint width x depth sweep at fixed
memory in Section 4.1.3, and both replicate on the kernel in
Section 4.2.2's geometry table.

**[PARTIALLY ANSWERED]** Whether accuracy loss is harmful requires
connecting it back to a real scheduling-outcome metric, which checklist
item 28 has since done directly: across every configuration tested
(default and steep penalty, small and large sketch, 4 and 8 CPUs, high-
and low-rate victims), corrupting the tracked count by orders of
magnitude produced no detectable change in victim scheduling latency.
That is evidence toward "tolerable" at the scales tested, not toward
"harmful."

[NEEDS: this still does not amount to a numeric threshold, and setting
one is an author judgment call this document should not make on its own
behalf — the data now available (item 26's accuracy figures, item 28's
outcome-connection result, Section 9.7's finding that real execution
shows meaningfully more error than Phase 1's synthetic model predicted)
is what a threshold decision should be made from, not a substitute for
making it.]

### 3.2 Phase 2: Kernel/BPF integration and hardware environment

[COMPLETE: the environment exists, the scheduler loads and runs in it
(checklist items 2, 3, 12), and Section 4.2 carries the
scheduling-quality results.]

- Development on a Fedora Linux VM, chosen because Fedora ships a
  sched_ext-enabled kernel (`CONFIG_SCHED_CLASS_EXT`) by default as of
  2026, avoiding a custom kernel build. Confirmed in practice: Fedora 44,
  kernel 6.19, `/sys/kernel/sched_ext` present, custom scheduler attaches
  and unregisters cleanly.
- The VM is managed by **Lima**, not UTM as originally planned. UTM's
  GUI-driven VM creation, paste-blocked console and manual SSH/sudo setup
  made it unworkable for scripted use; Lima is CLI-only, provisions SSH
  and passwordless sudo via cloud-init, and mounts the host repo into the
  guest directly. This is a tooling change with no bearing on the
  experimental design — the guest kernel and architecture are the same
  either way.
- The "resource-constrained device" condition is simulated via a
  memory-capped cgroup (Linux cgroup v2, `memory.max`), rather than
  physical embedded/mobile hardware, on the basis that the hypothesis
  under test concerns memory-footprint behavior of the tracking data
  structure itself, not CPU-architecture-specific effects.
**[RESOLVED]** Justification for a memory-capped VM as an adequate proxy
for real embedded hardware, split into what it supports confidently and
what it does not:

*The memory-footprint claims* (fixed sketch size vs. a growing exact
counter; the 8,192-byte figure at the reference parameters) are
genuinely architecture-independent. They follow from the data
structures' own layout — width × depth × 4 bytes for the sketch, a hash
map entry per distinct identity for the exact counter — not from
anything ARM, x86, or a specific device's memory controller does
differently. A `cgroup v2` `memory.max` ceiling is, if anything, a more
rigorous instrument than physical hardware for this claim: it gives a
precise, repeatable, sweepable limit, where a specific embedded board
gives one fixed number you cannot vary between runs. The VM runs a real
Linux kernel with genuine `sched_ext` support, so the scheduling
decisions and BPF verifier constraints under test are real, not
approximated — nothing here is emulated.

*The accuracy and timing-sensitive claims are a different matter*, and
this project's own Phase 2 work found a reason for real caution that
wasn't visible when this justification was first planned: Section 9.7
found that real OS scheduling contention among many concurrent processes
measurably changes the sketch's reported error (a 3x longer window
dropped mean overestimate from +277.3% to +98.9%, and neither matched
Phase 1's synthetic +31.9%). That is a timing-and-contention effect, not
a memory-footprint one, and it means accuracy figures measured on this
4-CPU VM should not be assumed to transfer unchanged to a real embedded
device with fewer, weaker cores — contention could plausibly be worse
there, not better. The memory-footprint argument for VM-as-proxy stands;
the accuracy-figure argument does not extend as far as originally
assumed, and any reporting of accuracy numbers should say so rather than
imply they generalize as cleanly as the memory numbers do.
- [NEEDS: if reviewer/audience credibility requires it, a follow-up
  validation pass on real embedded hardware (e.g. Raspberry Pi) once
  the VM-based result holds — deferred, not yet scheduled.]

### 3.3 Workload and evaluation metric

**Baseline strategy [RESOLVED — see rationale below]**: an earlier
version of this section planned only a single, narrow comparison
("same scheduler logic, exact counters instead of sketch"). This is a
valid *isolation* test — it isolates whether the sketch approximation
specifically degrades outcomes — but does not by itself answer whether
this approach is any good in absolute terms, or how it compares to
what the field would recognize as a fair baseline. Confirmed via
direct research into current sched_ext evaluation practice (see
citations below): a credible evaluation needs multiple baseline tiers,
not one:

1. **Default/mainline baseline** — stock EEVDF (the scheduler nearly
   every real system runs), unmodified. Answers "is a custom scheduler
   worth it at all," independent of this project's specific approach.
2. **Reference sched_ext baseline** — `scx_simple`, unmodified (the
   minimal reference scheduler already studied in Section 2.3).
   Answers "does this add anything over the simplest possible
   sched_ext scheduler."
3. **Isolation baseline** (the originally-planned comparison) — the
   same custom scheduler with exact per-identity counters instead of
   the sketch. Answers "does the approximation itself cost anything,"
   holding everything else constant.
4. **Production sched_ext baseline** — an established, deployed
   scheduler solving a related problem, e.g. `scx_rusty` or `scx_lavd`
   (SteamOS's latency-aware scheduler, already noted as relevant in
   Section 2.4). Answers "how does this compare to what people
   actually run today for latency-sensitive workloads," not just to
   this project's own internal variants.

5. **Count-blind negative control [ADDED AFTER ROUND 2 -- the most
   important tier, and the one this list originally lacked]** -- the
   same custom scheduler applying a vtime perturbation of equal
   strength that ignores the tracked count entirely.

   Tiers 1-4 all vary *the scheduler*. None of them varies *only
   whether the signal is used*, and so none can separate "tracking
   wakeup frequency helps" from "perturbing vtime helps." That gap is
   not hypothetical: round 2 produced a 6.8x improvement against the
   isolation baseline that this control subsequently reproduced almost
   entirely (Section 4.2). Every mechanism does something besides the
   thing being studied, and the correct baseline for "does the signal
   help" is the same intervention without the signal -- not a different
   scheduler.

**Evaluation metric [CORRECTED AFTER ROUND 2]**: this section
originally specified tail latency (p99) as the outcome measure, in line
with standard practice. That specification was wrong, and following it
alone would have produced the opposite conclusion.

A count-blind penalty and a count-proportional one reach statistically
indistinguishable p99. They are separated at the *median*: the
count-blind version taxes every task including the latency-sensitive
one, while the count-proportional version leaves the median untouched.
Tail latency alone cannot distinguish a discriminating policy from a
blunt one, because degrading every task uniformly also compresses the
tail.

The evaluation therefore reports p50 and p99 together, and treats a
tail improvement accompanied by median regression as a cost, not a win.
See Section 4.2.

**Standard tooling, not a bespoke metric**: rather than inventing an
ad-hoc evaluation harness, use the tools the sched_ext/kernel
community already treats as credible:

- **`schbench`** (Chris Mason, Meta/Facebook, 2016) — purpose-built to
  measure wakeup-to-execution latency distribution under a simulated
  server workload. This is a direct, standard-tool match for this
  project's own tracked signal (wakeup frequency), not just a generic
  latency benchmark — using it strengthens the paper's connection
  between what Phase 1 measured and what Phase 2 evaluates.
- **`cyclictest`** — standard scheduling-latency measurement tool,
  commonly reported alongside schbench.
- **`hackbench`** — standard scheduler throughput/stress test (pairs of
  threads/processes communicating via sockets or pipes), useful for
  confirming the new scheduler doesn't regress general throughput even
  if it improves the targeted latency-sensitive-task metric.

**Precedent found for this exact methodology**: a 2026 paper
evaluating an LLM-agent-driven custom scheduler framework ("Towards
Agentic OS," arXiv:2509.01245) uses precisely this multi-tier
approach — comparing generated/configured schedulers against default
EEVDF *and* against established production sched_ext schedulers
(`scx_rusty`, `scx_bpfland`, `scx_layered`), using schbench, and
reporting results as **relative multipliers** (e.g. "2.11× better P99
latency... versus EEVDF") rather than isolated absolute numbers. This
paper's evaluation should follow the same reporting convention —
every Phase 2 result should be stated relative to at least the default
EEVDF baseline, not just relative to this project's own other variant.

**Remaining open questions** (workload representation and specific
metric still need a decision, now properly scoped against the above):

- What synthetic or real workload represents the "latency-sensitive
  task" — an audio callback simulation, or a synthetic periodic task
  with a hard deadline? [NEEDS: decision. `rt-app` — a flexible,
  JSON-configured workload modeling tool cited as suitable for
  exactly this kind of custom scenario without hand-coding it — is
  worth using here rather than a hand-rolled synthetic task.]
- What is the primary scheduling-quality metric — deadline miss rate?
  P99/P999 wakeup latency (directly available from schbench)? Frame
  drop rate (if using a display/audio-pipeline-style workload)?
  [NEEDS: decision, and this should tie back to the accuracy-tolerance
  question from 3.1 — i.e., how much sketch error is tolerable should
  be defined in terms of how much it moves THIS metric, not in the
  abstract.]

---

### 3.4 Implementation validation

The strongest objection to a comparison like this one is that it
measures one author's implementation against the same author's other
implementation rather than measuring the algorithms. Every
implementation concern found on review is an instance of it: a hash
that may under-mix, a map type whose behaviour at small sizes is its
own, a value encoding that spends bytes on bookkeeping. The response is
not to argue the implementations are sound but to check each against an
independent reference before comparing them.

**The sketch was checked against a model.** The BPF hash was
reimplemented exactly outside the kernel, the measured workload driven
through it, and the resulting estimates compared with what the kernel
reported. In the stable-identity workload they agree: predicted
overestimate 1.00x / 1.23x / 3.59x at widths 2048 / 128 / 32 against
1.00x / 1.19x / 2.85x measured. The kernel implements the same sketch
the model does.

**The hash was checked against a better one.** Every width used is a
power of two, so `h % width` keeps only FNV-1a's least-mixed bits.
Re-running the model with a final avalanche step costs at most 13% less
overestimate at the narrowest width and 1-5% elsewhere. The concern is
real and the hash should be fixed; it does not move any result here.

**The identity population was measured, not assumed.** An earlier
version of this validation assumed the workload's identity count and
was wrong by a factor of four, which invalidated the accuracy figures
derived from it. The scheduler now counts distinct insertions into a map
large enough that nothing evicts, so the figure describes the workload
rather than the tracker. Across three runs
(`results/raw/identity-turnover-n3.txt`): the stable workload carries
304-335 distinct identities (about 200 of them system processes) and
mints ~2 per second; the churning workload mints 377-385 per second for
roughly 760 live per query span.

These figures were first reported as 329 stable, 413 per second and 826
live, from a run whose output was not archived. The re-measurement above
agrees on the stable total and puts the churning rate about 8% lower,
outside the spread of three consecutive runs. The corrected figures are
used throughout; the ratio between regimes, which is what the argument
rests on, moves from 103x to 190x.

**What this validates.** With the measured population the stable regime
agrees with the model (~392 predicted against 366.7 measured,
accounting for the fact that every wakeup triggers a query and the mean
is therefore mass-weighted).

The churning regime initially did not -- the model predicted ~64
against 220 measured -- and the discrepancy was resolved by
instrumenting the distribution rather than by further inference. A
histogram of tracked counts shows the regime is **bimodal**: most
queries fall in the 10-99 bucket exactly as the model predicts
(101,606 of them at 32 KB), while a minority of long-lived identities
carry counts in the thousands (22,209 in the 1k-10k bucket) and drag
the mean upward. The model counted only the churning tasks and ignored
the persistent ones.

The methodological point is small and practical: a mean tracked count
is not a useful summary of a workload with mixed identity lifetimes,
and three rounds of inference were spent on a number that one histogram
answered.

## 4. Results

Phase 1 (synthetic, no kernel) results now exist in full, across four
rounds of testing: an initial single-point measurement, a corrected
version after a methodology fix (Section 2.3.1's windowing redesign),
a battery of rigor tests addressing reproducibility and worst-case
behavior, and a reproducibility/correctness verification pass. Phase 2
(kernel/BPF, real scheduling-quality outcomes) is complete and is
reported in Section 4.2 onward.

### 4.1 Accuracy/memory tradeoff under normal (uniform) conditions

**[CORRECTED — see audit note below]** At `width=256, depth=4`, ~5,000
churn identities per window (1–20 wakeups each), across 30 random
seeds: the exact-counter baseline achieved zero error against ground
truth (as expected — no approximation). The sketch showed a **stable,
low-variance ~31.9% overestimate** (mean +31.9%, standard deviation
0.65% across seeds) — confirmed via dedicated multi-seed testing to be
a reproducible property of these parameters, not an artifact of an
unlucky random seed.

Memory: sketch fixed at 8,192 bytes (2x single-buffer size, per the
rotating-window design in Section 2.3.1); exact counter's real,
measured footprint (see the second audit note below) at ~537,901
bytes at steady state under this churn level — **65.7x** the sketch's
footprint.

**Parameter sweep (width)**, holding depth and churn level fixed:
accuracy improved as width increased, tracking the theoretical
`ε = e/w` bound closely and staying below the theoretical maximum at
every width tested — direct evidence the implementation behaves as
Count-Min Sketch theory predicts, with no correctness anomalies:

| Width | Memory (B) | Empirical error | Theoretical max error |
|------:|-----------:|-----------------:|----------------------:|
| 64    | 2,048      | +145.8%          | 429.3%                |
| 128   | 4,096      | +68.1%           | 214.6%                |
| 256   | 8,192      | +32.0%           | 107.3%                |
| 512   | 16,384     | +14.0%           | 53.6%                 |
| 1024  | 32,768     | +7.1%            | 26.8%                 |
| 2048  | 65,536     | +3.0%            | 13.4%                 |

Note the memory-savings-vs-exact-counter ratio is not fixed — it
shrinks as width grows to reduce error (e.g., ~8.2x at width=2048
versus 65.7x at width=256, against the same exact-counter baseline).
**The accuracy/memory tradeoff is a curve, not a single number**, and
any reported headline figure (e.g., "65.7x memory savings") must be
paired with its corresponding accuracy figure to be meaningful.

**SECOND AUDIT NOTE (memory measurement correction)**: a further
"savage" audit pass (`savage_audit.py`), specifically hunting for
remaining guesses/approximations rather than known bugs, found that
`RotatingExactCounter.memory_bytes()` had used a **guessed** constant
("~50 bytes per dict entry") since this project began, never actually
measured. Direct measurement via `sys.getsizeof` on an isolated
5,000-entry dict showed the guess was wrong by 2.13x (real: ~107
bytes/entry). **Important methodological correction to this
correction**: extrapolating that 2.13x factor directly onto the
headline ratio (implying "61x → ~130x") would itself have been an
error — the isolated microbenchmark was not representative of the
actual simulation's dict fill state (Python dict memory includes
non-linear, load-factor-dependent table overallocation, so isolated
and in-context measurements of "same" entry counts can differ). The
correct approach, used here, is to re-measure the ACTUAL simulation
end-to-end with the fixed method, not extrapolate from an isolated
proxy — this gives the real, modest correction (61x → 65.7x) reported
above, not the dramatically larger number a naive extrapolation would
have produced. This methodological point — verify end-to-end, don't
extrapolate from a simplified proxy — is stated explicitly because the
error very nearly propagated into this paper before being caught.
Also note explicitly: this measurement reflects Python dict overhead
as a proxy for prototype-internal comparison, not a literal prediction
of a real BPF hash map's memory cost in the eventual kernel
implementation.

**AUDIT NOTE (post-hoc correction)**: during a dedicated bug-hunting
pass across all experiment scripts, it was discovered that the numbers
originally reported in this section (37.1% headline error; a width
sweep table with different values; adversarial-distribution numbers in
4.1.1 below) were generated using an early version of `sketch_lib.py`
that predated the hash-randomization reproducibility fix (Section
2.1.1) — i.e., these figures were computed with the OLD, buggy,
non-reproducible Python `hash()`, and were never re-run after the fix
was introduced. This was caught by systematically re-running every
script's core measurement under the current, corrected implementation
and comparing against previously reported values, rather than assuming
a fix applied to one file (`sketch_lib.py`) had been re-validated
everywhere it was used — the same category of error as the
`experiment.py` drift bug found earlier (Section 2.1.1), but this time
affecting reported *scientific results* rather than a demo script.
**The theoretical max error column was ALSO corrected during this
pass**: it previously used only one epoch's L1 norm, but the rotating
dual-buffer merge (current+previous summed cell-wise) is mathematically
equivalent to a single sketch that ingested both epochs' events —
verified empirically by confirming a table built by merging two
independently-populated same-seed sketches is byte-for-byte identical
to a table built by inserting both epochs' events into one sketch from
the start. The correct theoretical bound therefore uses a doubled L1
norm; this was previously understated by roughly 2x.

**Reassuring finding**: despite the exact numbers changing (typically
by 4-8 percentage points), **every qualitative conclusion drawn from
the original (stale) numbers still holds** under the corrected values:
error still tracks the theoretical bound closely and stays below it at
every width, still roughly halves as width doubles, and the overall
"real but tunable accuracy cost" characterization of Section 4.1 is
unchanged. This is worth stating plainly rather than either
overclaiming ("nothing was wrong") or underclaiming ("everything is
invalid") — the specific numbers were wrong and are now fixed; the
scientific story they were telling was not.

### 4.1.1 Adversarial and worst-case behavior

Three further tests probed whether the favorable Section 4.1 numbers
generalize beyond the uniform-random churn assumption used to produce
them. **These figures are also corrected per the audit note above.**

**Skewed (more realistic) distribution**: 5% of churn identities heavy
(100–200 wakeups), 95% light (1–2) — a closer approximation of real
workloads, where a few processes dominate activity. Result: **error
was slightly LOWER than uniform** (+0.8% vs +4.7% at a smaller
matched-scale configuration), suggesting realistic skew is not
inherently harder for the sketch than uniform noise. (Original,
pre-correction figures: +6.4% vs +7.5% — same qualitative relationship,
different exact values.)

**Volume-flooding adversarial distribution**: 5x the identity count,
all at maximum wakeup volume, approximating a worst case by
maximizing total inserted volume (the actual driver of sketch error
per the theoretical `ε‖f‖₁` bound) without any knowledge of the hash
function. Result: **severe degradation — +60.2% error**, roughly 13x
worse than the matched-scale uniform case (+4.7%). This alone was
enough to falsify any claim that the Section 4.1 result generalizes
safely across churn patterns. (Original, pre-correction: +68.2% vs
+7.5% uniform — same conclusion, different exact magnitude.)

**Targeted-collision attack (white-box)**: using knowledge of the hash
function and per-row seeds, churn task identities were deliberately
constructed to collide with the latency-sensitive task's slot in each
row independently (finding a single key colliding in *all* rows
simultaneously is ~1-in-`width^depth` and computationally infeasible
by design — this is precisely what the `depth` parameter exists to
prevent). Result: **+440.6% error** — more than 5x the true value,
dramatically worse than either the uniform or volume-flooding cases.
(This specific test, unlike the three above, was built in
`strict_tests.py` *after* the reproducibility fix was already in
place, and was re-verified as part of this audit pass to confirm it
did not require correction — it did not.)

This finding materially changes the scope of any claim this work can
make: **the approach's accuracy is only well-characterized under
cooperative/non-adversarial churn.** If task identity strings are
influenceable by an untrusted or malicious co-located process (a
concrete risk for `comm`-string identities, which processes can set
themselves — see Section 2.1's still-open identity-key decision), this
is a real, demonstrated weakness, not a theoretical tail risk.

### 4.1.2 Correctness and reproducibility verification

Two additional checks, run independently of the accuracy tests above,
verify the implementation itself is sound:

- **Reproducibility**: an earlier implementation used Python's
  built-in `hash()`, which is randomized per-process by default
  (Section 2.1.1) — meaning every result reported above would have
  been silently non-reproducible across separate runs until this was
  caught and fixed. Verified fixed by confirming identical output
  across two genuinely separate process invocations of the same
  configuration.
- **Formal invariant (never-underestimate guarantee)**: Count-Min
  Sketch's one formal correctness guarantee — `estimate(key) ≥
  true_count(key)`, always — was checked directly against the exact
  counter across 80 (seed, epoch) combinations. **Zero violations
  found.** This had not been explicitly checked in any test prior to
  this verification pass; earlier tests only examined overestimation
  magnitude, silently assuming rather than confirming the guarantee
  held.

### 4.1.3 Follow-up investigation: width/depth tradeoff, mitigation, and hash choice

Three further tests, addressing gaps identified by the 4.1.1/4.1.2
findings themselves:

**Width×depth tradeoff at fixed memory.** Only width had been swept
previously, with depth held fixed. Testing all width/depth pairs
multiplying to a constant total slot count (2,048) confirms the
theoretical prediction directly: a wide-shallow configuration
(width=2048, depth=1) achieves 1.2% error, while a narrow-deep
configuration at the *same total memory* (width=128, depth=16)
achieves only 8.7% — a 7x difference. This matches Count-Min Sketch
theory precisely: width (`ε = e/w`) controls error *magnitude*, while
depth (`δ = e^-d`) controls the *probability* of an unusually bad draw
without directly reducing magnitude when a bad draw occurs. **Practical
implication: for a fixed memory budget, prioritizing width over depth
improves average-case accuracy.**

**Seed rotation as a defense against the targeted-collision attack
(4.1.1).** Since the rotating dual-buffer scheme already discards and
recreates a buffer every window, generating a *fresh* random hash seed
on each rotation was tested as a natural, near-free mitigation: if an
attacker's pre-computed colliding keys are only valid for a specific
seed, rotating the seed should render a static attack stale. Result:
**partial mitigation only.** The attack achieved +400% error in the
window it targeted (consistent with Section 4.1.1); replaying the same
stale keys after seed rotation still produced +200% error, not the
near-zero result a full mitigation would show. The mechanism is fully
explainable: the rotating window's "previous" buffer retains the prior
window's (already-poisoned) data for exactly one additional window
regardless of seed rotation, so the attack's damage persists via that
carry-over even though the *new* seed prevents *further* stale-key
damage. **Seed rotation reduces but does not eliminate the
vulnerability**; whether the effect fully clears by two windows out
was not tested and remains open.

**Hash function comparison (blake2b vs. FNV-1a).** The reproducibility
fix (Section 2.1.1) used `blake2b`, which is cryptographically strong
but far too computationally expensive for a real BPF hot-path hash.
FNV-1a — simple, fast, and a realistic stand-in for what an actual
kernel implementation would likely use — was tested under the
identical targeted-collision attack methodology to check whether a
weaker/faster hash is more vulnerable.

**A methodological note worth documenting in full**: the first attempt
at this comparison produced a striking, suspicious result — FNV-1a
showed **0% error** under the identical attack that produced +400% for
blake2b, suggesting FNV-1a might be immune. Per this project's
established practice of treating unexpectedly favorable results with
suspicion rather than accepting them, the "colliding" keys found for
FNV-1a were directly verified against the hash function — **they did
not actually collide**. The root cause was a genuine bug: the
collision-search helper function (`find_colliding_keys`, originally
written only for the blake2b test) hardcoded `blake2b` internally
regardless of which hash function the target sketch actually used,
so the "FNV-1a attack" was silently searching for blake2b collisions
and inserting them at effectively random FNV-1a slots — a broken,
no-op attack, not a demonstration of FNV-1a's security. After adding
an explicit `hash_fn` parameter and re-verifying the fix produces
genuine collisions before re-running: **corrected result — both hash
functions show identical +400% error.** This indicates the
targeted-collision vulnerability is a **structural property of
Count-Min Sketch under a knowledgeable adversary**, independent of
which specific hash function is used, and switching hash functions
for BPF performance reasons would not by itself mitigate this risk.

This bug is reported in the same detail as the finding it could have
corrupted deliberately: an unusually favorable experimental result
should trigger *more* scrutiny of the test itself, not less, and this
is a direct instance of that principle catching a real error before it
became a false claim in this paper.

### 4.1.4 Attack persistence and a stronger mitigation

Two further tests extend the seed-rotation finding (4.1.3) to ask how
long a single attack's damage persists, and whether a stronger active
defense can do better than passive rotation alone.

**Multi-window decay.** An attacker fires once, in a single window,
then goes silent. Tracking error across five subsequent windows with
seed rotation active: window 0 (attack), +400%; window 1 (stale
carry-over via the "previous" buffer), +200%; window 2 onward, **0.0%
exactly**. This confirms precisely the mechanistic model proposed in
4.1.3 — the rotating dual-buffer scheme carries poisoned data forward
for *exactly* one additional window, no more, no less, and fully
self-heals from a one-shot attack after that.

**Anomaly-triggered hard reset.** Rather than passively waiting for
natural rotation, this tests detecting an anomalous spike (query result
`>3×` an expected baseline) and immediately hard-resetting *both*
buffers — discarding the poisoned window entirely rather than letting
it become "previous" via a normal rotation. Result, averaged over 10
seeds: **without mitigation, +200.0% error (window N+1); with the hard
reset, +0.0% error, exactly, with zero variance across seeds.**

**A second methodological note, again caught by distrusting a
surprising result**: the first implementation of this mitigation
produced a nonsensical result — the "mitigation" appeared to make
things *worse* (+500% vs. the unmitigated +200%). Investigating
revealed a real bug: the code manually reset the `previous` buffer,
but then called the standard `rotate()` immediately after, which
unconditionally executes `previous = current` — silently overwriting
the manual reset with the *still-poisoned* current buffer, making the
"fix" a no-op that also happened to consume an extra random seed draw,
producing noisy, meaningless output attributed to a single untested
seed. Fixed by implementing a genuine hard reset that bypasses
`rotate()` entirely and assigns fresh buffers to both `current` and
`previous`, and by averaging over 10 seeds rather than trusting one
draw — standard practice this project had already established, but
which was skipped in the first pass at this specific test.

**Important caveat, stated rather than glossed over**: this test uses
the *known true value* as the anomaly-detection reference point, which
a real implementation would not have access to — a real system needs a
rolling baseline estimate, which introduces its own error and
false-positive/false-negative tradeoffs not modeled here. This result
demonstrates the *mechanism* can work in principle, not that it is a
validated, deployable real-world defense. Additionally, a hard reset
discards all historical data on any detected spike, including
legitimate (non-attack) traffic bursts — a real deployment would need
to weigh the cost of losing genuine data against the security benefit,
which was not evaluated here.

### 4.1.5 Savage audit: closing remaining approximations and untested assumptions

A final, dedicated audit pass (`savage_audit.py`) specifically targeted
every remaining guessed constant, unverified assumption, or narrower-
than-ideal check still present in the codebase, rather than looking for
further bugs of the kind already found. Six checks:

**Real memory measurement (replacing a guessed constant).** The exact
counter's memory model had used a guessed "~50 bytes per dict entry"
constant since this project began, never measured. Direct measurement
(`sys.getsizeof`) found the guess was wrong by 2.13x in isolation. A
methodologically important correction-to-the-correction: naively
extrapolating that 2.13x factor onto the headline ratio would itself
have been an error, since an isolated microbenchmark's dict fill state
is not representative of the actual simulation's (Python dict memory
has non-linear, load-factor-dependent overallocation behavior). Re-
measuring the actual end-to-end simulation with the fixed method gives
the real, modest correction reported in Section 4.1 (61x → 65.7x), not
the dramatically larger number naive extrapolation would have produced.
This is reported in detail as a caution against a second-order version
of the same mistake this project has already made twice: trust the
measurement closest to what you're actually claiming, not a proxy for
it, however tempting the proxy's number is to reach for.

**Exact L1 norm vs. the analytical approximation.** Every theoretical-
bound calculation had used an approximated L1 norm ("avg 10 wakeups ×
5,000 identities"). Measuring the real total from actual inserted
events: 53,458 vs. an approximated 50,500 — a 5.9% difference, small
enough that no reported theoretical-bound figure required correction.

**Extended invariant check across every key, not just the target.**
The never-underestimate guarantee had only ever been checked for the
single latency-sensitive task (Section 4.1.2). Extended to check
*every* distinct churn identity across multiple epochs and seeds:
**7,515 (key, epoch) combinations checked, zero violations** — a
substantially stronger correctness claim than the original single-key
check supported.

**Proper statistical significance testing.** The "severe degradation
under adversarial conditions" claim (Section 4.1.1) had relied on an
arbitrary hand-picked threshold (">30 percentage points = severe"), not
a formal test. A Welch's t-test (unequal variance) comparing uniform
vs. adversarial-clustered error distributions gives
**t = 605.92, p = 2.46×10⁻³²** — the difference is significant to an
extreme degree, formally substantiating a claim that had previously
rested on an eyeballed threshold.

**Edge-case and boundary fuzzing.** Four previously-untested boundary
conditions — `width=1` (maximal collision), `depth=1` (no redundancy),
zero churn identities, and extreme churn (50,000 identities/epoch) —
were each tested for crashes or invariant violations. **All four
passed cleanly**: no crashes, and the never-underestimate guarantee
held even in the degenerate `width=1` case (a single shared counter
correctly reported at least the true count of everything routed to
it).

**Collision-search verification.** `find_colliding_keys` has a bounded
search budget and could, in principle, silently return fewer keys than
requested — meaning a "successful" attack test could have been quietly
weaker than reported, with nothing flagging the shortfall. Checked
across 20 trials spanning four widths: **zero under-deliveries** — every
attack-test result relying on this function used the full requested
collision count, not a silently-reduced one.

**Net effect of this pass**: one real, meaningful correction (the
memory ratio, 61x→65.7x, now backed by a real measurement instead of a
guess), one near-miss self-caught before it became a worse error (the
extrapolation trap described above), and five confirmatory results
that either strengthened an existing claim (statistical significance,
extended invariant coverage) or found no issue worth correcting (L1
precision, edge cases, collision-search completeness). No further
open corrections remain from this pass.

### 4.2 Scheduling-quality outcomes (Phase 2, kernel)

**[RUN]** The specific test this section originally asked for
— "whether a scheduling-relevant decision can be manipulated via the
same targeted-collision technique" — is done: checklist item 28,
answered no on this scale, with the structural reason (corruption and
load are coupled) recorded there and in Section 5.

The broader comparison has now been run, in two rounds, and the second
round overturned the first round's reading. Both are reported because
the correction is the substantive content.

**Round 1: four-tier baseline.** Stock EEVDF, `scx_simple`, this
project's tiers, and `scx_lavd` on `schbench`. The result was
internally consistent across five repetitions with non-overlapping
ranges, and still could not answer this section's question: `scx_lavd`,
a production scheduler, lost to a minimal one. A workload that ranks a
serious scheduler below a toy is rewarding minimalism rather than
measuring scheduling quality, and structurally cannot show a mechanism
helping, because there is nothing for the mechanism to do.

**Round 2: mixed workload.** A latency-sensitive victim (`schbench`)
against wakeup-heavy, CPU-light background churn -- the regime where
ordinary vtime fairness is blind, since a task that burns CPU is
already deprioritised but one that merely wakes constantly is not. Two
findings from constructing it are worth recording:

- `rt-app` cannot serve as the victim in this environment. It measures
  timer-driven wakeups, and timer *delivery* on this VM has a floor near
  1.7ms; churn levels of 24, 4 and 0 tasks all produced ~1700us,
  indistinguishable. **This resolves checklist item 10 in the negative
  for this setup**: the audio-callback profile cannot be measured with
  `rt-app` here. `schbench` measures task-to-task wakeups and has no
  such floor.
- Victim latency tracks *runqueue depth*, not CPU demand. 128 light
  tasks (5.1 CPUs of demand) degraded the victim 9.07x while 48 heavy
  tasks (19.2 CPUs) degraded it 6.23x. Wakeup latency is a queueing
  phenomenon, and the relevant antagonist is many cheap frequent wakers.

**The gating result, and why it did not survive.** Against
`mechanism=none` -- identical scheduler, identical tracker, identical
per-wakeup overhead, `reach=100%` in both -- acting on the count reduced
victim p99 by 6.8x at n=15, ranges nowhere near overlapping.

That comparison is confounded, and the confound is the point. `penalty`
does two things at once: it consults the tracked count, and it perturbs
vtime. To separate them, a `flat` mechanism was added applying an
identical penalty to every task with no reference to the count, swept
across strengths chosen to be able to beat the treatment:

| condition | p50 median | p50 range | p99 median | p99 range |
|---|---|---|---|---|
| `none` | 3,920us | 2,148-3,956 | 80,640us | 63,680-138,496 |
| `exact+penalty` | 3,920us | 3,556-3,964 | 11,744us | 10,512-39,488 |
| `sketch+penalty` | 3,928us | 3,524-4,872 | 12,880us | 10,832-22,304 |
| `flat` (count-blind) | 11,776us | 10,832-12,368 | 16,576us | 15,248-17,568 |

(n=20, condition order randomised per repetition. An earlier version of
this table used numbers from a matrix that ran conditions in fixed
order; see "A measurement error that invalidated four rounds" below.)

**A count-blind penalty reproduces most of the tail improvement.**
Going from `none` (80,640us) to `flat` (16,576us) captures most of the
distance to `exact+penalty` (11,744us): about 82% of the total on a log
scale is generic vtime perturbation with no reference to the tracked
count. `exact+penalty` does reach a further improvement beyond `flat`
-- the medians separate, though the p99 ranges overlap on a single
outlier -- but the 6.8x figure quoted against `none` must not be
attributed to wakeup tracking, and by extension **neither should
comparable figures elsewhere that lack this control**. It is cheap to
run and, in this project, dissolved most of the headline result.

**What the median reveals.** `flat` buys its tail improvement by making
the victim's own typical wakeup slower: median 11,760us against
~3,950us for every other condition, ranges nowhere near overlapping.
`exact+penalty` achieves statistically indistinguishable tail benefit
while leaving p50 identical to doing nothing at all.

**[TERMINOLOGY CORRECTED]** An earlier draft called this "collateral
damage", implying `flat` degrades *other* tasks to help the victim. The
measurement does not show that. The p50 reported here is the **victim's
own**, and a separate check found background-task throughput unchanged
(157,059 loops under `penalty` vs 157,095 under `none`). So this is a
tradeoff *within the victim's own latency distribution* -- worse
typical case, better tail -- not damage inflicted on other tasks. The
distinction matters because the two claims call for different
evidence, and only the narrower one was collected.

**[SCOPE CORRECTED]** An earlier draft called this the project's most
transferable result, claiming tail-latency-only evaluation "rewards
blunt instruments". Checked against this project's own data, that
overstates it. A p99-only reading would have ranked `exact+penalty`
above `flat` correctly in the stable-identity workload, and would have
preferred `flat` in the high-turnover workload -- arguably also correct
there, since a deadline-sensitive task cares about the tail. In no run
did p99 alone give a clearly wrong ranking.

What it did do, once, is give an *inconclusive* one: at n=15 the two
conditions' p99 ranges overlapped, and p99 alone said "no difference"
while p50 showed one of them tripling typical latency. So the honest
and narrower claim is:

> When p99 cannot separate two policies, p50 can, and it reports what a
> tail improvement cost elsewhere in the same distribution. p50 is a
> cost-accounting and tie-breaking metric, not a replacement for tail
> latency in deadline-sensitive work.

Where the workload has a real deadline, p99 remains the number that
decides whether the scheduler works at all. Reporting both is still
recommended; claiming that tail metrics are systematically misleading
is not supported by what was measured here.

**Confirmed.** Paired sign test 20/20, one-sided p = 9.5e-7, p50 ranges
non-overlapping, under randomised condition ordering. `exact+penalty`
leaves the median identical to `none` to the microsecond (3,920us in
both) while achieving a ~6.9x tail reduction; `flat` reaches a smaller
tail reduction and makes the median 3x worse than doing nothing at all.

A pre-registration for this comparison (benchmark/
PREREGISTRATION_round2c.md, committed before data collection) was
written and then voided on its own gating precondition: it required the
p99 ranges of the two conditions to overlap, establishing "matched tail
benefit, different median cost", and in the run they did not. The
confirmation above therefore rests on the subsequent randomised-order
matrix rather than on that pre-registered test, and the framing is
simply that the count-proportional penalty dominates the count-blind one
on both metrics.

### An explanation that did not survive being tested

The harness ran conditions in a fixed order within every repetition.
Whatever the preceding condition left behind -- runqueue state, CPU
frequency, residue from the scheduler attach and detach path -- landed
on the same condition every time, which would make carryover a
systematic bias that additional repetitions could not average away.

Two matrices disagreed about the same configuration. One ran `none`
(p99 ~88ms) immediately before `exact+penalty` in every repetition; the
other did not include `none` at all. The measured maxima were 21,664us
and 14,000us, and the two runs disagreed about whether `exact+penalty`
separates from `flat`. We attributed that to carryover and reported it
as a methodological finding.

**It was not carryover.** The two matrices also differed in condition
subset (four conditions against three) and sample size (15 against 20),
and were separate runs. A controlled test (`results/raw/ordering-controlled-n20.txt`,
pre-registered in `benchmark/PREREGISTRATION_ordering.md`) holds
everything but ordering constant at n=20 per arm, with `none` adjacent
in 20 of 20 repetitions in the fixed arm:

| `exact+penalty` p99 | fixed | randomised | ratio |
|---|---|---|---|
| median | 11,808us | 12,080us | 0.98x |
| mean | 12,219us | 12,619us | 0.97x |
| maximum | 16,016us | 19,424us | 0.82x |
| CV | 0.11 | 0.18 | |

Mann-Whitney p = 0.86. Within the randomised arm, where adjacency was
assigned at random, the six repetitions following `none` had median
11,664us against 12,208us for the fourteen that did not (p = 0.46). The
condition-subset test is null as well (0.99x, p = 0.55,
`results/raw/condition-subset-n20.txt`).

Across six measurements of this configuration the median varies by 1.09x
and the maximum by 2.82x, with no relation to ordering or subset -- and
the largest maximum, 39,488us, comes from a randomised run with `none`
present. **The original evidence compared two maxima**, and 1.55x sits
inside the range the maximum spans anyway.

What this cost, and what it is worth reporting for, is not the harness.
Randomised ordering was adopted, costs six lines, and is retained as
insurance against a real phenomenon we could not demonstrate here. What
went wrong was upstream of any statistic: an anomaly appeared, one of
its three candidate explanations came with a textbook mechanism, and
that explanation was adopted, published and recommended without the
one-flag experiment that could refute it. See `results/REVISIONS.md`
revision 13.

**What this section does NOT establish.**

- *Nothing about the sketch, in THIS workload.* At the stable-identity
  scale used here, `exact+penalty` and `sketch+penalty` are
  indistinguishable on both metrics (p50 3,920 vs 3,928us). The sketch
  question is settled in Section 4.2.2, at budgets and identity scales
  this workload does not reach -- and note that this row is itself a
  case where the sketch did *not* lose, which Section 4.2.2 must
  account for rather than ignore.
- *Nothing beyond this VM*, this CPU count, and this workload shape.
- `cyclictest` and `hackbench` remain unrun across the tiers. A
  narrower throughput regression check was run (churn loop completions,
  157,059 under `penalty` vs 157,095 under `none`, 0.02% apart) and
  shows the victim's improvement is not bought by starving the
  antagonist; because that churn is rate-limited it can detect a
  regression but not a gain, so it is not a general throughput result.

### 4.2.2 The memory question: a trade, not a substitution

The central claim this paper set out to test is that a Count-Min Sketch
can replace exact per-identity counters, saving memory without
degrading scheduling quality. The answer is a qualified yes: roughly a
quarter of the memory, statistically identical median latency, and a
tail that is worse on average and considerably noisier.

Two earlier drafts of this section said otherwise -- first that exact
counting won at every budget, then that the approach did not work at
any budget measured. Both rested on the discrimination metric discussed
immediately below, which could not distinguish a tracker that
discriminates from one that has silently stopped. The `mechanism=none`
reference condition dissolved them (`results/REVISIONS.md`, revision 5).

An earlier draft of this section reported an apparent ~100x saving
(8 KB sketch against an 800 KB exact map). That was an artifact of
provisioning: the workload had ~132 distinct identities and the exact
map was sized for 16,384. An exact map sized honestly for 132 tasks is
about 6 KB, *smaller* than the sketch. The comparison had to be
rebuilt around matched budgets, which required adding `--max-tracked`
to size the exact hash -- without it, both trackers' maps exist in the
BPF object regardless of which is selected, and every condition
reports identical memory.

**Discrimination ratio** is the measure used throughout: the
count-blind baseline's median victim latency divided by the condition's.
It asks how well the tracker separates the latency-sensitive task from
background churn, with "no discrimination at all" as the 1.0x zero
point. Below 1.0x is worse than not discriminating.

The sweep below ran in the **high-turnover** workload, and it is
reported here as the metric's own failure case rather than as a result.
The stable-identity numbers that carry the result are further down.

| budget | exact | sketch |
|---|---|---|
| 128 KB | 3.72x | 3.71x |
| 32 KB | 3.70x | 3.53x |
| 8 KB | **3.64x** | **0.86x** |
| 2 KB | 3.60x | 0.97x |

**[SUPERSEDED -- an earlier draft claimed exact counting wins at every
budget, holding ~3.6x discrimination with 85 entries. That was an
artifact of the metric: the discrimination ratio compares against a
count-blind baseline which is itself worse than taking no action, so a
tracker that has stopped acting scores as well as one discriminating
perfectly. Adding a `mechanism=none` reference -- absent from the
original sweep -- showed exact at 85 and 21 entries is statistically
identical to `none`. It was inert, not discriminating.]**

**The result: 4.3x less memory, identical median latency, a worse and
noisier tail.** All figures n=20, randomised condition order,
stable-identity workload, **all six conditions in one interleaved
matrix** (`results/raw/headline-single-matrix-n20.txt`, seed 31). Note
that "equivalent" is *not* the claim -- a pre-registered equivalence
test refuted it on p99 while confirming it on p50
(`results/REVISIONS.md`, revision 8).

| condition | map | p50 | p99 |
|---|---|---|---|
| do nothing (`mechanism=none`) | -- | 3,912us | 65,440us |
| count-blind penalty (`flat`) | 35.6 KB | 11,040us | 16,864us |
| **exact, 341 entries** | **35.6 KB** | **3,892us** | **10,144us** |
| exact, 85 entries | 9.6 KB | 3,908us | 63,680us |
| sketch, depth 2 width 512 | 32.3 KB | 3,892us | 10,064us |
| **sketch, depth 2 width 256** | **8.3 KB** | **3,924us** | **11,344us** |

An earlier version of this table paired an exact figure from one matrix
against a sketch figure from another -- the cross-run comparison
withdrawn as revision 7, and the very pattern the ordering bias above
had already shown to be unsafe. The numbers above come from a single
interleaved run in which every condition was measured against the same
neighbours.

Medians agree within 1%. The p99 ranges overlap -- which shows only that
a difference was not *detected*, and a paired equivalence test at n=30
subsequently found one: the sketch's mean p99 ratio sits 11-39% above
exact counting's, though per-repetition it is better in roughly 40% of
runs and more than 50% worse in roughly 30%. Against `mechanism=none`
(p99 65,440us) both are a ~6.4x tail reduction with the median
untouched, and the sketch reaches that at **4.3x less memory**.

The two rows that make the comparison mean something are the ones a
tracker-versus-tracker table would omit. `exact, 85 entries` sits on top
of the do-nothing baseline: at a budget slightly *larger* than the
sketch's, exact counting has stopped acting altogether. And the
count-blind penalty reaches a respectable tail by making every wakeup
three times slower, which is what both working configurations have to
beat in order to be doing anything more than perturbing the machine.

**Where each structure stops working.** Using the default depth-4
geometry across budgets. The budget column is the *nominal* target both
structures were sized against; the measured maps differ slightly (the
85-entry exact map is 9.6 KB, the 2x128x4 sketch 8.3 KB) and each
multiplier is against the `none` condition in that budget's own matrix:

| budget | exact p99 | sketch p99 |
|---|---|---|
| 32 KB | 10,096us (6.4x) | 9,952us (6.5x) |
| 16 KB | 37,312us (1.75x) | 11,088us (5.9x) |
| 8 KB | 62,336us **inert** | 17,984us (3.65x) |
| 2 KB | 65,024us **inert** | 13,248us but **blunt** |

Exact discriminates at 32 KB, degrades at 16 KB, and by 8 KB is
statistically indistinguishable from taking no action. The sketch
discriminates down to 8 KB. The 8 KB row replicates the headline
table's `exact, 85 entries` from an independent run (62,336us against
63,680us), which is the agreement a cross-run pairing cannot claim and a
replication can.

The 16 KB and 8 KB rows come from
`results/raw/thesis-confirmation-n20.txt`, the 32 KB and 2 KB rows from
`results/raw/o1-o4-budget-geometry-churning-n20.txt`. Each row is a
single interleaved matrix; rows are not compared against each other.

**The lower bound is 8 KB, not 2 KB, and the distinction matters.** At
2 KB every sketch geometry is blunt: p50 collapses to the count-blind
baseline's level (~10,900us, discrimination 1.01-1.10x). The tail still
improves, but by taxing every task rather than by telling them apart --
which is the count-blind mechanism operating, not the tracked count. A
tail improvement accompanied by a median collapse is not the same result
as one without it, and reporting only p99 would have concealed the
difference.

**Geometry is load-bearing.** At a fixed 8 KB, varying only the
width/depth split:

| geometry | p50 | p99 |
|---|---|---|
| **d2 w256** | **3,900us** | **10,144us** |
| d1 w512 | 3,900us | 12,208us |
| d4 w128 (the default) | 4,008us | 18,624us |
| d8 w64 | 9,504us | 15,344us (blunt) |
| d4 w128 + seed rotation | 4,224us | 16,704us |

The default is **1.8x worse than the best at identical memory**. Phase
1's synthetic finding that width buys more accuracy than depth
replicates on the kernel, and the choice between depth 2 and depth 4 is
the difference between matching exact counting and falling well short.
Any memory figure quoted for a sketch is therefore a figure for a
particular geometry, not for sketches.

**Churning regime: neither structure carries information.** Where task
identities turn over rather than persist (n=20):

| budget | none | exact | sketch |
|---|---|---|---|
| 16 KB | 116,480us | 98,688us (overlapping) | 41,856us, p50 18,112us |
| 8 KB | 118,912us | 112,768us (inert) | 30,784us, p50 17,696us |

Exact is inert. The sketch does improve the tail with non-overlapping
ranges, but its p50 is 17,696us against `none`'s 3,984us: it has become
blunt, reaching the improvement the same way the count-blind baseline
does. So the memory result above is bounded to the regime where
wakeup-frequency tracking works at all, and that boundary belongs in the
claim rather than in a footnote (Section 4.2.3).

**Scope of this comparison.** The sweep ran in the high-turnover
workload, which Section 4.2.3 shows is also the regime where *every*
penalty variant underperforms the count-blind baseline on tail latency.
So this is a comparison of two trackers in conditions where neither
produces a scheduler worth shipping. Discrimination remains the right
basis for comparing trackers -- it isolates what the tracker knows from
what the policy does with it -- but the comparison should not be read as
"exact counting makes a good scheduler here". It does not.

**[WITHDRAWN -- an earlier draft argued here that an undersized LRU is
a better small-memory approximation than a sketch, on the reasoning
that scheduling needs the active set rather than the full identity
population, so forgetting the inactive is correct rather than lossy.
The argument is appealing and the measurements refute it. An LRU
under-provisioned against its working set does not retain the active
set; it thrashes, evicting entries between their own increments, and
the tracker goes inert (revision 12, and the `mechanism=none`
comparison of revision 5). At 85 entries against ~330 live identities
the exact tracker is statistically indistinguishable from taking no
action, while the sketch at a smaller budget still delivers 3.65x. This
paragraph rested on the discrimination metric that could not tell those
two states apart.]**

**Why the sketch reaches further.** The two structures fail in different
kinds, and they fail at different budgets. An exact tracker under a hard
entry bound fails *silently*: entries evict, queries miss, counts read
as zero, and the mechanism stops acting with nothing to signal it. A
sketch fails *loudly*: it never evicts, so under-provisioning inflates
estimates until every task looks like a heavy waker, and the penalty
intended for churn lands on the task the mechanism exists to protect.

The sketch's never-undercount guarantee is what makes its failure loud
rather than silent -- guaranteed *over*estimation is exactly the
misdirection described above. But it is also why the sketch is still
carrying information at 8 KB when the exact map has gone quiet: it
degrades continuously where an entry-bounded map degrades by falling
off a capacity cliff. Between those two points the sketch is the better
structure, not because it is more accurate at a given size, but because
it has not yet failed. Section 6 develops this.

**The churning collapse is not a property of one geometry.** Still in
the high-turnover workload: at the 8 KB budget where the sketch goes
blunt, holding memory constant and sweeping the width/depth split gives
1.96x (depth 1), 0.82x (depth 2), 0.86x (depth 4), 0.95x (depth 8) --
none approaching exact's 3.67x in that same matrix. That 3.67x is the
inert-tracker artifact described above and not a figure exact counting
earns; what the sweep establishes is only that *no* sketch geometry
rescues the churning regime. Seed
rotation changes nothing (0.86x with, 0.86x without): it relocates
collisions rather than creating room, and its value against
*adversarial* collisions (Section 4.1.4) is unaffected. Depth 1 is
additionally a lottery, with p50 ranging from 2,884us to 19,168us
across runs, because a single row has no min-query and the victim
either lands in a clean cell or does not.

### 4.2.3 The mechanism requires identity stability, and no key choice
### provides it

**[UNVALIDATED REGIME -- see Section 3.4.]** Everything in this
subsection comes from the churning workload, whose behaviour the
validation model does not reproduce. The scheduling outcomes are
measured and reproducible; the accuracy figures underlying their
explanation are not independently confirmed. Treat as preliminary.

A limitation absent from the original design, found only by running a
workload with continuous task turnover.

With `--identity-key pid` and churn tasks that respawn continuously,
every new process is a fresh identity at count 0, is never penalised,
and runs at full slice. Nothing controls the tail: every penalty
variant measured 2-3x **worse** on p99 than the count-blind baseline at
every memory budget.

`--identity-key comm` recovers the tail exactly as predicted
(68,608us -> 28,032us, non-overlapping) and destroys discrimination
doing it (3.60x -> 1.15x), leaving a mechanism indistinguishable from
the count-blind baseline. The cause is structural: **a coarse identity
key aggregates a multithreaded latency-sensitive application into the
heaviest waker on the system.** The victim's four threads share a
`comm`, so their wakeups sum to ~400/s against each churn slot's 200/s,
and the task being protected becomes the most-penalised identity
present.

So the constraint is not "choose a better key". Fine-grained keys
cannot see churning identities; coarse keys mis-attribute
multithreaded victims. **Wakeup-frequency tracking requires that
identities persist across the tracking window**, and workloads with
high task turnover violate that assumption structurally.

For completeness: `boost` (prioritising infrequent wakers rather than
penalising frequent ones) was also evaluated here, and produced the
worst tail latencies measured anywhere in this project (100-115ms).

### 4.2.4 Two bounded structures, two kinds of failure

An earlier version of this section claimed that BPF's `LRU_HASH`
degenerates below LRU semantics at small sizes, attributing it to the
per-CPU free lists being larger than the map. **That claim was withdrawn**
(`results/REVISIONS.md`, revision 12): a 42-entry LRU retains counts
normally with 8 or 20 identities and collapses only at 100 or 300, so the
failure tracks *overcommitment* rather than map size, which is a property
of LRUs and not of BPF.

What the measurements support is narrower, and was load-bearing for the
memory result regardless.

Under overcommitment the two map types degrade into **different kinds of
useless**, and the difference determines what can still be inferred from
a reading:

| structure | behaviour when overcommitted | what a low reading means |
|---|---|---|
| `LRU_HASH` | thrashes uniformly; nothing accumulates | ambiguous -- could be an idle task or an evicted one |
| plain `HASH` | locks in early arrivals; 83% of queries read zero | unambiguous -- zero means *not tracked* |

Neither is usable below its working set. But the plain hash's failure is
legible from the outside and the LRU's is not, which mattered here:
distinguishing "the tracker has stopped working" from "these tasks
genuinely are not busy" is what the `--plain-map` control existed to do.

This also sharpens the exact tracker's floor reported in Section 4.2.2.
It is a capacity limit, not an implementation artefact that a different
map type would avoid -- replacing `LRU_HASH` with a plain hash postpones
the failure by roughly one budget step and does not prevent it.

### 4.2.5 The mechanism costs no throughput

Section 3.3 specified `hackbench` and `cyclictest` alongside the latency
measurements, and the check matters here more than it usually would: the
mechanism works by *delaying* tasks, so it has an obvious route to
buying tail-latency improvements at the cost of the machine's ability to
get work done -- on a benchmark suite that measures only latency, that
would be invisible.

| condition | hackbench | vs EEVDF | cyclictest avg |
|---|---|---|---|
| EEVDF | 1.05s | 1.00x | 124us |
| `none` | 0.95s | 0.91x | 134us |
| `flat` | 1.00s | 0.95x | 117us |
| `exact+penalty` | 0.97s | 0.92x | 113us |
| `sketch+penalty` | 0.95s | 0.90x | 119us |

No regression anywhere; every tier matches or slightly beats stock
EEVDF, and `cyclictest` shows no meaningful separation (its absolute
values are floored by this environment's timer delivery, so only the
relative reading is usable). The latency results are not being bought
with throughput.

## 5. Limitations and Threats to Validity

**Confirmed limitations (from actual testing, not anticipated):**

- **Most of the apparent scheduling benefit is not the mechanism.** A
  count-blind penalty of equal strength reproduces the tail improvement
  (Section 4.2). This is listed first among limitations because it is
  the finding most likely to be missed by a reader skimming for the
  headline number, and because the same confound plausibly affects other
  work in this space.

- **Evaluation metric selection changed what could be concluded.**
  Reporting p99 alone would not have produced a *wrong* ranking in any
  run -- see the scope correction in Section 4.2 -- but it did produce
  an inconclusive one where p50 was decisive, and it cannot show what a
  tail improvement cost elsewhere in the same distribution. Where the
  workload has a real deadline, p99 remains the metric that decides
  whether the scheduler works; p50 is cost accounting alongside it.
  Recorded because this project's own methodology specified p99 alone.

- **The memory saving is bought with tail latency, and the tail cost is
  a distribution rather than a premium.** A pre-registered equivalence
  test refutes equivalence on p99 (90% CI [1.114, 1.394]) while
  confirming it on p50 (Section 4.2.2). Across two independent runs the
  sketch is *better* than exact counting in 37% and 40% of repetitions
  and more than 50% worse in 30% and 33%. A design that can tolerate a
  known 15% premium may not tolerate a third of runs at 50% worse, and
  the mean conceals exactly that.

  An earlier version of this entry said the approach does not work at
  any budget measured, and that exact counting beats the sketch from
  128 KB down to 2 KB. Both came from the discrimination metric
  withdrawn in revision 5 and are contradicted by the result in
  Section 4.2.2.

- **The mechanism only helps while the protected workload is not itself
  the bottleneck.** Every result was measured with one victim shape
  (4 threads, 100 rps) until a sensitivity check varied it. The headline
  holds across 2t/50rps, 4t/100rps and 8t/200rps -- the sketch measuring
  between 2% better and 36% worse than exact counting, within the spread
  already characterised, with median latency equivalent throughout.

  At 16 threads and 400 rps it does not, and neither does anything else.
  The victim saturates this 4-CPU machine by itself: `none` reaches
  959,488us and both tracking mechanisms manage only 1.1x and 1.2x
  better. With no headroom there is no scheduling decision left to make
  well, and a mechanism that works by reordering a queue has nothing to
  reorder.

  This is a condition a reader could easily violate without noticing,
  since it depends on the relationship between the protected workload
  and the machine rather than on anything visible in the scheduler's
  configuration.

- **The mechanism requires identity stability.** With high task
  turnover, fine-grained keys cannot see churning identities and coarse
  keys mis-attribute multithreaded victims (Section 4.2.3). Neither the
  original design nor this paper's methodology section stated this
  assumption.

- **Every result is latency-based, and the mechanism's canonical
  application is energy.** Section 2.4 identifies reducing
  idle-transition energy cost -- the "wakeup tax" -- as the established
  reason to track wakeup frequency, and this evaluation measures only
  scheduling latency. A sketch's overestimation is far less damaging to
  a batching heuristic than to a scheduling decision, so the negative
  result here does not transfer to the energy case. It was not measured
  because the VM exposes neither RAPL counters nor a battery gauge, and
  host-level power measurement would be swamped by virtualisation
  overhead.

- **The audio-callback workload profile could not be measured in this
  environment.** `rt-app`'s timer-delivery floor on this VM (~1.7ms)
  exceeds the scheduling differences being studied (checklist item 10).
  Results here rest entirely on `schbench`'s task-to-task wakeup path.

- **A known concurrency bug remains unfixed.** Increment-then-read is
  not atomic as a unit in the counters (delivery plan Section 9.8);
  the regression suite carries it as an expected failure. Distinct
  churn identities were used throughout Phase 6 specifically to keep
  this bug out of the measurements rather than have it silently
  contaminate them, which means the measurements do not exercise the
  same-identity concurrent path at all.

- **Single VM, single CPU count, single workload shape.** No bare-metal
  or cross-hardware validation. Rather than leave that as a generic
  caveat, the findings are sorted below by how much bare metal is
  expected to change them. The sorting is a falsifiable prediction: if
  someone re-runs this on real hardware and the wrong things move, the
  reasoning here was wrong.

  **Expected to survive.** The memory result -- exact counting failing
  when its map cannot hold the live identity set, and the sketch's
  footprint not growing with identity count -- is a capacity
  relationship rather than a hardware one. The count-blind control
  finding is a property of the mechanism's design. The identity-
  stability constraint is structural. Median-latency equivalence
  reflects the sketch usually estimating correctly.

  **Expected to shift in magnitude.** Every absolute latency figure:
  the ~65,000us do-nothing baseline is substantially inflated by
  virtualisation and real numbers would be smaller. And `rt-app`
  becomes usable once the 1.7ms timer floor disappears, reopening the
  audio-callback workload this environment forced us to abandon.

  **A prediction already falsified, recorded rather than deleted.** An
  earlier version of this section predicted that the exact tracker's
  failure threshold would *scale with core count*, on the reasoning that
  BPF's per-CPU free lists grow with CPUs. That reasoning was withdrawn
  before any bare-metal run took place (revision 12): the threshold
  tracks the ratio of live identities to map capacity, not the number of
  CPUs. So the corrected prediction is that **the threshold should be
  unchanged** on another 4-core machine -- and unchanged on a 16-core one
  too, provided the workload's identity population is the same. That is a
  sharper test than the original, and it can fail.

  **Most at risk: the tail-latency penalty.** It rests on the spread of
  per-repetition ratios, and a noisy environment manufactures spread.
  The p99 distributions here are wide, and some of that is plausibly
  virtualisation -- vCPU scheduling, timer jitter, and the host
  migrating vCPUs between performance and efficiency cores mid-run (see
  `results/ENVIRONMENT.md`).

  Per-condition variance is *not* the thing to predict. An earlier
  version of this entry quoted CV 0.18 for exact counting against 0.40
  for the sketch; the n=60 replication inverts them (0.43 and 0.35).
  That statistic is outlier-driven and does not replicate (revision 10).
  What does replicate closely is the shape of the paired ratio -- median
  1.18x and 1.14x, sketch better in 37% and 40%, more than 50% worse in
  30% and 33% -- so that is the prediction bare metal should score.

  Tighter distributions on bare metal cut both ways. Better resolving
  power could make a real difference easier to demonstrate, failing the
  equivalence test more decisively. Or the ratio spread could narrow
  toward its median, which would make the trade easier to design around
  without changing its direction.

  **A sketch-specific excursion mode was claimed here and withdrawn**
  (revision 9). The single 240,384us observation was attributed to the
  sketch on the grounds that a pre-registered check found it confined to
  one condition while `exact_32k` in the same repetition measured a
  normal 10,032us. That reasoning is wrong: conditions run
  *sequentially* within a repetition, so a disturbance lasting seconds
  hits exactly one of them -- the signature treated as exonerating is
  what an environmental cause produces. At n=60 per condition, exact
  counting shows excursions at the same rate (1/60 against the sketch's
  1/60) and nothing exceeded 5.7x across 360 further measurements. Bare
  metal should therefore expect excursions to shrink or vanish across
  *all* conditions together, which is a different prediction from the
  one this section originally made.

- **The approach is not robust to adversarial or unfavorable churn
  patterns.** This is the most significant limitation found: a
  targeted-collision attack (Section 4.1.1) degrades accuracy by over
  5x relative to true value in simulation — dramatically worse than the
  ~37% error characterizing the "well-behaved" uniform case this
  project initially reported — and the attack has since been
  reproduced against a real kernel (checklist item 27), where 64
  processes inflated a victim's estimate by +8,824%. Any claim of this
  approach's viability must be scoped accordingly.

  **[CORRECTED] On the privilege required.** An earlier version of this
  section stated the attack requires "only knowledge of the hash
  function and per-row seeds (not privileged system access)". That is
  wrong for a real implementation and overstates the risk. In the BPF
  scheduler the per-row seeds are generated by `bpf_get_prandom_u32()`
  and stored in a BPF map, so **reading them requires privilege**. An
  unprivileged co-located process cannot mount the targeted attack at
  all; measured at identical attacker volume, knowing the seeds is the
  difference between +8,824% and no measurable effect. The realistic
  adversary is therefore an insider, a seed leak, or a system with
  predictable seeds — not any co-tenant.

  This narrows who the attack applies to; it does not make the sketch
  safe. Volume flooding needs no seed knowledge and still inflated a
  victim's estimate by +5,450% given enough attackers. Seed secrecy
  raises the cost of the precise attack; it does not remove the
  approximate one.

  **[RESOLVED] Which identity key.** The above is also what settles the
  identity-key question left open in Section 2.1: `comm` is settable by
  the task, so an attacker can construct an identity landing in a
  victim's cells, whereas a kernel-assigned pid or tgid makes the
  targeted attack structurally unavailable rather than merely harder.
  Use PID or TGID.

  **[STILL OPEN] Mitigation.** Whether hash-seed rotation or a
  per-boot key materially reduces this on a real kernel is implemented
  (`--seed-rotation`) but untested against the attack. Phase 1 found
  seed rotation to be a partial mitigation only (+400% to +200%,
  Section 4.1.3), for a mechanistic reason that would apply equally
  here: the surviving buffer carries poisoned data forward for exactly
  one window regardless of reseeding.
- **An earlier implementation had a reproducibility defect** (Python's
  randomized string hashing, Section 2.1.1) that would have silently
  invalidated any claim of reproducible results had it not been caught
  during rigor testing. This is now fixed and verified, but is
  reported here as a limitation of the *process* that produced this
  work: the defect existed and was undetected for a period during
  development, discovered only because reproducibility was
  deliberately tested rather than assumed.
- The evaluation environment (memory-capped VM, per Section 3.2) is
  not physical embedded/mobile hardware; architecture-specific effects
  (real cache behavior, real interrupt latency) are not captured. This
  is a deliberate scope decision, not an oversight, but is restated
  here as a limitation on how far Phase 1/Phase 2 results can
  generalize to real devices.
- The synthetic churn workload (Section 3.1) — even its "skewed" and
  "adversarial" variants — is a modeled approximation, not derived
  from a real trace of process churn on an actual embedded/mobile
  device. [NEEDS: ideally validated against or informed by a real
  device trace, which has not been collected.]
- The hash function used in the Python prototype (`blake2b`-based,
  Section 2.1.1) was chosen for reproducibility and correctness during
  prototyping, not for speed. [NEEDS: verification that the eventual
  BPF implementation's hash choice (constrained by what's efficient
  and verifier-legal in BPF — likely a simpler multiplicative or FNV-1a
  style hash rather than blake2b) doesn't reopen either the
  reproducibility question or change the collision/attack
  characteristics found in Section 4.1.1. A weaker, faster hash chosen
  for BPF performance reasons could plausibly make the targeted-attack
  finding WORSE, not better — this needs explicit testing once the
  BPF implementation exists, not assumed to be equivalent.]

**Unknown until further results exist:**

**[RESOLVED, partially]** Whether the targeted-collision vulnerability
translates into an actual exploitable scheduling-decision manipulation
(e.g., can an attacker use this to make the scheduler wrongly throttle
or deprioritize a victim task) required Phase 2's actual
scheduling-outcome measurement, not just the frequency-tracking accuracy
measured in Phase 1 — that measurement is now done (checklist item 28).

**The distinction between the two claims must not be blurred.** Every
attack run in checklist item
27 was performed with `--mechanism none`: the scheduler was tracking
but not acting on what it tracked. What has been demonstrated is that
an attacker can corrupt the *signal* by orders of magnitude. What has
NOT been demonstrated is that this changes any scheduling decision, or
that a victim suffers measurably worse latency as a result.

Those are different claims. As of the real-kernel work (checklist item
28) the weaker one is demonstrated and the stronger one is NOT, and there
is now a structural reason why. With a mechanism active and attacker load
held constant, corrupting the signal produced no detectable change in the
victim's scheduling latency across configurations (up to n=15). The cause
is a coupling the Phase 1 simulation could not have surfaced: a cell's
inflation equals the colliding load that produces it, so large corruption
requires heavy load that saturates latency on its own, while at
measurable load the achievable corruption (2-3x) is too small to move a
scheduling decision. An attack on a signal nothing acts on is a
correctness problem; whether it is also a security one is unresolved and
appears, on this 4-CPU scale, to be structurally resisted. Levers that
might overturn this (more CPUs, a smaller sketch, a steeper mechanism)
are named in item 28 and untested.]

---

## 6. Conclusion

This project tested whether a Count-Min Sketch could replace exact
per-task counters for tracking wakeup frequency in a BPF scheduler,
saving memory without degrading scheduling quality. **The answer is a
qualified yes: roughly a quarter of the memory, identical typical
latency, a worse and noisier tail.**

**The finding.** A sketch at 8.3 KB continues to function at a budget
where exact counting has stopped affecting scheduling at all -- at 9.6 KB
the exact tracker is statistically indistinguishable from not acting on
the count. Median latency is equivalent within 20% by a pre-registered
test (90% CI [0.974, 1.060]). **Tail latency is not** (90% CI [1.114,
1.394] on the mean ratio, n=30 paired), and the per-repetition spread
matters more than that mean: across two independent runs the sketch was
*better* than exact counting in 37% and 40% of repetitions, and more than
50% worse in 30% and 33%. What less memory buys is not a predictable
premium but a coin weighted slightly against you.

A matched-memory control locates the cost. At the same budget the two
structures are indistinguishable (1.03x and 1.04x across the two runs),
so the tail premium is the price of the memory saving rather than an
intrinsic cost of approximating.

The boundaries are measured rather than assumed. Exact counting
discriminates at 32 KB, degrades at 16 KB, and by 8 KB is
indistinguishable from doing nothing. The sketch discriminates down to
8 KB; at 2 KB it still improves the tail but only by taxing every task,
which is the count-blind mechanism rather than the tracked count.

The result is bounded to workloads where identities persist. Where they
churn, exact counting is inert at every budget tested and the sketch
becomes blunt, so neither structure carries usable information.

Two earlier drafts of this section said the opposite -- first that exact
counting won at every budget, then that neither dominated. Both were
artifacts of a metric that compared against a count-blind baseline which
is itself worse than inaction, and which therefore could not distinguish
a tracker that discriminates from one that has stopped. Adding a
do-nothing reference condition dissolved them.

**Why the sketch wins where it does.** The two structures fail in
different kinds, and that is what decides the memory question. An exact tracker under a hard entry bound fails
*silently*: entries evict, queries miss, counts read as zero, and the
mechanism stops acting with no indication that it has. A sketch fails
*loudly*: it never evicts, so under-provisioning inflates every
estimate until each task looks like a heavy waker and the penalty meant
for background work lands on the task being protected.

Silent failure degrades to the underlying policy; loud failure
misdirects it. But the failures arrive at *different budgets*, and that
asymmetry is the whole result: exact counting goes silent at 8 KB while
the sketch is still discriminating, and the sketch only goes loud at
2 KB. Between those two points the sketch is the better structure, not
because it is more accurate at a given size, but because it has not yet
failed.

**So the question to ask of a bounded counting structure is not which
is more accurate at a given size, but at what size each stops working,
and what it does when it does.** An exact map going quiet is a more
forgiving failure than a sketch confidently reporting that everything
is hot -- but a structure that has not failed yet beats both.

**A design constraint the approach never stated.** Wakeup-frequency
tracking requires identities that persist across the tracking window.
Under high task turnover, fine-grained keys cannot see churning tasks
and coarse keys aggregate a multithreaded victim into the heaviest
waker on the system. No identity-key choice resolves this.

**A methodological caution, and not the one we expected to give.** We
reported fixed condition ordering as a systematic bias large enough to
reverse a conclusion, and recommended randomising order. A controlled
test found no such effect (Section 4.2, revision 13): the anomaly that
prompted the claim was two noisy maxima compared across runs that
differed in three ways. Randomising order remains worth doing as cheap
insurance. The caution that survives is about the reasoning: when two
runs disagree, count the ways they differ before explaining why, and
remember that the maximum of a sample is both the noisiest summary
available and the one the eye reaches for.

**On what did not survive.** Thirteen claims were stated during this
work and later withdrawn; each is recorded in `results/REVISIONS.md`
with the raw file that produced it and the raw file that overturned it.
Eight were caused by a faulty instrument rather than a faulty hypothesis
-- a metric with a broken zero point, a ratio with a collapsing
denominator, a workload model wrong by 4x, a cross-run comparison. One
was not a measurement at all but a sentence asserting a literature
search that never happened (revision 11).

**Four share a single failure and it is the one worth carrying away.**
In revisions 9, 10, 12 and 13 the instrument was sound and the numbers
were right; what was wrong was an explanation attached to them and never
tested. An outlier became a sketch-specific failure mode. A control that
failed for an unrelated reason became evidence about approximation. A
thrashing cache became a defect in BPF's LRU. Two noisy maxima became a
systematic ordering bias -- and that one reached a paper, a blog post
and three harness comments before anyone ran the experiment that could
refute it. In every case the untested explanation was the more
interesting of the two available, and in every case the test took under
an hour.

Two more are instructive beyond their content. The ~10% sketch failure
rate (revision 4) was an *interesting* result that arrived with a
plausible mechanism and was accepted with visibly less scrutiny than the
disappointing results received; its disappearance was then attributed to
ordering, an attribution revision 13 also withdraws, so why it appeared
is now simply unknown. Asymmetric skepticism is harder to detect than
insufficient sample size, and no amount of statistical discipline
catches it. And revision 7 paired figures from two different runs to
build the headline, which is the precise failure the section above
describes -- knowing a failure mode does not inoculate against it.

Two claims in earlier drafts were also narrowed after checking them
against the data rather than against intuition: that tail-latency-only
evaluation systematically rewards blunt policies (it gave an
inconclusive ranking once, never a wrong one), and that the count-blind
penalty inflicts collateral damage on other tasks (it is a tradeoff
within the victim's own latency distribution; background throughput was
unchanged).

**Future work.** The most promising direction is the one this
evaluation did not take. Section 2.4 identifies reducing
idle-transition energy -- the wakeup tax -- as the established reason to
track wakeup frequency, and every measurement here is latency-based. A
wakeup has a direct physical energy cost, frequent-but-cheap wakers are
the canonical power pathology, and a sketch's overestimation is far
less damaging to a batching heuristic than to a scheduling decision. So
the negative result above does not transfer, and the energy case
remains open. It requires bare metal: the VM used here exposes neither
RAPL counters nor a battery gauge.

**Conservative update was tried, and cannot be used here.** The failure identified above is
overestimation: collisions inflate the protected task's count.
Conservative update (incrementing only the cells currently holding the
minimum) attacks exactly that, costs no additional memory, and
preserves the never-undercount property, which matters because the
rotating-window design never decrements. Measured, it delivers: overestimation falls
15-35% at no memory cost (churning 8 KB, 4.30x -> 3.59x, and 2.78x
combined with hash mixing).

It is nonetheless unusable in BPF, for a reason belonging to the
platform rather than the algorithm. Conservative update must read all
`d` cells, take the minimum and write back as one atomic unit; each cell
needs its own `bpf_map_lookup_elem`; and the verifier rejects a lock
held across those calls outright with *"function calls are not allowed
while holding a lock"*. The lock-free implementation that remains races
observably, producing thousands of never-undercount violations in every
run. The rate does not replicate -- 1,749 against a baseline of 116 at
stable 16 KB in one run, 1,036 against 299 in another, and a neighbouring
variant moving 197 to 1,750 -- so no rate is quoted. One violation
suffices, since never-undercount is the guarantee that justifies choosing
the structure. Note the baseline is itself non-zero: the plain sketch
cannot undercount by construction, so those are the known
increment-then-read race (Section 5), which is the noise floor this
comparison sits on. Correct-and-slow is not available here, only
fast-and-wrong, and a sketch that undercounts has surrendered the
guarantee that justified choosing it.

Beyond that: cross-hardware validation, given that this environment's
timer-delivery floor invalidated one victim workload outright; fixing
the open increment-then-read atomicity bug and testing the
same-identity concurrent path that every Phase 6 measurement
deliberately avoided; and repositioning against Wu's lazy-wakeups work
once the LPC 2026 talks are public.

---

## Build checklist (everything marked `[NEEDS:` above, consolidated)

For quick reference when working through this:

1. [x] ~~Cite Cormode & Muthukrishnan CMS paper + formal error bounds (2.1)~~ DONE
2. [x] ~~Task identity key: PID vs TGID vs comm~~ **DECIDED: PID or
       TGID, not `comm`** — on evidence, per item 27. With `comm` a
       targeted collision attack inflated a victim's estimate by +8,824%
       using 64 processes at a modest wake rate; against `pid` that
       attack is structurally unavailable, since a task cannot choose its
       own pid and so cannot steer into a victim's cells. A qualitative
       difference, not a tuning one. This confirms the prior lean rather
       than overturning it, but it is now measured rather than assumed.
       [ ] TGID itself was not measured; the structural argument covers
       it, but that is reasoning, not evidence.

       Abstraction as built: `scx_cms/src/bpf/
       identity.bpf.c` resolves a task to PID, TGID, or an FNV-1a hash of
       `comm`, selected at run time via `--identity-key` (a `const
       volatile` set before load, so no rebuild to switch). Ergonomically
       all three are cheap to read in `runnable`, so BPF constraints do
       not decide this.
3. [x] ~~Implement actual BPF scheduler with CMS as a BPF map, wired
       into `runnable`~~ (2.3) DONE. `scheds/experimental/scx_cms/` loads
       on a real kernel (Fedora 44, 6.19) and tracks wakeup frequency per
       identity in `runnable` with the validated rotating dual-buffer
       windowing. Both counting methods exist and are selectable at
       launch (`--tracker exact|sketch`); the sketch is a BPF array map
       sized at load time to exactly `2 * width * depth` cells, which is
       8,192 bytes at the Phase 1 reference parameters. The
       never-undercount guarantee has been verified against a live event
       stream (zero violations in 52,316 samples).
       [ ] The targeted-collision robustness test that must accompany
       this (per 4.2) is not built yet.

       Correction to this item's premise: it says "fork of
       `scx_simple.bpf.c`". That file is no longer in this repo — the C
       schedulers moved to `sched-ext/scx-c-examples` and the project is
       now Rust userspace + BPF only. `scx_cms` ports `scx_simple`'s
       policy (recovered from repo git history at `d1810e62~1`) into the
       current crate layout. A real API drift was found in the process:
       `scx_bpf_dsq_move_to_local()` gained a second `enq_flags`
       argument since that code was written.
4. [x] ~~Decide sliding-window/decay mechanism (2.3)~~ DONE — rotating
       dual-buffer scheme adopted after an exponential-decay approach
       was tried and found to produce ambiguous ground truth; see
       Section 2.3.1 for full reasoning and the validated Phase 1
       result.
5. [x] ~~Literature search for prior CMS/Bloom filter use in OS
       scheduling specifically (2.4)~~ DONE — none found; TinyLFU
       identified as closest conceptual precedent (different domain,
       same technique)
6. [ ] Revisit Samuel Wu's LPC talk after Oct 2026 publication (2.4, 6)
7. [x] ~~Run full parameter sweep: width × depth × churn level~~ DONE
       for width alone (4.1 table) AND for joint width×depth at fixed
       memory (4.1.3) — wide-shallow beats narrow-deep at fixed budget
       (7x accuracy difference between width=2048/depth=1 and
       width=128/depth=16 at equal memory), confirming theoretical
       prediction that width controls error magnitude more than depth
       does.
8. [~] PARTIALLY DONE. "Connect accuracy to a real scheduling-outcome
       metric" (3.1) is done — item 28: across every configuration
       tested, corrupting the tracked count produced no detectable
       scheduling-outcome change. [ ] The numeric threshold itself is
       deliberately left as an author judgment call, not resolved here
       — and now needs to account for both the adversarial-case error
       (440% in Python, +8,824%/+6,064% replicated on a real kernel) and
       Section 9.7's finding that real execution shows meaningfully more
       benign-case error than Phase 1's synthetic model predicted.
9. [x] Explicit justification for memory-capped VM as hardware proxy
       (3.2) — DONE. Memory-footprint claims defended as genuinely
       architecture-independent; accuracy/timing claims explicitly NOT
       extended that far, per Section 9.7.
10. [x] ~~Decide on latency-sensitive workload representation~~
        PARTIALLY RESOLVED (3.3) — use `rt-app` (JSON-configured
        workload modeling) rather than a hand-rolled synthetic task;
        [ ] the specific workload profile (audio callback vs. periodic
        deadline task) still needs a final decision.
11. [x] ~~Decide on scheduling-quality metric~~ RESOLVED (3.3) — use
        schbench's P99/P999 wakeup latency as the primary metric,
        since it directly matches this project's own tracked signal
        (wakeup frequency); deadline miss rate and frame drops remain
        secondary/situational metrics depending on final workload
        choice.
12. [x] ~~Build exact-counter baseline scheduler~~ RESCOPED — this is
        now only ONE of four required baseline tiers (3.3): (a) stock
        EEVDF unmodified, (b) `scx_simple` unmodified, (c) this
        project's custom scheduler with exact counters (the original
        plan), (d) an established production sched_ext scheduler
        (`scx_rusty` or `scx_lavd`). All four need building/obtaining
        before Phase 2 results are credible — the original single
        isolation-only baseline was insufficient on its own.
        **Tier (c) is now built**: `scx_cms` with `tracker.bpf.c`'s
        exact rotating dual-buffer counter, plus a swappable
        `--mechanism none|penalty|boost`. `--mechanism none` tracks
        without altering scheduling, which isolates tracking overhead
        from mechanism effect — a comparison the Python work could not
        make. Verified on a real kernel: window rotation, lazy
        roll-forward and buffer discard all confirmed against live map
        dumps.
        **[x] Tiers (a), (b) and (d) are now obtained too** — stock
        EEVDF, `scx_simple` (fetched from `scx-c-examples`, since it is
        no longer in this repo) and `scx_lavd` all appear in the round 1
        four-tier comparison at item 13, and EEVDF again in
        Section 4.2.5's throughput check. Note what that exercise
        established: all four tiers vary *the scheduler*, so none of
        them could separate "tracking wakeup frequency helps" from
        "perturbing vtime helps". Tier 5, the count-blind control, is
        the one that mattered and was added later (Section 3.3).
        [ ] `boost` carries no validation from Phase 1 — see item 23.
13. [~] IN PROGRESS (Phase 6, round 1; delivery plan Section 12).
        `schbench` request-latency P99/P999, 5 interleaved repetitions,
        reported as multipliers against EEVDF as required:

        | scheduler | p99 vs. EEVDF | p999 vs. EEVDF |
        |---|---|---|
        | `scx_simple` | 0.57x | 0.45x |
        | `scx_cms` (exact) | 0.55x | 0.42x |
        | `scx_lavd` | 1.64x | 1.83x |

        Consistent across all 5 repetitions with non-overlapping ranges
        — not one of the single-run scares this project has caught
        before. `scx_lavd` losing to EEVDF got a direct follow-up rather
        than being reported flat: `--performance` (disables its core
        compaction) closes about a sixth of the gap (44,480us →
        37,568us median), confirming power management costs something
        here, but `scx_lavd` remains ~1.4x worse than EEVDF even with it
        off. The remaining gap is plausibly its criticality-classification
        overhead earning nothing on `schbench`'s single uniform task
        type — NOT verified, would need a mixed-workload test.

        The real-kernel targeted-collision replication this item asked
        for is done — see item 27, not this one; that work happened in
        Section 9, ahead of Phase 6.

        **[x] `cyclictest` and `hackbench` are now run** across every
        tier — see Section 4.2.5. No throughput regression anywhere;
        every tier matches or slightly beats stock EEVDF, and
        `cyclictest` shows no meaningful separation because its absolute
        values are floored by this environment's timer delivery.
        **[x] More than one workload shape tested** — a victim-shape
        sensitivity sweep at n=15 covers 2t/50rps, 4t/100rps, 8t/200rps
        and 16t/400rps; the headline holds for the first three and the
        fourth saturates the machine (Section 5).
        [ ] `rt-app` and the workload-profile decision (item 10) remain
        open, and are blocked on hardware rather than on effort: this
        VM's ~1.7ms timer-delivery floor exceeds the differences under
        study. See `04_bare_metal/README.md`.
14. [x] ~~Write Results, Limitations, Conclusion once real data
        exists~~ DONE. Results (4) and Limitations (5) carry Phase 1 and
        Phase 2 content, and Conclusion (6) is written against the
        Phase 2 measurements rather than blocked on them.
15. [x] ~~Investigate hash-seed rotation as a mitigation~~ DONE in Python
        (4.1.3) — PARTIAL mitigation only: reduces attack damage from
        +400% to +200% via one window's lag, but does not eliminate
        it, because the rotating buffer's "previous" slot carries
        poisoned data forward for exactly one extra window regardless
        of seed change.

        **[NEW] Replicated on a real kernel** (`--seed-rotation`,
        harness `attack/seed_rotation_attack.py`), and the real-kernel
        result is more nuanced than the Python one: effectiveness
        depends on attacker volume relative to sketch size, not only on
        Phase 1's one-window carry-over lag.

        | load | rotation OFF | rotation ON |
        |---|---|---|
        | light (160 events/s) | 9.5-181.8% | **0.0-4.8%** (near-total mitigation) |
        | heavy (12,800 events/s) | 1,219-14,084% | 791-2,011% (~6x lower, not cleared) |

        At light volume rotation nearly eliminates the attack. At heavy
        volume, sustained raw traffic saturates a 256-column table
        regardless of whether identities still hash to the intended
        column — a second effect Phase 1's Python test never modeled,
        since rotation invalidates *targeting*, not *volume*. Consistent
        with the plain-flooding finding in item 27 (comm/blind/256@1000/s
        → +5,450% with no seed knowledge at all).

        [ ] Single run per load level; light/heavy boundary not swept.
        Only the sustained-replay attack variant tested, not Phase 1's
        one-shot-then-silent variant. Whether damage fully clears by two
        windows out under the ORIGINAL one-shot variant remains untested
        on a real kernel.
16. [x] ~~Re-run targeted-collision attack using a BPF-realistic hash
        (FNV-1a) instead of blake2b~~ DONE (4.1.3) — both hashes show
        IDENTICAL +400% vulnerability once a bug in the test itself
        (hardcoded blake2b in the collision-search helper, producing
        a false "FNV-1a is immune" result) was caught and fixed.
        Conclusion: the vulnerability is structural to Count-Min
        Sketch under a knowledgeable adversary, not hash-specific —
        switching hash functions for BPF performance would not by
        itself mitigate this risk.
17. [x] ~~Test whether targeted-collision damage fully clears by
        window N+2~~ DONE (4.1.4) — clears exactly at window 2 (0.0%
        error), confirming the "one extra window" carry-over model
        precisely: window 0 = +400%, window 1 = +200%, window 2+ = 0%.
18. [x] ~~Investigate a stronger mitigation than seed rotation
        alone~~ DONE (4.1.4) — anomaly-triggered hard reset (discard
        both buffers on detecting a >3x spike) reduces window N+1
        error from +200% to +0.0% exactly, across 10 seeds. CAVEAT:
        uses a known-true-value oracle for anomaly detection, not a
        realistic rolling baseline — mechanism validated in principle,
        not yet a deployable defense. [ ] A realistic rolling-baseline
        anomaly detector (with attendant false-positive/negative
        tradeoffs) remains unbuilt and untested.
19. [x] ~~Audit all experiment scripts for bugs skewing results~~ DONE
        — found and fixed: (a) `experiment.py` drift bug (Section
        2.1.1, still-buggy duplicate classes after the fix was applied
        elsewhere); (b) Section 4.1's headline numbers, width-sweep
        table, and adversarial-distribution numbers in
        `sweep_experiment.py` were ALL computed before the
        reproducibility fix and never re-validated after — corrected
        (37.1%→31.9% headline; full table and adversarial figures
        corrected; theoretical-bound L1 norm also corrected, was
        understated ~2x). Every qualitative conclusion survived the
        correction; only exact figures changed. (c) `find_colliding_keys`
        hardcoded blake2b regardless of target hash (4.1.3, produced a
        false "FNV-1a is immune" result, caught by verifying claimed
        collisions actually collided). (d) Anomaly-triggered reset test
        had a manual buffer reset silently undone by a subsequent
        `rotate()` call (4.1.4), caught the same way — a suspiciously
        bad result ("mitigation makes things worse") triggered
        investigation rather than being reported as-is.
20. [ ] NEW: given how many bugs were found by systematically
        re-deriving/cross-checking numbers rather than trusting first
        results, consider adding an automated regression test suite
        (e.g. pytest, asserting known-good values for a fixed seed)
        BEFORE Phase 2 begins, so future refactors can't silently
        invalidate results the way `sketch_lib.py`'s fix did to
        `sweep_experiment.py` without anyone noticing for several
        turns of work.
21. [x] ~~"Savage" no-corners-cut audit of every remaining
        approximation/guess/narrow-check~~ DONE (4.1.5) — found and
        fixed the guessed memory constant (real measurement now used,
        61x→65.7x); verified L1 approximation, extended invariant
        coverage to all keys (7,515 checks, zero violations), added a
        formal significance test (p=2.46e-32) replacing a hand-picked
        threshold, fuzzed 4 boundary conditions (all clean), and
        verified the collision-search helper never silently
        under-delivers. `RotatingExactCounter.memory_bytes()` in
        `sketch_lib.py` now measures directly rather than guessing —
        this is a permanent fix, not just a one-off recomputation.
22. [x] Early directional scheduler-policy simulation, pre-Phase-2
        (4.2.1) — DONE. Found/fixed three real issues (event-model
        bug, one-shot-identity bug, oracle-knowledge artifact). Final
        result: sketch and exact tracking produced byte-identical
        scheduling outcomes in this scenario — a genuine non-finding,
        reported honestly rather than tuned toward a more flattering
        number. [ ] Whether this holds at higher load, or under a
        boost-based (rather than penalty-based) mechanism, remains
        open and was deliberately not pursued further, per the bounded
        scope agreed for this exploratory detour — a candidate for
        revisiting only if Phase 2 planning specifically needs it.
23. [ ] NEW: the `boost` mechanism now implemented in `scx_cms`
        (`mechanism.bpf.c`) is a **first attempt, not a port of anything
        validated**. Section 4.2.1 records that Phase 1's boost-style
        comparison policy was relying on oracle knowledge of which task
        was latency-sensitive, and collapsed to byte-identical with
        plain fairness once that was removed — so no working oracle-free
        boost design exists to port. With only a wakeup count available,
        the implemented stand-in favours tasks below a count threshold,
        on the reasoning that "wakes infrequently relative to surrounding
        churn" is the closest available proxy for "latency-sensitive".
        That proxy is untested and may simply not work. It must not be
        written up as inheriting Phase 1's validation, and if it shows an
        advantage, that result deserves the same suspicion this project
        has applied to every other unexpectedly favourable finding.
24. [ ] NEW: measurement hygiene for Phase 2 benchmarking. `scxtop`
        (this repo's `sched_ext` observability tool) must not run during
        any benchmark whose number is reported. In a 5s trace of
        `scx_cms`, `scxtop`'s own tokio worker threads were the top CPU
        consumers (one at ~90% of a core) and its analyzer flagged
        max-severity context-switch bottlenecks on all 4 CPUs that were
        purely its own overhead; `scx_cms` did not appear in the top 15
        processes by runtime. Stated precisely: the tracer was observed
        to dominate the traced workload. The magnitude of its distortion
        on a specific `schbench` P99 figure has NOT been measured — if
        that is ever needed, measure it (same benchmark bare vs. under
        trace) rather than estimating. See delivery plan Section 4.
25. [ ] NEW, and load-bearing for how every Phase 2 result must be
        reported: **a mechanism only reaches a fraction of dispatches,
        and that fraction depends on load.** `select_cpu` dispatches
        straight to the local queue when it finds an idle CPU, bypassing
        the `enqueue` path where the mechanism adjusts vtime. Measured
        reach was 0.8% on an idle VM against 85.9% under `hackbench`.
        A null result from a lightly loaded system therefore cannot be
        distinguished from a mechanism that never ran, and every result
        must state its reach. `scx_cms` prints it on every stats line.
        [ ] This is also a candidate explanation for 4.2.1's own null
        result, which the Python simulation could not account for — now
        a testable hypothesis rather than an open question.
26. [x] ~~First real-kernel accuracy measurement~~ DONE, via a compare
        mode that feeds both counters one identical event stream (the
        kernel-side equivalent of what Phase 1 did in Python).
        **+11.0% overestimate** at width=256/depth=4 under `hackbench`,
        max overshoot 836; **+0.0%** on an idle VM, where ~50-100
        distinct pids never collide at those parameters. Verified not to
        be a fall-through bug by shrinking the sketch to width=4/depth=1,
        where error appears immediately (+7.2%).
        **This figure is NOT comparable to 4.1's +31.9%** — different
        churn level, and a different statistic (a ratio of sums over all
        queried identities, versus the error on one tracked
        latency-sensitive task).

        **[NEW] A directly comparable measurement was then attempted**
        (Section 9.7): Phase 1's exact setup, ported to ~5,000 real
        churn processes and one tracked victim. It did NOT converge to
        Phase 1's +31.9% (got +277.3% at a 5s window, +98.9% at 15s), and
        that non-convergence is itself the finding — real OS scheduling
        contention among concurrent processes measurably affects sketch
        error in a way Phase 1's zero-cost synthetic events could not
        capture. Read as Phase 1 likely understating real-world error,
        not as this measurement being broken. See Section 9.7 for the
        full reasoning and the caveats on treating the exact magnitudes
        as precise (two data points, one run each).

27. [x] ~~Real-kernel replication of the targeted-collision attack~~ DONE
        for `comm` and `pid` (harness: `attack/collision_attack.py`).
        Victim and attackers are real processes; both counts come from
        the kernel's own query via a probe map, not a userspace
        reimplementation of the hash -- that being how 4.1.3 once
        produced a false "this hash is immune" result.

        | identity | seeds | attackers | inflation |
        |---|---|---|---|
        | comm | known | 64 @ 200/s | **+8,824%** |
        | comm | unknown | 64 @ 200/s | +0.0% |
        | comm | unknown | 256 @ 1000/s | **+5,450%** |
        | pid | known | 64 @ 200/s | +0.0% (unavailable) |
        | pid | unknown | 256 @ 1000/s | **+1,439%** |

        The attack transfers to a real kernel; Phase 1's finding was not
        a simulation artifact. Magnitude tracks attacker volume rather
        than being a property of the sketch, so **+8,824% is not
        comparable to 4.1.1's +440%**.

        CORRECTION TO SECTION 5's THREAT MODEL: it states the attack
        needs "only knowledge of the hash function and per-row seeds (not
        privileged system access)". On a real kernel the seeds live in a
        BPF map and reading them REQUIRES privilege, so an unprivileged
        co-tenant cannot mount the targeted attack -- only flooding. The
        adversary is an insider, a leak, or predictable seeds. Section 5
        should be revised accordingly.

        Also corrected mid-investigation: an early blind result of +0.0%
        briefly looked like "blind attacks are harmless". Retesting at
        higher volume gave +5,450%. Seed knowledge buys efficiency, not
        access.

        [ ] Single run per condition, no variance yet. The pid-vs-comm
        gap under blind flooding must NOT be read as a real effect.
        [ ] A contaminated run was caught and discarded: a stale
        scheduler was still attached, so a "pid" measurement was really
        the previous comm one. The harness now reads and prints the
        identity key from the kernel for that reason.

28. [x] ~~does the corrupted signal manipulate SCHEDULING?~~ Answered:
        **NO on this scale**, with a structural reason. Item 27 corrupts
        the count; this asks whether that changes what the scheduler does
        to the victim. Redone with `schbench` as the victim
        (`attack/schbench_attack.py`) after an earlier Python sleep-loop
        victim (`attack/latency_attack.py`) proved too noisy to decide.

        Attacker load held identical across three conditions; only the
        counter the mechanism reads changes. Metric is schbench request
        p99 (~1000 samples; wakeup-latency percentiles are unusable in
        rps mode, ~17 samples pinned to a ~900ms histogram artifact).

        | config | sketch+penalty | exact+penalty | gap |
        |---|---|---|---|
        | gentle penalty, high-rate victim, n=5 | 25,184us | 24,544us | +2.6% |
        | steep penalty, low-rate victim, n=5 | 14,896us | 11,056us | +34.7% |
        | steep penalty, low-rate victim, n=15 | 15,184us | 15,440us | -1.7% |

        The n=5 steep run looked real (+34.7%, correct direction, no flip
        between runs). At n=15 it collapsed to -1.7%. **Nearly written up
        as a positive finding; caught by higher N** -- the project's own
        recurring lesson, now twice in this line of work.

        Structural reason it is hard: a cell's inflation equals the
        colliding wakeups landing in it per window, which IS the load
        those attackers add. Large corruption (~89x, item 27) requires
        heavy load, which saturates victim latency on its own; at load
        light enough to measure latency cleanly, achievable corruption is
        only 2-3x -- too small to move scheduling even under a steep
        penalty. The corruption-heavy and latency-measurable regimes do
        not overlap on this 4-CPU machine.

        [x] All three named levers now tested, n=5 each, and all still
        null:

        | lever | config | gap |
        |---|---|---|
        | smaller sketch | width=32 (vs. 256) | -21.5% (wrong direction) |
        | more CPUs | 8 (vs. 4) | +3.0% |
        | combined | width=32, 8 CPUs, effectively uncapped adjustment | +11.4% |

        Every gap fell well within run-to-run noise. This substantially
        strengthens rather than overturns the finding: it now holds
        across sketch width, CPU count, mechanism steepness, and their
        combination, not just the original single configuration.

        Confirmed run on the fixed build (checked the scheduler binary's
        build timestamp against when these tests ran, rather than
        assuming) — no separate re-verification caveat needed here.