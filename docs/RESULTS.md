# Measurement log (summary)

Protocol: every design choice was made on **development** data; each **test** set was looked at once with the system
frozen, and the decision rule was written before measuring (pre-registration). Accuracy = (hand, second) pairs with
the right code. Baseline = best constant code per hand over the whole set.

The LEGO and IMPACT sets below were tests for v7 (11 Oct) and were then reused while choosing v9 (the gate), so for the
shipped system only **KIT subject 1** is a clean test. On IMPACT, v9 scored 72.9 % in that development table
(Gemma 70.0 %, v7 73.6 %).

## Clean tests
| Test set | Baseline | Gemma alone (v5) | Calibrated (v7) | v7 + gate (v9) |
|---|---|---|---|---|
| KIT Bimanual subject 1 (new person) — workshop, 1,347 | 48.4 % | 69.6 % | 78.8 % | **80.3 %** |
| KIT Bimanual subject 1 — kitchen, 1,958 | 55.0 % | 66.0 % | 76.0 % | **74.9 %** |
| KIT Bimanual subject 1 — total, 3,305 | — | 67.5 % | 77.1 % | **77.1 %** (±1 s: 87.2 %) |
| LEGO, blind human labels, 92 | — | 64.1 % | **71.7 %** | — |
| IMPACT, 4 new operators, 982 | 45.7 % | 70.0 % | **73.6 %** | — |

Pre-registered criterion for the final test (v9 ≥ Gemma in workshop and kitchen, and > Gemma in total): **met**.

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

## Changes after the final test (15 Oct, development data only)
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
