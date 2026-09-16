# Raw measurement summaries

Extracted from `results/raw/`. Every table in the posts and paper is a
transcription of one of these. Where a harness printed per-repetition
lines the full file has them, so summaries can be recomputed rather than
trusted -- the complete originals are at
https://github.com/blackjable/scx-cms-research/tree/main/results/raw

Per-repetition detail is elided here to keep this loadable; headers,
provenance notes and summary tables are kept in full.


==============================================================================
## condition-subset-n20.txt
==============================================================================

[80 per-repetition lines elided -- see the full file]

Condition-subset test: does a pathological condition in the matrix
change the other rows?

The companion to ordering-controlled-n20.txt. Between the two original
matrices that started the ordering claim, three things differed:
condition order, condition subset, and sample size. Ordering was ruled
out by the controlled test. This rules out subset.

Both arms randomised, n=20, seed 77, identical parameters. The only
difference is whether cms_none (p99 ~90ms) is present in the matrix at
all. The "with none" arm is 1b of ordering-controlled-n20.txt.

  condition            with none   without none   ratio   Mann-Whitney p
  cms_exact_penalty       12,080         12,192   0.99x            0.552
  cms_sketch_penalty      12,368*        12,368   0.95x            0.365
  flat_4ms                16,192*        16,336   1.01x            0.797

  (* medians; see the per-repetition lines below and in 1b)

Null. Removing the pathological condition changes nothing. If anything
the arm WITHOUT it was noisier -- CV 0.27 against 0.18 for
cms_exact_penalty.

SO WHAT DID EXPLAIN THE ORIGINAL DISAGREEMENT?

Six independent measurements of cms_exact_penalty p99 now exist, across
both orderings and both subsets:

  run                         order       subset          n   median      max     CV
  r2-count-attributable-n15   fixed       with none      15    12784    21664   0.23
  r2c-prereg-n20              fixed       without none   20    11712    14000   0.08
  r2d-randomised-n20          randomised  with none      20    11744    39488   0.47
  EXP1a                       fixed       with none      20    11808    16016   0.11
  EXP1b                       randomised  with none      20    12080    19424   0.18
  EXP4 (this run)             randomised  without none   20    12192    22048   0.27

The median varies by 1.09x across every configuration tested. The
maximum varies by 2.82x with no relationship to ordering or subset --
and the single largest maximum, 39,488us, comes from a randomised run
with the pathological condition present, which is the configuration the
ordering theory predicted would be cleanest.

The original claim compared two maxima: 21,664 against 14,000, a 1.55x
difference. That sits comfortably inside the 2.82x range the maximum
spans anyway.

The two matrices disagreed because the maximum of a sample is a noisy
statistic and the comparison was between two maxima. Not ordering, not
subset. See REVISIONS.md revision 13.

########## EXP 4 (redo): condition-subset test ##########
# Randomised, n=20, cms_none REMOVED. Compare against arm 1b,
# which is the same thing WITH cms_none present.
2026-09-14T03:38:33+01:00
Phase 6 round 2: mixed workload (audio-callback victim + churn)
victim: 2000us work every 10000us; churn: 128 tasks @ 200.0/s burning 200us each
  churn CPU demand ~= 5.1 CPUs (machine has 4)

penalty_ns = 20287 (supplied)

condition order randomised per repetition, seed=77

==============================================================================
Summary: median of 20 runs, victim wakeup latency
==============================================================================
  cms_exact_penalty    p99   12192us (   n/a)  range  10288- 22048  misses   0.0%  reach=100%
  cms_sketch_penalty   p99   12368us (   n/a)  range  10544- 17696  misses   0.0%  reach=100%
  flat_4ms             p99   16192us (   n/a)  range  14800- 41024  misses   0.0%  reach=100%

HOW TO READ THIS:
  1. POSCTL_low_churn vs eevdf -- if removing most of the antagonist
     does NOT improve the victim, this workload cannot detect
     scheduling quality and every other row below is
     uninterpretable. Check this FIRST.
  2. cms_exact_penalty vs cms_none -- the gating question: does acting
     on a perfect count help at all?
  3. cms_sketch_penalty vs cms_exact_penalty -- the paper's hypothesis,
     meaningful only if (2) showed something.
  Ranges overlapping = no effect demonstrated, regardless of medians.
EXP4 DONE


==============================================================================
## equivalence-n30-prereg.txt
==============================================================================

[210 per-repetition lines elided -- see the full file]

/tmp/run_equiv.sh: line 2: 365190 Killed                     sudo pkill -9 -f scx_ 2> /dev/null
########## EQUIVALENCE: n=30, duration 15s, seed 41 ##########
Round 4 matrix: headline
workload: 128 respawning churn slots, lifetime 60.0s, schbench victim (same as round 3)
n=30, condition order randomised, seed=41

==================================================================================
condition             p50 med       p50 range  p99 med         p99 range  discrim
==================================================================================
none_ref_32k             3908      2092-64448    77696      61376-153856    2.96x
flat_ref_32k            11552     10736-12304    17312       14512-28128    1.00x
exact_32k                3908       3796-4104    10032        9232-18208    2.96x
exact_8k                 3892       2132-4296    64832      58432-128384    2.97x
sketch_32k_d2            3904       3676-5208    10336       9520-240384    2.96x
sketch_8k_d2             3912       2316-5800    12544        8752-30944    2.95x

DISCRIM = flat_ref p50 / this row's p50. It measures how well the
tracker separates the victim from churn, with the count-blind
penalty as the zero point. 1.0x means no discrimination at all;
below 1.0x means worse than not discriminating.

KEY COMPARISON: every sketch row vs exact_ref. If ANY sketch
shape reaches exact's discrimination at this budget, round 3's
refutation must be narrowed to 'this configuration' rather than
stated about sketches generally.
EQUIV DONE

[exited with code 0]


==============================================================================
## excursion-rate-n60.txt
==============================================================================

[420 per-repetition lines elided -- see the full file]

/tmp/run_excursion.sh: line 2: 416647 Killed                     sudo pkill -9 -f scx_ 2> /dev/null
########## EXCURSION RATE: n=60, 10s runs, seed 51 ##########
Round 4 matrix: excursion
workload: 128 respawning churn slots, lifetime 60.0s, schbench victim (same as round 3)
n=60, condition order randomised, seed=51

==================================================================================
condition             p50 med       p50 range  p99 med         p99 range  discrim
==================================================================================
exact_32k                3956       3548-5144    10752        9488-42816     --
sketch_32k_d2            3948       3620-5928    11184        8848-33984     --
sketch_32k_d4            3940       3516-5256    10848        8688-62016     --
sketch_32k_d8            3948       3540-5176    10992        9328-40000     --
sketch_32k_d2_rot        3952       3628-5768    10752        9328-23648     --
sketch_8k_d2             4044      3564-11792    14640        8368-33472     --

DISCRIM = flat_ref p50 / this row's p50. It measures how well the
tracker separates the victim from churn, with the count-blind
penalty as the zero point. 1.0x means no discrimination at all;
below 1.0x means worse than not discriminating.

KEY COMPARISON: every sketch row vs exact_ref. If ANY sketch
shape reaches exact's discrimination at this budget, round 3's
refutation must be narrowed to 'this configuration' rather than
stated about sketches generally.
EXCURSION DONE

[exited with code 0]


==============================================================================
## headline-single-matrix-n20.txt
==============================================================================

[20 per-repetition lines elided -- see the full file]

discrim lookup fixed
ok
/tmp/run_headline.sh: line 2: 330834 Killed                     sudo pkill -9 -f scx_ 2> /dev/null
########## HEADLINE: single matrix, n=20, stable identities ##########
Round 4 matrix: headline
workload: 128 respawning churn slots, lifetime 60.0s, schbench victim (same as round 3)
n=20, condition order randomised, seed=31

==================================================================================
condition             p50 med       p50 range  p99 med         p99 range  discrim
==================================================================================
none_ref_32k             3912      2042-59840    65440      61376-635904    2.82x
flat_ref_32k            11040     10576-12048    16864       15696-17952    1.00x
exact_32k                3892       3524-4184    10144        9520-22816    2.84x
exact_8k                 3908       3596-4092    63680      56640-100736    2.82x
sketch_32k_d2            3892       3532-4076    10064        9360-22496    2.84x
sketch_8k_d2             3924       3572-8104    11344        8720-29088    2.81x

DISCRIM = flat_ref p50 / this row's p50. It measures how well the
tracker separates the victim from churn, with the count-blind
penalty as the zero point. 1.0x means no discrimination at all;
below 1.0x means worse than not discriminating.

KEY COMPARISON: every sketch row vs exact_ref. If ANY sketch
shape reaches exact's discrimination at this budget, round 3's
refutation must be narrowed to 'this configuration' rather than
stated about sketches generally.
HEADLINE DONE

[exited with code 0]


==============================================================================
## identity-turnover-n3.txt
==============================================================================

How many distinct identities does each workload actually contain?

Harness: measure_ids.py. Exact tracker with --max-tracked 65536, large
enough that nothing evicts, so the insert counter measures the WORKLOAD
rather than the tracker. 10s per measurement, --stats 1, identity key
pid. 128 churn slots at 200 wakeups/s, schbench victim 4 threads /
100 rps. Stable = --lifetime 60, churning = --lifetime 0.25.

rate is (last sample - second sample) / intervals, so the ramp-up
sample is excluded. "live per 2s window" is 2x the rate, the span a
query covers under the rotating dual-buffer scheme (current + previous
at a 1000ms window).

### run 1 ###
stable  (lifetime 60s)     total=    304  rate=     1.7 ids/s  live per 2s window ~=       3
churning(lifetime 0.25s)   total=   4616  rate=   377.5 ids/s  live per 2s window ~=     755
### run 2 ###
stable  (lifetime 60s)     total=    307  rate=     2.0 ids/s  live per 2s window ~=       4
churning(lifetime 0.25s)   total=   4430  rate=   384.7 ids/s  live per 2s window ~=     769
### run 3 ###
stable  (lifetime 60s)     total=    335  rate=     4.1 ids/s  live per 2s window ~=       8
churning(lifetime 0.25s)   total=   4646  rate=   380.8 ids/s  live per 2s window ~=     762

Summary across the three runs:

  regime     total identities   new ids/s        live per query span
  stable     304-335 (med 307)  1.7-4.1 (med 2.0)   3-8
  churning   4430-4646          377.5-384.7 (med 380.8)  755-769

PROVENANCE, stated because it matters here. The figures originally
reported from this measurement -- 329 identities stable, 413 ids/s and
826 live churning -- came from a run whose output was never archived.
The harness survived in the guest's /tmp; the output did not. These
three runs are a re-measurement on the same guest with the same harness
and the same parameters.

They agree on everything load-bearing and differ in detail:

  - The churning rate replicates tightly at 377.5-384.7 ids/s across
    three runs. The originally reported 413 sits about 8% above all
    three and outside the observed range. Use 380 ids/s, ~760 live per
    query span.
  - The stable rate is small and noisy: 1.7, 2.0, 4.1. The originally
    reported "about 4" is the top of that range rather than its centre.
    Use ~2 ids/s.
  - The stable identity total, 304-335, brackets the reported 329.

The claim these numbers exist to support is unaffected and is if
anything strengthened: the two regimes differ by roughly two orders of
magnitude in identity turnover (380 / 2.0 = 190x, against the 103x the
original figures implied), and that difference is invisible from the
scheduler's own metrics.


