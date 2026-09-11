# A Count-Min Sketch in a Linux scheduler: 4x less memory, a noisier tail

A BPF scheduler that adapts to task behaviour has to remember something
about each task, and that memory grows with the number of distinct tasks
the machine has seen. On a busy system with short-lived processes, that
is neither small nor predictable.

Probabilistic counting structures are the standard answer to this
elsewhere in systems software — network telemetry, query planners,
stream processing. A literature search before starting this turned up no
`sched_ext` scheduler using approximate data structures for behavioural
tracking — though absence of evidence and all that, and I'd genuinely
like to hear about prior work if it exists.

So I built one, and measured it. The short version:

> **A Count-Min Sketch at 8.3 KB keeps working at a memory budget where
> exact per-task counters have stopped working entirely.** Typical
> latency is identical. Tail latency is worse on average and much
> noisier: across two independent runs, the sketch beat exact counting
> in about 40% of runs and was more than 50% worse in about 30%. At
> *equal* memory the two are indistinguishable — so the tail cost is
> the price of the memory, not of approximating.

Below that budget the story gets more interesting, because the two
structures stop working at different points and fail in different ways.

## What was built

`scx_cms` is a `sched_ext` scheduler that tracks how often each task
wakes over a rolling window and penalises frequent wakers, so a
latency-sensitive task gets CPU sooner.

One design decision made the whole evaluation possible: **the counting
method is a load-time flag, not a compile-time choice.** Exact counters
and the sketch are both compiled in; `--tracker` selects between them
and the verifier eliminates the unused branch. Everything else — the
policy, the window, the identity key, the adjustment applied — is
byte-identical between the two.

That means the counting method is genuinely the only variable. No
separate builds, no "we changed one thing and also rebuilt with a
different compiler."

## The measurement

A `schbench` victim — a latency-sensitive task — running against 128
background tasks that wake 200 times a second while using very little
CPU each.

That background shape is deliberate. A task that burns CPU is already
deprioritised by ordinary vtime fairness; the information vtime *cannot*
see is "wakes constantly but is cheap." That's exactly what this
mechanism proposes to track, so it's the regime where it should pay.

Each configuration carries its own memory budget, all of them
interleaved in one randomised matrix, 30 repetitions. (The "one matrix"
part matters more than it sounds — see below.)

## The result

| tracker | memory | p50 | p99 |
|---|---|---|---|
| do nothing | — | 3,912µs | 65,440µs |
| count-blind penalty | 35.6 KB | 11,040µs | 16,864µs |
| **exact counters** | **35.6 KB** | **3,892µs** | **10,144µs** |
| exact counters | 9.6 KB | 3,908µs | 63,680µs |
| **sketch (d=2, w=256)** | **8.3 KB** | **3,924µs** | **11,344µs** |

Three things in that table.

**The sketch at 8.3 KB works; exact counting at 9.6 KB does not.** But
"works" needs qualifying, and the qualification only appeared when I
tested it properly. Those overlapping p99 ranges look like equivalence
and are not: a paired equivalence test at n=30, with the margin declared
before the run, refuted equivalence on p99 while confirming it on p50.
Overlapping ranges mean a difference was not detected, not that none
exists.

**Exact counting at 9.6 KB does not work at all.** Its p99 of 63,680µs
sits on top of the do-nothing baseline's 65,440µs. It hasn't degraded —
it has stopped. An exact map that can't hold the live identity set
evicts constantly, lookups miss, counts read as zero, and the mechanism
silently stops acting.

**The count-blind row is the control that makes the rest meaningful.**
It applies the same vtime perturbation while ignoring the tracked count
entirely. It reaches a decent tail (16,864µs) by making *every* wakeup
three times slower — including the task being protected. Both working
configurations beat it while leaving the median untouched, which is how
you know they're discriminating between tasks rather than just
disturbing everything.

That control also cost me a 6.8x result earlier in the project. It
turned out roughly 82% of what I'd attributed to wakeup tracking was
generic perturbation. Worth building before you believe your own
numbers.

## Where each structure stops

| budget | exact | sketch |
|---|---|---|
| 32 KB | works | works |
| 16 KB | degraded | works |
| 8 KB | **inert** | works |
| 2 KB | inert | **blunt** |

The two failures are different in kind, and that difference is the
useful part.

**Exact counting fails silently.** Entries evict, queries miss, the
mechanism stops adjusting, and nothing anywhere signals it. Scheduling
quietly reverts to the underlying policy — which is survivable, but you
won't know it happened.

**The sketch fails loudly.** It never evicts, so under-provisioning
means collisions, collisions mean overestimation, and eventually every
task looks like a heavy waker. At 2 KB its median collapsed to the
count-blind baseline's level: it had stopped distinguishing tasks and
was penalising everything equally. The tail still improved, which is
precisely why you must look at the median too — p99 alone would have
called that a success.

So the question to ask about a bounded counting structure isn't which is
more accurate at a given size. It's **at what size does each stop
working, and can you tell from outside when it has.**

## The tail cost is real, and it doesn't arrive as a steady tax

The equivalence test put the mean p99 ratio at 11–39% worse, and I first
wrote that up as "a 17% tail penalty." Both runs say that description is
wrong.

Per-repetition ratios of sketch to exact, measured twice independently:

| | run A (n=30) | run B (n=60) |
|---|---|---|
| median ratio | 1.18x | 1.14x |
| 10th percentile | 0.89x | 0.87x |
| 90th percentile | 2.08x | 1.85x |
| sketch **better** | 37% of runs | 40% of runs |
| sketch >50% worse | 30% of runs | 33% of runs |

