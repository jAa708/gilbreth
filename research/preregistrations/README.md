# Pre-registrations of the shipped-system tests (lab notes, in Spanish)

The three files here are the lab notes written before each clean test of the shipped system (v9: Gemma + calibrated
hand motion + gate), copied as they were:

| File | Test | Where it ran | Result (docs/RESULTS.md) |
|---|---|---|---|
| `PREREGISTRO_KIT_S1_11OCT.md` | KIT Bimanual subject 1 | lab GPU (Colab A100, Gemma 4 31B 4-bit) | 67.5 → 77.1 % |
| `PREREGISTRO_KIT_S3_AMD_15OCT.md` | KIT Bimanual subject 3 | AMD Token Factory, Gemma-4-31B-IT | 55.4 → 65.1 % |
| `PREREGISTRO_KIT_S4_GEMMA_TF_16OCT.md` | KIT Bimanual subject 4 | AMD Token Factory, Gemma-4-31B-IT | 51.5 → 57.4 % |

They were committed on 18 Oct, after the results, so the git date is not the evidence; the notes themselves are.
The commit hashes inside them predate the 17 Oct rewrite of the commit e-mail address. The trees are identical:
`5b3edd6` is `1db0ed0` in this public history, and `ab7188a` is `4710607`.

The station-mode and IMPACT pre-registrations, with their results and seals, are in
[`../station_v10/`](../station_v10/).
