# Station mode (v10): learning from other people at the same station

Gilbreth's shipped mode codes a new video from Gemma 4 plus a calibration on the first 30–40 seconds the engineer
reviews. When people doing **the same tasks in the same setting** have already been labelled, station mode learns from
all of their seconds, plus the new person's reviewed takes and their **dominant hand** (read from those takes).

Results, test protocol and what was tried and dropped: [`docs/RESULTS.md`](../../docs/RESULTS.md), section
«Station mode, v10». In short, on KIT Bimanual subject 4 (a new person, pre-registered, looked at once): Gemma alone
51.5 %, shipped Gilbreth 57.4 %, **station mode 83.4 %** (±1 s: 91.5 %); 85.0 % on average leaving one of the five
training people out.

## Files
| File | What it does |
|---|---|
| `rutas.py` | where the data is (environment variables; no data is in this repository) |
| `kit_verdad.py` | KIT labels per frame and per second, with the rule of all our tests |
| `construir.py` | one row per hand and second: motion (`agent/movimiento.py`), Gemma's codes and attributes, task |
| `cuadros.py` | one row per hand and tracker sample (10 Hz), labelled with KIT's per-frame code |
| `sistema.py` | dominant hand, gradient boosting per second (`ajustar_predecir`) |
| `final.py` | the frozen system: per-second model and 10 Hz model averaged (`predecir`) |
| `validar.py` | leave-one-person-out validation and the learning curve |
| `diagrama_s4.py` | the chart-level measures on subject 4 (time shares, hand to free, plan) for Gemma alone, the shipped mode and station mode |

`sistema.py` and `final.py` are byte-identical to the frozen copies used for the test; `construir.py` and `cuadros.py`
only read their paths from `rutas.py` and reproduce the frozen rows exactly (checked on subjects 1 and 3).

## Reproduce
1. Download KIT Bimanual Actions (https://bimanual-actions.humanoids.kit.edu, its own licence) and turn each subject's
   RGB frames into `mp4/` + `mp4/meta.json` and the hand tracker into `puntos/` (`agent/extraer_puntos.py`).
2. Run the shipped agent with Gemma on each subject (`scripts/tokenfactory_batch.py` or `agent/bimanual.py`) and keep
   each take's `pred.json` under `GILBRETH_GEMMA_CODES/s{N}/<take>/`.
3. Set `GILBRETH_KIT_VIDEOS`, `GILBRETH_KIT_GT`, `GILBRETH_GEMMA_CODES`, `GILBRETH_V10_OUT`, then:
   ```bash
   python research/station_v10/construir.py --sujeto 1 2 3 5 6 --prueba 4
   python research/station_v10/cuadros.py --sujeto 1 2 3 5 6 --prueba 4
   python research/station_v10/validar.py --sujetos 1 2 3 5 6
   ```
   `--prueba 4` builds subject 4 reading its labels only for takes 0–1 (the reviewed ones).

## Where it does not apply
A new station with nobody labelled: use the shipped mode. Not measured outside KIT. With the app's per-second labels
instead of KIT's per-frame labels, the 10 Hz model has nothing finer to learn from; the per-second model alone scored
82.5 % on subject 4.
