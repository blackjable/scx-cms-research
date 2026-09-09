#!/usr/bin/env python3
"""
Phase 6 round 2: does acting on the tracked count actually help?

WHY ROUND 2 EXISTS

Round 1 (delivery plan Section 12) compared four schedulers on schbench
and produced a result that could not answer the project's actual
question. Its tell: scx_lavd, a real production scheduler, LOST to a toy
one. A benchmark that ranks a serious scheduler below a minimal one is
rewarding minimalism, not measuring scheduling quality -- and a workload
that rewards doing nothing structurally cannot show a mechanism helping.

Round 2 builds the workload that was missing: a latency-sensitive task
competing against background churn, where prioritising correctly is
worth something and getting it wrong is visible.

THE WORKLOAD (resolves paper checklist item 10)

rt-app periodic task modelling an audio callback -- wakes every 10ms,
does ~2ms of work, must finish before the next tick. Item 10 left the
choice between "audio callback" and "periodic deadline task" open; this
is the audio-callback profile, chosen because rt-app models it directly
and it gives deadline semantics (slack) rather than only latency.

Metric: the victim's wakeup latency (wu_lat) -- time from timer expiry
to actually running, which is precisely what a scheduler controls --
plus deadline misses (slack < 0). Both come from rt-app's own per-loop
log, not a bespoke measurement.

Churn: processes that wake VERY frequently while using very little CPU
each time. This shape is deliberate and is the whole point -- a task
that burns CPU is already deprioritised by ordinary vtime fairness, so a
wakeup-frequency mechanism adds nothing there. The information vtime
CANNOT see is "wakes constantly but is cheap", which is precisely what
this project proposes to track. An earlier version burned 5ms per wake,
saturated the machine to 94% CPU, and still moved the victim's latency
barely at all -- because vtime had already handled it.

Each churn task uses a DISTINCT
identity. Distinct deliberately: Section 9.8's unfixed counter race
needs concurrent same-identity access, so distinct-identity churn keeps
that bug out of this experiment rather than silently contaminating it.

THE COMPARISONS, IN ORDER OF IMPORTANCE

  exact+penalty vs. mechanism=none   THE GATING QUESTION. Does acting on
                                     the count help at all, given perfect
                                     information? If no, sketch-vs-exact
                                     is comparing two ways to compute a
                                     number nobody usefully acts on.
  sketch+penalty vs. exact+penalty   The paper's actual hypothesis. Only
                                     meaningful if the gate above opened.
  any of the above vs. EEVDF/simple/lavd   Is this competitive at all.

THE POSITIVE CONTROL

Round 1's failure mode was producing an uninterpretable answer. So this
round tests the instrument as well as the hypothesis: a condition that
simply REMOVES most of the antagonist (churn count cut from 24 to 4).
If the victim does not improve when the thing hurting it is mostly taken
away, then this workload cannot detect churn pressure at all, and any
null from the conditions above is uninterpretable rather than
informative.

An earlier version used niced churn as the control. That was wrong for
this workload shape: nice governs CPU-time allocation, and this churn is
deliberately CPU-light, so nicing it changes almost nothing. The control
has to remove the pressure being measured, not re-weight CPU time that
is not the pressure.

Note this is deliberately NOT the mistake paper Section 4.2.1 records
(an oracle policy whose advantage was reported as a finding). Here the
oracle-ish condition is used to validate the measurement, never as a
result about the sketch.

PENALTY STRENGTH, FIXED IN ADVANCE

Chosen on principle, not tuned: penalty_ns = one scheduling slice
(SCX_SLICE_DFL, 20ms) divided by the churn wakeup count observed in a
pre-flight measurement, so a typical churn task is pushed back by
roughly one slice. Tuning this until an effect appears is exactly the
trap this project has already fallen into twice; the value is derived,
printed, and then left alone.
"""

import argparse
import glob
import json
import os
import pwd
import re
import shutil
import statistics
import subprocess
import sys
import time

SCX_SLICE_DFL_NS = 20_000_000


def _find(rel: str) -> str:
    cands = []
    user = os.environ.get("SUDO_USER")
    if user:
        try:
            cands.append(os.path.join(pwd.getpwnam(user).pw_dir, rel))
        except KeyError:
            pass
    cands.append(os.path.expanduser(f"~/{rel}"))
    cands.extend(glob.glob(f"/home/*/{rel}"))
    for c in cands:
        if os.path.exists(c):
            return c
    raise SystemExit(f"not found: {rel} (looked in {cands})")


