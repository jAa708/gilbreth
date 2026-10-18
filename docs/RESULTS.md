# Measurement log (summary)

Protocol: every design choice was made on **development** data; each **test** set was looked at once with the system
frozen, and the decision rule was written before measuring (pre-registration). Accuracy = (hand, second) pairs with
the right code. Baseline = best constant code per hand over the whole set.

The LEGO and IMPACT sets below were tests for v7 (11 Oct) and were then reused while choosing v9 (the gate), so for the
shipped system the clean tests are **KIT subject 1** (lab GPU), **KIT subject 3** and **KIT subject 4** (AMD, below), and
the **IMPACT test of 17 Oct** on 8 runs never coded before (AMD, below). On IMPACT, v9 scored 72.9 % in that development
table (Gemma 70.0 %, v7 74.3 %; v7 scored 73.6 % in its 11 Oct test).

## Clean tests
| Test set | Baseline | Gemma alone (v5) | Calibrated (v7) | v7 + gate (v9) |
|---|---|---|---|---|
| KIT Bimanual subject 1 (new person) — workshop, 1,347 | 48.4 % | 69.6 % | 78.8 % | **80.3 %** |
| KIT Bimanual subject 1 — kitchen, 1,958 | 55.0 % | 66.0 % | 76.0 % | **74.9 %** |
| KIT Bimanual subject 1 — total, 3,305 | — | 67.5 % | 77.1 % | **77.1 %** (±1 s: 87.2 %) |
| LEGO, blind human labels, 92 | — | 64.1 % | **71.7 %** | — |
| IMPACT, 4 new operators, 982 | 45.7 % | 70.0 % | **73.6 %** | — |

Pre-registered criterion for the final test (v9 ≥ Gemma in workshop and kitchen, and > Gemma in total): **met**.

## Clean test on AMD (15 Oct): KIT Bimanual subject 3, the shipped system
Pre-registered at 00:30 before the subject was downloaded; looked at once. The system exactly as shipped (commit
`5b3edd6`): Gemma-4-31B-IT on AMD Token Factory, the IMPACT motion prior, the gate; the first two takes of each task
reviewed, takes 2-9 measured. 1,512 requests, US$0.15, no failed answers.

| KIT subject 3 (new person), on AMD | Baseline | Gemma alone | **Gilbreth (v9)** | ±1 s |
|---|---|---|---|---|
| Workshop, 1,086 hand-seconds | 41.8 % | 59.3 % | **66.5 %** | 83.7 % |
| Kitchen, 1,172 hand-seconds | 41.7 % | 51.9 % | **63.9 %** | 76.7 % |
| Total, 2,258 hand-seconds | — | 55.4 % | **65.1 %** | 80.1 % |

Pre-registered criterion (v9 ≥ Gemma in workshop and in kitchen, and > Gemma in total): **met**. The gain matches the lab
test on subject 1 (+9.7 points here, +9.6 there). The gate kept Gemma in 3 of the 9 tasks; the calibrated model without
the gate scored 71.3 % on this subject, so the gate's choice, made on 40–100 reviewed hand-seconds per task, cost 6.2
points here (on subject 1 it cost nothing). That is the next thing to study, on development data.

## Clean test on AMD (17 Oct): KIT Bimanual subject 4, the shipped system
Pre-registered on 16 Oct at 22:35, when Gemma came back to Token Factory, before any result of subject 4 existed; looked
at once. Same system and same calculation as subject 3 (agent commit `ab7188a`, which only adds the strict mode used
for the MI300X runs and behaves byte for byte like `5b3edd6` with the shipped settings). 90 takes, 1,190 windows, no
failed answers, about US$0.13 of quota.

| KIT subject 4 (new person), on AMD | Baseline | Gemma alone | Calibrated (v7) | **Gilbreth (v9)** | ±1 s |
|---|---|---|---|---|---|
| Workshop, 756 hand-seconds | 37.0 % | 56.1 % | 72.2 % | **69.8 %** | 79.1 % |
| Kitchen, 1,132 hand-seconds | 44.7 % | 48.5 % | 54.4 % | **49.0 %** | 66.0 % |
| Total, 1,888 hand-seconds | 41.6 % | 51.5 % | 61.5 % | **57.4 %** | 71.2 % |

