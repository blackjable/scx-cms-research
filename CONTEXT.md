# Project context — paste this into a fresh conversation

A self-contained briefing on the `scx_cms` study. Everything it refers to
is public, so links can be followed rather than taken on trust.

---

## What this is

A `sched_ext` (BPF) scheduler built to answer one question: **can a
Count-Min Sketch replace exact per-task counters for tracking wakeup
frequency, saving memory without hurting scheduling quality?**

Two repositories:

- **https://github.com/blackjable/scx-cms-research** — paper draft, blog
  posts, benchmark harnesses, raw output of every run
- **https://github.com/blackjable/scx-cms** — the scheduler

---

## The result

**Qualified yes: roughly a quarter of the memory, identical typical
latency, a worse and noisier tail.**

| condition | map | p50 | p99 |
|---|---|---|---|
| do nothing | — | 3,912µs | 65,440µs |
| count-blind penalty | 35.6 KB | 11,040µs | 16,864µs |
| exact, 341 entries | 35.6 KB | 3,892µs | 10,144µs |
| exact, 85 entries | 9.6 KB | 3,908µs | 63,680µs |
| sketch, d=2 w=256 | 8.3 KB | 3,924µs | 11,344µs |

n=20, one interleaved matrix, randomised order.
[`headline-single-matrix-n20.txt`](https://github.com/blackjable/scx-cms-research/blob/main/results/raw/headline-single-matrix-n20.txt)

Three things matter in that table:

1. **Exact counting at 9.6 KB has stopped working** — its p99 sits on the
   do-nothing baseline. The sketch at a *smaller* budget still works.
2. The memory ratio is 36,432 / 8,496 bytes = **4.29x**, measured from
   the kernel's own `memlock`, not from configured dimensions.
3. The count-blind row is the control that makes the rest meaningful.

**Equivalence was tested, not assumed** (pre-registered, ±20% margin,
paired TOST on log-ratios, n=30):

- p50 **is** equivalent — 90% CI [0.974, 1.060]
- p99 is **not** — 90% CI [1.114, 1.394]

But the mean conceals the shape. Across two independent runs the sketch
was *better* than exact counting in **37% and 40%** of repetitions, and
more than 50% worse in **30% and 33%**. What less memory buys is not a
predictable premium but a coin weighted slightly against you.

**At matched memory the two are indistinguishable** (1.03x, 1.04x), so
the tail cost is the price of the memory saving, not an intrinsic cost of
approximating.

### Bounds

- Where task **identities churn** rather than persist, exact counting is
  inert at every budget and the sketch goes blunt. Neither works.
- The victim must not saturate the machine. At 16 threads / 400 rps
  everything collapses together.
- One environment: Fedora 44, kernel 6.19.10, **aarch64, 4 vCPU**, Lima
  VM on an Apple M4. No bare metal. No x86. Energy unmeasured — no RAPL
  in the guest.

---

## Read this before trusting anything else

**[`results/REVISIONS.md`](https://github.com/blackjable/scx-cms-research/blob/main/results/REVISIONS.md)**
— thirteen claims made and withdrawn, each tied to the raw file that
produced it and the raw file that overturned it.

Eight were instrument failures. **Four were not: the measurement was
correct and an explanation was attached to it that was never tested.**
That is the project's characteristic failure, and it recurred four times:

- a single 240ms outlier became "a sketch-specific failure mode"
  (revision 9) — exact counting shows the same rate
- a control failing for an unrelated reason became "the tail cost is
  intrinsic to approximation" (revision 10) — it isn't
- a thrashing cache became "BPF's LRU_HASH is broken at small sizes"
  (revision 12) — it's what any LRU does below its working set
- two noisy maxima became "fixed condition ordering biases results"
  (revision 13) — a controlled test found **no effect at all**,
  p = 0.86

Revision 13 is the one to read. It had reached a paper, a blog post and
three source-code comments as established fact, and was recommended to
other people, before anyone ran the experiment that could refute it.

**Do not resurrect these.** If a draft, comment or older summary asserts
an ordering bias, a `LRU_HASH` cliff, a sketch-specific excursion mode,
or that approximation carries an intrinsic tail cost — it is stale.

---

## What survives, and is worth reusing

- **The count-blind control.** Comparing "mechanism on vs off" conflates
  *consulting the signal* with *perturbing scheduling at all*. A control
  applying the same perturbation while ignoring the count reproduced
  **82%** of what looked like a 6.8x win. ~40 lines. No standard
  `sched_ext` baseline tier catches this, because they all vary the
  *scheduler*.
- **A do-nothing reference in every matrix.** Without it a discrimination
  metric cannot tell a working tracker from one that has silently
  stopped.
- **Equivalence testing.** Overlapping ranges mean a difference was not
  *detected*, not that none exists. The sloppier the experiment, the more
  things you can declare equivalent.
- **Identity stability.** Wakeup tracking needs identities that persist
  across the tracking window. Fine keys (pid) can't see churning tasks;
  coarse keys (comm) aggregate a multithreaded victim into the heaviest
  waker on the system. No key choice escapes both.
- **Silent vs loud failure.** An entry-bounded exact map fails *silently*
  — evicts, reads zero, stops acting, nothing signals it. A sketch fails
  *loudly* — never evicts, so under-provisioning inflates estimates until
  the penalty lands on the protected task. They fail at different
  budgets, and that asymmetry decides between them more than accuracy
  does.

---

## Layout and hazards

Three local directories; only two are published:

| path | what |
|---|---|
| `~/sched_ext/research` | the research repo |
| `~/sched_ext/scx_cms` | the scheduler repo (canonical source) |
| `~/sched_ext/repo` | a clone of upstream `sched-ext/scx` |

**`~/sched_ext/repo` must never be pushed.** It is upstream's, and its
`main` sits 11 commits ahead with this scheduler on it. It exists because
`scx_cms` does not build standalone — it depends on `scx_utils` by
relative path, so it must sit inside an scx checkout at
`scheds/experimental/scx_cms/` to compile. That copy is a build tree kept
in sync by rsync; the canonical source is the standalone repo.

Measurements run in a Lima VM (`limactl shell scx-fedora`). Two
benchmarks must never run concurrently — it happened once and
contaminated 15 minutes of results.

---

## State and what's open

Measurement phase is complete. Both repos are public and clean.

- **Bare metal.** Nothing has been validated off this one VM. Predictions
  for what should survive and what should move are written down and dated
  in the paper's limitations section — that is deliberate, so the
  hardware run is a scoreboard. Blocked on buying a used ThinkPad T14
  (i5 10th gen); the one question to ask a seller is whether the **BIOS
  supervisor password is cleared**, as that cannot be fixed after
  delivery. Setup is in `sched_ext_phase2_handoff/04_bare_metal/`.
- **Energy.** The established reason to track wakeup frequency is energy,
  not latency, and none was measured. Method is written up in advance in
  `benchmark/ENERGY_METHOD.md`.
- **Publishing.** Seven blog posts are written. Links inside them are
  repo-relative and need absolutising for anywhere other than GitHub —
  two prefixes, documented in `blog/README.md`.
- **Never tested, and arguably the strongest competitor:**
  `BPF_MAP_TYPE_TASK_STORAGE` — O(1) per live task, freed by the kernel
  on exit, no eviction policy to get wrong.

---

## How to work on this

The standard that produced the result, and the one worth keeping:

1. **When a measurement suggests a mechanism, state it as a hypothesis
   with a test, not as a finding.** Four of the thirteen retractions were
   this. The tests were all cheap — under an hour each.
2. **When two runs disagree, count the ways they differ before
   explaining why.** If it's more than one, you have a candidate, not an
   explanation.
3. **A more careful statistic does not fix a confounded design.** It
   makes the confound harder to see, because the careful version reads as
   more trustworthy.
4. **Archive raw output.** Every table is a transcription of a file in
   `results/raw/`, catalogued in `results/MANIFEST.md`. Figures that were
   never archived have twice turned out not to replicate.
5. Prefer re-running a measurement over reasoning about it. The VM is
   available and most runs take under an hour.
