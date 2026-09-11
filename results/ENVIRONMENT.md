# Measurement environment

Recorded because several findings are environment-specific, and one of
them -- the BPF `LRU_HASH` cliff -- depends directly on the CPU count.

## Guest (where everything was measured)

| | |
|---|---|
| kernel | `6.19.10-300.fc44.aarch64` |
| distro | Fedora Linux 44 (Cloud Edition) |
| architecture | **aarch64** |
| CPUs | **4** |
| RAM | 3 GB |

## Host

| | |
|---|---|
| machine | Apple M4 |
| OS | macOS 26.6.1 |
| virtualisation | Lima 2.2.0, `vz` driver |

## Why these numbers matter to specific findings

**CPU count (4) and the LRU cliff.** BPF's `LRU_HASH` keeps per-CPU free
lists, so the entry count below which it stops behaving like an LRU
scales with the number of CPUs. The cliff observed here sits between 42
and 85 entries on 4 CPUs; on a 16-core machine it would be expected at a
proportionally larger map size. The finding is real but the *threshold*
is not portable.

**Architecture (aarch64) and everything else.** No x86 validation was
performed. Memory-ordering behaviour around the atomic counters, cache
effects underlying the runqueue-depth result, and the BPF LRU internals
are all plausibly architecture-sensitive. Every result should be treated
as aarch64-specific until checked elsewhere.

**Virtualisation and timer delivery.** Timer *delivery* in this guest has
a floor near 1.7ms, which is high enough to swamp the scheduling
differences under study. This invalidated `rt-app` as a victim workload
outright: churn levels of 24, 4 and 0 tasks all produced ~1700us,
indistinguishable. All results therefore rest on `schbench`'s
task-to-task wakeup path, which has no such floor. On bare metal this
constraint disappears and `rt-app` should be re-tested.

**RAM (3 GB) and what could not be measured.** No RAPL counters and no
battery gauge are exposed to the guest, so energy -- the established
motivation for tracking wakeup frequency, and the direction this work
most wants to go next -- could not be measured at all.

## Workload constants

Unless a run's own header says otherwise:

- victim: `schbench`, 2 message threads, 4 worker threads, 100 rps
- churn: 128 tasks or slots, 200 wakeups/s, 200us CPU burn each
- window: 1000ms, estimates summing current and previous windows
- `--penalty-ns 20287`, derived once from a pre-flight measurement and
  never retuned
- `--flat-ns 4000000` for the count-blind control
- stable-identity runs use `--lifetime 60`; churning runs `--lifetime 0.25`
