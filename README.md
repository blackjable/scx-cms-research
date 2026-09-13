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

The BPF/Rust scheduler this research drives, `scx_cms`, has its own
repository: **https://github.com/blackjable/scx-cms**, extracted with
`git subtree split` so its commit history is preserved.

It does **not** build standalone. It depends on `scx_utils` by relative
path and uses scx's BPF tooling, so it has to sit inside a checkout of
[sched-ext/scx](https://github.com/sched-ext/scx) at
`scheds/experimental/scx_cms/` to build. That local scx clone is
upstream's, not this project's — nothing here is ever pushed to it.

The two repositories move together: the delivery plan's order of
operations tracks the scheduler's progress, and the paper's build
checklist cites it.