==============================================================================
## lru-working-set-n5.txt
==============================================================================

Does a small LRU_HASH work when the working set FITS?  n=5 runs per cell

Repeat of lru-working-set-test.txt, which was n=1 per cell and is the
sole evidence for REVISIONS.md revision 12. Same harness (lru_test.py),
same parameters, same guest. Run first in a strictly sequential script
with nothing else on the machine.

 identities  slots           LRU median (range)         plain median (range)   verdict
------------------------------------------------------------------------------------------------
          8    128          878.4 (870.0-880.3)          850.7 (846.7-857.6)   fits
          8     42          843.8 (835.2-848.1)          820.3 (803.9-855.5)   fits
         20    128          679.0 (676.3-685.6)          656.2 (653.8-662.0)   fits
         20     42          410.2 (384.7-476.2)          535.4 (531.1-549.6)   fits
        100     42                2.5 (2.3-2.6)          209.8 (205.7-212.1)   OVER capacity
        300     42                1.5 (1.5-1.7)                0.1 (0.0-0.2)   OVER capacity

REVISION 12 IS CONFIRMED, and more strongly than at n=1.

A 42-entry LRU_HASH retains counts normally with 8 or 20 identities
(median 843.8 and 410.2) and collapses only at 100 and 300 (2.5 and
1.5). Separation between the two groups is 164x. Were BPF's per-CPU free
lists responsible, the map would fail at 42 entries regardless of how
many identities competed for it; it does not. The collapse tracks
OVERCOMMITMENT, which is what any LRU does below its working set.

ONE CELL DOES NOT REPLICATE, and it is quoted in the write-ups.

  300 identities / 42 slots, plain HASH:
    original (n=1):  200.4
    this run (n=5):  0.1, with a range of 0.0-0.2

Every other cell agrees within run-to-run spread; the original 200.4 is
the outlier, five consistent runs against one. At 100 identities the
plain hash still reads ~210, so the "locks in early arrivals and lets
those accumulate" behaviour is real -- but it holds at 100 identities
and not at 300. The likely reason is that with 300 competing identities
the 42 keys the map locked in are decreasingly likely to be the ones
currently waking, so the mean over all queries collapses toward zero
even though the tracked keys themselves still carry counts.

That refines rather than reverses the point the plain-hash control was
making. Both map types are useless when overcommitted; the plain hash's
"mean ~200" signature is itself a function of how badly overcommitted it
is, and at 300 identities it looks like the LRU rather than like itself.

The claim that survives without qualification is the one about the LRU
column, which is what revision 12 turns on.

########## EXP 2 (redo): LRU working-set test, 5 repeats ##########
===== lru_test repeat 1/5 =====
2026-09-14T03:27:07+01:00
Does a small LRU_HASH work when the working set FITS?

 identities  slots  LRU mean  plain mean   verdict
--------------------------------------------------------------
          8    128     870.0       846.7   fits
          8     42     836.7       855.5   fits
         20    128     683.0       657.4   fits
         20     42     476.2       549.6   fits
        100     42       2.4       210.9   OVER capacity
        300     42       1.6         0.1   OVER capacity
===== lru_test repeat 2/5 =====
2026-09-14T03:29:23+01:00
Does a small LRU_HASH work when the working set FITS?

 identities  slots  LRU mean  plain mean   verdict
--------------------------------------------------------------
          8    128     880.3       850.7   fits
          8     42     848.1       820.3   fits
         20    128     685.6       656.2   fits
         20     42     407.6       531.1   fits
        100     42       2.6       209.8   OVER capacity
        300     42       1.5         0.0   OVER capacity
===== lru_test repeat 3/5 =====
2026-09-14T03:31:40+01:00
Does a small LRU_HASH work when the working set FITS?

 identities  slots  LRU mean  plain mean   verdict
--------------------------------------------------------------
          8    128     872.1       850.2   fits
          8     42     835.2       812.4   fits
         20    128     679.0       655.6   fits
         20     42     429.9       539.4   fits
        100     42       2.3       207.4   OVER capacity
        300     42       1.5         0.0   OVER capacity
===== lru_test repeat 4/5 =====
2026-09-14T03:33:56+01:00
Does a small LRU_HASH work when the working set FITS?

 identities  slots  LRU mean  plain mean   verdict
--------------------------------------------------------------
          8    128     878.6       851.7   fits
          8     42     843.8       833.1   fits
         20    128     678.5       662.0   fits
         20     42     384.7       534.4   fits
        100     42       2.5       212.1   OVER capacity
        300     42       1.7         0.2   OVER capacity
===== lru_test repeat 5/5 =====
2026-09-14T03:36:12+01:00
Does a small LRU_HASH work when the working set FITS?

 identities  slots  LRU mean  plain mean   verdict
--------------------------------------------------------------
          8    128     878.4       857.6   fits
          8     42     847.0       803.9   fits
         20    128     676.3       653.8   fits
         20     42     410.2       535.4   fits
        100     42       2.5       205.7   OVER capacity
        300     42       1.5         0.1   OVER capacity
EXP2 DONE


==============================================================================
## lru-working-set-test.txt
==============================================================================

Does a small LRU_HASH work when the working set FITS?

 identities  slots  LRU mean  plain mean   verdict
--------------------------------------------------------------
          8    128     880.7       851.9   fits
          8     42     781.2       796.7   fits
         20    128     679.2       664.1   fits
         20     42     456.2       537.3   fits
        100     42       2.5       201.7   OVER capacity
        300     42       2.0       200.4   OVER capacity

Compare mode, exact_mean per query, 10s per measurement, stable
identities, 4-core aarch64 guest. Harness: lru_test.py. Analysed in
REVISIONS.md revision 12.


==============================================================================
## map-memlock-verification.txt
==============================================================================

Which map does the reported "map X KB" column actually describe?

Checked because round3_identity_scale.py selected the exact tracker's
map by substring ("count"), and there are two maps matching it:
cms_counts (LRU_HASH, the one in use) and cms_counts_plain, which
bpftool truncates to cms_counts_plai -- still matching. Dict iteration
order decided which memlock got reported. Both are sized to
--max-tracked, so the entry count was right either way, but LRU_HASH
and HASH have different per-entry overhead, so the BYTES could have
come from the map that was not selected.

The headline memory claim rests on that column, so it is worth settling
rather than assuming.

scx_cms --tracker exact --mechanism none --max-tracked 341
        --sketch-width 256 --sketch-depth 2
Fedora 44, kernel 6.19.10-300.fc44.aarch64, 4 vCPU guest.

  63033: lru_hash  name cms_counts  flags 0x0
          key 8B  value 24B  max_entries 341  memlock 36432B
  63034: hash  name cms_counts_plai  flags 0x0
          key 8B  value 24B  max_entries 341  memlock 36784B
  63035: array  name cms_sketch  flags 0x0
          key 4B  value 4B  max_entries 1024  memlock 8496B

VERDICT: the archived figure is correct and the bug was latent, not
active.

  cms_counts       36,432 B = 35.58 KB -> prints as 35.6 KB  <- matches
  cms_counts_plain 36,784 B = 35.92 KB -> would print 35.9 KB
  cms_sketch        8,496 B =  8.30 KB -> prints as 8.3 KB   <- matches

Every archived run reporting 35.6 KB was therefore reading cms_counts,
the LRU map actually in use. bpftool lists maps by id and cms_counts is
created first, which is why iteration reached it first every time.

The memory ratio the paper and posts quote as "4.3x less memory":

  36432 / 8496 = 4.287x

The two exact maps differ by 352 B, about 1%, so even had the selection
gone the other way the ratio would have been 4.33x and no claim would
have moved. The harness now matches the map name exactly regardless.


==============================================================================
## o1-o4-budget-geometry-churning-n20.txt
==============================================================================

[40 per-repetition lines elided -- see the full file]

/tmp/run_overnight.sh: line 2: 3558836 Killed                     sudo pkill -9 -f scx_ 2> /dev/null
########## O1: complete the budget table, stable, 32KB + 2KB, n=20 ##########
Round 3: identity-count scaling -- the memory question
load held constant at 128 concurrent churn tasks; identity count varied by task lifetime

condition order randomised per repetition, seed=22
budgets matched on measured memlock; check the map column

### budget ~32 KB   exact 341 entries   sketch 2x512x4 ###
  none             p50   3940us  p99   64320us   --    p50 rng  2116-3988  p99 rng  62016-116608 map    35.6KB
  flat             p50  11120us  p99   16672us  1.00x  p50 rng 10768-11600 p99 rng  15856-18528  map    35.6KB
  exact_penalty    p50   3932us  p99   10096us  0.61x  p50 rng  3764-4012  p99 rng   9424-12528  map    35.6KB
  sketch_penalty   p50   3932us  p99    9952us  0.60x  p50 rng  3772-4028  p99 rng   9424-14032  map    32.3KB

### budget ~2 KB   exact 21 entries   sketch 2x32x4 ###
  none             p50   3888us  p99   64448us   --    p50 rng  2164-3988  p99 rng  61888-89984  map     3.1KB
  flat             p50  10960us  p99   16896us  1.00x  p50 rng 10736-11696 p99 rng  15504-20064  map     3.1KB
  exact_penalty    p50   3892us  p99   65024us  3.85x  p50 rng  3820-3964  p99 rng  59712-131328 map     3.1KB
  sketch_penalty   p50   9936us  p99   13248us  0.78x  p50 rng  8944-11152 p99 rng  11696-14800  map     2.3KB

HOW TO READ THIS:
  Compare sketch_penalty against exact_penalty AT EACH LIFETIME,
  both relative to flat. The count-attributable benefit is the
  gap from flat; the sketch's cost is how much of that gap it
  fails to reproduce. Ranges overlapping = no difference shown.
  Then compare the maps column: the sketch's whole claim is that
  its number does not move as identities grow while exact's must.
  If exact's quality holds at every scale AND its memory stays
  affordable, the sketch is solving a problem this machine does
  not have, and that is the finding.

########## O2: geometry sweep at n=20, stable, 8KB ##########
Round 4 matrix: bestshot
workload: 128 respawning churn slots, lifetime 60.0s, schbench victim (same as round 3)
n=20, condition order randomised, seed=1

==================================================================================
condition             p50 med       p50 range  p99 med         p99 range  discrim
==================================================================================
exact_ref                3916       3860-3956    61760      57792-105600    2.78x
flat_ref                10880     10704-11408    16928       15728-18464    1.00x
sketch_d1_w512           3900       3836-3948    12208        8912-27040    2.79x
sketch_d2_w256           3900       3820-7464    10144        8976-25504    2.79x
sketch_d4_w128           4008      3820-11088    18624        9072-29216    2.71x
sketch_d8_w64            9504      4712-11728    15344       12016-19424    1.14x
sketch_d4_rotate         4224      3852-11504    16704       10832-23776    2.58x

DISCRIM = flat_ref p50 / this row's p50. It measures how well the
tracker separates the victim from churn, with the count-blind
penalty as the zero point. 1.0x means no discrimination at all;
below 1.0x means worse than not discriminating.

KEY COMPARISON: every sketch row vs exact_ref. If ANY sketch
shape reaches exact's discrimination at this budget, round 3's
refutation must be narrowed to 'this configuration' rather than
stated about sketches generally.

