# Nine claims I retracted

I set out to test whether a Count-Min Sketch could replace exact
per-task counters in a Linux scheduler, saving memory without hurting
scheduling quality.

The answer turned out to be yes — equivalent scheduling quality at 4.3x
less memory. But between forming the hypothesis and confirming it, I
announced and then withdrew nine separate conclusions, including, at one
point, the conclusion that the hypothesis was refuted — and, twice near
the end, claims I had already written up as final.

None of them failed because the hypothesis was wrong. Every one failed
because an instrument was wrong. That pattern is the thing worth writing
about.

## The retractions

**1. "Seed rotation mitigates the collision attack at heavy volume."**
Looked clear on one run. Didn't replicate on the second.

**2. "+34.7% improvement."** At n=5. At n=15 it was −1.7%. Ordinary
small-sample optimism, and the only one on this list that more
repetitions would have caught.

**3. "Acting on the tracked count improves tail latency 6.8x."** Real,
replicated, non-overlapping ranges at n=20. Then I built a control that
applied the same vtime perturbation while ignoring the tracked count
entirely, and it reproduced about 82% of the improvement. The comparison
had been measuring "does perturbing scheduling help" and I'd been
reading it as "does tracking wakeups help."

**4. "The sketch has a ~10% severe failure rate."** Two of twenty runs
showed the protected task getting catastrophically mis-scheduled. I had
a mechanism for it — hash collisions inflating the victim's count — and
called it the most policy-relevant sketch finding I'd made. After fixing
an unrelated benchmark bug, it was zero of twenty. It had been an
artifact of condition ordering.

**5. "Exact counting beats the sketch at every memory budget."** The
metric was a discrimination ratio measured against a count-blind
baseline. That baseline is *worse than taking no action at all*, so a
tracker that had quietly stopped working scored just as well as one
working perfectly. Adding a do-nothing reference condition — which the
sweep had never included — showed that at small budgets the exact
tracker wasn't discriminating. It was inert.

**6. "The sketch works down to 2.3 KB."** It improved the tail there,
5x over doing nothing. But its median had collapsed to the level of the
blunt control, meaning it had stopped telling tasks apart and was just
perturbing everything. Genuine working range: 8 KB. My memory claim went
from 15x to 4.3x.

**7. "A sketch at 8 KB matches exact counting at 32 KB."** The claim
survived. The evidence for it didn't. The two numbers came from
*different runs* — and I'll come back to this one, because it's the
worst of the seven.

**8. "The sketch is equivalent to exact counting at 4x less memory."**
The memory saving held. *Equivalent* did not. I'd inferred it from
overlapping measurement ranges, which show a difference was not
detected, not that none exists. A pre-registered equivalence test at
n=30 put the sketch 11–39% worse on tail latency, with equivalent
median. The corrected claim is a trade rather than a substitution.

**9. "The sketch has a rare, severe failure mode invisible to normal
monitoring."** I found one run in thirty where a sketch performing
normally returned a tail latency twenty-four times its own median, with
its typical-case latency untouched. It looked like a distinct and
rather alarming failure mode, so I wrote it into three posts. Then I
measured it: at sixty repetitions per condition, **exact counting
produces the same excursions at the same rate**, and the 24x never
recurred across 360 further measurements. It belongs to the
environment, not to the sketch.

## The pattern

Reading them together, the striking thing is that more data would have
saved me from exactly one — number 2.

The rest were instrument failures:

- **A benchmark harness that ran conditions in fixed order**, so
  carryover from one condition landed on the same neighbour every
  repetition. Systematic bias that repetitions cannot average away. Same
  configuration measured 21,664µs or 14,000µs depending on what preceded
  it.
- **A metric that couldn't distinguish "working" from "doing nothing"**,
  because its reference point was worse than doing nothing.
- **A ratio whose denominator was collapsing**, so an "inflation" figure
  of 1,043x turned out to be 2.6x once measured against truth rather
  than against a dying comparator.
- **A workload model wrong by 4x**, which I patched twice with better
  reasoning before instrumenting the thing and discovering the
  distribution was bimodal.
- **A BPF map that wasn't doing what its name says.** `LRU_HASH` below
  about 85 entries on a 4-core machine stops behaving like an LRU —
  mean retained count of 1.6 where a plain hash at identical capacity
  gives 189.8. That made exact counting look intrinsically worse than
  it is.

Every fix came from adding a control or an instrument. None came from
running more repetitions of the same measurement.

