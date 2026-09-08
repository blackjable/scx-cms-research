"""
savage_audit.py

A no-corners-cut pass over every remaining approximation, guess, or
untested assumption in the codebase. Each test here either replaces a
guessed constant with a measured one, extends a check that was
narrower than it should have been, or fuzzes an edge case nobody had
tried yet.

1. REAL MEMORY MEASUREMENT — the exact counter's memory_bytes() has
   used a GUESSED constant ("~50 bytes per dict entry") since this
   project began, never actually measured. This replaces the guess
   with sys.getsizeof-based real measurement and reports how wrong the
   guess was.

2. EXACT (not approximated) L1 NORM for the theoretical bound — every
   theoretical-bound calculation so far has used an analytical
   approximation of total event volume ("avg 10 wakeups * 5000
   identities"). This computes the ACTUAL L1 norm from real inserted
   events and compares against the approximation.

3. EXTENDED INVARIANT CHECK — the never-underestimate guarantee
   (strict_tests.py Test B) was only ever checked for ONE key (the
   latency-sensitive task). This extends it to EVERY churn key in a
   window, a much stronger correctness claim.

4. PROPER STATISTICAL SIGNIFICANCE TEST — the adversarial-vs-uniform
   "severe degradation" claim (sweep_experiment.py Test 3) used an
   arbitrary hand-picked threshold ("degradation > 30 percentage
   points = severe"), not a real hypothesis test. This runs a proper
   Welch's t-test.

5. EDGE-CASE / BOUNDARY FUZZING — width=1, depth=1, zero churn,
   extreme churn — none of these have ever been tried. Checks for
   crashes, negative values, or other undefined behavior.

6. COLLISION-SEARCH VERIFICATION — find_colliding_keys has a bounded
   search budget and could theoretically return FEWER keys than
   requested without any test ever checking for that silently-weaker
   attack. This asserts the requested count is always actually found.
"""

import statistics
import sys

from sketch_lib import (
    ChurnDistribution, CountMinSketch, RotatingCountMinSketch,
    RotatingExactCounter, SimConfig, generate_churn_events, run_simulation,
    stable_hash,
)
from strict_tests import find_colliding_keys


# ---------------------------------------------------------------------
# Test 1: Real memory measurement vs. the guessed constant
# ---------------------------------------------------------------------

def test_real_memory_measurement() -> dict:
    print("=" * 76)
    print("TEST 1: Real memory measurement (replacing the guessed constant)")
    print("=" * 76)
    print()
    print("  sketch_lib.RotatingExactCounter.memory_bytes() has used a")
    print("  GUESSED constant (~50 bytes/entry) since this project began.")
    print("  Measuring the REAL memory footprint of the actual Python")
    print("  dict structures used, via sys.getsizeof (recursively, since")
    print("  getsizeof on a dict alone doesn't include its contents).")
    print()

    def real_dict_memory(d: dict) -> int:
        total = sys.getsizeof(d)
        for k, v in d.items():
            total += sys.getsizeof(k) + sys.getsizeof(v)
        return total

    exact = RotatingExactCounter()
    import random
    rng = random.Random(0)
    for i in range(5000):
        key = f"epoch0_churn_{i}"
        exact.increment(key, rng.randint(1, 20))

    guessed_bytes = len(exact.current) * 50
    real_bytes = real_dict_memory(exact.current)
    ratio = real_bytes / guessed_bytes

    print(f"  5,000-entry dict:")
    print(f"    Guessed memory:  {guessed_bytes:>10,} bytes (the constant used everywhere so far)")
    print(f"    REAL memory:     {real_bytes:>10,} bytes (sys.getsizeof, actual)")
    print(f"    Guess was off by: {ratio:.2f}x "
          f"({'UNDERESTIMATE' if ratio > 1 else 'OVERESTIMATE'})")
    print()
    if abs(ratio - 1) > 0.5:
        print("  --> SIGNIFICANT: the guessed constant meaningfully misstates")
        print("      the exact-counter's real memory cost. Every memory-ratio")
        print("      figure in the paper (e.g. '61x') is affected by this and")
        print("      should be corrected using the real measurement.")
        corrected_ratio_scale = ratio
    else:
        print("  --> The guess was reasonably close; existing ratios are not")
        print("      meaningfully distorted by this approximation.")
        corrected_ratio_scale = ratio
    print()
    return {"guessed": guessed_bytes, "real": real_bytes, "ratio": ratio}


