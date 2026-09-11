# Blog series: a Count-Min Sketch in a Linux scheduler

Eight posts. Post 00 is the result; the rest are what it took to trust it.

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

## A note on publishing these

Links here are repo-relative and resolve when browsing the repository. If
the posts are published anywhere else, those links need rewriting to
absolute URLs — `../results/` and `../benchmark/` are the two prefixes to
find and replace, plus `../../repo/` for links into the scheduler source.

**Push the code and data first, then fix the links, then publish the
posts.** A post citing data nobody can reach is worse than one citing
none, because it implies verifiability that isn't there.
