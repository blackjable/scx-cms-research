"""
experiment.py

Phase 1 demo script: the basic sketch-vs-exact-counter comparison under
the rotating dual-buffer window scheme, using the shared, canonical
implementation in sketch_lib.py.

CORRECTNESS NOTE: an earlier version of this file had its OWN
independent copy of the sketch/counter classes, which was never
updated when sketch_lib.py fixed the hash-randomization
reproducibility bug (see sketch_lib.py's module docstring and the
paper draft's Section 2.1.1). That meant this file was silently
running the OLD, buggy, non-reproducible version even after the fix
was "done" elsewhere — exactly the kind of drift the sketch_lib
refactor was supposed to prevent, and a good reminder that factoring
shared code into a module only helps if every caller actually uses
it. Fixed by importing from sketch_lib directly instead of duplicating.

No kernel, no BPF, no VM required to run this — see run.sh.
"""

import sys

from sketch_lib import SimConfig, run_simulation


def print_report(config: SimConfig, result) -> None:
    print("=" * 76)
    print("Count-Min Sketch vs Exact Counter — Rotating Window Wakeup Tracking")
    print("=" * 76)
    print()

    true_window = config.latency_task_wakeups_per_epoch * 2
    print(f"{'Sample':>8}  {'TrueWin':>8}  {'SketchErr':>10}  {'ExactErr':>9}")
    for i in range(len(result.steady_state_sketch_errors)):
        print(f"{i:>8}  {true_window:>8}  "
              f"{result.steady_state_sketch_errors[i]:>+10}  "
              f"{result.steady_state_exact_errors[i]:>+9}")
    print()
    print("Memory footprint (bytes):")
    print(f"  Sketch — steady state: {result.sketch_memory_bytes:>10,}  "
          f"(fixed — 2x single buffer, still bounded)")
    print(f"  Exact  — steady state: {result.exact_memory_bytes_final:>10,}  "
          f"(scales with PER-WINDOW churn, not lifetime churn)")
    print()
    ratio = result.exact_memory_bytes_final / result.sketch_memory_bytes
    print(f"  Exact counter uses {ratio:.1f}x more memory than the sketch"
          f" at steady state, this churn level.")
    print()
    import statistics
    avg_sketch_err = statistics.mean(result.steady_state_sketch_errors)
    avg_exact_err = statistics.mean(result.steady_state_exact_errors)
    print(f"  Steady-state avg error: sketch {avg_sketch_err:+.1f}, "
          f"exact {avg_exact_err:+.1f}")
    print()
    print("For rigor testing (multi-seed variance, parameter sweeps,")
    print("adversarial distributions), see sweep_experiment.py.")
    print("For reproducibility/invariant/targeted-attack testing, see")
    print("strict_tests.py.")


if __name__ == "__main__":
    config = SimConfig()
    result = run_simulation(config)
    print_report(config, result)