**In roughly 40% of runs the sketch beats exact counting outright. In
roughly 30% it's more than 50% worse.** The median sits at ~1.15x
because those cancel, not because any particular run experiences 15%.

That shape replicated closely across two independent runs, which is more
than I can say for most things in this project. What you're buying with
4x less memory is not a predictable 15% tax — it's a coin weighted
slightly against you.

I should flag that this is the same mistake this project made elsewhere,
one level up. Reporting a median tail ratio hides that a third of runs
are 50% worse, exactly as reporting p99 alone hid what `flat` was doing
to the median. Summary statistics conceal distributions at every level
you apply them.

## And the cost is the memory's, not approximation's

I got this backwards initially, on the strength of one outlier.

At *matched* memory — sketch at 32 KB against exact at 32 KB — the two
are indistinguishable:

| | run A | run B |
|---|---|---|
| sketch @32KB / exact @32KB, p99 | 1.03x | 1.04x |
| sketch @8KB / exact @32KB, p99 | 1.25x | 1.36x |

Give the sketch the same memory and it performs the same. Take 4x the
memory away and the tail degrades. **So you are trading tail latency for
memory**, which is a comprehensible engineering trade, rather than
paying some intrinsic tax for approximating, which would not be.

## Geometry is not a detail

At a fixed 8 KB, varying only the width/depth split:

| geometry | p99 |
|---|---|
| depth 2, width 256 | **10,144µs** |
| depth 1, width 512 | 12,208µs |
| depth 4, width 128 *(the default)* | 18,624µs |
| depth 8, width 64 | 15,344µs (blunt) |

**The default is 1.8x worse than the best at identical memory.** Width
buys more than depth here, replicating a finding from the synthetic
phase. Any memory figure quoted for a sketch is really a figure for a
*geometry*, and choosing depth 2 over depth 4 is the difference between
matching exact counting and falling well short of it.

## Where it doesn't hold

**Task churn breaks it, and no identity key fixes that.** With
continuously respawning background processes, exact counting is inert at
every budget and the sketch becomes blunt. Keying on PID can't see
short-lived tasks — they never live long enough to look like frequent
wakers. Keying on `comm` sees them, but aggregates a multithreaded
victim's threads into the heaviest waker on the system, so the mechanism
penalises exactly the task it exists to protect.

The requirement that goes unstated is that **identities persist across
the tracking window** and match the granularity of the decision. Those
are two separate properties, and task churn breaks the first while
multithreading breaks the second.

**Everything here is one machine.** aarch64, 4 CPUs, kernel 6.19, inside
a VM. No x86 validation. The VM's timer delivery floor (~1.7ms) was high
enough to invalidate one of my two candidate workloads outright, which
is a good reminder that environment-specific effects are present until
you've checked elsewhere.

**Energy is unmeasured**, and it's the more natural application. A
wakeup has a direct physical cost — it drags a core out of a deep idle
state. That's a one-step causal chain, where the latency argument is
three steps. And a sketch's overestimation matters far less to a
batching heuristic than to a scheduling decision. I couldn't measure it:
no RAPL in the guest.

## Why this took much longer than it should have

Seven claims made and withdrawn along the way, including, briefly, the
conclusion that the whole idea was refuted.

Almost none of those failed because the hypothesis was wrong. They
failed because an instrument was wrong — a harness that ran conditions
in fixed order so carryover always landed on the same neighbour; a
metric that scored a broken tracker as highly as a working one; a BPF
map that stops behaving like an LRU at small sizes.

The final numbers use five controls that didn't exist when I started,
each added after something it would have caught went wrong. The raw
output for every run, including the ones that produced the wrong
answers, is archived alongside the code.

I've written the failures up separately, because they turned out to be
more generally useful than the result.

## Data

Every figure in this post comes from an archived run. Raw harness output,
unedited, including the parameters each run printed at startup:

| claim | file |
|---|---|
| the headline table (all six conditions, one interleaved matrix, n=20) | [`headline-single-matrix-n20.txt`](../results/raw/headline-single-matrix-n20.txt) |
| the equivalence test and per-repetition ratios (n=30) | [`equivalence-n30-prereg.txt`](../results/raw/equivalence-n30-prereg.txt) |
| the ratio distribution replication, and excursion rates (n=60) | [`excursion-rate-n60.txt`](../results/raw/excursion-rate-n60.txt) |
| where each structure stops working, across budgets | [`thesis-confirmation-n20.txt`](../results/raw/thesis-confirmation-n20.txt), [`o1-o4-budget-geometry-churning-n20.txt`](../results/raw/o1-o4-budget-geometry-churning-n20.txt) |
| the geometry sweep | [`o1-o4-budget-geometry-churning-n20.txt`](../results/raw/o1-o4-budget-geometry-churning-n20.txt) |
| identity churn breaking the mechanism | [`r4-identity-bestshot-n10.txt`](../results/raw/r4-identity-bestshot-n10.txt) |

The equivalence test was pre-registered before the data existed:
[`PREREGISTRATION_equivalence.md`](../benchmark/PREREGISTRATION_equivalence.md),
analysed by [`analyse_equivalence.py`](../benchmark/analyse_equivalence.py).

Ten claims were made and withdrawn on the way to this one. Each is
recorded with the file that produced it and the file that overturned it:
[`REVISIONS.md`](../results/REVISIONS.md). Measurement environment:
[`ENVIRONMENT.md`](../results/ENVIRONMENT.md).
