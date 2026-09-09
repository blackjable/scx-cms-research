#!/usr/bin/env python3
"""
Does corrupting the tracked signal actually manipulate scheduling?

The collision attack (collision_attack.py) showed a victim's estimated
wakeup count can be inflated by orders of magnitude. That is a corrupted
signal, not yet a corrupted scheduling decision -- those runs had no
mechanism enabled, so nothing acted on the number. This asks the harder
question: with a mechanism live, does the attack make the victim's own
scheduling measurably worse?

THE CONFOUND, AND THE CONTROL

  An attack is also a load. 64 processes waking hundreds of times a
  second degrade everyone's latency whether or not any sketch is
  involved, so "victim latency got worse under attack" proves nothing on
  its own.

  The control is to hold the load identical and vary only which counter
  the mechanism reads:

    sketch + penalty   mechanism reads a corruptible count
    exact  + penalty   mechanism reads a truthful count, same attackers
    sketch + none      count is corrupted, nothing acts on it

  Every run uses --compare, so both counters are live and the attacker
  identities are computed the same way in all three; the only difference
  is which counter reaches the scheduling decision.

  If the manipulation is real, the victim suffers in the first
  configuration and not in the other two. If all three look alike, the
  corrupted signal is not reaching scheduling -- which is a result worth
  having, and the one the paper currently cannot claim either way.

WHAT IS MEASURED

  The victim sleeps in a tight periodic loop and records how late each
  wakeup actually was. That overshoot is what a latency-sensitive task
  experiences, and it is the same quantity schbench reports as wakeup
  latency. Percentiles are reported because a mean would hide exactly
  the tail behaviour that matters.
"""

import argparse
import glob
import json
import os
import pwd
import statistics
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from collision_attack import (  # noqa: E402
    find_colliding_comms,
    map_id,
    read_identity_key,
    read_probe,
    read_seeds,
    set_comm,
    set_probe_pid,
    spawn,
)

def _find_scheduler() -> str:
    """Locate the scx_cms binary.

    Under sudo, ~ is /root, but the build lives in the invoking user's
    home. Resolve via SUDO_USER before falling back.
    """
    candidates = []
    user = os.environ.get("SUDO_USER")
    if user:
        try:
            # The account's home is not always /home/<user>; on this VM the
            # login name and the directory differ.
            candidates.append(
                os.path.join(pwd.getpwnam(user).pw_dir, "scx-target/debug/scx_cms")
            )
        except KeyError:
            pass
    candidates.append(os.path.expanduser("~/scx-target/debug/scx_cms"))
    candidates.extend(glob.glob("/home/*/scx-target/debug/scx_cms"))

    for path in candidates:
        if os.path.exists(path):
            return path
    raise SystemExit(f"scx_cms not found; looked in: {', '.join(candidates)}")


SCHED = _find_scheduler()


def victim_loop(path: str, interval: float, duration: float) -> None:
    """Wake periodically; record how late each wakeup was, with a wall-clock
    timestamp.

    The timestamp is not optional bookkeeping. An earlier version stored
    bare latencies and split them in half to separate the baseline from the
    attack, which silently assumed the victim produces samples at the same
    rate in both phases. It does not: under attack it completes fewer
    loops, so the midpoint of the array falls after the real phase boundary
    and attack samples get counted as baseline. That produced the
    impossible-looking result of p99 latency IMPROVING under attack.
    """
    set_comm("victim")
    samples = []
    end = time.time() + duration
    while time.time() < end:
        t0 = time.perf_counter()
        time.sleep(interval)
        now = time.perf_counter()
        late = (now - t0 - interval) * 1e6  # microseconds
        if late > 0:
            samples.append((time.time(), late))
    with open(path, "w") as f:
        json.dump(samples, f)


def spawn_victim(path: str, interval: float, duration: float) -> int:
    pid = os.fork()
    if pid == 0:
        try:
            victim_loop(path, interval, duration)
        finally:
            os._exit(0)
    return pid


