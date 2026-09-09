# Paper Draft — Sections 2–6

Companion to the Introduction (already drafted separately). Sections
below are a mix of writable-now prose and explicit placeholders for
work that hasn't been done yet. Search for `[NEEDS:` to find every spot
that requires either running an experiment, building something, or a
decision from the author before this is real.

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
identity to count, with no eviction — memory grows monotonically with
the number of distinct identities ever observed. This represents the
naive approach assumed implicitly by existing sched_ext example
schedulers, none of which currently perform this class of historical
behavioral tracking at all (see Related Work, Section 2.4).

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

[NEEDS: expand this properly. What exists so far, informally, from
prior research (not yet verified against a real literature search):]

- No existing sched_ext scheduler applies probabilistic/approximate
  data structures for behavioral tracking, as far as could be
  determined via web search at time of writing (see
  `sched_ext_embedded_research.md` for the specific searches run and
  their results).
- A proposed LPC 2026 talk ("Amortizing CPU wakeup costs with lazy
  wakeups," Samuel Wu, Google) addresses a related but distinct
  problem — detecting wakeup-heavy tasks to reduce idle-transition
  energy cost — without (as far as the published abstract indicates)
  addressing the memory-scaling problem of the tracking mechanism
  itself. [NEEDS: revisit after LPC 2026 (5–7 Oct) once slides/recording
  are published, to properly cite or differentiate.]
**[RESOLVED]** Literature search conducted (see search queries logged
in project history). Findings:

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

[NEEDS: this is one data point, not a result. A proper methodology
requires sweeping `w`, `d`, and `N` across a meaningful range, and
reporting accuracy/memory tradeoffs as curves, not single numbers. This
sweep has not been run yet.]

[NEEDS: a decision on what "acceptable accuracy loss" means
quantitatively for this domain — e.g., is a 37% overestimate on a
wakeup-frequency signal actually harmful to scheduling decisions, or
tolerable given the signal is only used for a coarse
classification/throttling decision rather than an exact computation?
This requires connecting the accuracy metric back to an actual
scheduling-outcome metric (Section 3.3), which hasn't been done.]

### 3.2 Phase 2: Kernel/BPF integration and hardware environment

[PARTIALLY STARTED: the environment now exists and a scheduler loads and
runs in it (see checklist items 2, 3, 12). No scheduling-quality results
have been produced yet — Section 4.2 remains unrun.]

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
- [NEEDS: an explicit justification paragraph for why a memory-capped
  VM is an adequate proxy for real embedded hardware, anticipating
  reviewer pushback — likely drawing on the reasoning already
  discussed: the hypothesis is about data-structure memory scaling, not
  ARM-vs-x86 timing behavior, but this should be stated and defended
  in the paper itself, not just assumed.]
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

## 4. Results

Phase 1 (synthetic, no kernel) results now exist in full, across four
rounds of testing: an initial single-point measurement, a corrected
version after a methodology fix (Section 2.3.1's windowing redesign),
a battery of rigor tests addressing reproducibility and worst-case
behavior, and a reproducibility/correctness verification pass. Phase 2
(kernel/BPF, real scheduling-quality outcomes) remains entirely
unbuilt — see Section 4.2.

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

**[PARTIALLY RUN]** The specific test this section originally asked for
— "whether a scheduling-relevant decision can be manipulated via the
same targeted-collision technique" — is done: checklist item 28,
answered no on this scale, with the structural reason (corruption and
load are coupled) recorded there and in Section 5.

[NEEDS: the broader scheduling-quality comparison is still entirely
unrun — the four-tier baseline benchmark (stock EEVDF, `scx_simple`,
this project's exact-counter tier, and a production scheduler) using
`schbench`/`cyclictest`/`hackbench` per Section 3.3's tooling choice.
Item 28 answered the security question; it did not compare the
approach's scheduling quality against any baseline, which is the
question this section is actually named for.]

### 4.2.1 Early directional policy simulation (pre-Phase-2)

Before committing to the real BPF/kernel build (Section 3.2), a
lightweight, pure-Python discrete-event scheduler simulation
(`scheduler_policy_simulation.py`) was built to get early, cheap signal
on whether the project's core mechanism — deprioritizing/boosting
tasks based on tracked wakeup frequency — actually changes scheduling
outcomes at all, before investing in kernel infrastructure.

**Explicit, repeated scope limitation, stated here as it is in the
script's own output**: this simulation has no connection to real
hardware timing, context-switch cost, cache effects, BPF verifier
constraints, or real kernel behavior. It operates in abstract simulated
time units and answers only "does this policy protect the
latency-sensitive task better than that policy, under the same
synthetic arrival process." It does not replace, and should not be
read as a preview of, the real Phase 2 kernel benchmarking planned in
Section 3.3 (schbench/cyclictest/hackbench against real EEVDF/
`scx_simple`/a production sched_ext scheduler).

**Three real issues were found and fixed during this exercise**, each
caught by applying the same discipline used throughout this project —
treating a suspiciously clean or suspiciously favorable result as a
signal to investigate, not to report:

1. **Event-model bug**: the first version processed one arrival-check
   per scheduling decision, then advanced time by the chosen task's
   full run duration with no arrivals modeled during that interval.
   This meant the runnable queue was drained in lockstep with arrivals
   and never built genuine backlog — producing a degenerate result
   (the FIFO-like policy showing exactly 0.0 latency on every single
   sample, and multiple distinct policies producing byte-identical
   output). Fixed by rebuilding as a proper discrete-event simulation
   with a real event queue (arrivals generated independently via a
   Poisson process, able to queue while the CPU is busy).

2. **One-shot-identity bug**: churn arrivals were originally modeled
   as unique, never-recurring task identities. Since each identity was
   only ever inserted once, tracked "wakeup frequency" was uniformly
   ~1 for every churn task — there was no actual recurring heavy-waker
   signal for the frequency-tracking policies to detect, which
   defeated the entire purpose of the comparison (this is precisely
   the mechanism the whole project concerns). Fixed by drawing churn
   arrivals from a fixed, persistent pool of identities with a skewed
   draw distribution (matching the Phase 1 skewed-churn model), so
   genuine recurring heavy wakers exist.

3. **Oracle-knowledge artifact**: the `scx_lavd`-style comparison
   policy initially had direct, privileged knowledge of which task was
   latency-sensitive (a hardcoded vruntime bonus), rather than having
   to infer this from observed behavior the way a real interactivity
   heuristic — and the frequency-tracking policies under test — must.
   This produced an apparent, seemingly meaningful result (`scx_lavd`
   -like beating the sketch/exact policies by roughly 2x on P99
   latency) that was entirely an artifact of the unfair information
   advantage, not a real algorithmic property. Fixed by requiring the
   policy to infer "interactivity" purely from each task's own observed
   recent burst-length history, on equal footing with every other
   policy — after which its apparent advantage disappeared completely,
   collapsing to byte-identical with plain EEVDF-like fairness.

**Result, after all three fixes**: `isolation_exact_tracking` and
`our_sketch_tracking` produced **byte-identical outcomes** to each
other and to plain EEVDF-like fairness in this scenario (P99 latency
22.4, matching to the reported precision, across 10 seeds). Only true
FIFO (`scx_simple_like`) differed meaningfully (P99 ratio 0.52x),
which is expected given it ignores vruntime/history entirely by
construction, not due to any tracking mechanism.

**Honest interpretation**: this is a genuine non-finding, reported as
such rather than engineered into a more flattering result by further
parameter tuning (a live temptation that was explicitly named and
declined during this work — see project discussion on the "fail early,
fail often" principle). Two readings are both plausible and neither is
resolved by this simulation alone: (a) sketch approximation error is
robust enough, at this load level, to never actually change a
scheduling decision relative to exact tracking — a mildly reassuring
signal for the core hypothesis; or (b) the specific penalty-based
mechanism tested here doesn't meaningfully leverage frequency-tracking
information at all in this scenario (since the latency task's own
vruntime already wins most contention without any penalty needed),
meaning this simulation has not yet exercised a condition under which
sketch-vs-exact divergence *would* show up, despite Phase 1's
higher-churn and adversarial tests demonstrating that divergence is
real at the tracking-accuracy level. Distinguishing between these two
readings would require either a higher-load regime or a boost-based
(rather than penalty-based) mechanism design — deliberately not
pursued further here, per the bounded scope agreed for this
exploratory detour, to avoid open-ended iteration toward a more
favorable number.



Phase 1 supports a **qualified, not unqualified**, version of the
original hypothesis. Under cooperative/uniform churn, the sketch
achieves substantial memory savings (65.7x at matched
accuracy-tolerant parameters, or a smaller but still meaningful ratio
at higher-accuracy parameter choices) at a real, quantifiable, and
tunable accuracy cost that behaves exactly as Count-Min Sketch theory
predicts. However, this result is **not robust to adversarial or
even moderately unfavorable churn conditions**: a volume-flooding
scenario degrades accuracy by roughly 9x, and a targeted-collision
attack — requiring only knowledge of the hash function, not privileged
access — degrades it by over 40x relative to the theoretical minimum
case. Any downstream claim or deployment recommendation must scope
itself explicitly to environments where task identity cannot be
adversarially influenced, pending further Phase 2 investigation of
whether this vulnerability translates into an actual exploitable
scheduling-decision manipulation.

---

## 5. Limitations and Threats to Validity

**Confirmed limitations (from actual testing, not anticipated):**

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

[NEEDS: entirely dependent on results. Cannot be honestly written yet.
Placeholder structure once results exist:]

- Restate the hypothesis and what was actually found (memory savings
  achieved: [NEEDS number]; accuracy cost: [NEEDS number]; scheduling
  outcome preserved: [NEEDS yes/no/partially]).
- State plainly whether the hypothesis was supported, partially
  supported, or not supported — per the project's own honesty standard
  established earlier in this research process, this should not be
  oversold if results are mixed or negative.
- [NEEDS: future work paragraph — likely candidates: real hardware
  validation, extending beyond wakeup-frequency to other resource
  signals (e.g. the memory-bandwidth case that motivated Section 1),
  revisiting after LPC 2026 talks are public to properly position
  against Wu's lazy-wakeups work.]

---

## Build checklist (everything marked `[NEEDS:` above, consolidated)

For quick reference when working through this in Claude Code:

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
8. [ ] Define quantitative "acceptable accuracy loss" threshold tied to
       a real scheduling-outcome metric (3.1) — now also needs to
       account for the adversarial-case error (440%), not just the
       benign-case error (37%), when defining what's "acceptable."
9. [ ] Write explicit justification for memory-capped VM as hardware
       proxy (3.2)
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
        [ ] Tiers (a), (b) and (d) are not obtained yet. Note tier (b)
        now means fetching `scx_simple` from `scx-c-examples`, since it
        is no longer in this repo.
        [ ] `boost` carries no validation from Phase 1 — see item 23.
13. [ ] Run Phase 2 kernel experiments once 3–12 are done (4.2), using
        schbench/cyclictest/hackbench (not a bespoke metric) and
        reporting results as relative multipliers against the EEVDF
        baseline (per the "Towards Agentic OS" precedent cited in
        3.3), not just relative to this project's own other variants.
        MUST also include a real-kernel replication of the
        targeted-collision attack (4.1.1), not just the benign-case
        comparison originally
        scoped.
14. [x] ~~Write Results, Limitations, Conclusion once real data
        exists~~ Results (4) and Limitations (5) now have substantial
        real content from Phase 1. [ ] Conclusion (6) still blocked on
        Phase 2.
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
26. [ ] NEW: first real-kernel accuracy measurement, via a compare mode
        that feeds both counters one identical event stream (the
        kernel-side equivalent of what Phase 1 did in Python).
        **+11.0% overestimate** at width=256/depth=4 under `hackbench`,
        max overshoot 836; **+0.0%** on an idle VM, where ~50-100
        distinct pids never collide at those parameters. Verified not to
        be a fall-through bug by shrinking the sketch to width=4/depth=1,
        where error appears immediately (+7.2%).
        **This figure is NOT comparable to 4.1's +31.9%** — different
        churn level, and a different statistic (a ratio of sums over all
        queried identities, versus the error on one tracked
        latency-sensitive task). [ ] A directly comparable measurement,
        matching Phase 1's churn level and single-target statistic, has
        not been made.

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