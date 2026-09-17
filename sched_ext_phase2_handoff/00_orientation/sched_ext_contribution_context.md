# Linux Scheduler Contribution — Context & Plan

## Goal
Find a meaningful contribution path into the Linux kernel, starting from a
specific interest in **CPU scheduling** (SCHED_DEADLINE / EDF / CBS), open to
wider areas over time.

## Why sched_ext is the recommended entry point

- Merged into mainline in **Linux 6.12**.
- Lets you write scheduling policies as **BPF programs**, loaded/unloaded at
  runtime — no reboot, no kernel rebuild-and-reboot cycle.
- Historically, working on core CFS/EEVDF required years of ramp-up due to
  codebase density and the high review bar (any regression affects every
  Linux machine). sched_ext lowers that barrier for experimentation while
  still being a real, production-used kernel feature.
- Active production users: Meta and Google (custom gaming/AI-training
  schedulers), SteamOS (uses `scx_lavd` during gameplay), CachyOS (ships
  `scx_bpfland` by default).
- Actively growing community: weekly office hours + Slack channel dedicated
  to sched_ext development.

## Core repo & starting file

- Repo: `github.com/sched-ext/scx`
- Recommended first read: `scheds/c/scx_simple.bpf.c`
  - Under 200 lines of BPF C.
  - Implements a single global FIFO dispatch queue with optional weighted
    vtime ordering — small enough to fully understand in one sitting, but a
    real, bootable scheduler.
- The scheduler is defined via callbacks on `struct sched_ext_ops`:
  `select_cpu`, `enqueue`, `dispatch`, `runnable`, `running`, `stopping`,
  `quiescent`, `init_task`, `exit_task`, `tick`, and a few others.

## Dev environment

- Use **virtme_ng** for a fast VM-based dev loop (avoids reinstalling the
  kernel and physically rebooting on every scheduler change).
- Kernel config requirements for sched_ext:
  ```
  CONFIG_BPF=y
  CONFIG_SCHED_CLASS_EXT=y
  CONFIG_BPF_SYSCALL=y
  CONFIG_BPF_JIT=y
  CONFIG_DEBUG_INFO_BTF=y
  CONFIG_BPF_JIT_ALWAYS_ON=y
  CONFIG_BPF_JIT_DEFAULT_ON=y
  ```
- Some schedulers (e.g. `scx_rustland`) are hybrid userspace-Rust + BPF —
  expect a Rust + BPF toolchain to be part of the build setup depending on
  which scheduler(s) you're building against.
- Verifier errors are one of the more painful early hurdles — cryptic
  rejection messages when a BPF program doesn't satisfy the verifier's
  safety proofs (bounded loops, memory access bounds, etc.).

## Where prior scheduling knowledge (SCHED_DEADLINE / EDF / CBS) transfers

- `SCHED_DEADLINE` (mainline, since 3.14) is EDF (Earliest Deadline First) +
  CBS (Constant Bandwidth Server) based. Each task has Runtime, Deadline,
  Period; scheduler always runs the earliest absolute deadline; CBS
  throttles tasks that overrun their budget.
- Priority order in the kernel: stop_sched_class → dl_sched_class
  (SCHED_DEADLINE) → rt_sched_class (FIFO/RR) → fair_sched_class
  (CFS/EEVDF) → idle_sched_class.
- Optional flags on `sched_setattr()`:
  - `SCHED_FLAG_RECLAIM` — enables GRUB (Greedy Reclamation of Unused
    Bandwidth): lets a task opportunistically use bandwidth unused by other
    deadline tasks, up to the admission-control limit. Trade-off: reduces
    strict predictability in exchange for better average-case throughput.
  - `SCHED_FLAG_DL_OVERRUN` — kernel sends `SIGXCPU` when a task overruns
    its runtime and gets CBS-throttled. Useful for detecting bad
    worst-case-execution-time estimates during development, or runtime
    health monitoring in production.
- There is active community interest in bringing more deadline-aware /
  hybrid EDF-style policies into sched_ext schedulers (relevant to
  latency-sensitive schedulers like `scx_lavd`) — a natural bridge from
  existing EDF/CBS knowledge into sched_ext work.

## General kernel contribution mechanics (useful beyond scheduling too)

- Patches go via **`git send-email`** to mailing lists — not GitHub PRs.
- Canonical process doc: `Documentation/process/submitting-patches.rst`.
- Static analysis expected before submitting: `checkpatch.pl`, `sparse`,
  `smatch`.
- **kernelnewbies.org** — maintains beginner-friendly task lists and general
  "how to start" guidance.
- **LWN.net** — best source for tracking *why* decisions are being made in
  real time (worth a subscription for anyone getting serious).
- Triaging/fixing reported regressions (syzbot, regression tracking) is a
  reliable way to build maintainer trust before submitting larger patches.

## Locking/synchronization notes (from broader scheduler discussion)

Relevant if scheduler work touches concurrency internals:

- Linux scheduler already moved past a single global lock: **per-CPU
  runqueues**, each with its own spinlock.
- **RCU (Read-Copy-Update)** used heavily for read-mostly scheduler data
  (cgroup hierarchy, sched_domains topology) — readers never block at all.
- **qspinlock** (queued spinlock) replaced ticket spinlocks specifically to
  avoid cache-line contention among waiters at high core counts — this
  modernization already happened in-kernel.
- Newer/more specialized primitives that exist but are more narrowly
  applicable: NUMA-aware/cohort locks, flat combining, hazard pointers.
- For distributed (not single-machine) schedulers, the bottleneck is
  usually database/queue-level contention, not the in-process lock choice.

## Suggested first concrete steps

1. Clone `github.com/sched-ext/scx`.
2. Read and fully understand `scx_simple.bpf.c` (annotate
   it against `struct sched_ext_ops` callback semantics).
3. Set up `virtme_ng` for a fast build/test loop.
4. Join sched_ext Slack + attend an office hours session to find currently
   wanted small tasks, rather than starting a from-scratch scheduler design.
5. Once comfortable, look at where EDF/deadline-aware ideas could inform an
   existing latency-sensitive scheduler (e.g. `scx_lavd`) as a first real
   contribution angle that leverages prior SCHED_DEADLINE knowledge.
