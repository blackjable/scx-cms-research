# Can a Count-Min Sketch replace exact per-task counters in a Linux scheduler?

A scheduler that adapts to how tasks behave has to remember something
about each task. `sched_ext` makes that easy — a BPF scheduler can keep a
hash table keyed on pid and consult it from the scheduling callbacks. The
catch is that the memory grows with the number of distinct tasks the
machine has seen, which on a busy system with short-lived processes is
neither small nor predictable.

Bounding that cost is a solved problem elsewhere in systems software.
Count-Min Sketches give fixed-size approximate counting and are routine in
network telemetry, query planners and stream processing. Applying one
inside a scheduler is an obvious idea, and as far as I could determine
nobody had tried it.

So I built one: [`scx_cms`](https://github.com/blackjable/scx-cms) tracks
per-task wakeup frequency using **either** exact counters **or** a
Count-Min Sketch — selectable at load time, with the policy, window,
identity key and adjustment identical between them — and penalises
frequent wakers so a latency-sensitive task gets CPU sooner.

## What was measured

A `schbench` victim against 128 background tasks that wake 200 times a
second while using little CPU each. That shape is deliberate: a task that
burns CPU is already deprioritised by ordinary fairness, so the
information a scheduler *cannot* already see is "wakes constantly but is
cheap". Tail latency (p99) of the victim is the outcome.

Then shrink the memory budget for the tracking and see which structure
breaks first.

| tracker | tracking memory | victim p99 |
|---|---|---|
| exact counters | 35.6 KB | 10,144µs |
| exact counters | 9.6 KB | 63,680µs — **stopped working** |
| **Count-Min Sketch** | **8.3 KB** | **11,344µs** |

Exact counting at 9.6 KB has not degraded, it has *stopped*: its tail sits
on top of the do-nothing baseline of 65,440µs. The map can no longer hold
the live identity set, so lookups miss, counts read as zero, and the
mechanism quietly stops acting. The sketch at a smaller budget still
works. **That gap is the result.**

## The cost

Not free, and not a steady tax. Equivalence was tested rather than
assumed, with the margin declared before the run: median latency **is**
equivalent (90% CI [0.974, 1.060]), tail latency is **not**
([1.114, 1.394]).

The mean hides the shape. Across two independent runs the sketch was
*better* than exact counting in 37% and 40% of repetitions, and more than
50% worse in 30% and 33%. What less memory buys is a coin weighted
slightly against you.

At *matched* memory the two are indistinguishable, so that tail cost is
the price of the saving rather than something inherent to approximating.

Full table including the controls that make the above meaningful:
[`blog/00`](blog/00-a-sketch-in-a-scheduler.md).

---

## Start here

| | |
|---|---|
| [`CONTEXT.md`](CONTEXT.md) | the whole project in ~1,300 words |
| [`blog/`](blog/) | seven posts — the readable version |
| [`results/REVISIONS.md`](results/REVISIONS.md) | **thirteen claims made and withdrawn** |
| [`REVIEW.md`](REVIEW.md) | what to attack, if you're reviewing |

If you read one thing, read `REVISIONS.md`. It is the most useful
document here and the least flattering.

---

## What makes this unusual

Thirteen claims were stated during this work and later withdrawn. Each is
recorded with the raw file that produced it and the raw file that
overturned it.

Eight were instrument failures. **Four were not** — the measurement was
correct and an explanation was attached to it that was never tested. That
turned out to be the characteristic failure of the whole project:

- a single outlier became "a sketch-specific failure mode"
- a control failing for an unrelated reason became "the tail cost is
  intrinsic to approximating"
- a thrashing cache became "BPF's `LRU_HASH` is broken at small sizes"
- two noisy maxima became "fixed condition ordering biases results" —
  which had reached a paper, a blog post and three source comments, and
  been recommended to other people, before a controlled test found no
  effect at all (p = 0.86)

Every run that produced a wrong answer is kept in
[`results/raw/`](results/raw/) rather than deleted.

---

## Findings that don't depend on sketches

- **A count-blind control is necessary and isn't a standard baseline.**
  "Mechanism on vs off" conflates *consulting a signal* with *perturbing
  scheduling at all*. A control applying the same perturbation while
  ignoring the count reproduced **82%** of an apparent 6.8x win. About
  forty lines. No standard `sched_ext` baseline tier catches it, because
  they all vary the *scheduler*.
- **Behavioural tracking needs identities that persist.** Fine keys (pid)
  can't see churning tasks; coarse keys (`comm`) aggregate a
  multithreaded victim into the heaviest waker on the system. No key
  choice escapes both.
- **Bounded structures fail in different kinds.** An entry-bounded exact
  map fails *silently* — evicts, reads zero, stops acting, nothing
  signals it. A sketch fails *loudly* — never evicts, so
  under-provisioning inflates estimates until the penalty lands on the
  protected task. They fail at different budgets, and that asymmetry
  decides between them more than accuracy does.

---

## Scope

One environment: Fedora 44, kernel 6.19.10, **aarch64, 4 vCPU**, in a
Lima VM on an Apple M4. Latency only — no bare metal, no x86, and energy
unmeasured because the guest exposes no RAPL counters. Where task
identities churn rather than persist, neither structure carries usable
information.

Predictions for what should survive a bare-metal run, and what should
move, are written down and dated in the paper's limitations section
before any such run happens.

---

## Layout

| path | |
|---|---|
| [`blog/`](blog/) | seven posts |
| [`results/`](results/) | raw output, the manifest, the revision record |
| [`benchmark/`](benchmark/) | harnesses, pre-registrations, analysis scripts |
| [`sched_ext_phase2_handoff/`](sched_ext_phase2_handoff/) | paper draft, delivery plan, Phase 1 Python prototype |

The scheduler itself is a separate repository:
**https://github.com/blackjable/scx-cms**
