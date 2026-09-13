# Measurement environment

Recorded because several findings are environment-specific, and because
one finding was wrongly attributed to the scheduler when it belonged
here instead (the 240,384us excursion, revision 9).

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

**CPU count (4).** This was initially thought to determine the entry
count below which `LRU_HASH` stops behaving like an LRU. It does not --
see `REVISIONS.md` revision 12. The exact tracker's failure threshold
tracks the ratio of live identities to map capacity, so it should be
reproducible on any core count given the same workload. The CPU count
still matters for the scheduling results themselves, since runqueue
depth is the mechanism under study and four cores is a small machine.

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
most wants to go next -- could not be measured at all. The method for
doing so when hardware allows is written up in advance in
[`../benchmark/ENERGY_METHOD.md`](../benchmark/ENERGY_METHOD.md).

## An uncontrolled variable: the host is heterogeneous

The M4 host has **10 physical cores -- 4 performance and 6 efficiency**.
The guest's 4 vCPUs are scheduled onto those by macOS, and nothing in
the guest controls or observes which class they land on. The assignment
may also change during a run as the host rebalances.

This is an uncontrolled variable in **every measurement in this
archive**. It plausibly contributes to the wide p99 ranges seen
throughout, since a vCPU migrating from a performance core to an
efficiency core mid-run would inflate latency for reasons having nothing
to do with the scheduler being tested.

It also offers an alternative explanation for the sporadic tail
excursions once attributed to sketch collisions: a host-level scheduling
hiccup would produce the same signature from inside the guest.

**That alternative is the surviving explanation.** An earlier version of
this section claimed the opposite, and the reasoning is worth recording
because it was pre-registered and still wrong.

The pre-registration required reporting whether outliers cluster across
conditions within a repetition, on the stated assumption that a
host-level disturbance would affect whichever conditions were running
near that moment. They did not cluster: in the repetition where
`sketch_32k_d2` reached 240,384us, `exact_32k` measured a wholly
unremarkable 10,032us. That was read as ruling the host out.

**It rules nothing out.** Conditions run *sequentially* within a
repetition, so a disturbance lasting a few seconds hits exactly one of
them. The signature treated as exonerating is precisely what an
environmental cause produces. A dedicated run at n=60 per condition
settled it: exact counting shows excursions at the same rate as every
sketch geometry (1/60 against 1/60), the 24x never recurred across 360
further measurements, and nothing exceeded 5.7x. The excursions belong
to this environment, not to approximation. See `REVISIONS.md`
revision 9, and `BENCHMARK_HOST.md` for what to disable on a host to
reduce them.

Specifying a check in advance guarantees it was not chosen to fit the
data. It does not guarantee the check tests what it claims to.

The general limitation stands regardless: this environment cannot
isolate the guest from host scheduling decisions, and bare metal would
remove the question rather than answer it.

**This also rules out running experiments in parallel VMs.** Two guests
of 4 vCPUs each would need 8 of the host's 10 cores, forcing at least
four vCPUs onto efficiency cores, and `vz` offers no physical-core
pinning to prevent it. The two VMs would be measuring different
hardware, with the assignment shifting under them.

## Preparing a host for these measurements

Configuring a machine so that what is measured is the scheduler rather
than the machine -- which timers to disable, why frequency scaling is a
confound, and why nothing else should run on the host -- is documented
separately in [`BENCHMARK_HOST.md`](BENCHMARK_HOST.md).

## Workload constants

Unless a run's own header says otherwise:

- victim: `schbench`, 2 message threads, 4 worker threads, 100 rps
- churn: 128 tasks or slots, 200 wakeups/s, 200us CPU burn each
- window: 1000ms, estimates summing current and previous windows
- `--penalty-ns 20287`, derived once from a pre-flight measurement and
  never retuned
- `--flat-ns 4000000` for the count-blind control
- stable-identity runs use `--lifetime 60`; churning runs `--lifetime 0.25`
