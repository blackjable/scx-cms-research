# sched_ext wakeup-frequency tracking — research

Research material for the Count-Min Sketch vs. exact-counter scheduling
study. Start at
[`sched_ext_phase2_handoff/MANIFEST.md`](sched_ext_phase2_handoff/MANIFEST.md),
which explains what every file here is and the order to read them in.

## Why this is its own repository

This material previously lived at
`sched_ext/repo/.claude/sched_ext_phase2_handoff/`, inside a clone of
[sched-ext/scx](https://github.com/sched-ext/scx). That location is
covered by that repo's `.gitignore` (`**/.claude`), so none of it —
the paper draft, the delivery plan, the validated Python prototype, the
pytest suite — was under version control at all. It was one
`git clean -xdf` or one lost machine away from being gone.

It also should not simply be committed *into* that clone: that repo is a
fork of an upstream project, and this is not upstream's material.

## Relationship to the scheduler code

The BPF/Rust scheduler this research drives, `scx_cms`, lives in the scx
clone at `sched_ext/repo/scheds/experimental/scx_cms/` and is committed
there, since it is a scheduler in the shape that repo expects. The two
move together: the delivery plan's order of operations tracks the
scheduler's progress, and the paper's build checklist cites it.
