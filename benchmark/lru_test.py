"""Is BPF's LRU_HASH pathological at small sizes, or just thrashing?

The claim on record is that BPF's per-CPU free lists make a small
LRU_HASH stop behaving like an LRU. The evidence is that at 42 entries
it reports a mean tracked count of 1.6 where a plain hash reports 189.8.

But a CORRECT LRU would also report ~1 in that situation. With ~330 live
identities competing for 42 slots, every insert evicts something about to
be needed again, entries are dropped between their own increments, and
counts never accumulate. That is textbook thrashing, not a bug.

The two explanations are separated by shrinking the identity population
below the map capacity. With few identities and plenty of slots, a
working LRU must hold all of them and counts must accumulate normally.

  counts recover  -> ordinary thrashing; the pathology claim is wrong
  counts stay ~1  -> the map is not doing LRU even when it easily could
"""
import os, re, statistics, sys, time
sys.path.insert(0, "/tmp")
import round2_mixed_workload as r2
import round3_identity_scale as r3

CMP = re.compile(r"compare: samples=(\d+) exact_mean=([\d.]+)")

def measure(scx, entries, slots, plain, duration=10):
    args = ["--tracker","exact","--mechanism","none","--compare",
            "--identity-key","pid","--window-ms","1000",
            "--max-tracked",str(entries),
            "--sketch-width","256","--sketch-depth","4","--stats","2"]
    if plain: args.append("--plain-map")
    class A:
        pass
    a=A(); a.duration=duration; a.churn_rate=200.0; a.churn_burn_us=200
    a.victim_threads=4; a.victim_rps=100; a.window_ms=1000
    h=r2.SchedulerHandle(scx,args)
    with h:
        churn=r3.spawn_scaling_churn(slots,a.churn_rate,duration+2,a.churn_burn_us,60.0)
        time.sleep(duration)
        for p in churn:
            try: os.kill(p,9)
            except ProcessLookupError: pass
        for p in churn:
            try: os.waitpid(p,0)
            except ChildProcessError: pass
    rows=CMP.findall(open(h.log).read())
    return float(rows[-1][1]) if rows else None

scx=r2._find("scx-target/debug/scx_cms")
print("Does a small LRU_HASH work when the working set FITS?\n")
print(f"{'identities':>11}{'slots':>7}{'LRU mean':>10}{'plain mean':>12}   verdict")
print("-"*62)
# ~8 system identities always present; slots is the churn count
for slots, entries in [(8, 128), (8, 42), (20, 128), (20, 42), (100, 42), (300, 42)]:
    lru = measure(scx, entries, slots, plain=False)
    pln = measure(scx, entries, slots, plain=True)
    fits = "fits" if slots + 10 < entries else "OVER capacity"
    print(f"{slots:>11}{entries:>7}{lru:>10.1f}{pln:>12.1f}   {fits}")