Pre-registered criterion: **met** (+5.9 points). The gate kept Gemma in 4 of the 9 tasks (three kitchen tasks, two of
them ties on the reviewed takes) and cost 4.1 points against the calibrated model without the gate; on subject 3 it
cost 6.2, on subject 1 nothing.

## Station mode, v10 (16–17 Oct): learning from other people at the same station
When people doing the same tasks have already been labelled, the system can learn from all of their seconds instead of
only the 20–50 reviewed seconds of the new person. Built and chosen on KIT subjects 1, 2 and 3 (already used), then on
5 and 6 (downloaded that night), always leaving one person out; then frozen, pre-registered and tested once on subject 4.
- Inputs per hand and second: hand-tracker motion (the second, its halves, a 10 Hz profile, ±2 s, the other hand),
  Gemma's codes and attributes (±2 s, the other hand), the task, and the person's **dominant hand** in that task, read
  from the reviewed takes (share of seconds operating). Subject 3 is left-handed: on development data, with the
  dominant hand the model scored 82.8–83.2 % on that person, against 76.7–81.0 % for the variants without it.
- Two gradient-boosting models averaged: one per second, one at 10 Hz trained on KIT's per-frame labels and averaged
  per second. On development data (subjects 1–3, per-second model), 85 % of the errors were in the second next to a
  change of activity (964 of 1,128; 94 % right away from changes); the
  10 Hz model is what helps there.
- Tried and dropped on development data: a second stacking level, Viterbi smoothing, self-training, Extra Trees, a
  recurrent network, prior correction, more weight on the reviewed takes.

| Leaving one person out (development) | s1 | s2 | s3 | s5 | s6 | Mean |
|---|---|---|---|---|---|---|
| Gemma alone | 67.5 % | 47.7 % | 55.4 % | 47.5 % | 49.5 % | 53.5 % |
| Station mode, 4 people to learn from | 86.9 % | 82.2 % | 85.4 % | 84.3 % | 86.4 % | **85.0 %** |

How many labelled people it needs (each new person scored with every combination of the others, development): 1 person
83.8 % (20 runs), 2 people 84.5 % (30), 3 people 84.9 % (20), 4 people 85.0 % (5). Almost all of the gain comes from the
first labelled person.

**Clean test, KIT subject 4** (trained on subjects 1, 2, 3, 5, 6 plus the reviewed takes of subject 4; the same 1,888
hand-seconds as above; pre-registered criterion: above v9 in total and not below it in workshop or kitchen):

| Subject 4 | Workshop | Kitchen | Total | Total ±1 s |
|---|---|---|---|---|
| Gemma alone | 56.1 % | 48.5 % | 51.5 % | 69.7 % |
| Gilbreth (v9, shipped) | 69.8 % | 49.0 % | 57.4 % | 71.2 % |
| **Station mode** | **82.9 %** | **83.7 %** | **83.4 %** | **91.5 %** |
| Station mode, per-second labels only (what the review page gives) | 82.9 % | 82.2 % | 82.5 % | 91.0 % |

Criterion: **met** for both. Before looking, Codex audited the code (15 findings, no leak of the test labels; the ones
that mattered were fixed and the development figures recomputed). Where it applies: only where people doing the same
task in the same setting have been labelled. Code: [`research/station_v10/`](../research/station_v10/).

**At the chart level (17 Oct, second look at subject 4, declared as such).** The three chart measures of the next
section, on the same 72 takes (tasks 1–9, takes 2–9) and the same seconds, with the station-mode predictions recomputed
from the frozen code and data (they reproduce the 83.4 % exactly, 1,574 of 1,888 hand-seconds) and the shipped and
Gemma-alone predictions of the clean test:

| Subject 4, 72 takes | Gemma alone | Gilbreth (shipped) | **Station mode** |
|---|---|---|---|
| Share of time per hand and activity, points away from the human labels | 12.5 | 12.8 | **6.3** |
| Which hand holds or waits the most: right | 79 % | 71 % | **92 %** |
| Time after the plan, distance from the plan built on the human labels (% of the cycle) | 10.0 % | 9.4 % | **5.6 %** |
| Top lever matches | 43 % | 44 % | 47 % |

