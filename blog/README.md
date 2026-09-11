# Blog series: a Count-Min Sketch in a Linux scheduler

Eight posts. Post 00 is the result; the rest are what it took to trust
it.

I came to this knowing how to write a scheduler and nothing about how to
measure one. That turned out to be the harder half: ten claims made and
withdrawn, almost all of them because an instrument was wrong rather
than because the idea was. Each fix — a control condition, randomised
ordering, an equivalence test — is standard practice somewhere else and
was new to me.

So these are written from the position of someone who didn't know, for
anyone else who came to benchmarking through code rather than through a
statistics course. The mistakes are the content.

| # | post | stands alone? |
|---|---|---|
| 00 | [A Count-Min Sketch in a Linux scheduler](00-a-sketch-in-a-scheduler.md) | the result |
| 01 | [My scheduler benchmark was lying to me for four rounds](01-benchmark-was-lying.md) | yes — any benchmark author |
| 02 | [The control that killed my 6.8x speedup](02-the-control-that-killed-my-speedup.md) | yes — anyone evaluating a heuristic |
| 03 | [What happens when your BPF map runs out of room](03-when-your-bpf-map-runs-out-of-room.md) | yes — any BPF author |
| 04 | [Your per-task tracking assumes identities hold still](04-identities-that-wont-hold-still.md) | yes — behaviour-tracking schedulers |
| 05 | [p99 told me one story, p50 told me another](05-p99-and-p50-told-different-stories.md) | yes — anyone reporting latency |
| 06 | [Ten claims I retracted](06-the-claims-i-retracted.md) | yes |
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
