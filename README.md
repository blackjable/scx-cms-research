# Can a Count-Min Sketch replace exact per-task counters in a Linux scheduler?

A `sched_ext` (BPF) scheduler tracks how often each task wakes and
penalises frequent wakers, so a latency-sensitive task gets CPU sooner.
The memory for that tracking grows with the number of distinct tasks the
machine has seen. This asks whether a fixed-size probabilistic counter
can replace it.

**Answer: a qualified yes — roughly a quarter of the memory, identical
typical latency, a worse and noisier tail.**

| condition | memory | p50 | p99 |
|---|---|---|---|
| do nothing | — | 3,912µs | 65,440µs |
| count-blind penalty | 35.6 KB | 11,040µs | 16,864µs |
| **exact counters** | **35.6 KB** | **3,892µs** | **10,144µs** |
| exact counters | 9.6 KB | 3,908µs | 63,680µs |
| **Count-Min Sketch** | **8.3 KB** | **3,924µs** | **11,344µs** |

n=20, one interleaved matrix, randomised condition order
([raw output](results/raw/headline-single-matrix-n20.txt)).

Exact counting at 9.6 KB has *stopped working* — its tail sits on the
do-nothing baseline. The sketch at a smaller budget still works. That gap
is the result.

Equivalence was tested rather than assumed, with the margin declared
before the run: median latency **is** equivalent (90% CI [0.974, 1.060]),
tail latency is **not** ([1.114, 1.394]). And the mean hides the shape —
across two runs the sketch was *better* than exact counting in 37% and
40% of repetitions, and more than 50% worse in 30% and 33%. What less
memory buys is a coin weighted slightly against you, not a steady tax.

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