########## O3: geometry sweep at n=20, stable, 2KB (does d2 still win?) ##########
Round 4 matrix: bestshot
workload: 128 respawning churn slots, lifetime 60.0s, schbench victim (same as round 3)
n=20, condition order randomised, seed=1

==================================================================================
condition             p50 med       p50 range  p99 med         p99 range  discrim
==================================================================================
exact_ref                3908       2140-4824    65920      59584-110720    2.80x
flat_ref                10928     10736-12016    17184       15312-23840    1.00x
sketch_d1_w128           6336      3852-11120    17152       13104-31648    1.72x
sketch_d2_w64            9584      3844-11696    15200       13360-22240    1.14x
sketch_d4_w32            9920      9072-10768    13408       11440-16176    1.10x
sketch_d8_w16           10800     10768-10864    12688       11152-14672    1.01x
sketch_d4_rotate        10080      8944-10768    13136       12208-14896    1.08x

DISCRIM = flat_ref p50 / this row's p50. It measures how well the
tracker separates the victim from churn, with the count-blind
penalty as the zero point. 1.0x means no discrimination at all;
below 1.0x means worse than not discriminating.

KEY COMPARISON: every sketch row vs exact_ref. If ANY sketch
shape reaches exact's discrimination at this budget, round 3's
refutation must be narrowed to 'this configuration' rather than
stated about sketches generally.

########## O4: churning regime confirmation, n=20 ##########
Round 3: identity-count scaling -- the memory question
load held constant at 128 concurrent churn tasks; identity count varied by task lifetime

condition order randomised per repetition, seed=23
budgets matched on measured memlock; check the map column

### budget ~16 KB   exact 170 entries   sketch 2x256x4 ###
  none             p50   3964us  p99  116480us   --    p50 rng  3940-3988  p99 rng 104576-137984 map    18.2KB
  flat             p50  14512us  p99   35584us  1.00x  p50 rng 13488-16112 p99 rng  30688-51520  map    18.2KB
  exact_penalty    p50   3956us  p99   98688us  2.77x  p50 rng  3924-3988  p99 rng  77440-114816 map    18.2KB
  sketch_penalty   p50  18112us  p99   41856us  1.18x  p50 rng 16608-19616 p99 rng  35136-52288  map    16.3KB

### budget ~8 KB   exact 85 entries   sketch 2x128x4 ###
  none             p50   3984us  p99  118912us   --    p50 rng  3748-4136  p99 rng 100480-128128 map     9.6KB
  flat             p50  14704us  p99   35392us  1.00x  p50 rng 13680-16272 p99 rng  31008-45760  map     9.6KB
  exact_penalty    p50   3980us  p99  112768us  3.19x  p50 rng  3860-4060  p99 rng 101760-128896 map     9.6KB
  sketch_penalty   p50  17696us  p99   30784us  0.87x  p50 rng 16240-18464 p99 rng  26784-47552  map     8.3KB

HOW TO READ THIS:
  Compare sketch_penalty against exact_penalty AT EACH LIFETIME,
  both relative to flat. The count-attributable benefit is the
  gap from flat; the sketch's cost is how much of that gap it
  fails to reproduce. Ranges overlapping = no difference shown.
  Then compare the maps column: the sketch's whole claim is that
  its number does not move as identities grow while exact's must.
  If exact's quality holds at every scale AND its memory stays
  affordable, the sketch is solving a problem this machine does
  not have, and that is the finding.
OVERNIGHT DONE


==============================================================================
## ordering-controlled-n20.txt
==============================================================================

[200 per-repetition lines elided -- see the full file]

Controlled ordering experiment: does condition order bias results?

Pre-registered in benchmark/PREREGISTRATION_ordering.md, committed
before this output was read. Analysed by benchmark/analyse_ordering.py.

Two arms, back to back on the same guest, n=20 each. Same four
conditions, same parameters (--penalty-ns 20287, --duration 10, 128
churn slots at 200/s, schbench victim 4t/100rps). The ONLY difference
is whether condition order is shuffled per repetition.

Arm 1a runs the declaration order every repetition, so cms_none
(p99 ~90ms) immediately precedes cms_exact_penalty 20 times out of 20 --
reproducing the confound the ordering claim was built on.
Arm 1b shuffles; cms_none landed immediately before cms_exact_penalty in
6 of 20 repetitions, against ~5 expected by chance.

RESULT: no ordering effect on cms_exact_penalty p99.

  statistic        fixed  randomised    ratio
  median           11808       12080    0.98x
  mean             12219       12619    0.97x
  maximum          16016       19424    0.82x
  CV                0.11        0.18
  >14000us          2/20        3/20
  Mann-Whitney U=194  z=-0.18  two-sided p=0.8604
  P(fixed run > randomised run) = 0.48

Three of the four pre-registered predictions FAILED. The fixed arm is
marginally BETTER and markedly LESS variable than the randomised arm.

Within-arm check, where adjacency was assigned at random and which is
therefore a genuine randomised experiment on the same question:

  cms_exact_penalty p99, randomised arm only
    preceded by cms_none      n= 6  median 11664  mean 11840  max 12976
    NOT preceded by cms_none  n=14  median 12208  mean 12953  max 19424
    ratio of medians 0.96x   Mann-Whitney p=0.458

Both angles agree: being preceded by a ~90ms pathological condition does
not measurably degrade the next condition in this workload.

See results/REVISIONS.md revision 13.

# EXP 1: controlled ordering test -- fixed vs randomised
# Same conditions, same n, same parameters. The ONLY difference
# is whether condition order is shuffled per repetition.
##################################################################
===== 1a: FIXED order (cms_none runs immediately before exact) =====
2026-09-13T20:59:59+01:00
Phase 6 round 2: mixed workload (audio-callback victim + churn)
victim: 2000us work every 10000us; churn: 128 tasks @ 200.0/s burning 200us each
  churn CPU demand ~= 5.1 CPUs (machine has 4)

penalty_ns = 20287 (supplied)

condition order FIXED per repetition (deliberate: carryover control experiment)

==============================================================================
Summary: median of 20 runs, victim wakeup latency
==============================================================================
  cms_none             p99   92928us (   n/a)  range  63424-144128  misses   0.0%  reach=100%
  cms_exact_penalty    p99   11808us (   n/a)  range  10736- 16016  misses   0.0%  reach=100%
  cms_sketch_penalty   p99   13104us (   n/a)  range  10384- 22752  misses   0.0%  reach=100%
  flat_4ms             p99   16800us (   n/a)  range  15120- 20960  misses   0.0%  reach=100%

HOW TO READ THIS:
  1. POSCTL_low_churn vs eevdf -- if removing most of the antagonist
     does NOT improve the victim, this workload cannot detect
     scheduling quality and every other row below is
     uninterpretable. Check this FIRST.
  2. cms_exact_penalty vs cms_none -- the gating question: does acting
     on a perfect count help at all?
  3. cms_sketch_penalty vs cms_exact_penalty -- the paper's hypothesis,
     meaningful only if (2) showed something.
  Ranges overlapping = no effect demonstrated, regardless of medians.
1a DONE
2026-09-13T21:15:44+01:00
===== 1b: RANDOMISED order, seed 77 =====
2026-09-13T21:15:49+01:00
Phase 6 round 2: mixed workload (audio-callback victim + churn)
victim: 2000us work every 10000us; churn: 128 tasks @ 200.0/s burning 200us each
  churn CPU demand ~= 5.1 CPUs (machine has 4)

penalty_ns = 20287 (supplied)

condition order randomised per repetition, seed=77

==============================================================================
Summary: median of 20 runs, victim wakeup latency
==============================================================================
  cms_none             p99   65664us (   n/a)  range  61504-165120  misses   0.0%  reach=100%
  cms_exact_penalty    p99   12080us (   n/a)  range  10128- 19424  misses   0.0%  reach=100%
  cms_sketch_penalty   p99   11760us (   n/a)  range  10544- 25120  misses   0.0%  reach=100%
  flat_4ms             p99   16336us (   n/a)  range  15088- 18656  misses   0.0%  reach=100%

HOW TO READ THIS:
  1. POSCTL_low_churn vs eevdf -- if removing most of the antagonist
     does NOT improve the victim, this workload cannot detect
     scheduling quality and every other row below is
     uninterpretable. Check this FIRST.
  2. cms_exact_penalty vs cms_none -- the gating question: does acting
     on a perfect count help at all?
  3. cms_sketch_penalty vs cms_exact_penalty -- the paper's hypothesis,
     meaningful only if (2) showed something.
  Ranges overlapping = no effect demonstrated, regardless of medians.
1b DONE


==============================================================================
## r2-count-attributable-n15.txt
==============================================================================

[75 per-repetition lines elided -- see the full file]

/tmp/run_final.sh: line 2: 85221 Killed                     sudo pkill -9 -f scx_ 2> /dev/null
Phase 6 round 2: mixed workload (audio-callback victim + churn)
victim: 2000us work every 10000us; churn: 128 tasks @ 200.0/s burning 200us each
  churn CPU demand ~= 5.1 CPUs (machine has 4)

penalty_ns = 20287 (supplied)

==============================================================================
Summary: median of 15 runs, victim wakeup latency
==============================================================================
  cms_none             p99   88192us (   n/a)  range  64064-157952  misses   0.0%  reach=100%
  cms_exact_penalty    p99   12784us (   n/a)  range  10928- 21664  misses   0.0%  reach=100%
  cms_sketch_penalty   p99   12880us (   n/a)  range  10576- 32288  misses   0.0%  reach=100%
  flat_4ms             p99   16544us (   n/a)  range  15344- 29600  misses   0.0%  reach=100%

HOW TO READ THIS:
  1. POSCTL_low_churn vs eevdf -- if removing most of the antagonist
     does NOT improve the victim, this workload cannot detect
     scheduling quality and every other row below is
     uninterpretable. Check this FIRST.
  2. cms_exact_penalty vs cms_none -- the gating question: does acting
     on a perfect count help at all?
  3. cms_sketch_penalty vs cms_exact_penalty -- the paper's hypothesis,
     meaningful only if (2) showed something.
  Ranges overlapping = no effect demonstrated, regardless of medians.

[exited with code 0]


==============================================================================
## r2-gating-n15.txt
==============================================================================

[21 per-repetition lines elided -- see the full file]


==============================================================================
Summary: median of 15 runs, victim wakeup latency
==============================================================================
  eevdf                p99  250624us ( 1.00x)  range 208128-343552  misses   0.0%
  cms_none             p99   82304us ( 0.33x)  range  63808-165632  misses   0.0%  reach=100%
  cms_exact_penalty    p99   12016us ( 0.05x)  range  11152- 19040  misses   0.0%  reach=100%
  cms_sketch_penalty   p99   13456us ( 0.05x)  range  10928- 27168  misses   0.0%  reach=100%

HOW TO READ THIS:
  1. POSCTL_low_churn vs eevdf -- if removing most of the antagonist
     does NOT improve the victim, this workload cannot detect
     scheduling quality and every other row below is
     uninterpretable. Check this FIRST.
  2. cms_exact_penalty vs cms_none -- the gating question: does acting
     on a perfect count help at all?
  3. cms_sketch_penalty vs cms_exact_penalty -- the paper's hypothesis,
     meaningful only if (2) showed something.
  Ranges overlapping = no effect demonstrated, regardless of medians.

[exited with code 0]


==============================================================================
## r2b-flat-control-n8.txt
==============================================================================