def percentiles(samples: list) -> dict:
    if not samples:
        return {}
    s = sorted(samples)
    return {
        "n": len(s),
        "p50": s[len(s) // 2],
        "p99": s[min(len(s) - 1, int(len(s) * 0.99))],
        "max": s[-1],
        "mean": statistics.fmean(s),
    }


def wait_for_state(want: str, timeout: float = 12.0) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        try:
            with open("/sys/kernel/sched_ext/state") as f:
                if f.read().strip() == want:
                    return True
        except OSError:
            pass
        time.sleep(0.4)
    return False


def start_scheduler(tracker: str, mechanism: str, penalty_ns: int,
                    window_ms: int, adjust_max_ns: int) -> subprocess.Popen:
    subprocess.run(["pkill", "-9", "scx_cms"], capture_output=True)
    if not wait_for_state("disabled"):
        raise RuntimeError("previous scheduler still attached")

    proc = subprocess.Popen(
        [SCHED, "--compare", "--tracker", tracker, "--mechanism", mechanism,
         "--identity-key", "comm", "--penalty-ns", str(penalty_ns),
         "--adjust-max-ns", str(adjust_max_ns),
         "--window-ms", str(window_ms), "--stats", "2"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    if not wait_for_state("enabled"):
        proc.kill()
        raise RuntimeError(f"scheduler failed to attach ({tracker}/{mechanism})")
    return proc


def run_condition(tracker: str, mechanism: str, args) -> dict:
    print(f"\n=== tracker={tracker} mechanism={mechanism} ===")
    proc = start_scheduler(tracker, mechanism, args.penalty_ns, args.window_ms,
                           args.adjust_max_ns)
    time.sleep(1.0)

    key = read_identity_key()
    if key != "comm":
        raise RuntimeError(f"scheduler keyed on {key}, expected comm")

    tmp = tempfile.mktemp(suffix=".json")
    victim = spawn_victim(tmp, args.interval, args.phase * 2 + 4)
    time.sleep(0.5)
    set_probe_pid(victim)

    # Baseline: victim alone.
    time.sleep(args.phase)
    base_probe = read_probe()

    # Attack: colliding processes, identical set across all conditions.
    # The collision search runs BEFORE the phase boundary is marked, so its
    # cost is not charged to either phase.
    seeds = read_seeds()
    victim_id = int(base_probe["identity"])
    colliding = find_colliding_comms(victim_id, seeds, args.width,
                                     args.depth, args.attackers)
    names = [n for n, _ in colliding]

    attack_start = time.time()
    attackers = [spawn(n, args.attacker_rate, args.phase + 3) for n in names]
    time.sleep(args.phase)
    atk_probe = read_probe()
    attack_end = time.time()

    for pid in attackers:
        try:
            os.kill(pid, 9)
            os.waitpid(pid, 0)
        except (ProcessLookupError, ChildProcessError):
            pass
    try:
        os.waitpid(victim, 0)
    except ChildProcessError:
        pass

    try:
        with open(tmp) as f:
            samples = json.load(f)
        os.unlink(tmp)
    except (OSError, json.JSONDecodeError):
        samples = []

    proc.send_signal(2)
    proc.wait(timeout=10)

    # Split by the actual phase boundary, not by sample count.
    base = [lat for ts, lat in samples if ts < attack_start]
    atk = [lat for ts, lat in samples if attack_start <= ts <= attack_end]

    exact_n = int(atk_probe["exact"])
    sketch_n = int(atk_probe["sketch"])

    # What the mechanism actually did with each count, so a null result can
    # be told apart from a penalty that was clipped before it could differ.
    pen_truth = min(exact_n * args.penalty_ns, args.adjust_max_ns)
    pen_corrupt = min(sketch_n * args.penalty_ns, args.adjust_max_ns)

    result = {
        "tracker": tracker,
        "mechanism": mechanism,
        "attackers": len(names),
        "baseline": percentiles(base),
        "attacked": percentiles(atk),
        "exact_attacked": exact_n,
        "sketch_attacked": sketch_n,
        "penalty_truth_ns": pen_truth,
        "penalty_corrupt_ns": pen_corrupt,
    }

    b, a = result["baseline"], result["attacked"]
    if b and a:
        print(f"  samples: {b['n']} baseline, {a['n']} attacked")
        print(f"  victim latency p50: {b['p50']:8.1f}us -> {a['p50']:8.1f}us")
        print(f"  victim latency p99: {b['p99']:8.1f}us -> {a['p99']:8.1f}us")
    print(f"  count seen: exact={exact_n} sketch={sketch_n} "
          f"({sketch_n / exact_n:.1f}x inflated)" if exact_n else "")
    print(f"  vtime penalty implied: truthful={pen_truth / 1e6:.1f}ms "
          f"corrupted={pen_corrupt / 1e6:.1f}ms"
          + ("  [BOTH AT CAP -- corruption cannot express itself]"
             if pen_truth == pen_corrupt == args.adjust_max_ns else ""))
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--width", type=int, default=256)
    ap.add_argument("--depth", type=int, default=4)
    ap.add_argument("--attackers", type=int, default=64)
    ap.add_argument("--attacker-rate", type=float, default=200.0)
    ap.add_argument("--interval", type=float, default=0.005,
                    help="victim wake period in seconds")
    ap.add_argument("--phase", type=float, default=8.0,
                    help="seconds per phase (baseline, then attack)")
    ap.add_argument("--penalty-ns", type=int, default=20000,
                    help="vtime penalty per tracked wakeup")
    ap.add_argument("--window-ms", type=int, default=2000)
    ap.add_argument("--repeat", type=int, default=1,
                    help="repetitions per condition; conditions are "
                         "interleaved so slow drift hits all of them alike")
    ap.add_argument("--adjust-max-ns", type=int, default=20_000_000,
                    help="ceiling on any single vtime adjustment; if both the "
                         "truthful and corrupted counts exceed it, the "
                         "corruption cannot affect scheduling at all")
    args = ap.parse_args()

    if os.geteuid() != 0:
        print("needs root", file=sys.stderr)
        return 1

    conditions = [
        ("sketch", "penalty"),   # corruptible signal, acted on
        ("exact", "penalty"),    # truthful signal, same load
        ("sketch", "none"),      # corrupted signal, not acted on
    ]

    runs = []
    for rep in range(args.repeat):
        if args.repeat > 1:
            print(f"\n########## repetition {rep + 1}/{args.repeat} ##########")
        # Interleaved rather than all repeats of one condition together, so
        # that anything drifting over the session (thermal, background work)
        # affects every condition rather than whichever ran last.
        for t, m in conditions:
            runs.append(run_condition(t, m, args))

    print("\n" + "=" * 72)
    print(f"Victim wakeup latency under attack, {args.repeat} run(s) per condition")
    print("=" * 72)

    for t, m in conditions:
        rs = [r for r in runs if r["tracker"] == t and r["mechanism"] == m
              and r["baseline"] and r["attacked"]]
        if not rs:
            continue
        b50 = statistics.median(r["baseline"]["p50"] for r in rs)
        a50 = statistics.median(r["attacked"]["p50"] for r in rs)
        b99 = statistics.median(r["baseline"]["p99"] for r in rs)
        a99 = statistics.median(r["attacked"]["p99"] for r in rs)
        spread = ""
        if len(rs) > 1:
            lo = min(r["attacked"]["p99"] for r in rs)
            hi = max(r["attacked"]["p99"] for r in rs)
            spread = f"  [p99 range {lo:.0f}-{hi:.0f}]"
        print(f"  {t:>6}/{m:<8} p50 {b50:7.1f} -> {a50:7.1f}   "
              f"p99 {b99:7.1f} -> {a99:7.1f}{spread}")

    # The comparison that matters, stated explicitly so it is not eyeballed.
    sk = [r["attacked"]["p99"] for r in runs
          if r["tracker"] == "sketch" and r["mechanism"] == "penalty"
          and r["attacked"]]
    ex = [r["attacked"]["p99"] for r in runs
          if r["tracker"] == "exact" and r["mechanism"] == "penalty"
          and r["attacked"]]
    if sk and ex:
        msk, mex = statistics.median(sk), statistics.median(ex)
        print(f"\n  corrupted vs truthful count, victim p99 under attack:")
        print(f"    sketch/penalty {msk:.1f}us   exact/penalty {mex:.1f}us   "
              f"({(msk - mex) / mex * 100:+.1f}%)")
        if len(sk) > 1:
            print(f"    (medians of {len(sk)} runs; ranges overlap = "
                  f"{max(min(sk), min(ex)) <= min(max(sk), max(ex))})")

    print("\nRead this by COMPARING ROWS, not by looking at any one of them:")
    print("  every row has the same attacker load, so a row degrading on its")
    print("  own says only that load hurts. Manipulation via the sketch shows")
    print("  up as sketch/penalty degrading MORE than exact/penalty.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
