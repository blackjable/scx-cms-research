# sched_ext + Resource-Constrained Scheduling — Research Notes

Context: pivot from "general Linux scheduler contribution" toward
scheduling in resource-constrained environments (mobile/embedded), backed
by real, current, citable community activity — not speculative.

## Headline finding

This is a live, active area with a dedicated conference presence in
**three weeks from today (LPC 2026, 5–7 October, Prague)**. This is not
a niche or hypothetical interest — there are named engineers, open patch
threads, and explicit agenda items matching this exact intersection.

## Directly relevant LPC 2026 talks

### 1. "RT tasks in sched-ext support" — Android MC
- Speakers: Rohan Tabish, Tengfei Fan
- Source: https://lpc.events/event/20/contributions/ (contribution #261)
- Abstract (verbatim excerpt): "The upstream Linux kernel explicitly
  excludes real-time (RT) tasks from the sched-ext extensible scheduler
  framework, restricting sched-ext BPF schedulers to only manage
  SCHED_NORMAL/SCHED_BATCH/SCHED_IDLE tasks. However, Android's production
  workloads present a fundamentally different reality: many
  performance-critical scenarios — including audio pipelines, camera
  capture, display..."
- **Why it matters**: this is a real, currently-unsolved architectural
  gap. sched_ext today literally cannot manage RT-class tasks, but
  mobile/embedded workloads that most need custom scheduling policy
  (audio, camera, display pipelines) are often RT-class. Direct entry
  point for EDF/CBS background, since SCHED_DEADLINE sits at the RT tier.

### 2. "Amortizing CPU wakeup costs with lazy wakeups" — Power Management MC
- Speaker: Samuel Wu (Google)
- Abstract (verbatim excerpt): "Transitioning a CPU into and out of idle
  has a non-negligible energy overhead. This 'wakeup tax' is frequently
  triggered by background tasks with low utilization but a high number of
  wakeups. Furthermore, these tasks largely escape detection from existing
  energy-aware mechanisms like PELT and EAS, which are optimized for
  continuous execution rather than transient hardware states."
- **Why it matters**: a real, named problem where existing *exact*
  accounting (PELT/EAS) fails to detect a behavioral pattern (frequent
  low-utilization wakeups). Structurally similar to the
  approximate/behavioral-classification idea discussed earlier — worth
  reading in full before assuming novelty elsewhere.

### 3. "Kernel Lock Contention Hotspots Causing Frame Drops on Android Mainline" — Android MC
- Speakers: Barry Song, Bo Zhang, Hongru Zhang (Xiaomi)
- Abstract excerpt: profiled 40 popular Android apps on a Pixel 6 (kernel
  6.18.0-mainline, 90Hz), correlating `ftrace lock_contention` events with
  Perfetto to find UI-critical thread (RenderThread) frame drops — each
  frame has ~11ms budget at 90Hz.
- **Why it matters**: concrete, measured, real-world data connecting lock
  contention (a topic already covered in this research) directly to
  mobile-specific latency budgets.

### 4. "Energy-Aware Scheduling on x86 Hybrid Topologies: Latency Analysis
   and Idle CPU Selection" — Scheduler and Real-Time MC
- Speaker: Ricardo Neri (Intel)
- Note: at OSPM 2026, agreement was reached to stop requiring schedutil to
  enable EAS on x86, meaning EAS may soon be active by default on hybrid
  x86 systems. Directly relevant to heterogeneous-core (big.LITTLE-style)
  scheduling.

### 5. "EPP-boost: Per-core util-based performance boosting in AMD p-state driver" — Gaming on Linux MC
- Speaker: David Vernet (Meta) — one of sched_ext's original authors
- Real RFC already posted upstream:
  https://lore.kernel.org/all/20260728073150.54964-1-void@manifault.com/
- Observed impact on tail latencies/stale frame numbers on Steam Deck.

## sched_ext MC (dedicated microconference) — confirms active, self-sustaining community

- Full track name: "sched_ext: The BPF extensible scheduler class MC"
- Talk: "Bridging the VM Boundary: Scheduling Passthrough via pvsched and
  sched_ext" — Josh Don, Vineeth Remanan Pillai (Google)
- Talk: "BPF-based Composable Idle cpumask Selection" — Emil Tsalapatis
  (Meta) — notes that all sched_ext schedulers currently duplicate idle
  CPU selection logic via hardcoded policy, a genuine architectural gap.
- From the LPC 2025 sched_ext MC topic list (still relevant/carried
  forward): **"Deadline server(s) for the SCHED_EXT class"** — an
  explicitly named open topic directly matching SCHED_DEADLINE/EDF/CBS
  background.

## Scheduler and Real-Time MC at LPC 2026 (7 Oct, 10:00–13:30, Prague)

Source: https://realtime-linux.org/event/scheduler-and-real-time-mc-at-lpc-2026/

- Explicit scope statement (verbatim): "scaling from small,
  power-constrained devices to large-scale HPC systems — is key to
  delivering the optimal user experience."
- Progress since last year (real patch threads, all on lore.kernel.org):
  - Cache aware scheduler — https://lore.kernel.org/all/cover.1775065312.git.tim.c.chen@linux.intel.com/
  - Paravirt Scheduling — https://lore.kernel.org/all/20260407191950.643549-1-sshegde@linux.ibm.com/
  - CPU Isolation and IPI interference — https://lore.kernel.org/lkml/20260324094801.3092968-1-vschneid@redhat.com/
  - Push callback for fair scheduler — https://lore.kernel.org/all/20251202181242.1536213-1-vincent.guittot@linaro.org/
  - Runtime verification — https://lore.kernel.org/lkml/20260330111010.153663-1-gmonaco@redhat.com/
  - Proxy execution — https://lore.kernel.org/all/20260324191337.1841376-1-jstultz@google.com/
