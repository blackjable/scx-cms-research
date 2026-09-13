# Measuring energy, when hardware allows it

The established reason to track wakeup frequency is not latency. It is
that every wakeup drags a core out of a deep idle state, and re-entering
costs real joules -- the "wakeup tax". That is a one-step causal chain
where this project's latency argument is three, and a sketch's
overestimation matters far less to a batching heuristic than to a
scheduling decision.

None of it was measured. The VM exposed neither RAPL counters nor a
battery gauge, so this document is the method written in advance, while
the reasoning is fresh and before any data exists to shape it.

## Measure the mechanism, not only the outcome

The obvious experiment is "does the scheduler use less energy". The
better one also asks **"does it do the thing that would cause that"**,
because a joules figure alone cannot distinguish a real effect from a
coincidence.

The causal chain is: *fewer or better-batched wakeups → fewer idle-state
exits → less energy*. The middle step is directly observable:

```
/sys/devices/system/cpu/cpu*/cpuidle/state*/usage   # times entered
/sys/devices/system/cpu/cpu*/cpuidle/state*/time    # total us resident
/sys/devices/system/cpu/cpu*/cpuidle/state*/name    # C1, C1E, C6, C10...
```

Sample before and after each condition and difference them. If a
mechanism reduces energy **without** changing deep-state residency,
something other than the wakeup tax is responsible and the explanation
is wrong. If it increases deep-state residency but energy does not move,
the effect is real but too small to matter on this hardware.

Either mismatch is more informative than the energy number alone.

## Reading package energy

Easiest, wrapping a command:

```bash
perf stat -e power/energy-pkg/,power/energy-cores/,power/energy-ram/ \
    -- ./run-condition.sh
```

Directly, for finer control:

```bash
cat /sys/class/powercap/intel-rapl:0/energy_uj          # microjoules
cat /sys/class/powercap/intel-rapl:0/max_energy_range_uj
```

**The counter wraps.** Read `max_energy_range_uj` and handle it, or a
long run silently produces a negative or absurd delta:

```python
delta = (after - before) % max_range
```

Domains vary by platform: `intel-rapl:0` is the package, `:0:0` usually
cores, `:0:1` uncore or graphics, `:0:2` DRAM where present. Read package
as the headline and cores separately if available.

AMD exposes package energy through the same `perf` PMU on Zen and later,
but with fewer domains and less maturity than Intel. The `amd_energy`
hwmon driver was removed from the kernel over a side-channel issue; the
perf PMU is the supported path.

## Whole-system draw, on a laptop

```bash
cat /sys/class/power_supply/BAT0/power_now      # microwatts, if present
# otherwise: current_now * voltage_now
```

A degraded battery still reports **instantaneous** current and voltage
accurately -- capacity loss does not corrupt a power reading. So a
battery that holds almost no charge is still usable for short spot
checks on mains-free runs.

Two independent measurements agreeing is considerably stronger than
either alone, and whole-system draw is the more honest figure if the
argument is ever framed in embedded terms.

## The metric must be energy per unit work

**Raw joules is not the measure.** A scheduler that gets less done uses
less energy, trivially and uselessly. Normalise:

    joules / requests completed

The victim's completed request count and the churn loop counts are both
already collected by the existing harnesses. Report energy, throughput,
and the ratio -- a mechanism that cuts energy 10% while cutting work 15%
has made things worse.

## The control still applies

The count-blind control (`--mechanism flat`) dissolved 82% of this
project's apparent latency benefit. There is no reason to expect energy
to be different, and every reason to check.

Conditions, at minimum:

| condition | question |
|---|---|
| `mechanism=none` | baseline: tracking overhead only |
| `mechanism=flat` | does *any* vtime perturbation change energy? |
| `exact + penalty` | does acting on the count change energy? |
| `sketch + penalty` | does approximation preserve whatever the count buys? |

If `flat` captures most of the effect again, the finding is about
perturbation rather than tracking -- exactly as it was for latency.

## Pitfalls specific to energy

**RAPL is package-wide.** It reports everything on the die, including
whatever else is running. The host-cleanliness requirements in
`../results/BENCHMARK_HOST.md` matter more here than for latency, not
less.

**Establish an idle baseline.** Measure the machine doing nothing, for
the same duration, and report both absolute and idle-subtracted figures.
Absolute energy is dominated by baseline draw and will hide a real
effect.

**Frequency scaling is a confound twice over** -- it changes both
latency and energy. The governor must be pinned before any of this
means anything.

**Longer runs.** RAPL updates roughly every millisecond, but thermal
behaviour and idle-state distribution need time to settle. Prefer 30-60s
per measurement over the 10-15s used for latency.

**Permissions.** `perf` energy events need
`kernel.perf_event_paranoid <= 0` or root.

## What would falsify the energy case

Deep-state residency unchanged across conditions, or energy per unit
work statistically indistinguishable between `flat` and
`exact + penalty`. In that event the honest report is that
wakeup-frequency tracking does not reduce energy on this hardware --
which, given the latency results, would make this a negative result
about the technique generally rather than about one application of it.

That outcome must be as publishable as the alternative. Writing that
down here, before any data exists, is the point of writing it down at
all.