/tmp/run_flat.sh: line 2: 78924 Killed                     sudo pkill -9 -f scx_ 2> /dev/null

==============================================================================
Summary: median of 8 runs, victim wakeup latency
==============================================================================
  cms_none             p99   99072us (   n/a)  range  61760-110976  misses   0.0%  reach=100%
  cms_exact_penalty    p99   12384us (   n/a)  range  11568- 15120  misses   0.0%  reach=100%
  flat_2ms             p99   17824us (   n/a)  range  16736- 25952  misses   0.0%  reach=100%
  flat_4ms             p99   17248us (   n/a)  range  15440- 20128  misses   0.0%  reach=100%
  flat_8ms             p99   18880us (   n/a)  range  15472- 26912  misses   0.0%  reach=100%

HOW TO READ THIS:
  1. POSCTL_low_churn vs eevdf -- if removing most of the antagonist
     does NOT improve the victim, this workload cannot detect
     scheduling quality and every other row below is
     uninterpretable. Check this FIRST.
  2. cms_exact_penalty vs cms_none -- the gating question: does acting
     on a perfect count help at all?
  3. cms_sketch_penalty vs cms_exact_penalty -- the paper's hypothesis,
     meaningful only if (2) showed something.
  Ranges overlapping = no effect demonstrated, regardless of medians.

[exited with code 0]


==============================================================================
## r2c-prereg-n20.txt
==============================================================================

[80 per-repetition lines elided -- see the full file]

/tmp/run_2c.sh: line 2: 94852 Killed                     sudo pkill -9 -f scx_ 2> /dev/null
Phase 6 round 2: mixed workload (audio-callback victim + churn)
victim: 2000us work every 10000us; churn: 128 tasks @ 200.0/s burning 200us each
  churn CPU demand ~= 5.1 CPUs (machine has 4)

penalty_ns = 20287 (supplied)

==============================================================================
Summary: median of 20 runs, victim wakeup latency
==============================================================================
  cms_exact_penalty    p99   11712us (   n/a)  range  10352- 14000  misses   0.0%  reach=100%
  cms_sketch_penalty   p99   12912us (   n/a)  range  10032- 24224  misses   0.0%  reach=100%
  flat_4ms             p99   16160us (   n/a)  range  15248- 21920  misses   0.0%  reach=100%

HOW TO READ THIS:
  1. POSCTL_low_churn vs eevdf -- if removing most of the antagonist
     does NOT improve the victim, this workload cannot detect
     scheduling quality and every other row below is
     uninterpretable. Check this FIRST.
  2. cms_exact_penalty vs cms_none -- the gating question: does acting
     on a perfect count help at all?
  3. cms_sketch_penalty vs cms_exact_penalty -- the paper's hypothesis,
     meaningful only if (2) showed something.
  Ranges overlapping = no effect demonstrated, regardless of medians.

[exited with code 0]


==============================================================================
## r2d-randomised-order-n20.txt
==============================================================================

[100 per-repetition lines elided -- see the full file]

/tmp/run_2d.sh: line 2: 105758 Killed                     sudo pkill -9 -f scx_ 2> /dev/null
Phase 6 round 2: mixed workload (audio-callback victim + churn)
victim: 2000us work every 10000us; churn: 128 tasks @ 200.0/s burning 200us each
  churn CPU demand ~= 5.1 CPUs (machine has 4)

penalty_ns = 20287 (supplied)

condition order randomised per repetition, seed=1

==============================================================================
Summary: median of 20 runs, victim wakeup latency
==============================================================================
  cms_none             p99   80640us (   n/a)  range  63680-138496  misses   0.0%  reach=100%
  cms_exact_penalty    p99   11744us (   n/a)  range  10512- 39488  misses   0.0%  reach=100%
  cms_sketch_penalty   p99   12880us (   n/a)  range  10832- 22304  misses   0.0%  reach=100%
  flat_4ms             p99   16576us (   n/a)  range  15248- 17568  misses   0.0%  reach=100%

HOW TO READ THIS:
  1. POSCTL_low_churn vs eevdf -- if removing most of the antagonist
     does NOT improve the victim, this workload cannot detect
     scheduling quality and every other row below is
     uninterpretable. Check this FIRST.
  2. cms_exact_penalty vs cms_none -- the gating question: does acting
     on a perfect count help at all?
  3. cms_sketch_penalty vs cms_exact_penalty -- the paper's hypothesis,
     meaningful only if (2) showed something.
  Ranges overlapping = no effect demonstrated, regardless of medians.

[exited with code 0]


==============================================================================
## r3-memory-sweep-n8.txt
==============================================================================

/tmp/run_r3.sh: line 2: 149088 Killed                     sudo pkill -9 -f scx_ 2> /dev/null
Round 3: identity-count scaling -- the memory question
load held constant at 128 concurrent churn tasks; identity count varied by task lifetime

condition order randomised per repetition, seed=1
budgets matched on measured memlock; check the map column

### budget ~128 KB   exact 1365 entries   sketch 2x2048x4 ###
  flat             p50  14224us  p99   30176us  1.00x  p50 rng 12976-15536 p99 rng  28064-33728  map   139.6KB
  exact_penalty    p50   3820us  p99   65120us  2.16x  p50 rng  3572-3908  p99 rng  54080-73856  map   139.6KB
  sketch_penalty   p50   3832us  p99   67328us  2.23x  p50 rng  3636-4060  p99 rng  56512-86912  map   128.3KB

### budget ~32 KB   exact 341 entries   sketch 2x512x4 ###
  flat             p50  14448us  p99   30464us  1.00x  p50 rng 13744-14896 p99 rng  27808-36544  map    35.6KB
  exact_penalty    p50   3996us  p99   65440us  2.15x  p50 rng  2220-4104  p99 rng  51520-83584  map    35.6KB
  sketch_penalty   p50   4600us  p99   58688us  1.93x  p50 rng  3892-5496  p99 rng  51264-65664  map    32.3KB

### budget ~8 KB   exact 85 entries   sketch 2x128x4 ###
  flat             p50  14208us  p99   33776us  1.00x  p50 rng 13712-15952 p99 rng  29088-38848  map     9.6KB
  exact_penalty    p50   4004us  p99  102784us  3.04x  p50 rng  3836-4084  p99 rng  89216-128896 map     9.6KB
  sketch_penalty   p50  17056us  p99   30560us  0.90x  p50 rng 16144-17824 p99 rng  26464-37184  map     8.3KB

### budget ~2 KB   exact 21 entries   sketch 2x32x4 ###
  flat             p50  14000us  p99   34240us  1.00x  p50 rng 13328-14928 p99 rng  28704-38592  map     3.1KB
  exact_penalty    p50   3892us  p99   96256us  2.81x  p50 rng  3836-3932  p99 rng  86400-119424 map     3.1KB
  sketch_penalty   p50  14448us  p99   20576us  0.60x  p50 rng 14160-14672 p99 rng  19424-22368  map     2.3KB

HOW TO READ THIS:
  Compare sketch_penalty against exact_penalty AT EACH LIFETIME,
  both relative to flat. The count-attributable benefit is the
  gap from flat; the sketch's cost is how much of that gap it
  fails to reproduce. Ranges overlapping = no difference shown.
  Then compare the maps column: the sketch's whole claim is that
  its number does not move as identities grow while exact's must.
  If exact's quality holds at every scale AND its memory stays
  affordable, the sketch is solving a problem this machine does
  not have, and that is the finding.

[exited with code 0]


==============================================================================
## r4-identity-bestshot-n10.txt
==============================================================================

[20 per-repetition lines elided -- see the full file]

/tmp/run_all.sh: line 2: 717563 Killed                     sudo pkill -9 -f scx_ 2> /dev/null
########## MATRIX 1: identity + boost (n=10) ##########
Round 4 matrix: identity
workload: 128 respawning churn slots, lifetime 0.25s, schbench victim (same as round 3)
n=10, condition order randomised, seed=1

==================================================================================
condition             p50 med       p50 range  p99 med         p99 range  discrim
==================================================================================
flat_ref                14336     13040-15632    30752       25056-35776    1.00x
penalty_pid              3980       3732-4044    68608       58176-80256    3.60x
penalty_comm            12416     10960-13232    28032       21728-34624    1.15x
boost_pid                4000       3620-4152   115456      96128-141056    3.58x
boost_comm               4004       3676-4020   100608      94592-108928    3.58x

DISCRIM = flat_ref p50 / this row's p50. It measures how well the
tracker separates the victim from churn, with the count-blind
penalty as the zero point. 1.0x means no discrimination at all;
below 1.0x means worse than not discriminating.

KEY COMPARISON: penalty_comm vs penalty_pid on p99. If comm
recovers the tail, the mechanism's failure in round 3 was
identity turnover, not the mechanism. Also check whether boost
beats penalty at all -- it has never been run before this.

########## MATRIX 2: sketch best-shot at 8KB (n=10) ##########
Round 4 matrix: bestshot
workload: 128 respawning churn slots, lifetime 0.25s, schbench victim (same as round 3)
n=10, condition order randomised, seed=1

==================================================================================
condition             p50 med       p50 range  p99 med         p99 range  discrim
==================================================================================
exact_ref                4012       3988-4136    98432      84096-197376    3.67x
flat_ref                14736     14192-15856    34624       28832-44224    1.00x
sketch_d1_w512           7512      2884-19168    54528       44992-61888    1.96x
sketch_d2_w256          17920     16272-19808    40064       35008-67456    0.82x
sketch_d4_w128          17184     15824-18784    31008       27488-48576    0.86x
sketch_d8_w64           15584     15120-16112    24320       21664-32960    0.95x
sketch_d4_rotate        17184     16544-17952    30304       24992-35648    0.86x

DISCRIM = flat_ref p50 / this row's p50. It measures how well the
tracker separates the victim from churn, with the count-blind
penalty as the zero point. 1.0x means no discrimination at all;
below 1.0x means worse than not discriminating.

KEY COMPARISON: every sketch row vs exact_ref. If ANY sketch
shape reaches exact's discrimination at this budget, round 3's
refutation must be narrowed to 'this configuration' rather than
stated about sketches generally.

########## MATRIX 3: round 3 crossover budgets (n=20) ##########
Round 3: identity-count scaling -- the memory question
load held constant at 128 concurrent churn tasks; identity count varied by task lifetime

condition order randomised per repetition, seed=2
budgets matched on measured memlock; check the map column

### budget ~32 KB   exact 341 entries   sketch 2x512x4 ###
  flat             p50  14768us  p99   31168us  1.00x  p50 rng 13744-15632 p99 rng  26016-65664  map    35.6KB
  exact_penalty    p50   3988us  p99   60864us  1.95x  p50 rng  3972-4084  p99 rng  52544-88192  map    35.6KB
  sketch_penalty   p50   4184us  p99   57536us  1.85x  p50 rng  3932-5256  p99 rng  48832-75648  map    32.3KB

### budget ~8 KB   exact 85 entries   sketch 2x128x4 ###
  flat             p50  14544us  p99   31840us  1.00x  p50 rng 13648-16304 p99 rng  26208-35008  map     9.6KB
  exact_penalty    p50   3992us  p99   98688us  3.10x  p50 rng  3972-4136  p99 rng  82304-111488 map     9.6KB
  sketch_penalty   p50  16864us  p99   27840us  0.87x  p50 rng 16048-17504 p99 rng  25120-36672  map     8.3KB