# ---------------------------------------------------------------------
# Test 2: Exact (measured) L1 norm vs. the analytical approximation
# ---------------------------------------------------------------------

def test_exact_l1_norm() -> dict:
    print("=" * 76)
    print("TEST 2: Exact L1 norm vs. the analytical approximation")
    print("=" * 76)
    print()
    print("  Every theoretical-bound calculation so far has approximated")
    print("  L1 norm as 'avg 10 wakeups * 5000 identities + 500' rather")
    print("  than measuring the REAL total from actual inserted events.")
    print("  Measuring directly now.")
    print()

    config = SimConfig()
    import random
    rng = random.Random(config.seed)
    total_events_epoch0 = 0
    events = generate_churn_events(
        rng, 0, config.num_churn_identities_per_epoch,
        config.wakeups_per_churn_task, config.distribution,
    )
    total_events_epoch0 = len(events) + config.latency_task_wakeups_per_epoch

    approx_l1_per_epoch = (5000 * 10) + 500
    print(f"  Approximated L1 (per epoch): {approx_l1_per_epoch:,}")
    print(f"  MEASURED L1 (per epoch):     {total_events_epoch0:,}")
    diff_pct = 100 * (total_events_epoch0 - approx_l1_per_epoch) / approx_l1_per_epoch
    print(f"  Difference: {diff_pct:+.1f}%")
    print()
    if abs(diff_pct) > 10:
        print("  --> The approximation meaningfully differs from the real")
        print("      total. Theoretical bound figures in the paper used the")
        print("      approximation and should ideally use this measured")
        print("      value instead for full precision.")
    else:
        print("  --> The approximation is close enough (<10% off) that it")
        print("      does not meaningfully change any reported conclusion.")
    print()
    return {"approx": approx_l1_per_epoch, "measured": total_events_epoch0, "diff_pct": diff_pct}


# ---------------------------------------------------------------------
# Test 3: Extended invariant check across ALL keys, not just one
# ---------------------------------------------------------------------

def test_extended_invariant_check(num_seeds: int = 5) -> bool:
    print("=" * 76)
    print("TEST 3: Extended invariant check — EVERY key, not just the target")
    print("=" * 76)
    print()
    print("  strict_tests.py's Test B only checked the never-underestimate")
    print("  guarantee for ONE key (the latency-sensitive task). This")
    print("  checks it for EVERY distinct churn key inserted, a much")
    print("  stronger claim of correctness.")
    print()

    violations = 0
    total_checks = 0

    for seed in range(num_seeds):
        config = SimConfig(seed=seed, num_churn_identities_per_epoch=500, num_epochs=3)
        import random
        rng = random.Random(config.seed)
        sketch = RotatingCountMinSketch(width=config.sketch_width, depth=config.sketch_depth)
        exact = RotatingExactCounter()

        for epoch in range(config.num_epochs):
            events = generate_churn_events(
                rng, epoch, config.num_churn_identities_per_epoch,
                config.wakeups_per_churn_task, config.distribution,
            )
            events.append("latency_sensitive_task")
            for _ in range(config.latency_task_wakeups_per_epoch - 1):
                events.append("latency_sensitive_task")
            rng.shuffle(events)

            for task_id in events:
                sketch.increment(task_id)
                exact.increment(task_id)

            # Check EVERY distinct key seen this epoch, not just the target.
            all_keys = set(events)
            for key in all_keys:
                sketch_est = sketch.estimate(key)
                exact_est = exact.estimate(key)
                total_checks += 1
                if sketch_est < exact_est:
                    violations += 1
                    print(f"  VIOLATION at seed={seed}, epoch={epoch}, key={key}: "
                          f"sketch={sketch_est} < exact={exact_est}")

            sketch.rotate()
            exact.rotate()

    print(f"  Checked {total_checks} (key, epoch) combinations across "
          f"{num_seeds} seeds and ALL churn identities (not just one key).")
    if violations == 0:
        print("  --> PASS: zero violations across every key checked.")
    else:
        print(f"  --> FAIL: {violations} violations. This is a real")
        print("      correctness bug, broader than previously known.")
    print()
    return violations == 0


