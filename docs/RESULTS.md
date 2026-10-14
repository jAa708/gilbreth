# Measurement log (summary)

Protocol: every design choice was made on **development** data; each **test** set was looked at once with the system
frozen, and the decision rule was written before measuring (pre-registration). Accuracy = (hand, second) pairs with
the right code. Baseline = best constant code per hand over the whole set.

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
- Gearbox (IMPACT `LE07UF17_Reassembly_A_004`, operator never seen, first 60 s reviewed with the dataset's human
  labels), from second 60, 307 hand-seconds: Gemma alone **70.0 %**, Gilbreth **73.9 %** (A100 development run of
  the same example: 67.8 % and 76.2 %).
- LEGO against the two blind batches labelled by a person (92 hand-seconds, already used as a test, so this is a second look):
  Gemma alone **58.7 %**, Gilbreth **62.0 %** (A100 example: 60.9 %). The 71.7 % in the table above came from the lab
  run of v7 on 11 Oct, which trains the calibrated model with a different routine than the shipped pipeline;
  with 92 hand-seconds that difference moves the figure by about ten points, so it is not a robust number. The KIT test (3,305 hand-seconds) is.

## MIT-pure mode (no IMPACT-derived motion prior)
Decision set KIT subject 2 (total): v9 with prior 62.4 % · v9 without prior **49.8 %** (= Gemma; the gate rejects the
calibrated model in 9/9 tasks because, trained on half of the reviewed seconds, it is too weak). Second look on KIT
subject 1: 77.1 % vs 68.9 %. The prior is therefore distributed separately (CC BY-NC-SA 4.0) and downloaded on use.