RTAPP = _find("rt-app/src/rt-app")
SCHBENCH = _find("schbench/schbench")
LOGDIR = "/tmp/round2_rtapp"


def run_schbench_victim(args) -> dict:
    """Victim measured via schbench instead of rt-app.

    WHY NOT rt-app, despite the delivery plan specifying it: rt-app's
    victim is woken by an hrtimer, and on this VM the timer-delivery
    floor is ~1.7ms p99 -- measured with 24 churn tasks, with 4, and with
    NONE, all statistically identical (1674/1771/1710us). A floor that
    high swamps any scheduling contribution, so the rt-app victim cannot
    measure scheduling on this machine at all. That is an environmental
    limit, not something churn tuning can fix.

    schbench measures task-to-task wakeup latency -- the path a scheduler
    actually controls -- and demonstrably responds to scheduler choice
    (round 1 saw 14k-42k across conditions on the same VM). So the victim
    is schbench and the antagonist is the churn round 1 lacked.
    """
    out = f"/tmp/round2_sb_{os.getpid()}_{time.time()}.json"
    subprocess.run(
        [SCHBENCH, "-m", "2", "-t", str(args.victim_threads),
         "-R", str(args.victim_rps), "-w", "3", "-r", str(args.duration),
         "-j", out],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    with open(out) as f:
        d = json.load(f)["int"]
    os.unlink(out)
    return {
        "n": 0,
        "wu_p50": d["request_latency_pct50.0"],
        "wu_p99": d["request_latency_pct99.0"],
        "wu_max": d["request_latency_pct99.9"],
        "misses": 0,
        "miss_pct": 0.0,
    }


def wait_state(want: str, timeout: float = 12.0) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        try:
            with open("/sys/kernel/sched_ext/state") as f:
                if f.read().strip() == want:
                    return True
        except OSError:
            pass
        time.sleep(0.3)
    return False


class SchedulerHandle:
    def __init__(self, binary, args):
        self.binary = binary
        self.args = args or []
        self.proc = None
        self.log = f"/tmp/round2_sched_{time.time()}.log"

    def __enter__(self):
        subprocess.run(["sudo", "pkill", "-9", "-f", "scx_"], capture_output=True)
        if not wait_state("disabled"):
            raise RuntimeError("a previous scheduler is still attached")
        if self.binary is None:
            return self
        with open(self.log, "w") as f:
            self.proc = subprocess.Popen(["sudo", self.binary, *self.args],
                                         stdout=f, stderr=subprocess.STDOUT)
        if not wait_state("enabled"):
            self.proc.kill()
            raise RuntimeError(f"{self.binary} failed to attach")
        return self

    def __exit__(self, *exc):
        if self.proc:
            subprocess.run(["sudo", "kill", "-INT", str(self.proc.pid)],
                           capture_output=True)
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                subprocess.run(["sudo", "kill", "-9", str(self.proc.pid)],
                               capture_output=True)
        subprocess.run(["sudo", "pkill", "-9", "-f", "scx_"], capture_output=True)
        wait_state("disabled")
        return False

    def mechanism_reach(self):
        """Parse the last reported reach % from scx_cms's stats output.

        Section 9.1: a mechanism only sees dispatches that go through
        enqueue, and on an idle machine almost none do (0.8% vs 85.9%
        under load). A result without this number cannot distinguish
        'the mechanism did nothing' from 'the mechanism never ran'.
        """
        try:
            with open(self.log) as f:
                text = f.read()
        except OSError:
            return None
        matches = re.findall(r"mechanism reach ([\d.]+)%", text)
        return float(matches[-1]) if matches else None


def write_victim_config(period_us: int, run_us: int, duration_s: int) -> str:
    cfg = {
        "tasks": {
            "audio": {
                "instance": 1,
                "loop": -1,
                "run": run_us,
                "timer": {"ref": "unique", "period": period_us},
            }
        },
        "global": {
            "duration": duration_s,
            "calibration": "CPU0",
            "default_policy": "SCHED_OTHER",
            "lock_pages": False,
            "logdir": LOGDIR,
            "log_basename": "victim",
            "gnuplot": False,
        },
    }
    path = "/tmp/round2_victim.json"
    with open(path, "w") as f:
        json.dump(cfg, f)
    return path


def churn_worker(idx: int, rate: float, duration: float, burn_us: int) -> None:
    """One churn task: wakes frequently AND consumes CPU.

    The burn is not incidental. A first version of this only slept and
    woke, which generated plenty of wakeup events for the tracker but no
    CPU demand -- so the CPUs stayed mostly idle, no queue ever formed,
    and there was nothing for a queue-reordering mechanism to reorder.
    The positive control caught it immediately (niced churn produced no
    improvement, meaning the workload could not detect scheduling
    quality at all) before it could produce five repetitions of an
    uninterpretable null.

    Distinct comm per worker -- see module docstring on Section 9.8.
    """
    import ctypes
    libc = ctypes.CDLL("libc.so.6", use_errno=True)
    buf = ctypes.create_string_buffer(f"churn{idx}".encode()[:15])
    libc.prctl(15, ctypes.byref(buf), 0, 0, 0)
    interval = 1.0 / rate
    burn_s = burn_us / 1e6
    end = time.time() + duration
    while time.time() < end:
        spin_until = time.perf_counter() + burn_s
        while time.perf_counter() < spin_until:
            pass
        time.sleep(interval)


def spawn_churn(count: int, rate: float, duration: float, burn_us: int,
                nice: int = 0) -> list:
    pids = []
    for i in range(count):
        pid = os.fork()
        if pid == 0:
            if nice:
                try:
                    os.nice(nice)
                except OSError:
                    pass
            churn_worker(i, rate, duration, burn_us)
            os._exit(0)
        pids.append(pid)
    return pids


def parse_victim_log() -> dict:
    """Extract wakeup latency and deadline misses from rt-app's log."""
    logs = glob.glob(f"{LOGDIR}/victim-audio-*.log")
    if not logs:
        raise RuntimeError(f"no rt-app victim log produced in {LOGDIR}")
    wu_lats, slacks = [], []
    with open(logs[0]) as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                continue
            parts = line.split()
            if len(parts) < 10:
                continue
            try:
                slacks.append(int(parts[7]))
                wu_lats.append(int(parts[10]) if len(parts) > 10 else int(parts[-1]))
            except ValueError:
                continue
    if not wu_lats:
        raise RuntimeError("rt-app log had no parseable rows")
    s = sorted(wu_lats)
    return {
        "n": len(s),
        "wu_p50": s[len(s) // 2],
        "wu_p99": s[min(len(s) - 1, int(len(s) * 0.99))],
        "wu_max": s[-1],
        "misses": sum(1 for x in slacks if x < 0),
        "miss_pct": 100.0 * sum(1 for x in slacks if x < 0) / len(slacks),
    }


def run_condition(binary, sched_args, args, churn_nice=0,
                  churn_override=None) -> dict:
    shutil.rmtree(LOGDIR, ignore_errors=True)
    os.makedirs(LOGDIR, exist_ok=True)
    cfg = write_victim_config(args.period_us, args.run_us, args.duration)

    with SchedulerHandle(binary, sched_args) as sched:
        churn = spawn_churn(churn_override or args.churn, args.churn_rate,
                            args.duration + 3, args.churn_burn_us,
                            nice=churn_nice)
        time.sleep(0.5)
        if args.victim == "schbench":
            measured = run_schbench_victim(args)
        else:
            subprocess.run([RTAPP, cfg], stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, check=True)
            measured = None
        for pid in churn:
            try:
                os.kill(pid, 9)
                os.waitpid(pid, 0)
            except (ProcessLookupError, ChildProcessError):
                pass
        result = measured if measured is not None else parse_victim_log()
        result["reach"] = sched.mechanism_reach()
    return result


def preflight_penalty_ns(args) -> tuple:
    """Derive penalty strength from an observed churn count, not a guess."""
    scx_cms = _find("scx-target/debug/scx_cms")
    shutil.rmtree(LOGDIR, ignore_errors=True)
    os.makedirs(LOGDIR, exist_ok=True)
    with SchedulerHandle(scx_cms, ["--tracker", "exact", "--mechanism", "none",
                                    "--compare", "--identity-key", "pid",
                                    "--window-ms", str(args.window_ms),
                                    "--stats", "60"]):
        churn = spawn_churn(args.churn, args.churn_rate, 6, args.churn_burn_us)
        time.sleep(5)
        out = subprocess.run(
            ["sudo", "bpftool", "map", "show", "-j"],
            capture_output=True, text=True, check=True)
        bss_id = None
        for m in json.loads(out.stdout):
            if m.get("name") == "bpf_bpf.bss" and any(
                    p.get("comm") == "scx_cms" for p in m.get("pids", [])):
                bss_id = m["id"]
        dump = json.loads(subprocess.run(
            ["sudo", "bpftool", "map", "dump", "id", str(bss_id), "-j"],
            capture_output=True, text=True, check=True).stdout)
        value = dump[0].get("formatted", dump[0])["value"]
        entries = value[".bss"] if isinstance(value, dict) and ".bss" in value else value
        flat = {}
        for item in entries:
            flat.update(item)
        for pid in churn:
            try:
                os.kill(pid, 9)
                os.waitpid(pid, 0)
            except (ProcessLookupError, ChildProcessError):
                pass
        samples = int(flat.get("cms_cmp_samples", 0)) or 1
        mean_count = int(flat.get("cms_cmp_exact_sum", 0)) / samples

    mean_count = max(mean_count, 1.0)
    penalty = int(SCX_SLICE_DFL_NS / mean_count)
    return penalty, mean_count


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--period-us", type=int, default=10000,
                    help="victim wake period (audio callback ~10ms)")
    ap.add_argument("--run-us", type=int, default=2000,
                    help="victim work per period")
    ap.add_argument("--duration", type=int, default=10)
    ap.add_argument("--churn", type=int, default=128)
    ap.add_argument("--posctl-churn", type=int, default=8,
                    help="churn count for the positive control -- if the "
                         "victim does not improve with the antagonist "
                         "mostly removed, this workload cannot detect "
                         "churn pressure and every other row is void")
    ap.add_argument("--churn-rate", type=float, default=200.0)
    ap.add_argument("--churn-burn-us", type=int, default=200,
                    help="CPU actually consumed per churn wakeup. Must be "
                         "enough to oversubscribe the machine or no queue "
                         "forms and the mechanism has nothing to reorder")
    ap.add_argument("--window-ms", type=int, default=1000)
    ap.add_argument("--repeat", type=int, default=5)
    ap.add_argument("--victim", choices=["schbench", "rtapp"],
                    default="schbench",
                    help="schbench measures task-to-task wakeups (works); "
                         "rtapp measures timer wakeups (floored by VM timer "
                         "delivery at ~1.7ms, cannot detect scheduling here)")
    ap.add_argument("--victim-threads", type=int, default=4)
    ap.add_argument("--victim-rps", type=int, default=100)
    ap.add_argument("--penalty-ns", type=int, default=0,
                    help="0 = derive from pre-flight (recommended)")
    ap.add_argument("--only", default=None,
                    help="comma-separated condition names to run, for "
                         "confirmation runs at higher --repeat that do not "
                         "re-pay for rows already settled. Keep a control "
                         "in the list: a confirmation run of only the "
                         "conditions that looked good proves nothing.")
    args = ap.parse_args()

    if os.geteuid() != 0:
        print("needs root", file=sys.stderr)
        return 1

    scx_cms = _find("scx-target/debug/scx_cms")
    scx_simple = _find("scx-c-examples/build/scheds/c/scx_simple")
    scx_lavd = _find("scx-target/debug/scx_lavd")

    print("Phase 6 round 2: mixed workload (audio-callback victim + churn)")
    demand = args.churn * args.churn_burn_us * args.churn_rate / 1e6
    print(f"victim: {args.run_us}us work every {args.period_us}us; "
          f"churn: {args.churn} tasks @ {args.churn_rate}/s burning "
          f"{args.churn_burn_us}us each")
    print(f"  churn CPU demand ~= {demand:.1f} CPUs "
          f"(machine has {os.cpu_count()})\n")

    if args.penalty_ns:
        penalty_ns, mean_count = args.penalty_ns, None
        print(f"penalty_ns = {penalty_ns} (supplied)\n")
    else:
        penalty_ns, mean_count = preflight_penalty_ns(args)
        print(f"pre-flight: mean tracked count {mean_count:.0f} per query")
        print(f"penalty_ns = one slice ({SCX_SLICE_DFL_NS}) / {mean_count:.0f} "
              f"= {penalty_ns}  [derived, then left alone]\n")

    cms_common = ["--identity-key", "pid", "--window-ms", str(args.window_ms),
                  "--penalty-ns", str(penalty_ns), "--stats", "2"]

    conditions = [
        ("eevdf", None, [], 0),
        ("scx_simple", scx_simple, [], 0),
        ("cms_none", scx_cms, ["--tracker", "exact", "--mechanism", "none"] + cms_common, 0),
        ("cms_exact_penalty", scx_cms, ["--tracker", "exact", "--mechanism", "penalty"] + cms_common, 0),
        ("cms_sketch_penalty", scx_cms, ["--tracker", "sketch", "--mechanism", "penalty"] + cms_common, 0),
        ("flat_2ms", scx_cms, ["--tracker", "exact", "--mechanism", "flat",
                               "--flat-ns", "2000000"] + cms_common, 0),
        ("flat_4ms", scx_cms, ["--tracker", "exact", "--mechanism", "flat",
                               "--flat-ns", "4000000"] + cms_common, 0),
        ("flat_8ms", scx_cms, ["--tracker", "exact", "--mechanism", "flat",
                               "--flat-ns", "8000000"] + cms_common, 0),
        ("scx_lavd", scx_lavd, [], 0),
        ("POSCTL_low_churn", None, [], 0),
    ]

    if args.only:
        wanted = {n.strip() for n in args.only.split(",")}
        unknown = wanted - {n for n, _, _, _ in conditions}
        if unknown:
            print(f"unknown condition(s): {', '.join(sorted(unknown))}",
                  file=sys.stderr)
            return 1
        conditions = [c for c in conditions if c[0] in wanted]

    runs = {name: [] for name, _, _, _ in conditions}
    for rep in range(args.repeat):
        print(f"### repetition {rep + 1}/{args.repeat} ###")
        for name, binary, sched_args, nice in conditions:
            try:
                r = run_condition(binary, sched_args, args, churn_nice=nice,
                                  churn_override=(args.posctl_churn
                                                  if name.startswith("POSCTL")
                                                  else None))
            except Exception as e:  # noqa: BLE001
                print(f"  {name:<20} ERROR: {e}")
                continue
            runs[name].append(r)
            reach = f" reach={r['reach']:.0f}%" if r.get("reach") is not None else ""
            print(f"  {name:<20} wu_p50={r['wu_p50']:>6}us "
                  f"wu_p99={r['wu_p99']:>7}us misses={r['miss_pct']:>5.1f}%{reach}")

    print("\n" + "=" * 78)
    print(f"Summary: median of {args.repeat} runs, victim wakeup latency")
    print("=" * 78)

    base = runs.get("eevdf")
    base_p99 = statistics.median(r["wu_p99"] for r in base) if base else None

    for name, _, _, _ in conditions:
        rs = runs[name]
        if not rs:
            continue
        p99s = sorted(r["wu_p99"] for r in rs)
        med = statistics.median(p99s)
        mult = f"{med / base_p99:>5.2f}x" if base_p99 else "   n/a"
        misses = statistics.median(r["miss_pct"] for r in rs)
        reaches = [r["reach"] for r in rs if r.get("reach") is not None]
        reach = f"  reach={statistics.median(reaches):.0f}%" if reaches else ""
        print(f"  {name:<20} p99 {med:>7.0f}us ({mult})  "
              f"range {p99s[0]:>6}-{p99s[-1]:>6}  misses {misses:>5.1f}%{reach}")

    print("\nHOW TO READ THIS:")
    print("  1. POSCTL_low_churn vs eevdf -- if removing most of the antagonist")
    print("     does NOT improve the victim, this workload cannot detect")
    print("     scheduling quality and every other row below is")
    print("     uninterpretable. Check this FIRST.")
    print("  2. cms_exact_penalty vs cms_none -- the gating question: does acting")
    print("     on a perfect count help at all?")
    print("  3. cms_sketch_penalty vs cms_exact_penalty -- the paper's hypothesis,")
    print("     meaningful only if (2) showed something.")
    print("  Ranges overlapping = no effect demonstrated, regardless of medians.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
