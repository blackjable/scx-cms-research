#!/usr/bin/env python3
"""
Phase 6: four-tier baseline benchmark.

The delivery plan (Section 3) requires four baseline tiers before any
scheduling-quality claim is credible -- the original plan's single
"exact vs. sketch" comparison isolates the sketch's own effect, but says
nothing about whether any of this is worth using at all, or how it
compares to what people actually run:

  1. EEVDF        stock kernel scheduler, no sched_ext scheduler loaded
  2. scx_simple   the field's minimal reference scheduler
  3. scx_cms      this project's own scheduler, exact counters, no
                  mechanism (--tracker exact --mechanism none) --
                  isolates "does this project's scaffolding cost
                  anything" from the sketch/mechanism questions Section 9
                  already answered
  4. scx_lavd     an established production scheduler (SteamOS's
                  latency-aware scheduler), chosen over scx_rusty for
                  thematic alignment -- it is also fundamentally about
                  tracking task behavior to protect latency-sensitive
                  work, the same problem space as this project

METRIC: schbench request-latency P99, matched to the choice validated in
Section 9.5's manipulation experiment (large sample count, stable;
wakeup-latency percentiles in rps mode were found unusable there -- ~17
samples pinned to a histogram-ceiling artifact).

METHODOLOGY LESSONS CARRIED FORWARD FROM SECTIONS 9.5/9.6:
  - Conditions are interleaved across repetitions, not run back-to-back,
    so thermal/background drift hits every condition alike rather than
    whichever ran last.
  - Report medians and ranges, not single points -- a single run in an
    interesting direction was wrong twice already in this project
    (9.5's +34.7%-that-became--1.7%, 9.6's heavy-volume near-clearance
    that turned out to be a fluke).
  - Per Section 3, every result is reported as a multiplier against
    EEVDF, not just relative to this project's own variants.
"""

import argparse
import glob
import json
import os
import pwd
import statistics
import subprocess
import sys
import time


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


SCHBENCH = _find("schbench/schbench")


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
    """Starts one condition's scheduler (or none, for EEVDF); guarantees
    cleanup even on failure. None binary means EEVDF: verify no
    sched_ext scheduler is loaded rather than assuming."""

    def __init__(self, binary, args):
        self.binary = binary
        self.args = args or []
        self.proc = None

    def __enter__(self):
        subprocess.run(["sudo", "pkill", "-9", "-f", "scx_"], capture_output=True)
        if not wait_state("disabled"):
            raise RuntimeError("a previous scheduler is still attached")
        if self.binary is None:
            return self  # EEVDF: nothing to start
        self.proc = subprocess.Popen(
            ["sudo", self.binary, *self.args],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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


def run_schbench(message_threads, worker_threads, rps, warmup, runtime) -> dict:
    out = f"/tmp/bench_{os.getpid()}_{time.time()}.json"
    subprocess.run(
        [SCHBENCH, "-m", str(message_threads), "-t", str(worker_threads),
         "-R", str(rps), "-w", str(warmup), "-r", str(runtime), "-j", out],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    with open(out) as f:
        data = json.load(f)
    os.unlink(out)
    return data["int"]


def build_conditions(args):
    scx_cms = _find("scx-target/debug/scx_cms")
    scx_simple = _find("scx-c-examples/build/scheds/c/scx_simple")
    scx_lavd = _find("scx-target/debug/scx_lavd")
    return [
        ("eevdf", None, []),
        ("scx_simple", scx_simple, []),
        ("scx_cms_exact", scx_cms,
         ["--tracker", "exact", "--mechanism", "none", "--stats", "60"]),
        ("scx_lavd", scx_lavd, []),
    ]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--message-threads", type=int, default=2)
    ap.add_argument("--worker-threads", type=int, default=4)
    ap.add_argument("--rps", type=int, default=100)
    ap.add_argument("--warmup", type=int, default=3)
    ap.add_argument("--runtime", type=int, default=10)
    ap.add_argument("--repeat", type=int, default=5)
    args = ap.parse_args()

    if os.geteuid() != 0:
        print("needs root", file=sys.stderr)
        return 1

    conditions = build_conditions(args)
    print("Phase 6: four-tier baseline comparison")
    print(f"schbench: -m{args.message_threads} -t{args.worker_threads} "
          f"-R{args.rps} -w{args.warmup} -r{args.runtime}, "
          f"{args.repeat} interleaved reps/condition\n")

    runs = {name: [] for name, _, _ in conditions}
    for rep in range(args.repeat):
        print(f"### repetition {rep + 1}/{args.repeat} ###")
        for name, binary, sched_args in conditions:
            with SchedulerHandle(binary, sched_args):
                time.sleep(0.5)
                result = run_schbench(args.message_threads, args.worker_threads,
                                      args.rps, args.warmup, args.runtime)
            p50 = result["request_latency_pct50.0"]
            p99 = result["request_latency_pct99.0"]
            p999 = result["request_latency_pct99.9"]
            runs[name].append({"p50": p50, "p99": p99, "p999": p999})
            print(f"  {name:<16} p50={p50:>6}us  p99={p99:>7}us  "
                  f"p999={p999:>7}us")

    print("\n" + "=" * 72)
    print(f"Summary: median of {args.repeat} runs, multiplier vs. EEVDF")
    print("=" * 72)

    eevdf_p99 = statistics.median(r["p99"] for r in runs["eevdf"])
    eevdf_p999 = statistics.median(r["p999"] for r in runs["eevdf"])

    for name, _, _ in conditions:
        rs = runs[name]
        p99s = sorted(r["p99"] for r in rs)
        p999s = sorted(r["p999"] for r in rs)
        med99, med999 = statistics.median(p99s), statistics.median(p999s)
        mult99 = med99 / eevdf_p99 if eevdf_p99 else float("nan")
        mult999 = med999 / eevdf_p999 if eevdf_p999 else float("nan")
        print(f"  {name:<16} p99 {med99:>7.0f}us ({mult99:>5.2f}x)  "
              f"range {p99s[0]:>6}-{p99s[-1]:>6}   "
              f"p999 {med999:>7.0f}us ({mult999:>5.2f}x)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
