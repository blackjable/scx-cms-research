# Blog series: a Count-Min Sketch in a Linux scheduler

Eight posts. Post 00 is the result; the rest are what it took to trust
it.

I came to this knowing how to write a scheduler and nothing about how to
measure one. That turned out to be the harder half: thirteen claims made
and withdrawn, most of them because an instrument was wrong rather than
because the idea was. Each fix — a control condition, a do-nothing
reference, an equivalence test — is standard practice somewhere else and
was new to me.

Four of the thirteen were a different failure, and the more interesting
one: the measurement was correct and I attached an explanation to it
that I never tested. The last of those was the benchmarking advice in
post 01, which I had to withdraw after running the experiment that could
say no.

So these are written from the position of someone who didn't know, for
anyone else who came to benchmarking through code rather than through a
statistics course. The mistakes are the content.

| # | post | stands alone? |
|---|---|---|
| 00 | [A Count-Min Sketch in a Linux scheduler](00-a-sketch-in-a-scheduler.md) | the result |
| 01 | [I spent a day fixing a benchmark bug that wasn't there](01-benchmark-was-lying.md) | yes — any benchmark author |
| 02 | [The control that killed my 6.8x speedup](02-the-control-that-killed-my-speedup.md) | yes — anyone evaluating a heuristic |
| 03 | [What happens when your BPF map runs out of room](03-when-your-bpf-map-runs-out-of-room.md) | yes — any BPF author |
| 04 | [Your per-task tracking assumes identities hold still](04-identities-that-wont-hold-still.md) | yes — behaviour-tracking schedulers |
| 05 | [p99 told me one story, p50 told me another](05-p99-and-p50-told-different-stories.md) | yes — anyone reporting latency |
| 06 | [Thirteen claims I retracted](06-the-claims-i-retracted.md) | yes |
| 07 | [Overlapping ranges are not equivalence](07-overlapping-ranges-are-not-equivalence.md) | yes — anyone comparing systems |

Posts 01–05 and 07 don't require caring about count-min sketches.

## Data

Every post ends with a table mapping its claims to the raw harness output
that produced them, in [`../results/raw/`](../results/raw/). The output is
unedited, including the parameters each run printed at startup, and where
the harness emitted per-repetition lines the individual values are present
so summaries can be recomputed rather than trusted.

- [`../results/MANIFEST.md`](../results/MANIFEST.md) — what each file is,
  and which files carry known measurement bias
- [`../results/REVISIONS.md`](../results/REVISIONS.md) — every claim made
  and withdrawn, with the file that produced it and the file that
  overturned it
- [`../results/ENVIRONMENT.md`](../results/ENVIRONMENT.md) — kernel, CPU
  count, and the uncontrolled variables

Runs that produced conclusions later retracted are kept deliberately. The
wrong answers are part of the record.

## Still open

These aren't a content schedule — they're the threads this work left
hanging, and I've written down enough in advance that the answers can
embarrass me.

**Everything I predicted bare metal would change.** All of this was
measured in a VM on 4 aarch64 cores. Before buying hardware I wrote down
which findings should survive and which should move, and why: the memory
result should hold, every absolute latency figure should shrink, the
exact tracker's failure threshold should be unchanged, and the tail penalty is
the one most at risk because it rests on rare events in an environment
that manufactures them. That's in the paper's limitations section, dated
and unhedged. The post is the scoreboard.

**Does any of this actually save energy?** The established reason to
track wakeup frequency isn't latency at all — it's that every wakeup
drags a core out of a deep idle state and costs real joules. That's a
one-step causal chain where my latency argument is three. And a sketch's
overestimation matters far less to a batching heuristic than to a
scheduling decision, so my negative findings may simply not transfer. I
couldn't measure it: no energy counters in the guest.

**Which other scheduler heuristics survive a placebo arm?** The
count-blind control dissolved 82% of my headline result. Schedulers
track plenty of other things — run length, migration rate, waker-wakee
locality, cache warmth. I have no idea how many of those survive the
same test, and the test costs about forty lines.

**What is the right identity for a task?** Post 04 shows PID can't see
churning tasks and `comm` turns a multithreaded victim into the heaviest
waker on the system, with nothing usable in between. Cgroup? Executable
path? Parent lineage? I don't know, and it blocks any scheduler that
tracks behaviour under churn.

If you want to be told when these land, or to tell me I'm wrong about
one of them first, that's what the subscribe button is for.

## Repositories

- **https://github.com/blackjable/scx-cms-research** — this repository: paper, posts, harnesses, raw data
- **https://github.com/blackjable/scx-cms** — the scheduler itself

Both are private for now. **The posts link to data that is not yet
publicly readable**, so they cannot be published until at least this
repository is made public. A post citing unreachable data is worse than
one citing none: it implies a verifiability that isn't there.

## A note on publishing these

Links within posts are repo-relative and resolve when browsing this
repository on GitHub. Links into the scheduler source are absolute,
because it lives in a separate repository.

If the posts are published anywhere other than GitHub — Medium, a
personal blog — the relative links need absolutising. The two prefixes
to find and replace:

```
../results/    -> https://github.com/blackjable/scx-cms-research/blob/main/results/
../benchmark/  -> https://github.com/blackjable/scx-cms-research/blob/main/benchmark/
```

Order of operations, which matters: **make the repositories public,
verify the links resolve, then publish the posts.**
