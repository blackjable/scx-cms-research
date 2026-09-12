# Preparing a machine to measure scheduling latency

Notes on configuring a host so that what you measure is the scheduler
rather than the machine. Written after spending a day investigating a
240,384us latency excursion that turned out to be environmental
(`REVISIONS.md`, revision 9), which is a reasonably expensive way to
learn that the measurement environment is part of the experiment.

The principle throughout: **anything that wakes up on a timer is worse
than steady background load.** Constant load raises every number and
mostly cancels out of a comparison. Periodic load fires *during* some
runs and not others, producing exactly the sporadic spikes that look
like a finding.

## Install a minimal system

Fedora Server or a minimal install, not Workstation. A desktop session
brings a compositor, file indexers, and a dozen daemons, none of which
you need on a machine driven over SSH.

Anything from Fedora 42 onward carries a kernel new enough for
`sched_ext`, which landed in 6.12. Check with `uname -r` rather than
assuming.

## Disable periodic timers

The main offenders:

```bash
systemctl list-timers --all          # audit first

sudo systemctl disable --now dnf-makecache.timer
sudo systemctl disable --now fstrim.timer
sudo systemctl disable --now man-db-cache-update.timer
sudo systemctl disable --now logrotate.timer
```

`dnf-makecache` deserves singling out: it wakes periodically, hits the
network and burns CPU. On a host measuring wakeup latency that is
directly contaminating, and it fires often enough to catch some runs and
not others.

## Disable services you are not using

```bash
sudo systemctl disable --now bluetooth cups ModemManager
```

Keep `avahi-daemon` if you want `hostname.local` to resolve; it is quiet
enough to leave alone.

## Pin the CPU frequency

Frequency scaling is a confound. A core ramping up partway through a run
changes latency for reasons that have nothing to do with the scheduler.

```bash
sudo dnf install tuned
sudo tuned-adm profile latency-performance
cat /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor   # expect: performance
```

Consider disabling turbo as well. It costs peak throughput and removes a
source of frequency variation -- and since every measurement here is
*relative* (tracker against tracker, condition against control), a slower
but stable machine is strictly better than a fast one whose clock wanders.

The same reasoning applies to thermal throttling, which is the laptop
version of this problem. Verify before trusting any results:

```bash
stress-ng --cpu $(nproc) --timeout 600s &
watch -n5 'grep MHz /proc/cpuinfo'
```

If clocks sag over ten minutes, pin a lower fixed frequency and accept it.

## Run headless

Drive the host over SSH and leave nothing running locally:

```bash
sudo systemctl enable --now sshd
sudo systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target
```

On a laptop, also stop the lid suspending it -- set `HandleLidSwitch=ignore`
and `HandleLidSwitchExternalPower=ignore` in `/etc/systemd/logind.conf`.

Use wired ethernet rather than wireless where possible. It removes a
driver from the equation, and on a headless box a wireless failure means
you cannot get in to fix it.

**Do not run an agent, IDE, or analysis tooling on the host itself.**
Everything that runs there competes for the resource being measured, and
it competes *while you are actively working*, which is worse than random
noise. Keep tooling on a separate machine and treat the host as an
instrument.

`tmux` is the exception worth installing, so a dropped connection does
not kill a run in progress.

## Audit before trusting anything

```bash
systemctl list-units --type=service --state=running
systemctl list-timers --all
```

On a properly minimal system this is a short list. Investigate anything
unexpected before running experiments rather than afterwards.

## Record what you ended up with

Whatever configuration you settle on, write it down alongside the kernel
version and CPU details. "What else was running on the box" is precisely
the sort of detail that turns out to matter several retractions later,
and it is unrecoverable after the fact.
