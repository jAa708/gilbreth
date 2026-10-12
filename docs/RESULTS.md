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

## MIT-pure mode (no IMPACT-derived motion prior)
Decision set KIT subject 2 (total): v9 with prior 62.4 % · v9 without prior **49.8 %** (= Gemma; the gate rejects the
calibrated model in 9/9 tasks because, trained on half of the reviewed seconds, it is too weak). Second look on KIT
subject 1: 77.1 % vs 68.9 %. The prior is therefore distributed separately (CC BY-NC-SA 4.0) and downloaded on use.