# ---------------------------------------------------------------------
# Test 4: Proper statistical significance test
# ---------------------------------------------------------------------

def test_statistical_significance(num_seeds: int = 15) -> dict:
    print("=" * 76)
    print("TEST 4: Proper statistical significance (Welch's t-test)")
    print("=" * 76)
    print()
    print("  The 'severe degradation under adversarial conditions' claim")
    print("  used an arbitrary hand-picked threshold (>30 percentage")
    print("  points = severe), not a real hypothesis test. Running a")
    print("  proper Welch's t-test (unequal variance) instead.")
    print()

    from scipy import stats as scipy_stats

    uniform_errors = []
    adversarial_errors = []
    for seed in range(num_seeds):
        for dist, target_list in [
            (ChurnDistribution.UNIFORM, uniform_errors),
            (ChurnDistribution.ADVERSARIAL_CLUSTERED, adversarial_errors),
        ]:
            config = SimConfig(
                seed=seed, distribution=dist,
                num_churn_identities_per_epoch=1000, num_epochs=10,
            )
            result = run_simulation(config)
            avg_err = statistics.mean(result.steady_state_sketch_errors)
            true_val = config.latency_task_wakeups_per_epoch * 2
            target_list.append(100 * avg_err / true_val)

    t_stat, p_value = scipy_stats.ttest_ind(
        adversarial_errors, uniform_errors, equal_var=False,
    )

    print(f"  Uniform:     mean={statistics.mean(uniform_errors):+.1f}%, "
          f"n={len(uniform_errors)}")
    print(f"  Adversarial: mean={statistics.mean(adversarial_errors):+.1f}%, "
          f"n={len(adversarial_errors)}")
    print(f"  Welch's t-statistic: {t_stat:.2f}")
    print(f"  p-value: {p_value:.2e}")
    print()
    if p_value < 0.001:
        print("  --> Difference is HIGHLY statistically significant")
        print("      (p < 0.001), replacing the earlier hand-picked")
        print("      threshold with a rigorous test. The 'severe")
        print("      degradation' claim is now formally justified.")
    elif p_value < 0.05:
        print("  --> Difference is statistically significant (p < 0.05).")
    else:
        print("  --> NOT statistically significant at conventional")
        print("      thresholds — the earlier claim may not be justified.")
    print()
    return {"t_stat": t_stat, "p_value": p_value}


# ---------------------------------------------------------------------
# Test 5: Edge-case / boundary fuzzing
# ---------------------------------------------------------------------