Where coworkers have been labelled, the per-second gain does carry over to what the engineer reads: station mode halves
the error in the time shares and finds the hand to free in 92 % of the takes. The top lever still matches in only about
half of these short takes. Script: `research/station_v10/diagrama_s4.py`.

**Outside KIT: the gearbox example in the app (17 Oct, second look, declared as such).** Station = the 11 runs of the
9 IMPACT operators the motion prior already uses (their per-second labels as the review, Gemma's codes only); the new
worker = the gearbox operator, first 60 s reviewed, scored like the app (from second 60, 307 hand-seconds):

| Gearbox, from second 60 | Gemma alone | Gilbreth (shipped) | **Station mode (`agent/estacion.py`)** |
|---|---|---|---|
| Per hand and second | 70.0 % | 73.9 % | **77.9 %** |
| Share of time per hand, points away from the human labels | 3.8 | 6.4 | 3.9 |
| Hand that holds or waits the most | right | wrong | right |
| Top lever | wrong | right | right |

`agent/estacion.py` is the shipped station mode: the frozen per-second system with per-second labels (what the review
page exports). The lab version with the dataset's per-frame labels (`final.py`, both models) scored 81.1 % on the same
seconds. One video: it shows that station mode runs outside KIT, not how much it gains there; the pre-registered test
on eight IMPACT runs never coded before (next section) found a tie with the shipped mode.

## Clean test outside KIT (17 Oct): IMPACT, 8 runs never coded before
Another station: gearbox disassembly and reassembly with tools (IMPACT), the 4 test operators, 8 runs that Gemma, the
shipped system and station mode had never coded (34.9 min of video). Gemma-4-31B-IT on AMD Token Factory with the
shipped pipeline (2,094 requests, no failed answers); the first 60 s of each run reviewed with the dataset's labels,
measured from second 60. Pre-registered before Gemma had coded any of them, the script audited by Codex (no leak of
the labels) and sealed, looked at once. Station mode learned from the 11 labelled runs of the other 9 IMPACT
operators (their Gemma codes come from the lab run, codes only).

| IMPACT, 3,142 hand-seconds from second 60 | Baseline | Gemma alone | **Gilbreth (shipped)** | Station mode | Station mode, per-second labels |
|---|---|---|---|---|---|
| Per hand and second | 46.5 % | 66.5 % | **71.1 %** | 71.3 % | 72.2 % |
| Within ±1 s | — | 78.4 % | **82.4 %** | 79.6 % | 81.0 % |
| Disassembly (1,296) / reassembly (1,846) | 44.9 / 47.6 % | 68.4 / 65.2 % | 74.7 / 68.5 % | 74.0 / 69.3 % | 73.6 / 71.2 % |
| Hand that holds or waits the most, right (8 runs) | — | 8 / 8 | 8 / 8 | 8 / 8 | 8 / 8 |
| Top lever matches (8 runs) | — | 8 / 8 | 8 / 8 | 8 / 8 | 8 / 8 |
| Share of time per hand, points away from the labels | — | 8.1 | 8.0 | 8.9 | 8.3 |

Pre-registered criterion (station mode above the shipped mode in total): met by 6 hand-seconds (2,239 against 2,233),
which is a tie. What the test shows: outside KIT the shipped system beats Gemma by 4.6 points on new people at a new
station, and on runs of 4–5 minutes the engineer's decisions (the hand to free and the top lever) come out right in all
8 runs with any of the systems. Station mode adds nothing here. Two likely reasons, not measured: the shipped motion
prior was built from these same 9 operators, so at IMPACT the shipped mode already learns from the station; and the
station's Gemma codes come from the lab run, the test's from AMD. Pre-registration with the result:
`research/station_v10/PREREGISTRO_V10_IMPACT.md`.

## What the per-second figure means for the chart (15 Oct, second look, rule written before computing)
An engineer reads the chart (share of time each hand operates, transports, holds, waits) and the plan, not the per-second
score. On KIT subject 3 on AMD (72 takes of about 15 s) and on the gearbox example, against the human labels:
- **Share of time per hand and activity:** Gilbreth is 10.9 points away on average on KIT (6.4 on the gearbox); Gemma
  alone 10.7 (3.8). Both over-count transport and under-count the left hand operating.
- **Which hand holds or waits the most:** right in 81 % of the KIT takes (Gemma alone 90 %).
- **Plan:** estimated time after the plan within 7.8 % of the cycle of the plan built from the human labels (Gemma alone
  9.1 %); the top lever matches in 43 % of the short KIT takes (49 %), where levers differ by under a second, and matches
  on the gearbox (right hand, 28 s vs 21 s from the labels).
So the calibration's per-second gain (+9.7 points) does not carry over to the time shares, which are already about as
close with the vision model alone; making the chart, not only the seconds, closer is the next target.

## What did not work (measured, not shipped)
- Higher image resolution per frame (560 tokens): worse (72 % vs 79 %).
- Context frames ±0.5 s, smoothing isolated seconds, voting 5 times: worse or no change.
- Motion-only classifier without calibration: does not transfer to a new camera.
- A "general" stacked model without human review: worse than Gemma on LEGO → without review, Gemma alone is used.
- Temporal model (GRU + 10 Hz GBM): helped on IMPACT only, lost on KIT workshop → not shipped.
- Asking for descriptions in the same request as the codes: codes got worse (70 → 45 %) → descriptions are a
  separate second pass.
- Sharper activity boundaries (12–14 Oct, development set KIT subject 2 + IMPACT; pass mark: +1.0 point on the
  total and no part losing more than 0.5). 63–80 % of the remaining errors sit in the second next to a change, so
  four ways of moving the boundary were tested; none passed:
  - move the boundary to the best split point of the 10 Hz hand-speed signal: −0.64 (68.82 → 68.18 %);
  - remove isolated one-second segments: −5.05 (many one-second changes are real);
  - motion features at half-second resolution: −0.09 (64.95 → 64.86 %, motion prior trained without the
    development operators);
  - ask Gemma, with 8 frames 0.25 s apart, in which frame the change happens (654 questions, same reference):
    −1.04 (64.95 → 63.91 %). It fixed 61 seconds and broke 84; with perfect answers the ceiling would have been
    +10.6.

  The boundary is not recoverable below one second with these signals, so the shipped system keeps 1-second
  resolution and reports the ±1 s agreement next to the exact one.

## Second look on AMD (14 Oct): the examples as shipped
The app's examples were recomputed end to end on AMD Token Factory (Gemma-4-31B-IT, shared endpoint, JSON object
output with the schema in the prompt) with the shipped pipeline (gate on).
- Gearbox (IMPACT `LE07UF17_Reassembly_A_004`, operator not in the training data, first 60 s reviewed with the dataset's human
  labels), from second 60, 307 hand-seconds: Gemma alone **70.0 %**, Gilbreth **73.9 %** (A100 development run of
  the same example: 67.8 % and 76.2 %).
