# CMS Prototype — Phase 1 (No Kernel Required)

This is the lowest-friction possible starting point for the sched_ext
research project. It validates the core hypothesis — sketch vs. exact
counters under simulated process churn — in plain Python, in a
container, on your Mac. No VM, no custom kernel, no GUI setup steps.

## Run it

```bash
chmod +x run.sh
./run.sh
```

That's it. First run builds a small Python image (seconds, not
minutes); every run after that is instant since the image is cached
and `experiment.py` is mounted live (edit locally, re-run immediately,
no rebuild).

To also get a chart of memory growth over time:
```bash
./run.sh --plot
```
This writes `memory_growth.png` into the current directory (visible on
your Mac immediately — it's a live-mounted volume, not something
trapped inside the container).

## What this actually tests

`experiment.py` simulates:
- **Process churn**: thousands of short-lived "worker" task identities,
  each firing a handful of wakeup events then disappearing — standing
  in for the embedded/mobile process churn discussed in the project
  definition.
- **One persistent latency-sensitive task**: the thing you actually
  care about tracking accurately throughout.

It then compares a `CountMinSketch` (fixed memory footprint) against an
`ExactCounter` (a plain dict, memory grows with distinct identities
seen) on two axes:
1. **Memory footprint over time** — does the sketch actually stay flat
   while the exact counter grows, as hypothesized?
2. **Accuracy** — how close is each method's estimate of the
   latency-sensitive task's true wakeup count?

## Regression tests

`test_sketch_lib.py` is a pytest suite guarding `sketch_lib.py` — the
code that gets ported to BPF next. It exists because Phase 1 was
bitten twice by a fix in `sketch_lib.py` silently failing to propagate
into dependent scripts (see the paper's Section 4.1 audit note); this
suite exists so that class of drift fails a test run instead of
waiting for another manual audit, protecting the upcoming BPF port.

```bash
docker build -t cms-prototype .
docker run --rm -v "$(pwd)":/work cms-prototype pytest -q
```

It covers both CMS invariants that must hold by construction
(never-underestimate, merge equivalence between the rotating buffers
and a single sketch) and frozen-value regression checks captured from
the current implementation at a fixed seed (e.g. the paper's reported
537,901-byte exact-counter figure and 8,192-byte sketch figure at
width=256/depth=4). An intentional behavior change should update the
frozen values deliberately, with a note on why — a failure here isn't
automatically a bug, but it always means something changed and needs
explaining.

## Why this comes before any BPF/kernel work

This isolates the actual research question — does the sketch approach
work at all, and how big is the accuracy/memory tradeoff — from the
much larger effort of building the kernel/BPF harness. If the sketch
turns out not to hold up here (e.g. hash collisions under high churn
degrade accuracy too much), that's a cheap, fast thing to discover and
iterate on now, rather than after setting up a full sched_ext dev
environment.

## Parameters worth experimenting with

Edit the call to `run_simulation()` at the bottom of `experiment.py`:
- `num_churn_identities` — how many distinct short-lived tasks (higher
  = more realistic churn, and where the sketch's advantage should grow)
- `wakeups_per_churn_task` — range of wakeup counts per churn task
- `latency_task_wakeups` — how many wakeups the task you care about
  protecting actually generates
- Sketch `width`/`depth` in `CountMinSketch.__init__` — the classic
  sketch tuning knobs (bigger = more memory but better accuracy)

A good next experiment: sweep `num_churn_identities` across a few
orders of magnitude and plot how the exact counter's memory grows
linearly while the sketch stays flat, and separately how sketch
accuracy degrades (if at all) as churn increases relative to a fixed
sketch size — that's the actual core result for your writeup.

## When to move to the real kernel/BPF phase

Once you're satisfied the sketch's accuracy/memory tradeoff is
favorable here, the next step is porting the validated logic into an
actual sched_ext BPF program's `runnable`/`quiescent` callbacks,
tracking real task wakeups instead of synthetic data — that's where the
Fedora VM setup (covered separately) becomes necessary, since BPF
programs need a real kernel with `CONFIG_SCHED_CLASS_EXT`. Nothing
about that setup is required to make progress today, though.