def test_edge_cases() -> dict:
    print("=" * 76)
    print("TEST 5: Edge-case and boundary fuzzing")
    print("=" * 76)
    print()

    results = {}

    # Case A: width=1 (degenerate — every key collides with every other)
    print("  Case A: width=1 (maximal collision, degenerate case)")
    try:
        sketch = RotatingCountMinSketch(width=1, depth=4)
        exact = RotatingExactCounter()
        for i in range(100):
            sketch.increment(f"key_{i}")
            exact.increment(f"key_{i}")
        est = sketch.estimate("key_0")
        true_val = exact.estimate("key_0")
        print(f"    No crash. estimate={est}, true={true_val}, "
              f"est >= true: {est >= true_val}")
        results["width_1"] = "PASS" if est >= true_val else "FAIL (underestimate!)"
    except Exception as e:
        print(f"    CRASH: {e}")
        results["width_1"] = f"CRASH: {e}"

    # Case B: depth=1 (no redundancy — should still never underestimate)
    print("\n  Case B: depth=1 (no redundancy)")
    try:
        sketch = RotatingCountMinSketch(width=256, depth=1)
        exact = RotatingExactCounter()
        for i in range(1000):
            sketch.increment(f"key_{i}", amount=3)
            exact.increment(f"key_{i}", amount=3)
        est = sketch.estimate("key_500")
        true_val = exact.estimate("key_500")
        print(f"    No crash. estimate={est}, true={true_val}, "
              f"est >= true: {est >= true_val}")
        results["depth_1"] = "PASS" if est >= true_val else "FAIL (underestimate!)"
    except Exception as e:
        print(f"    CRASH: {e}")
        results["depth_1"] = f"CRASH: {e}"

    # Case C: zero churn (empty windows — only the latency task exists)
    print("\n  Case C: zero churn identities (empty background)")
    try:
        config = SimConfig(num_churn_identities_per_epoch=0, num_epochs=3)
        result = run_simulation(config)
        print(f"    No crash. Errors: {result.steady_state_sketch_errors}")
        all_correct = all(e == 0 for e in result.steady_state_sketch_errors)
        print(f"    All errors exactly zero (expected — no collision "
              f"source at all): {all_correct}")
        results["zero_churn"] = "PASS" if all_correct else "UNEXPECTED (nonzero error with no churn)"
    except Exception as e:
        print(f"    CRASH: {e}")
        results["zero_churn"] = f"CRASH: {e}"

    # Case D: extreme churn (10x normal — stress test)
    print("\n  Case D: extreme churn (50,000 identities/epoch, stress test)")
    try:
        config = SimConfig(num_churn_identities_per_epoch=50000, num_epochs=2,
                            wakeups_per_churn_task=(1, 2))
        result = run_simulation(config)
        print(f"    No crash. Errors: {result.steady_state_sketch_errors}")
        results["extreme_churn"] = "PASS (no crash)"
    except Exception as e:
        print(f"    CRASH: {e}")
        results["extreme_churn"] = f"CRASH: {e}"

    print()
    return results


# ---------------------------------------------------------------------
# Test 6: Collision-search verification
# ---------------------------------------------------------------------

def test_collision_search_verification(num_trials: int = 20) -> dict:
    print("=" * 76)
    print("TEST 6: Collision-search verification (no silent under-delivery)")
    print("=" * 76)
    print()
    print("  find_colliding_keys has a bounded search budget and could")
    print("  theoretically return FEWER keys than requested without any")
    print("  test ever asserting the full count was found. Checking this")
    print("  explicitly across many (width, target) combinations.")
    print()

    under_delivered = 0
    for trial in range(num_trials):
        width = [64, 128, 256, 512][trial % 4]
        target_index = trial * 7 % width
        keys = find_colliding_keys(
            seed=trial, target_index=target_index, width=width,
            count_needed=10, prefix=f"verify_trial{trial}",
        )
        if len(keys) < 10:
            under_delivered += 1
            print(f"  UNDER-DELIVERY at trial {trial} (width={width}): "
                  f"only found {len(keys)}/10 requested")

    print(f"  Checked {num_trials} trials across widths [64, 128, 256, 512].")
    if under_delivered == 0:
        print("  --> PASS: every trial found the full requested count. All")
        print("      attack-test results relying on this function were not")
        print("      silently weakened by an incomplete search.")
    else:
        print(f"  --> FAIL: {under_delivered}/{num_trials} trials under-delivered.")
        print("      Any attack test using an under-delivered trial reported")
        print("      a WEAKER attack than intended — investigate immediately.")
    print()
    return {"under_delivered": under_delivered, "total": num_trials}


if __name__ == "__main__":
    r1 = test_real_memory_measurement()
    r2 = test_exact_l1_norm()
    r3 = test_extended_invariant_check()
    r4 = test_statistical_significance()
    r5 = test_edge_cases()
    r6 = test_collision_search_verification()

    print("=" * 76)
    print("SAVAGE AUDIT SUMMARY")
    print("=" * 76)
    print(f"  Real vs guessed memory ratio: {r1['ratio']:.2f}x")
    print(f"  Approx vs measured L1 norm difference: {r2['diff_pct']:+.1f}%")
    print(f"  Extended invariant check: {'PASS' if r3 else 'FAIL'}")
    print(f"  Statistical significance (adversarial vs uniform): "
          f"p={r4['p_value']:.2e}")
    print(f"  Edge cases: {r5}")
    print(f"  Collision search under-delivery: {r6['under_delivered']}/{r6['total']}")