- **Explicit open discussion topics for Oct 2026 include: "Improve
  SCHED_DEADLINE"** — directly matches existing background.
- Key attendees (i.e. who is actually in the room for this): Ingo Molnar,
  Peter Zijlstra, Juri Lelli, Vincent Guittot, Dietmar Eggemann, Steven
  Rostedt, Ben Segall, Mel Gorman, Valentin Schneider, K Prateek Nayak,
  Thomas Gleixner, John Stultz, Sebastian Andrzej Siewior, Shrikanth
  Hegde, Phil Auld, Dhaval Giani, Clark Williams.
- Format note: presentations limited to 2–3 slides to seed discussion —
  this is a working-session format, not a lecture series. Preference
  given to topics with patch sets already being discussed on the mailing
  list.

## Assessment: is this a real gap or manifesting?

Verdict from checking: **real gap, not manifesting**, specifically for
the RT-tasks-in-sched_ext angle and the general resource-constrained
framing. This is different from the earlier Bloom-filter/CMS
task-classification idea, which was judged to be a legitimate technical
exploration but *not* an acknowledged unmet need (cgroups/orchestration
already solve that problem in mainstream deployments). The RT-exclusion
gap and the "Improve SCHED_DEADLINE" / "Deadline server(s) for SCHED_EXT"
topics are different: they are current, named, open items on a concrete
conference agenda with a firm date, not inferred gaps.

## Defined solo research project (locked in)

**Problem statement**: sched_ext schedulers need behavioral signals about
tasks (beyond simple CPU time) to make good scheduling decisions, but
tracking per-task-identity history exactly doesn't scale on
memory-constrained devices with high process churn, since BPF maps are
fixed-size and exact tracking grows with the number of distinct
identities seen.

**Metric chosen**: wakeup frequency / idle-transition pattern per task
identity (ties to the "lazy wakeups" LPC 2026 talk — see Related Work
below).

**Hypothesis**: A Count-Min Sketch tracking per-task-identity wakeup
frequency over a sliding window achieves comparable scheduling-decision
quality to exact per-task counters, while using a fixed, small memory
footprint that doesn't grow with the number of distinct task identities
seen — a meaningful property on memory-constrained devices with high
process churn.

**Target platform**: Raspberry Pi (real hardware, genuinely
resource-constrained, not a simulated constraint).

**Workload**: synthetic — many short-lived worker processes (simulating
embedded process churn) running alongside one latency-sensitive task.

**Baseline for comparison**: the *same* scheduler logic, but with exact
per-task-identity counters instead of the sketch. This isolates the
sketch's effect cleanly rather than comparing against unrelated
schedulers like CFS or `scx_simple`.

**Success criterion**: the sketch version matches the exact version's
latency-protection outcome closely, while using meaningfully
less/bounded memory as churn increases — with any accuracy gap small
enough to justify the memory savings.

## Related work / non-duplication check

Before starting, checked whether this duplicates existing LPC 2026 work,
specifically "Amortizing CPU wakeup costs with lazy wakeups" (Samuel Wu,
Google). Conclusion at time of writing (talk has not yet occurred —
LPC 2026 is 5–7 Oct; no patch/RFC found on lore.kernel.org under Wu's
name as of this check):

- Wu's stated problem is a **what-to-do-with-the-signal** question:
  detecting low-utilization, high-wakeup-frequency tasks that PELT/EAS
  miss, in order to reduce idle-transition energy cost ("wakeup tax").
- This project's hypothesis is a **how-to-track-the-signal-cheaply**
  question: given you need per-task-identity wakeup-frequency tracking,
  is a bounded-memory sketch as effective as exact counters under process
  churn on memory-constrained devices.
- These are different axes and plausibly complementary rather than
  duplicative — this project could be a building block relevant to Wu's
  stated problem (an efficient way to gather the signal), not a
  competing solution to it.
- **Action item**: re-check after LPC 2026 concludes (slides/recordings
  are typically published afterward) to see whether Wu's proposed
  mechanism overlaps with the sketch-based tracking approach here. Cite
  and differentiate honestly if so.
- Same discipline applies to "Deadline server(s) for the SCHED_EXT
  class" and "Improve SCHED_DEADLINE" — those appear structurally
  unrelated to this project (admission control / EDF semantics, not
  approximate tracking), but worth periodically checking
  lore.kernel.org / the scx GitHub repo rather than assuming no overlap
  indefinitely.

## Suggested next steps

1. Read the full "RT tasks in sched-ext support" abstract/any linked
   patches once the contribution page is browsable (it did not resolve
   via direct fetch at time of writing — may need to search the LPC site
   again closer to the event, or check lore.kernel.org for a
   correspondingly-named RFC from Rohan Tabish or Tengfei Fan).
2. Read the linked lore.kernel.org threads above in full — these are the
   actual current patch discussions, not just talk abstracts.
3. Consider whether attending/watching LPC 2026 (or its later published
   recordings/slides — LPC has historically published both) is worthwhile
   before committing to a specific sub-project.
4. Given the "Deadline server(s) for the SCHED_EXT class" topic has
   apparently been open since at least LPC 2025 and is being carried
   forward, search lore.kernel.org / the scx GitHub repo directly for any
   existing WIP patches or RFCs on this before starting from scratch.
5. `scx_lavd` (SteamOS's latency-aware scheduler) remains a good codebase
   to study in parallel, since it's the closest existing example of a
   sched_ext scheduler built for latency-sensitive, non-server workloads.