- LEGO against the two blind batches labelled by a person (92 hand-seconds, already used as a test, so this is a second look):
  Gemma alone **58.7 %**, Gilbreth **62.0 %** (A100 example: 60.9 %). The 71.7 % in the table above came from the lab
  run of v7 on 11 Oct, which trains the calibrated model with a different routine than the shipped pipeline;
  with 92 hand-seconds that difference moves the figure by about ten points, so it is not a robust number. The KIT test (3,305 hand-seconds) is.

## The shipped model against the lab model, and a fallback for the live demo (15 Oct, development data)
KIT subject 2, takes 1 and 2 of the nine tasks (418 hand-seconds, the same seconds for every row), shipped agent,
JSON-object mode on AMD Token Factory:

| Vision model | Exact | ±1 s | Workshop | Kitchen | Failed answers | US$ per request |
|---|---|---|---|---|---|---|
| Gemma 4 31B QAT on an A100 (the lab runs) | 53.3 % | 71.3 % | 56.0 % | 50.0 % | — | — |
| **Gemma-4-31B-IT on AMD Token Factory (shipped)** | **55.3 %** | 72.7 % | 60.8 % | 48.4 % | 0 % | 0.000099 |
| **Qwen3.8-Flash-Next on AMD Token Factory (reasoning off)** | **56.9 %** | 72.0 % | 60.3 % | 52.7 % | 0 % | 0.000522 |
| Qwen3.8-27B on AMD Token Factory (reasoning off) | 51.9 % | 65.6 % | 50.0 % | 54.3 % | 0 % | 0.000134 |
| DeepSeek-V4-Flash-Vision-Exp | 42.8 % | 57.4 % | 42.7 % | 43.0 % | 2.4 % | 0.000386 |
| DeepSeek-V4.1-Flash | 46.7 % | 61.2 % | 49.6 % | 43.0 % | 0 % | 0.000880 |
| MiMo-V2.6-Flash | 36.8 % | 60.0 % | 44.0 % | 28.0 % | 0 % | 0.000475 |

