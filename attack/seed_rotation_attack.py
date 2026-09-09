#!/usr/bin/env python3
"""
Does --seed-rotation mitigate the targeted-collision attack on a real kernel?

Phase 1 (paper 4.1.3/4.1.4) found seed rotation to be a PARTIAL mitigation
only: an attack that hit +400% in the window it targeted still showed
+200% one window later (stale keys landing at effectively random columns
in the now-differently-seeded "current" buffer, while the poisoned
"previous" buffer -- unaffected by reseeding -- still carries forward),
clearing to ~0% only in the second window after the attack stopped.

This replays that experiment against the real BPF sketch: fire a sustained
attack using identities computed against the seeds at t=0, and sample the
victim's inflation at each window boundary as those seeds are rotated out
from under the attacker.

CONTROL: the identical attack run with --seed-rotation OFF, so any decay
is attributable to reseeding and not to some other window-boundary effect.
"""

import argparse
import glob
import json
import os
import pwd
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from collision_attack import (  # noqa: E402
    find_colliding_comms,
    fnv1a_comm,
    read_bss,
    read_identity_key,
    read_probe,
    read_seeds,
    set_probe_pid,
    spawn,
)


def epoch() -> int:
    return int(read_bss().get("cms_epoch", 0))


def wait_for_epoch(target: int, timeout: float = 6.0) -> int:
    """Block until cms_epoch reaches target, rather than sleeping a fixed
    duration and hoping it lined up with the kernel's own timer. An earlier
    version of this script slept window_ms between samples and drifted out
    of phase with real rotations -- confirmed by a diagnostic run that
    logged epoch alongside each sample and found it inconsistent with wall
    clock sleeps. That produced a result (0%, 0%, then rising to 787%)
    that looked like a finding and was not: it was measuring drift, not
    the attack."""
    end = time.time() + timeout
    e = epoch()
    while e < target and time.time() < end:
        time.sleep(0.05)
        e = epoch()
    return e


def _find_scheduler() -> str:
    """Locate scx_cms. Under sudo, ~ is /root, not the build's home."""
    cands = []
    user = os.environ.get("SUDO_USER")
    if user:
        try:
            cands.append(os.path.join(pwd.getpwnam(user).pw_dir,
                                      "scx-target/debug/scx_cms"))
        except KeyError:
            pass
    cands.append(os.path.expanduser("~/scx-target/debug/scx_cms"))
    cands.extend(glob.glob("/home/*/scx-target/debug/scx_cms"))
    for c in cands:
        if os.path.exists(c):
            return c
    raise SystemExit(f"scx_cms not found; looked in: {cands}")


SCHED = _find_scheduler()


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


def start(seed_rotation: bool, window_ms: int) -> subprocess.Popen:
    subprocess.run(["pkill", "-9", "scx_cms"], capture_output=True)
    if not wait_state("disabled"):
        raise RuntimeError("previous scheduler still attached")
    args = [SCHED, "--compare", "--tracker", "sketch", "--identity-key", "comm",
            "--window-ms", str(window_ms), "--stats", "2"]
    if seed_rotation:
        args.append("--seed-rotation")
    proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if not wait_state("enabled"):
        proc.kill()
        raise RuntimeError("scheduler failed to attach")
    return proc


def run(seed_rotation: bool, args) -> list:
    proc = start(seed_rotation, args.window_ms)
    time.sleep(1.0)
    assert read_identity_key() == "comm"

    victim = spawn("victim", 20, args.window_ms / 1000 * (args.windows + 1) + 5)
    time.sleep(0.5)
    set_probe_pid(victim)

    # Colliding identities computed ONCE, against the seeds live at t=0 --
    # this is the whole point: does the attacker's precomputation stay
    # valid as the sketch reseeds under it. Confirmed unchanged across the
    # search (epoch checked before and after) so the target seeds are known
    # to match what was actually live when the attack begins.
    ep_before = epoch()
    seeds = read_seeds()
    victim_id = int(read_probe()["identity"])
    names = [n for n, _ in find_colliding_comms(victim_id, seeds, args.width,
                                                 args.depth, args.attackers)]
    ep_start = epoch()
    if ep_start != ep_before:
        print(f"  [rotated during collision search: epoch {ep_before}->{ep_start}, "
              f"retargeting]", file=sys.stderr)

    attackers = [spawn(n, args.attacker_rate,
                       args.window_ms / 1000 * args.windows + 3)
                 for n in names]

    samples = []
    for w in range(args.windows):
        wait_for_epoch(ep_start + w + 1)
        p = read_probe()
        exact, sketch = int(p["exact"]), int(p["sketch"])
        over = (sketch - exact) / exact * 100 if exact else 0.0
        samples.append((over, epoch()))

    for pid in attackers + [victim]:
        try:
            os.kill(pid, 9)
            os.waitpid(pid, 0)
        except (ProcessLookupError, ChildProcessError):
            pass
    proc.send_signal(2)
    proc.wait(timeout=10)
    return samples


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--width", type=int, default=256)
    ap.add_argument("--depth", type=int, default=4)
    ap.add_argument("--attackers", type=int, default=64)
    ap.add_argument("--attacker-rate", type=float, default=200.0)
    ap.add_argument("--window-ms", type=int, default=2000)
    ap.add_argument("--windows", type=int, default=4,
                    help="how many window boundaries to sample after the "
                         "attack starts (attackers keep firing throughout, "
                         "replaying their t=0 identities -- matches Phase "
                         "1's 'replay stale keys' test, not the one-shot "
                         "'fire once and go silent' variant)")
    args = ap.parse_args()

    if os.geteuid() != 0:
        print("needs root", file=sys.stderr)
        return 1

    print(f"Seed rotation vs. targeted collision, {args.attackers} attackers "
          f"@ {args.attacker_rate}/s, {args.window_ms}ms windows, sustained "
          f"(replaying t=0 identities)\n")

    print("with --seed-rotation OFF (control):")
    off = run(False, args)
    for i, (v, ep) in enumerate(off):
        print(f"  window {i} (epoch {ep}): {v:+.1f}%")

    print("\nwith --seed-rotation ON:")
    on = run(True, args)
    for i, (v, ep) in enumerate(on):
        print(f"  window {i} (epoch {ep}): {v:+.1f}%")

    print("\n" + "=" * 60)
    print(f"{'window':<8}{'no rotation':>15}{'seed rotation':>17}")
    for i in range(args.windows):
        print(f"{i:<8}{off[i][0]:>14.1f}%{on[i][0]:>16.1f}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