HOW TO READ THIS:
  Compare sketch_penalty against exact_penalty AT EACH LIFETIME,
  both relative to flat. The count-attributable benefit is the
  gap from flat; the sketch's cost is how much of that gap it
  fails to reproduce. Ranges overlapping = no difference shown.
  Then compare the maps column: the sketch's whole claim is that
  its number does not move as identities grow while exact's must.
  If exact's quality holds at every scale AND its memory stays
  affordable, the sketch is solving a problem this machine does
  not have, and that is the finding.
ALL DONE

[exited with code 0]


==============================================================================
## r5-inflation-and-stable-sweep.txt
==============================================================================

/tmp/run_r5.sh: line 2: 2062613 Killed                     sudo pkill -9 -f scx_ 2> /dev/null
########## A: inflation vs budget, both regimes (n=3) ##########
Round 5: measured sketch inflation, both identity regimes
compare mode runs BOTH trackers over the same wakeup stream,
so exact_mean and sketch_mean describe identical queries.

### regime: stable  (~128 identities) ###
    budget   cells     exact    sketch  inflation  max_over  underest
     128KB   16384     366.7     366.7      1.00x         0      1195
      64KB    8192     363.1     363.5      1.00x         0       153
      32KB    4096     365.9     366.9      1.00x         0       154
      16KB    2048     299.3     366.6      1.25x         0      2726
       8KB    1024     193.7     434.9      2.42x         0         0
       4KB     512       1.5     613.7    399.13x         0         0
       2KB     256       1.0    1042.6   1042.60x         0         0

### regime: churning(~5000 identities) ###
    budget   cells     exact    sketch  inflation  max_over  underest
     128KB   16384     220.2     220.4      1.00x         0      1583
      64KB    8192     220.8     222.4      1.01x         0         0
      32KB    4096     219.8     230.8      1.04x         0         0
      16KB    2048      79.2     271.9      3.39x         0         0
       8KB    1024      90.1     352.3      3.89x         0         0
       4KB     512       2.5     532.9    212.68x         0         0
       2KB     256       1.7     881.3    518.41x         0         0

HOW TO READ THIS:
  inflation 1.0x = the sketch agrees with exact counting.
  If inflation is near 1.0 in the stable regime at a budget where
  round 3 saw the sketch collapse, then identity count -- not the
  byte budget -- is the variable that breaks it, and the paper's
  'loses at every budget' framing is wrong as stated.
  underest MUST be 0: a non-zero value means the never-undercount
  guarantee was violated on real kernel data, which would be a
  correctness bug, not an accuracy result.

########## B: scheduling outcome, STABLE identities (n=8) ##########
Round 3: identity-count scaling -- the memory question
load held constant at 128 concurrent churn tasks; identity count varied by task lifetime

condition order randomised per repetition, seed=3
budgets matched on measured memlock; check the map column

### budget ~128 KB   exact 1365 entries   sketch 2x2048x4 ###
  flat             p50  11344us  p99   16896us  1.00x  p50 rng 10832-11792 p99 rng  15728-17568  map   139.6KB
  exact_penalty    p50   3912us  p99   11216us  0.66x  p50 rng  3884-4020  p99 rng   9744-22816  map   139.6KB
  sketch_penalty   p50   3904us  p99   10992us  0.65x  p50 rng  3876-4004  p99 rng  10096-15056  map   128.3KB

### budget ~32 KB   exact 341 entries   sketch 2x512x4 ###
  flat             p50  11344us  p99   17856us  1.00x  p50 rng 10832-12400 p99 rng  16800-24672  map    35.6KB
  exact_penalty    p50   3916us  p99   11184us  0.63x  p50 rng  3884-4036  p99 rng   9712-21728  map    35.6KB
  sketch_penalty   p50   3916us  p99   10224us  0.57x  p50 rng  3876-5256  p99 rng   9392-13264  map    32.3KB

### budget ~16 KB   exact 170 entries   sketch 2x256x4 ###
  flat             p50  11760us  p99   17088us  1.00x  p50 rng 11344-12336 p99 rng  15856-29984  map    18.2KB
  exact_penalty    p50   4392us  p99   40640us  2.38x  p50 rng  3980-6392  p99 rng  16144-58304  map    18.2KB
  sketch_penalty   p50   3948us  p99   11616us  0.68x  p50 rng  3916-4360  p99 rng   9328-21472  map    16.3KB

### budget ~8 KB   exact 85 entries   sketch 2x128x4 ###
  flat             p50  11552us  p99   17248us  1.00x  p50 rng 10992-12112 p99 rng  15216-25120  map     9.6KB
  exact_penalty    p50   3964us  p99   63616us  3.69x  p50 rng  2148-4052  p99 rng  60864-106368 map     9.6KB
  sketch_penalty   p50   7812us  p99   17248us  1.00x  p50 rng  4020-11632 p99 rng  13008-30688  map     8.3KB

HOW TO READ THIS:
  Compare sketch_penalty against exact_penalty AT EACH LIFETIME,
  both relative to flat. The count-attributable benefit is the
  gap from flat; the sketch's cost is how much of that gap it
  fails to reproduce. Ranges overlapping = no difference shown.
  Then compare the maps column: the sketch's whole claim is that
  its number does not move as identities grow while exact's must.
  If exact's quality holds at every scale AND its memory stays
  affordable, the sketch is solving a problem this machine does
  not have, and that is the finding.
ALL DONE

[exited with code 0]


==============================================================================
## r5b-verify-reversal-inertness.txt
==============================================================================

/tmp/run_verify.sh: line 2: 2184926 Killed                     sudo pkill -9 -f scx_ 2> /dev/null
########## VERIFY 1: stable identities, reversal rows, n=15 seed 4 ##########
Round 3: identity-count scaling -- the memory question
load held constant at 128 concurrent churn tasks; identity count varied by task lifetime

condition order randomised per repetition, seed=4
budgets matched on measured memlock; check the map column

### budget ~16 KB   exact 170 entries   sketch 2x256x4 ###
  none             p50   3900us  p99   63808us   --    p50 rng  3540-4012  p99 rng  62016-93568  map    18.2KB
  flat             p50  11152us  p99   17312us  1.00x  p50 rng 10480-12080 p99 rng  15184-23328  map    18.2KB
  exact_penalty    p50   4456us  p99   25184us  1.45x  p50 rng  3924-6248  p99 rng  17056-47040  map    18.2KB
  sketch_penalty   p50   3940us  p99   10992us  0.63x  p50 rng  3716-5608  p99 rng   9648-47168  map    16.3KB

### budget ~8 KB   exact 85 entries   sketch 2x128x4 ###
  none             p50   3948us  p99   78976us   --    p50 rng  2148-57152 p99 rng  62400-738304 map     9.6KB
  flat             p50  11376us  p99   17312us  1.00x  p50 rng 10992-12336 p99 rng  15088-32672  map     9.6KB
  exact_penalty    p50   3948us  p99   71808us  4.15x  p50 rng  3924-54336 p99 rng  58432-160512 map     9.6KB
  sketch_penalty   p50   5320us  p99   14064us  0.81x  p50 rng  3500-11984 p99 rng  10608-29856  map     8.3KB

HOW TO READ THIS:
  Compare sketch_penalty against exact_penalty AT EACH LIFETIME,
  both relative to flat. The count-attributable benefit is the
  gap from flat; the sketch's cost is how much of that gap it
  fails to reproduce. Ranges overlapping = no difference shown.
  Then compare the maps column: the sketch's whole claim is that
  its number does not move as identities grow while exact's must.
  If exact's quality holds at every scale AND its memory stays
  affordable, the sketch is solving a problem this machine does
  not have, and that is the finding.

########## VERIFY 2: churning identities, inertness check, n=8 seed 5 ##########
Round 3: identity-count scaling -- the memory question
load held constant at 128 concurrent churn tasks; identity count varied by task lifetime

condition order randomised per repetition, seed=5
budgets matched on measured memlock; check the map column

### budget ~8 KB   exact 85 entries   sketch 2x128x4 ###
  none             p50   3940us  p99  113024us   --    p50 rng  3916-5784  p99 rng 106880-159488 map     9.6KB
  flat             p50  15632us  p99   35904us  1.00x  p50 rng 14640-17056 p99 rng  30816-99456  map     9.6KB
  exact_penalty    p50   3936us  p99  100096us  2.79x  p50 rng  3924-4044  p99 rng  84864-108416 map     9.6KB
  sketch_penalty   p50  17088us  p99   42176us  1.17x  p50 rng 16240-17760 p99 rng  28000-50752  map     8.3KB

### budget ~2 KB   exact 21 entries   sketch 2x32x4 ###
  none             p50   3960us  p99  112896us   --    p50 rng  3940-4052  p99 rng 102272-144128 map     3.1KB
  flat             p50  14560us  p99   32064us  1.00x  p50 rng 13968-15408 p99 rng  30240-65216  map     3.1KB
  exact_penalty    p50   3960us  p99  106496us  3.32x  p50 rng  3948-4076  p99 rng  92032-124544 map     3.1KB
  sketch_penalty   p50  14864us  p99   23840us  0.74x  p50 rng 14448-15920 p99 rng  20576-31648  map     2.3KB

HOW TO READ THIS:
  Compare sketch_penalty against exact_penalty AT EACH LIFETIME,
  both relative to flat. The count-attributable benefit is the
  gap from flat; the sketch's cost is how much of that gap it
  fails to reproduce. Ranges overlapping = no difference shown.
  Then compare the maps column: the sketch's whole claim is that
  its number does not move as identities grow while exact's must.
  If exact's quality holds at every scale AND its memory stays
  affordable, the sketch is solving a problem this machine does
  not have, and that is the finding.
ALL DONE

[exited with code 0]


==============================================================================
## r6-sketch-variants-n3.txt
==============================================================================

/tmp/run_r6.sh: line 2: 2569187 Killed                     sudo pkill -9 -f scx_ 2> /dev/null
Round 6: sketch fixes and the map-type control
compare mode; exact and sketch figures describe identical queries

########## regime: stable ##########

### 32 KB -- exact 341 entries, sketch 2x512x4 ###
  variant           exact   sketch   sk/ex  under   count distribution
  baseline          361.2    361.5   1.00x    461   z0/3520/24083/174980/27006/0
  hash_mix          362.9    365.7   1.01x    448   z0/2884/20632/178464/28139/0
  conservative      362.2    362.5   1.00x    153   z0/2292/12995/182717/28140/0
  both              361.7    362.0   1.00x    890   z0/3024/14062/183584/27474/0
  plain_map         300.8    369.5   1.23x    153   z86563/2137/13446/100718/27744/0

### 16 KB -- exact 170 entries, sketch 2x256x4 ###
  variant           exact   sketch   sk/ex  under   count distribution
  baseline          310.2    372.5   1.21x    116   z0/15921/35603/155727/23273/0
  hash_mix          311.3    376.8   1.19x    154   z0/21085/32804/153813/24049/0
  conservative      340.2    362.4   1.07x   1749   z0/18636/28617/156720/27609/0
  both              341.2    366.4   1.08x    197   z0/12714/37807/154692/24665/0
  plain_map         199.7    372.5   1.82x      0   z176512/1528/10615/15347/27549/0