The rule written before the screening: the fallback is the best model with at most 2 % failed answers, used only if it
is within 5 points of the lab Gemma. Qwen3.8-27B passed first; Qwen3.8-Flash-Next and DeepSeek-V4.1-Flash were
screened the next day under the same rule, and Qwen3.8-Flash-Next became the fallback (+1.6 points over Gemma on these
seconds, short of the +3 we set to call a model stronger). The app uses it (`GILBRETH_FALLBACK_MODEL`) only when Gemma
does not answer the image health check, and says so on screen. MiniCPM-V-4.7 was not measured: its endpoint failed
with six images per request.

## Tried on 15 Oct on development data and not shipped (each rule written before measuring)
KIT subject 2 with Gemma on AMD (takes 0-1 reviewed, takes 2-9 measured, 1,466 hand-seconds; the sawing takes 3-9 are
missing because Gemma left the Token Factory catalog before they ran). Pass mark: +1.0 point on that total, no other
set losing more than 0.5.
- **The shipped model against the lab model, whole subject:** Gemma on AMD 52.9 % vs the 4-bit lab model 50.8 %
  (1,892 hand-seconds; workshop +3.7, kitchen +0.4).
- **A gate that keeps the calibrated model unless Gemma is clearly better on the reviewed seconds** (Gemma only if
  c − b > √(b + c)): +0.95 (kitchen +1.9, workshop 0). Never below the current gate on any other set (KIT subject 2 with
  the lab model +1.1, KIT subject 1 +0.7, IMPACT +0.4 / 0, LEGO 0, MIT-pure 0), but short of the mark → not shipped.
  The idea came from the subject-3 test, which was therefore left out of this decision.
- **Gemma's own per-hand observations** (motion, grip, works on the piece, only holds) as extra features of the calibrated
  model: +0.9 (kitchen +1.8, workshop +0.1) → not shipped. A fixed rule from those observations instead of Gemma's code:
  −1.2 → not shipped.
- **"Not visible" rule, second look with Gemma on AMD:** +0.7 on the whole subject (workshop +0.4, kitchen +1.0), same
  sign as on the lab model.

## Changes after the KIT subject 1 test, frozen before the subject 3 test on AMD (15 Oct, development data only)
Both rules were written down before measuring; the shipped examples are unchanged by them (0 seconds in four
examples, 2 hand-seconds in the cardboard one).
- **"Not visible" against the hand tracker.** On KIT subject 2, 218 of Gemma's 971 errors were NV for a hand the
  labels do code. When the tracker sees that hand in at least half of the second, NV becomes D (delay). KIT subject 2:
  51.3 → 53.0 % (workshop +1.5, kitchen +1.9); IMPACT development 2 and LEGO 0-70 s: no change. Most of the other NV
  errors are hands outside the frame, which KIT labels as idle and the bimanual chart writes as NV.
- **A request that fails is not a delay.** A window whose request still fails after a second pass copies the nearest
  valid second and is flagged for review. Simulated on KIT subject 2: D/D was right for 23.5 % of such hand-seconds,
  the neighbour for 36.6 %, and a false D inflated the idle share of the chart.

## MIT-pure mode (no IMPACT-derived motion prior)
Decision set KIT subject 2 (total): v9 with prior 62.4 % · v9 without prior **49.8 %** (= Gemma; the gate rejects the
calibrated model in 9/9 tasks because, trained on half of the reviewed seconds, it is too weak). Second look on KIT
subject 1: 77.1 % vs 68.9 %. The prior is therefore distributed separately (CC BY-NC-SA 4.0) and downloaded on use.
