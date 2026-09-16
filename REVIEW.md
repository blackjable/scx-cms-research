# Review brief

Read [`CONTEXT.md`](CONTEXT.md) first for what the project is and what it
found. This file is about how to review it usefully.

Everything is public, so claims can be checked rather than taken on
trust. Raw output for every run is in
[`results/raw/`](results/raw/), catalogued in
[`results/MANIFEST.md`](results/MANIFEST.md).

---

## The standard this work is held to

Not "is it well written". These four:

1. **Every number traces to an archived file.** If a figure appears in a
   post or the paper and does not appear in `results/raw/`, that is a
   defect. It has happened twice and both times the figure turned out not
   to replicate when re-measured.
2. **No mechanism is asserted without a test.** A correct measurement
   with an invented explanation attached is this project's characteristic
   failure — four of the thirteen retractions are exactly that. A
   plausible causal story is a reason to run one more experiment, not a
   reason to stop.
3. **Claims are scoped to what was measured.** One environment: 4-core
   aarch64 VM. Latency only. If a sentence generalises beyond that
   without saying so, it is overclaiming.
4. **A more careful statistic does not repair a confounded design.** It
   makes the confound harder to see.

---

## What is already dead — do not resurrect

These appear stated confidently in older drafts, some source comments and
any summary written before the correction. All are refuted, with the
evidence in [`results/REVISIONS.md`](results/REVISIONS.md):

| withdrawn claim | reality | revision |
|---|---|---|
| fixed condition ordering biased results | controlled test found no effect, p = 0.86 | 13 |
| BPF's `LRU_HASH` breaks at small sizes | ordinary thrashing below the working set | 12 |
| the tail cost is intrinsic to approximating | at matched memory the two are indistinguishable | 10 |
| the sketch has a rare severe failure mode | exact counting shows the same rate | 9 |
| exact counting beats the sketch at every budget | metric had a broken zero point | 5 |

Flagging one of these as a finding would be repeating a mistake that has
already been made and corrected.

---

## Known soft spots — these are where to push

I would rather have these attacked than have the prose polished.

**The energy premise is an untested mechanism, stated in six places.**
"A sketch's overestimation matters far less to a batching heuristic than
to a scheduling decision, so the negative result here does not transfer
to the energy case." That is reasoning, not measurement, and it is doing
real work — it is the stated reason the whole energy direction is still
open. It has the exact shape of retractions 9, 10, 12 and 13. It should
either be argued properly, tested, or labelled as speculation. It appears
in `benchmark/ENERGY_METHOD.md`, `blog/00`, `blog/README`, paper §1.4,
§5 and §6.

**Is the trade actually worth anything?** The saving is 35.6 KB → 8.3 KB.
That is 27 KB, on a machine with gigabytes. Nobody has pressed the "so
what" question: what deployment is memory-constrained enough to care,
and would it accept a tail that is worse in a third of runs? If the
honest answer is "none identified", the paper should say so.

**The never-undercount instrument has a non-zero noise floor.** Compare
mode reports violations for the plain sketch, which cannot undercount by
construction — those are a known unfixed concurrency bug. Every accuracy
figure taken from that instrument sits on that floor. Is it sound enough
to support what is claimed from it?

**Sample sizes are uneven.** The victim-shape sensitivity sweep is n=15,
one run per shape. Some supporting figures are still single runs. The
headline is n=20 and the equivalence test n=30, but the supporting cast
is thinner and the text does not always make that visible.

**The discrimination metric is still used** after being shown to have a
broken zero point (revision 5). Where it survives it is scoped, but check
whether every surviving use is actually safe.

**Paper §4.2.2 carries two tables close together** — a churning-workload
discrimination sweep and a stable-workload budget table — that say
apparently opposite things. The scoping note is there. Is it enough?

**The delivery plan is a chronological log** with superseded sections
marked by banners rather than deleted. Is that navigable, or does it
mislead a reader who lands mid-document?

---

## What not to spend time on

- Line editing. The prose has had several passes.
- Suggesting more repetitions as a general remedy. Of thirteen
  retractions, more data would have caught exactly one; the rest needed a
  control or a test that did not exist yet.
- Re-flagging the retractions themselves. They are deliberately kept,
  including the runs that produced wrong answers.

---

## Where to start

1. [`blog/`](blog/) — seven posts, the public deliverable, ~9,300 words
2. [`results/REVISIONS.md`](results/REVISIONS.md) — the record, and the
   most useful single document
3. `sched_ext_phase2_handoff/00_orientation/paper_abstract_and_section_1.md`
   — the paper's public-facing half
4. Everything else on demand

The most valuable output would be: a claim in the posts or paper that is
not supported by the file it cites, or a mechanism asserted without a
test that nobody has noticed yet.
