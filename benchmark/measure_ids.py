"""How many distinct identities does each workload actually contain?

Run with a map large enough that nothing evicts, so the insert counter
measures the workload rather than the tracker.
"""
import os, re, sys, time
sys.path.insert(0, "/tmp")
import round2_mixed_workload as r2
import round3_identity_scale as r3

INS = re.compile(r"distinct_inserts=(\d+)")

class A:
    duration=10; churn_rate=200.0; churn_burn_us=200
    victim_threads=4; victim_rps=100; window_ms=1000

scx = r2._find("scx-target/debug/scx_cms")
for label, lifetime in [("stable  (lifetime 60s)", 60.0),
                        ("churning(lifetime 0.25s)", 0.25)]:
    args_l = ["--tracker","exact","--mechanism","none","--identity-key","pid",
              "--window-ms","1000","--max-tracked","65536","--stats","1"]
    h = r2.SchedulerHandle(scx, args_l)
    with h:
        churn = r3.spawn_scaling_churn(128, A.churn_rate, A.duration+2,
                                       A.churn_burn_us, lifetime)
        time.sleep(1)
        r2.run_schbench_victim(A)
        for p in churn:
            try: os.kill(p,9)
            except ProcessLookupError: pass
        for p in churn:
            try: os.waitpid(p,0)
            except ChildProcessError: pass
    vals=[int(x) for x in INS.findall(open(h.log).read())]
    if len(vals) >= 3:
        span = vals[-1]-vals[1]
        secs = len(vals)-2
        print(f"{label:<26} total={vals[-1]:>7}  rate={span/max(secs,1):>8.1f} ids/s"
              f"  live per 2s window ~= {2*span/max(secs,1):>7.0f}")
    else:
        print(f"{label:<26} insufficient samples: {vals}")
