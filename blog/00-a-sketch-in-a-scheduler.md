# A Count-Min Sketch in a Linux scheduler: 4x less memory, and a less predictable tail

A BPF scheduler that adapts to task behaviour has to remember something
about each task, and that memory grows with the number of distinct tasks
the machine has seen. On a busy system with short-lived processes, that
is neither small nor predictable.

Probabilistic counting structures are the standard answer to this
elsewhere in systems software — network telemetry, query planners,
stream processing. As far as I can determine, nobody had tried one
inside a scheduler.

So I built one, and measured it. The short version:

> **A Count-Min Sketch at 8.3 KB keeps working at a memory budget where
> exact per-task counters have stopped working entirely.** Median
> latency is equivalent (tested). Tail latency is not — but what the
> sketch costs turns out to be *predictability* rather than a flat
> penalty: usually comparable to exact counting, occasionally several
> times worse. It is a trade, not a free lunch.

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

## What the sketch actually costs is predictability

The equivalence test put the mean p99 ratio at 11–39% worse, and I
first wrote that up as "a 17% tail penalty." Looking at the
per-repetition ratios, that description is wrong in a way worth
correcting:

```
0.69 0.73 0.88 0.89 0.89 0.92 0.93 0.94 0.96 0.96 0.97 1.01 1.03 1.04 1.07
1.29 1.36 1.37 1.39 1.47 1.48 1.50 1.60 1.60 1.65 1.68 1.99 2.08 2.51 3.08
```

**The sketch was better than exact counting in 11 of 30 runs.** The
spread runs from 31% better to 208% worse. There is no 17% tax; there is
a right-skewed distribution whose mean sits 17% above parity.

The variance numbers say it more directly:

| condition | median p99 | coefficient of variation | worst run / median |
|---|---|---|---|
| exact @ 32 KB | 10,032µs | **0.18** | 1.8x |
| sketch @ 8 KB | 12,544µs | **0.40** | 2.5x |
| sketch @ 32 KB | 10,336µs | 2.18 | **23.3x** |

Exact counting is boring: its worst repetition is 1.8x its median. The
sketch is erratic. And note the last row — at *matched* memory the
sketch's median is within 3% of exact, and that enormous CV comes almost
entirely from one repetition that hit 24x.

So the sketch doesn't pay a steady tax. It usually matches exact
counting and occasionally doesn't, which for a scheduler is arguably
the worse failure: a known 17% penalty you can budget for, while
unpredictable multi-second excursions you cannot.

## And that cost is the sketch's, not the memory saving's

The most useful number in the whole study came from a control I nearly
didn't bother running: the sketch at *matched* memory, 32 KB against
exact's 32 KB.

It's also not equivalent on p99. Same budget, same everything, still a
heavier tail. So the 17% is not what you pay for the memory saving — it
is what a Count-Min Sketch costs at any size, because collisions
occasionally inflate a task's count and produce a bad scheduling
decision that exact counting would not make. One repetition showed it
starkly: 240,384µs, twenty-four times that condition's own median, with
nothing else in that repetition disturbed.

Which reframes the result. You are not trading memory for tail latency.
You are paying a tail penalty for approximation, and separately getting
a memory saving — and if your budget is large enough for exact counting
to work, the sketch has nothing to offer you.

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

The requirement nobody writes down is that **identities persist across
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