### 8 KB -- exact 85 entries, sketch 2x128x4 ###
  variant           exact   sketch   sk/ex  under   count distribution
  baseline          184.2    430.1   2.35x      0   z0/195248/1125/7734/26748/0
  hash_mix          189.9    439.8   2.32x      0   z0/195259/799/7401/27295/0
  conservative      178.6    440.9   2.52x      0   z0/196067/649/7549/27017/0
  both              186.1    363.7   1.95x    882   z0/195731/922/7506/27121/0
  plain_map         192.4    420.6   2.19x      0   z188822/778/6159/7116/27976/0

### 4 KB -- exact 42 entries, sketch 2x64x4 ###
  variant           exact   sketch   sk/ex  under   count distribution
  baseline            1.6    621.3 388.31x      0   z7/225216/3228/0/0/0
  hash_mix            1.8    588.6 321.28x      0   z6/223857/2636/363/0/0
  conservative        1.4    584.6 416.79x      0   z12/229499/1062/0/0/0
  both                1.4    370.4 263.36x      0   z10/228196/1615/0/0/0
  plain_map         189.8    607.3   3.39x      0   z189072/373/2389/8935/27462/0

### 2 KB -- exact 21 entries, sketch 2x32x4 ###
  variant           exact   sketch   sk/ex  under   count distribution
  baseline            1.0   1031.51031.50x      0   z0/229241/358/0/0/0
  hash_mix            1.0    929.2 928.30x      0   z1/229908/280/0/0/0
  conservative        1.0    894.2 894.20x      0   z0/226452/243/0/0/0
  both                1.1    536.7 487.91x      0   z0/225188/375/0/0/0
  plain_map           0.2   1055.45064.50x      0   z190973/218/1226/7373/27689/0
########## regime: churning ##########

### 32 KB -- exact 341 entries, sketch 2x512x4 ###
  variant           exact   sketch   sk/ex  under   count distribution
  baseline          224.0    233.0   1.04x      0   z0/43281/101606/12113/22209/0
  hash_mix          220.7    230.9   1.05x      0   z0/41184/106645/11473/22407/0
  conservative      221.5    227.7   1.02x      0   z0/40846/104252/11571/21973/0
  both              223.0    228.2   1.02x      0   z0/42566/98948/12207/21979/0
  plain_map         210.0    232.8   1.11x      0   z130800/6078/7012/11890/22772/0

### 16 KB -- exact 170 entries, sketch 2x256x4 ###
  variant           exact   sketch   sk/ex  under   count distribution
  baseline           97.4    272.0   2.79x      0   z0/80661/74068/26386/1259/0
  hash_mix          104.7    257.3   2.46x      0   z0/73763/79597/21595/7516/0
  conservative      103.3    257.7   2.40x      0   z0/78973/66646/26134/293/0
  both              106.7    242.0   2.27x      0   z0/68720/85595/19702/9081/0
  plain_map         207.1    269.4   1.29x      0   z139522/4066/1621/11758/22103/0

### 8 KB -- exact 85 entries, sketch 2x128x4 ###
  variant           exact   sketch   sk/ex  under   count distribution
  baseline           80.8    347.8   4.30x      0   z0/136206/7760/22941/2523/0
  hash_mix           76.9    319.0   4.10x      0   z3/144876/7750/22610/2754/0
  conservative       89.0    306.2   3.59x      0   z3/142997/6798/24242/2054/0
  both               95.6    264.3   2.78x      0   z0/147076/6997/21367/4496/0
  plain_map         205.6    343.0   1.68x      0   z137889/1932/1204/12127/21356/0

### 4 KB -- exact 42 entries, sketch 2x64x4 ###
  variant           exact   sketch   sk/ex  under   count distribution
  baseline            3.1    506.4 168.90x      0   z4/173135/7621/692/0/0
  hash_mix            3.1    449.7 145.74x      0   z5/169110/9150/550/0/0
  conservative        3.1    417.9 134.81x      0   z5/166721/8103/445/0/0
  both                3.0    312.2 103.07x      0   z4/167720/8850/462/0/0
  plain_map         213.9    515.6   2.42x      0   z142478/808/1166/11494/22447/0

### 2 KB -- exact 21 entries, sketch 2x32x4 ###
  variant           exact   sketch   sk/ex  under   count distribution
  baseline            1.8    852.3 473.61x      0   z2/176567/2391/428/0/0
  hash_mix            1.9    722.7 389.58x      0   z4/167728/2501/434/0/0
  conservative        1.7    708.8 416.94x      0   z1/180698/2067/401/0/0
  both                1.7    437.3 254.47x      0   z0/181585/1653/442/0/0
  plain_map         208.0    820.9   3.91x      0   z137839/300/910/12187/21643/0

HOW TO READ THIS:
  conservative vs baseline: does conservative update reduce the
    sketch's overestimate? If yes, the negative result applies
    only to the standard construction.
  hash_mix vs baseline: is the power-of-two modulo costing
    accuracy on real data, as simulation predicted (<=13%)?
  plain_map vs baseline (exact column): if exact stops
    collapsing without an LRU, the collapse was the LRU
    implementation rather than capacity.
  under MUST be 0. Conservative update preserves
    never-undercount only if its read-min-write is atomic;
    a non-zero value means the spin lock is not doing its job.
  distribution buckets: zero/1-9/10-99/100-999/1k-10k/10k+ of
    the EXACT count seen per query.
R6 DONE

[exited with code 0]


==============================================================================
## r7-r9-throughput-mapcontrol-geometry.txt
==============================================================================

[15 per-repetition lines elided -- see the full file]

/tmp/run_r7plus.sh: line 2: 2907821 Killed                     sudo pkill -9 -f scx_ 2> /dev/null
########## R7: throughput + cyclictest across tiers ##########
Round 7: throughput and RT-wakeup checks across the tiers
hackbench: yes   cyclictest: yes
hackbench -g 10 -l 1000, n=5

========================================================================
condition           hackbench s  vs eevdf  ct avg us  ct max us
========================================================================
eevdf                      1.05     1.00x        124       3315
cms_none                   0.95     0.91x        134       3845
flat                       1.00     0.95x        117       3582
exact_penalty              0.97     0.92x        113       4755
sketch_penalty             0.95     0.90x        119       1629

HOW TO READ THIS:
  hackbench is a THROUGHPUT measure: lower is better, and a
  penalty tier above 1.0x vs eevdf is buying its latency wins
  with throughput. That belongs beside the latency results, not
  in a footnote.
  cyclictest absolute values are floored by this VM's timer
  delivery (~1.7ms, Section 4.2); read the columns for relative
  differences between schedulers only.

########## R8a: scheduling outcome, LRU map, STABLE ##########
Round 3: identity-count scaling -- the memory question
load held constant at 128 concurrent churn tasks; identity count varied by task lifetime

condition order randomised per repetition, seed=11
budgets matched on measured memlock; check the map column

### budget ~32 KB   exact 341 entries   sketch 2x512x4 ###
  none             p50   3928us  p99   77952us   --    p50 rng  3540-4232  p99 rng  63552-166144 map    35.6KB
  flat             p50  11760us  p99   16584us  1.00x  p50 rng 10608-12624 p99 rng  14736-17888  map    35.6KB
  exact_penalty    p50   3932us  p99   10272us  0.62x  p50 rng  3692-3964  p99 rng   9008-20256  map    35.6KB
  sketch_penalty   p50   3960us  p99   13200us  0.80x  p50 rng  3836-3988  p99 rng  10096-18208  map    32.3KB

### budget ~16 KB   exact 170 entries   sketch 2x256x4 ###
  none             p50   3916us  p99   77824us   --    p50 rng  2140-3948  p99 rng  61504-139008 map    18.2KB
  flat             p50  11712us  p99   16680us  1.00x  p50 rng 10992-12368 p99 rng  14320-18528  map    18.2KB
  exact_penalty    p50   5032us  p99   42240us  2.53x  p50 rng  3940-6152  p99 rng  30496-49728  map    18.2KB
  sketch_penalty   p50   3908us  p99    9888us  0.59x  p50 rng  3892-3972  p99 rng   9328-15408  map    16.3KB

### budget ~8 KB   exact 85 entries   sketch 2x128x4 ###
  none             p50   3940us  p99   71552us   --    p50 rng  3196-4004  p99 rng  65664-91264  map     9.6KB
  flat             p50  11728us  p99   17504us  1.00x  p50 rng 10992-12176 p99 rng  16016-18656  map     9.6KB
  exact_penalty    p50   3936us  p99   68608us  3.92x  p50 rng  3924-3996  p99 rng  58048-86656  map     9.6KB
  sketch_penalty   p50   4328us  p99   12192us  0.70x  p50 rng  3916-11024 p99 rng   7640-17376  map     8.3KB

### budget ~2 KB   exact 21 entries   sketch 2x32x4 ###
  none             p50   3912us  p99   72704us   --    p50 rng  3900-3956  p99 rng  63296-79744  map     3.1KB
  flat             p50  11408us  p99   18080us  1.00x  p50 rng 11152-11728 p99 rng  17120-18848  map     3.1KB
  exact_penalty    p50   3912us  p99   67456us  3.73x  p50 rng  3900-3964  p99 rng  61760-146176 map     3.1KB
  sketch_penalty   p50  10064us  p99   13184us  0.73x  p50 rng  9776-10992 p99 rng  12080-15792  map     2.3KB

HOW TO READ THIS:
  Compare sketch_penalty against exact_penalty AT EACH LIFETIME,
  both relative to flat. The count-attributable benefit is the
  gap from flat; the sketch's cost is how much of that gap it
  fails to reproduce. Ranges overlapping = no difference shown.
  Then compare the maps column: the sketch's whole claim is that
  its number does not move as identities grow while exact's must.
  If exact's quality holds at every scale AND its memory stays
  affordable, the sketch is solving a problem this machine does
  not have, and that is the finding.

########## R8b: scheduling outcome, PLAIN map, STABLE ##########
Round 3: identity-count scaling -- the memory question
load held constant at 128 concurrent churn tasks; identity count varied by task lifetime

condition order randomised per repetition, seed=11
budgets matched on measured memlock; check the map column

### budget ~32 KB   exact 341 entries   sketch 2x512x4 ###
  none             p50   3912us  p99   68736us   --    p50 rng  3900-3964  p99 rng  64960-165632 map    35.6KB
  flat             p50  11424us  p99   17728us  1.00x  p50 rng 10960-11984 p99 rng  16544-33600  map    35.6KB
  exact_penalty    p50   3920us  p99   10048us  0.57x  p50 rng  3908-4076  p99 rng   9680-13456  map    35.6KB
  sketch_penalty   p50   3924us  p99    9728us  0.55x  p50 rng  3900-4092  p99 rng   9200-19104  map    32.3KB

### budget ~16 KB   exact 170 entries   sketch 2x256x4 ###
  none             p50   3940us  p99   76672us   --    p50 rng  3908-3948  p99 rng  63040-112768 map    18.2KB
  flat             p50  11520us  p99   17472us  1.00x  p50 rng 10928-12048 p99 rng  16736-19680  map    18.2KB
  exact_penalty    p50   6824us  p99   18112us  1.04x  p50 rng  6712-11312 p99 rng  15728-43584  map    18.2KB
  sketch_penalty   p50   3928us  p99   11024us  0.63x  p50 rng  3916-4084  p99 rng   9456-18976  map    16.3KB