## The one that bothers me most

Number 7, and not because it was the largest error. It was the
smallest — the claim turned out to be right when I re-measured it
properly.

It bothers me because **post 1 of this series is entirely about why
figures from different matrices aren't comparable.** I found that bug,
spent hours tracing it, fixed it, understood the mechanism well enough
to explain it to strangers — and then built my headline result by
pairing a number from one run against a number from another.

Nobody caught it in review. I caught it while writing up a defence of
my own confidence, going through the numbers one more time to explain
why they should be trusted.

Knowing a failure mode does not inoculate you against it. I could
state the principle correctly, at length, in public, while
simultaneously violating it in the most important comparison I had.
The knowledge and the application live in different places, and only
one of them gets exercised when you're pleased with a result.

Re-running it as a single interleaved matrix took forty minutes. The
claim held: 12% apart on median p99, ranges overlapping, medians within
1%. But for a day before that, the headline of the whole project rested
on a comparison I had personally written a blog post explaining you
must not make.

## The other one that bothers me

Number 4.

The others were disappointing results that I attacked properly — I ran
controls, raised sample sizes, and at one point voided my own
pre-registration when it failed its gating condition.

Number 4 was an *interesting* result. It came with a plausible
mechanism. Collisions inflating the protected task's count was exactly
what the theory predicted, so when the data showed it, the mechanism
felt like confirmation rather than something still to be tested. I
accepted it at n=20 with visibly less scrutiny than I'd applied to
results I didn't like — and I'd explicitly predicted it was the finding
*least* likely to be an ordering artifact, right before it turned out to
be one.

That's not a sample-size problem and no statistical discipline catches
it. Asymmetric skepticism is invisible from the inside, because at each
moment you're applying what feels like the appropriate level of rigour.
The asymmetry only shows up when you line the decisions up afterwards.

The practical defence I've landed on: **have a mechanism and treat it as
a reason for more scrutiny, not less.** A plausible causal story means
you now have a specific prediction to test, not that you're done.

## What it cost, and what it bought

Roughly a day. Nine announcements withdrawn — one of them a claim that
the whole project had failed, and the last two arriving after I had
already written the result up as final and published the explanation.

The eighth is the only one caught by a test built specifically so that
it could fail: margin, metric, analysis and falsification clause all
committed before the data existed, with the margin set tighter than the
difference already observed. Every previous revision was caught by
accident — a disagreement between two runs, a control added for
completeness, someone asking how confident I really was.

And then the ninth punctured my satisfaction about that.

The outlier in retraction 9 came with a *pre-registered* check meant to
rule out an environmental cause: I'd specified in advance that I would
report whether outliers clustered across conditions within a
repetition, reasoning that a host-level disturbance would disturb
several. Only one condition was affected, so I concluded the sketch was
responsible.

**Conditions run sequentially.** A disturbance lasting a few seconds
hits exactly one of them. The signature I had declared exonerating was
precisely what an environmental cause produces. I'd written the check
in advance and it was simply the wrong check.

That's the distinction I'd underweighted: pre-registration guarantees
you didn't choose your test to fit the data. It does not guarantee your
test measures what you think it measures. The first is a defence
against motivated reasoning; nothing defends against being wrong about
the mechanism except measuring it.

What it bought: the final result is one I believe. The memory claim is
n=20 with non-overlapping ranges, the geometry that achieves it is
measured rather than defaulted, the regime where it stops holding is
stated in the claim, and the failure modes of both structures are
characterised.

It also produced findings I'd never have gone looking for — the
`LRU_HASH` cliff, the count-blind control, the ordering bias — all of
which are useful to people who don't care about count-min sketches at
all.

## If I were starting again

**Put a do-nothing condition in every matrix.** Without it you cannot
tell a working mechanism from a stopped one, because both leave your
protected workload alone.

**Put a blunt control in every matrix** — the same intervention applied
without the information. It tells you what fraction of your result is
attributable to the signal rather than the disturbance.

**Randomise condition order**, and print the seed.

**Instrument before you infer.** I spent three rounds reasoning about a
4x discrepancy that one histogram resolved in a single run.

**Write down what would falsify each claim, before the run.** I did this
once, via a pre-registration, and it was the only time I caught myself
about to accept a favourable result whose framing had already failed.

None of that is novel advice. What surprised me is how much of it I
only adopted after being burned, despite knowing all of it beforehand.