### budget ~8 KB   exact 85 entries   sketch 2x128x4 ###
  none             p50   3940us  p99   75904us   --    p50 rng  3900-3964  p99 rng  61632-97408  map     9.6KB
  flat             p50  11520us  p99   17824us  1.00x  p50 rng 10928-12144 p99 rng  16080-21216  map     9.6KB
  exact_penalty    p50   3924us  p99   66400us  3.73x  p50 rng  2140-32288 p99 rng  58048-150784 map     9.6KB
  sketch_penalty   p50   4704us  p99   14592us  0.82x  p50 rng  3876-11056 p99 rng   8152-28000  map     8.3KB

### budget ~2 KB   exact 21 entries   sketch 2x32x4 ###
  none             p50   3936us  p99   74368us   --    p50 rng  3916-3956  p99 rng  64320-85632  map     3.1KB
  flat             p50  11808us  p99   16648us  1.00x  p50 rng 11312-12240 p99 rng  15088-21472  map     3.1KB
  exact_penalty    p50   3928us  p99   72960us  4.38x  p50 rng  3892-3948  p99 rng  63552-136448 map     3.1KB
  sketch_penalty   p50   9936us  p99   13056us  0.78x  p50 rng  8976-11056 p99 rng  12176-14352  map     2.3KB

HOW TO READ THIS:
  Compare sketch_penalty against exact_penalty AT EACH LIFETIME,
  both relative to flat. The count-attributable benefit is the
  gap from flat; the sketch's cost is how much of that gap it
  fails to reproduce. Ranges overlapping = no difference shown.
  Then compare the maps column: the sketch's whole claim is that
  its number does not move as identities grow while exact's must.
  If exact's quality holds at every scale AND its memory stays
  affordable, the sketch is solving a problem this machine does
  not have, and that is the finding.

########## R8c: scheduling outcome, PLAIN map, CHURNING ##########
Round 3: identity-count scaling -- the memory question
load held constant at 128 concurrent churn tasks; identity count varied by task lifetime

condition order randomised per repetition, seed=12
budgets matched on measured memlock; check the map column

### budget ~32 KB   exact 341 entries   sketch 2x512x4 ###
  none             p50   3944us  p99  111872us   --    p50 rng  3916-3996  p99 rng 100480-132864 map    35.6KB
  flat             p50  14304us  p99   34880us  1.00x  p50 rng 13584-15760 p99 rng  30496-45376  map    35.6KB
  exact_penalty    p50   3940us  p99  110976us  3.18x  p50 rng  3916-3980  p99 rng  98176-116864 map    35.6KB
  sketch_penalty   p50   4200us  p99   63680us  1.83x  p50 rng  3980-5048  p99 rng  56768-86912  map    32.3KB

### budget ~8 KB   exact 85 entries   sketch 2x128x4 ###
  none             p50   3980us  p99  130880us   --    p50 rng  2268-4152  p99 rng  99968-160512 map     9.6KB
  flat             p50  14608us  p99   38016us  1.00x  p50 rng 13904-15408 p99 rng  34240-48832  map     9.6KB
  exact_penalty    p50   4000us  p99  124032us  3.26x  p50 rng  3980-4104  p99 rng 112000-136448 map     9.6KB
  sketch_penalty   p50  17568us  p99   35456us  0.93x  p50 rng 16864-18592 p99 rng  30880-75392  map     8.3KB

### budget ~2 KB   exact 21 entries   sketch 2x32x4 ###
  none             p50   4008us  p99  118144us   --    p50 rng  3972-4092  p99 rng 108160-125312 map     3.1KB
  flat             p50  14864us  p99   34864us  1.00x  p50 rng 13456-15696 p99 rng  30752-40768  map     3.1KB
  exact_penalty    p50   4000us  p99  122496us  3.51x  p50 rng  2212-4168  p99 rng 115840-136448 map     3.1KB
  sketch_penalty   p50  15520us  p99   25248us  0.72x  p50 rng 15376-16208 p99 rng  21088-30816  map     2.3KB

HOW TO READ THIS:
  Compare sketch_penalty against exact_penalty AT EACH LIFETIME,
  both relative to flat. The count-attributable benefit is the
  gap from flat; the sketch's cost is how much of that gap it
  fails to reproduce. Ranges overlapping = no difference shown.
  Then compare the maps column: the sketch's whole claim is that
  its number does not move as identities grow while exact's must.
  If exact's quality holds at every scale AND its memory stays
  affordable, the sketch is solving a problem this machine does
  not have, and that is the finding.

########## R9: sketch geometry sweep, STABLE regime ##########
Round 4 matrix: bestshot
workload: 128 respawning churn slots, lifetime 60.0s, schbench victim (same as round 3)
n=10, condition order randomised, seed=1

==================================================================================
condition             p50 med       p50 range  p99 med         p99 range  discrim
==================================================================================
exact_ref                3904       3876-4012    63232       61504-88448    2.95x
flat_ref                11504     11056-12432    17344       16144-23968    1.00x
sketch_d1_w512           3936       3812-6696    20448        9072-34240    2.92x
sketch_d2_w256           3932       3876-7832    11456        8656-22688    2.93x
sketch_d4_w128           4432       4036-7608    19968       10032-26592    2.60x
sketch_d8_w64            9680      8304-10192    16928       12976-22816    1.19x
sketch_d4_rotate         4054      3836-11216    15248        9392-32544    2.84x

DISCRIM = flat_ref p50 / this row's p50. It measures how well the
tracker separates the victim from churn, with the count-blind
penalty as the zero point. 1.0x means no discrimination at all;
below 1.0x means worse than not discriminating.

KEY COMPARISON: every sketch row vs exact_ref. If ANY sketch
shape reaches exact's discrimination at this budget, round 3's
refutation must be narrowed to 'this configuration' rather than
stated about sketches generally.
ALL DONE


==============================================================================
## refactor-verification-n20.txt
==============================================================================

[140 per-repetition lines elided -- see the full file]

Verification: the headline matrix re-run on the refactored binary

Same parameters, same seed (31), same guest as
headline-single-matrix-n20.txt -- which was produced BEFORE the tracker
axis became a registered list. If generalising the dispatch from a
hand-written if/else changed behaviour, it shows here.

  condition           p50 old  p50 new   ratio  p99 old  p99 new   ratio
  none_ref_32k           3912     3936   1.01x    65440    77952   1.19x
  flat_ref_32k          11040    11376   1.03x    16864    17568   1.04x
  exact_32k              3892     3908   1.00x    10144    10064   0.99x
  exact_8k               3908     3916   1.00x    63680    64320   1.01x
  sketch_32k_d2          3892     3944   1.01x    10064    10576   1.05x
  sketch_8k_d2           3924     4016   1.02x    11344    12016   1.06x

NOTHING MOVED BEYOND RUN-TO-RUN NOISE.

Every p50 median is within 3%. Every p99 median is within 6% except
none_ref_32k at 1.19x, which is the noisiest condition in the matrix by a
wide margin -- its archived p99 range is 61,376-635,904us, so a 19% move
in its median sits well inside its own spread.

For calibration: ordering-controlled-n20.txt and condition-subset-n20.txt
give six independent measurements of one condition under deliberately
varied setups, and its median spans 1.09x across all of them. The
largest same-condition move here, 1.06x, is smaller than that.

The two load-bearing qualitative results both reproduce:

  exact at 9.6 KB is still inert -- p99 64,320us against the do-nothing
  baseline's 77,952us, i.e. sitting on top of it, exactly as before.

  the sketch at 8.3 KB still works -- p99 12,016us, a 6.5x tail
  improvement over inaction, against exact-at-35.6KB's 10,064us. The
  sketch/exact p99 ratio reads 1.12x before and 1.19x after, both inside
  the 0.87-1.85 per-repetition spread already characterised in
  REVISIONS.md revision 10.

WHAT THIS DOES AND DOES NOT ESTABLISH. One run cannot prove zero change;
it can show that nothing moved further than this workload moves on its
own, which is what it shows. Combined with the regression suite -- where
the null tracker applies exactly 0 penalties over 11,836 wakeups, and the
two known concurrency bugs still fail exactly as expected rather than
having been accidentally altered -- the refactor is behaviour-preserving
as far as this environment can demonstrate.

########## VERIFICATION: headline matrix on the refactored binary ##########
# Same parameters and seed as results/raw/headline-single-matrix-n20.txt.
# If the tracker-registry refactor changed behaviour, it shows here.
2026-09-14T04:52:50+01:00
Round 4 matrix: headline
workload: 128 respawning churn slots, lifetime 60.0s, schbench victim (same as round 3)
n=20, condition order randomised, seed=31

==================================================================================
condition             p50 med       p50 range  p99 med         p99 range  discrim
==================================================================================
none_ref_32k             3936      3772-35648    77952      61760-170240    2.89x
flat_ref_32k            11376     10800-12560    17568       15856-44480    1.00x
exact_32k                3908       3556-4044    10064        9392-23968    2.91x
exact_8k                 3916       2124-4104    64320      57408-151296    2.91x
sketch_32k_d2            3944       3620-5976    10576        9264-19040    2.88x
sketch_8k_d2             4016      3716-11184    12016        8624-24352    2.83x

DISCRIM = flat_ref p50 / this row's p50. It measures how well the
tracker separates the victim from churn, with the count-blind
penalty as the zero point. 1.0x means no discrimination at all;
below 1.0x means worse than not discriminating.

KEY COMPARISON: every sketch row vs exact_ref. If ANY sketch
shape reaches exact's discrimination at this budget, round 3's
refutation must be narrowed to 'this configuration' rather than
stated about sketches generally.
VERIFY DONE


==============================================================================
## sketch-variants-n10.txt
==============================================================================

Sketch variants at n=10 -- a repeat of r6-sketch-variants-n3.txt

Same harness (round6_sketch_variants.py), same parameters, budgets
narrowed to the three the claims actually rest on. Run sequentially with
nothing else on the guest.

WHAT REPLICATES. The exact and sketch mean columns agree closely across
almost every cell. Conservative update still reduces the sketch's
overestimate at no memory cost, and hash mixing still helps a little:
at churning 8 KB, baseline 6.02x against conservative 4.27x and 4.50x
combined with mixing (n=3 gave 4.30x / 3.59x / 2.78x). The direction and
the ordering hold; the magnitudes move by more than the n=3 run implied.

WHAT DOES NOT REPLICATE, and it matters because the figure is quoted in
the scheduler README, blog post 03 and paper Section 6:

  never-undercount violations, stable 16 KB
                      n=3      n=10
    baseline          116       299
    conservative     1749      1036
    both              197      1750

  and elsewhere: churning 16 KB "both" went 0 -> 2855, stable 8 KB
  "both" went 882 -> 0.

The violation counts jump by orders of magnitude between runs and do not
order consistently across variants. "1,749 against a baseline of 116" is
a single draw from a very wide distribution, not a measurement.

The CONCLUSION drawn from it survives and does not depend on the
magnitude: a lock-free conservative update races, and one violation is
enough to prove it, since never-undercount is the guarantee that
justifies choosing a Count-Min Sketch at all. Thousands of violations
appear in both runs. What cannot be supported is any particular rate.

Note also that the BASELINE is not zero (116, 299, and single digits
elsewhere). The plain sketch cannot undercount by construction, so those
are the known increment-then-read race documented in tracker.bpf.c --
the noise floor this comparison sits on, which the n=3 run made look
smaller and steadier than it is.

SECOND NON-REPLICATION: stable 4 KB, plain_map exact mean 189.8 -> 72.5.
Its count distribution shows why -- 90.6% of queries read zero in this
run against 82.8% before, with far fewer entries in the 1k-10k bucket.
A non-evicting map's mean depends entirely on which 42 keys won the race
to fill it and how active those keys remain, which is not a stable
property of the configuration. Consistent with lru-working-set-n5.txt,
where the same column moved 200.4 -> 0.1 at 300 identities. A candidate
explanation -- that system processes grab slots at attach and then go
quiet -- is untested and recorded as a candidate, not a finding.

########## EXP 3 (redo): sketch variants at n=10 ##########
2026-09-14T03:50:40+01:00
Round 6: sketch fixes and the map-type control
compare mode; exact and sketch figures describe identical queries

########## regime: stable ##########

### 16 KB -- exact 170 entries, sketch 2x256x4 ###
  variant           exact   sketch   sk/ex  under   count distribution
  baseline          297.2    363.0   1.22x    299   z0/9932/50176/140473/17055/0
  hash_mix          298.4    370.0   1.23x    151   z0/18371/26536/162188/20402/0
  conservative      297.9    353.8   1.18x   1036   z0/11036/43873/148497/26060/0
  both              291.8    356.1   1.24x   1750   z1/25827/42136/135001/27628/0
  plain_map         200.4    367.6   1.83x      0   z172678/1462/12584/15850/27677/0

### 8 KB -- exact 85 entries, sketch 2x128x4 ###
  variant           exact   sketch   sk/ex  under   count distribution
  baseline          159.2    411.4   2.73x      5   z0/193548/1362/12774/20986/0
  hash_mix          185.8    433.5   2.35x      2   z0/195887/859/7581/26935/0
  conservative      159.9    396.1   2.49x      0   z0/189377/2308/14865/18421/0
  both              160.2    359.1   2.27x      0   z0/191174/1597/12977/20814/0
  plain_map         193.1    419.6   2.15x      4   z184653/790/7153/9298/27832/0

### 4 KB -- exact 42 entries, sketch 2x64x4 ###
  variant           exact   sketch   sk/ex  under   count distribution
  baseline            1.4    632.0 430.33x      0   z15/225491/2332/0/0/0
  hash_mix            1.5    578.7 383.27x      0   z6/229839/908/0/0/0
  conservative        1.4    520.8 359.29x      0   z12/228703/1294/0/0/0
  both                1.5    369.2 246.23x      0   z7/219126/4308/120/0/0
  plain_map          72.5    613.7   9.38x      0   z202983/405/3352/3781/13544/0
########## regime: churning ##########

### 16 KB -- exact 170 entries, sketch 2x256x4 ###
  variant           exact   sketch   sk/ex  under   count distribution
  baseline          109.5    246.1   2.23x      0   z0/60593/62893/18851/7655/0
  hash_mix          103.5    239.2   2.30x      0   z0/57187/80821/21152/2649/0
  conservative       97.4    232.3   2.38x      0   z0/64358/69002/22262/3572/0
  both               99.9    223.1   2.22x   2855   z2/63263/75066/22862/1873/0
  plain_map         194.2    246.3   1.27x      0   z117718/4034/1095/14648/16489/0

### 8 KB -- exact 85 entries, sketch 2x128x4 ###
  variant           exact   sketch   sk/ex  under   count distribution
  baseline           51.6    317.5   6.02x      0   z0/130563/12685/16688/0/0
  hash_mix           56.8    290.3   5.12x      0   z0/125313/9089/16947/3751/0
  conservative       66.0    280.2   4.27x      0   z1/133057/10981/17826/1207/0
  both               55.3    246.2   4.50x      0   z0/134532/8813/19770/1383/0
  plain_map         196.9    319.1   1.63x      0   z123954/1951/1101/14167/17108/0

### 4 KB -- exact 42 entries, sketch 2x64x4 ###
  variant           exact   sketch   sk/ex  under   count distribution
  baseline            2.9    469.9 160.88x      0   z6/153794/7494/403/0/0
  hash_mix            2.9    415.2 143.76x      0   z6/149299/7569/413/0/0
  conservative        2.9    384.4 131.97x      0   z9/150402/7719/421/0/0
  both                3.1    292.7  93.73x      0   z4/151330/7762/632/0/0
  plain_map         195.4    466.9   2.41x      0   z130800/857/849/13925/17706/0

HOW TO READ THIS:
  conservative vs baseline: does conservative update reduce the
    sketch's overestimate? If yes, the negative result applies
    only to the standard construction.
  hash_mix vs baseline: is the power-of-two modulo costing
    accuracy on real data, as simulation predicted (<=13%)?
  plain_map vs baseline (exact column): if exact stops
    collapsing without an LRU, the collapse was the LRU
    implementation rather than capacity.
  under MUST be 0. Conservative update preserves
    never-undercount only if its read-min-write is atomic;
    a non-zero value means the spin lock is not doing its job.
  distribution buckets: zero/1-9/10-99/100-999/1k-10k/10k+ of
    the EXACT count seen per query.
EXP3 DONE


==============================================================================
## thesis-confirmation-n20.txt
==============================================================================

/tmp/run_confirm_thesis.sh: line 2: 3513250 Killed                     sudo pkill -9 -f scx_ 2> /dev/null
########## THESIS CONFIRMATION: stable, 16KB + 8KB, n=20, seed 21 ##########
Round 3: identity-count scaling -- the memory question
load held constant at 128 concurrent churn tasks; identity count varied by task lifetime

condition order randomised per repetition, seed=21
budgets matched on measured memlock; check the map column

### budget ~16 KB   exact 170 entries   sketch 2x256x4 ###
  none             p50   3880us  p99   65376us   --    p50 rng  2076-58816 p99 rng  62400-133888 map    18.2KB
  flat             p50  11280us  p99   17440us  1.00x  p50 rng 10480-12112 p99 rng  15952-19936  map    18.2KB
  exact_penalty    p50   4736us  p99   37312us  2.14x  p50 rng  3916-6216  p99 rng  16416-57920  map    18.2KB
  sketch_penalty   p50   3944us  p99   11088us  0.64x  p50 rng  3620-6952  p99 rng   9488-25824  map    16.3KB

### budget ~8 KB   exact 85 entries   sketch 2x128x4 ###
  none             p50   3924us  p99   65696us   --    p50 rng  3260-3948  p99 rng  62656-110208 map     9.6KB
  flat             p50  11104us  p99   16960us  1.00x  p50 rng 10800-12464 p99 rng  14320-21344  map     9.6KB
  exact_penalty    p50   3924us  p99   62336us  3.68x  p50 rng  2132-3948  p99 rng  59072-135424 map     9.6KB
  sketch_penalty   p50   4328us  p99   17984us  1.06x  p50 rng  3660-11920 p99 rng  12016-30752  map     8.3KB

HOW TO READ THIS:
  Compare sketch_penalty against exact_penalty AT EACH LIFETIME,
  both relative to flat. The count-attributable benefit is the
  gap from flat; the sketch's cost is how much of that gap it
  fails to reproduce. Ranges overlapping = no difference shown.
  Then compare the maps column: the sketch's whole claim is that
  its number does not move as identities grow while exact's must.
  If exact's quality holds at every scale AND its memory stays
  affordable, the sketch is solving a problem this machine does
  not have, and that is the finding.
CONFIRM DONE

[exited with code 0]


==============================================================================
## victim-shape-sensitivity-n15.txt
==============================================================================

[240 per-repetition lines elided -- see the full file]

victim matrix added
ok
/tmp/run_victim.sh: line 2: 518952 Killed                     sudo pkill -9 -f scx_ 2> /dev/null
########## VICTIM SHAPE: 2 threads, 50 rps ##########
Round 4 matrix: victim
workload: 128 respawning churn slots, lifetime 60.0s, schbench victim (same as round 3)
n=15, condition order randomised, seed=61

==================================================================================
condition             p50 med       p50 range  p99 med         p99 range  discrim
==================================================================================
none_ref                 2092       1950-3004    65920      59968-164096     --
exact_32k                2100       1958-2148     7848        6328-10448     --
sketch_8k_d2             2108       1938-2148     9744        5976-20128     --

DISCRIM = flat_ref p50 / this row's p50. It measures how well the
tracker separates the victim from churn, with the count-blind
penalty as the zero point. 1.0x means no discrimination at all;
below 1.0x means worse than not discriminating.

KEY COMPARISON: every sketch row vs exact_ref. If ANY sketch
shape reaches exact's discrimination at this budget, round 3's
refutation must be narrowed to 'this configuration' rather than
stated about sketches generally.

########## VICTIM SHAPE: 4 threads, 100 rps ##########
Round 4 matrix: victim
workload: 128 respawning churn slots, lifetime 60.0s, schbench victim (same as round 3)
n=15, condition order randomised, seed=61

==================================================================================
condition             p50 med       p50 range  p99 med         p99 range  discrim
==================================================================================
none_ref                58176      7032-63680   170240     165632-230144     --
exact_32k                4360       3988-5944    15632       13840-20512     --
sketch_8k_d2             4568       4200-5896    15280       13776-30368     --

DISCRIM = flat_ref p50 / this row's p50. It measures how well the
tracker separates the victim from churn, with the count-blind
penalty as the zero point. 1.0x means no discrimination at all;
below 1.0x means worse than not discriminating.

KEY COMPARISON: every sketch row vs exact_ref. If ANY sketch
shape reaches exact's discrimination at this budget, round 3's
refutation must be narrowed to 'this configuration' rather than
stated about sketches generally.

########## VICTIM SHAPE: 8 threads, 200 rps ##########
Round 4 matrix: victim
workload: 128 respawning churn slots, lifetime 60.0s, schbench victim (same as round 3)
n=15, condition order randomised, seed=61

==================================================================================
condition             p50 med       p50 range  p99 med         p99 range  discrim
==================================================================================
none_ref                 7752      3948-64960   116352      68224-189184     --
exact_32k                7800       7688-8720    15376       14288-26784     --
sketch_8k_d2             7880      7672-10352    20896       13520-27744     --

DISCRIM = flat_ref p50 / this row's p50. It measures how well the
tracker separates the victim from churn, with the count-blind
penalty as the zero point. 1.0x means no discrimination at all;
below 1.0x means worse than not discriminating.

KEY COMPARISON: every sketch row vs exact_ref. If ANY sketch
shape reaches exact's discrimination at this budget, round 3's
refutation must be narrowed to 'this configuration' rather than
stated about sketches generally.

########## VICTIM SHAPE: 16 threads, 400 rps ##########
Round 4 matrix: victim
workload: 128 respawning churn slots, lifetime 60.0s, schbench victim (same as round 3)
n=15, condition order randomised, seed=61

==================================================================================
condition             p50 med       p50 range  p99 med         p99 range  discrim
==================================================================================
none_ref                70272     66176-71040   959488    818176-1628160     --
exact_32k               29280     23456-35008   836608    695296-1037312     --
sketch_8k_d2            32480     24928-41408   781312     701440-977920     --

DISCRIM = flat_ref p50 / this row's p50. It measures how well the
tracker separates the victim from churn, with the count-blind
penalty as the zero point. 1.0x means no discrimination at all;
below 1.0x means worse than not discriminating.

KEY COMPARISON: every sketch row vs exact_ref. If ANY sketch
shape reaches exact's discrimination at this budget, round 3's
refutation must be narrowed to 'this configuration' rather than
stated about sketches generally.

VICTIM DONE

[exited with code 0]
