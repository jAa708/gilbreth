# ⏱️ Gilbreth — AI motion study from a workstation video

**A phone video of a manual operation goes in. A draft bimanual chart, method alerts and an improvement plan in
seconds come out — for the methods engineer to review and approve.**

Built for the **AMD Developer Hackathon: ACT III** (Track 1, *Intelligent Industry*) by team **ArkhanLabs**
(Juan David Sabogal Orozco, industrial engineering student, Cali, Colombia).
Vision model: **Gemma 4 31B** on **AMD GPUs** through **AMD Token Factory** (the event's OpenAI-compatible endpoint)
for every example and test here. Hand tracking: **MediaPipe**.

> **Status, 15 Oct:** AMD removed `Gemma-4-31B-IT` from Token Factory that morning. The agent does not depend on one
> model: we screened six vision models on AMD on the same development seconds, with the rule written beforehand, and
> the live demo now runs the best one, `Qwen3.8-Flash-Next` (56.9 % against 55.3 % for Gemma), and names it on screen.

> Named after Frank and Lillian Gilbreth, who filmed workers a century ago to study and improve their motions.

## The problem
Methods engineers improve manual work (assembly, packing, kitting) with the **bimanual chart**: what the left and
right hand do, row by row (ILO symbols ○ operation, ⇨ transport, D delay, ▽ hold). Drawing it by hand from a video is
slow: about **one hour of one person for a 4.7-minute video**, by our estimate from a course project. The gains it
reveals are well known: fixtures that free the holding hand, balanced hands, parts within reach.

**Who uses Gilbreth:** industrial/methods engineers and plant supervisors. **What it targets:** time per unit of a
manual operation (and the time it takes to analyse it).

## What it produces
| Output | Example (LEGO assembly, 284 s) |
|---|---|
| Bimanual chart, second by second, as rows | 123 rows, Excel in the course format + interactive review |
| Improvement plan **in seconds per unit**, each lever with its evidence and assumption | 284 s → **≈ 215 s (−24 %)**, **+32 % output per shift**; top lever: a fixture that frees the left hand (≈ 41 s) |
| Method alerts (hands crossing, long reaches, both hands idle, hand used as a vise…) | with the fix for each |
| What it is worth | labour hours and money per year from your units, shift and wage |

The plan is an **estimate to prioritise changes**; to check a change, film several cycles after it and compare the
observed cycle times with Gilbreth.

## How it works
1. **Hands** — MediaPipe tracks both hands at 10 fps; handedness from a ±2 s majority vote.
2. **Operation sheet** — Gemma looks at 6 frames of the whole video and writes what is assembled, where the parts,
   tools and documents are, and the typical cycle. Nothing about the product is hard-coded.
3. **Every second** — Gemma 4 31B on AMD GPUs gets 4 frames with the hands marked, a crop of each hand and
   hand-speed data, and returns the activity of each hand as schema-checked JSON.
4. **Human calibration (the human + AI loop)** — the engineer corrects the first cycle (≥ 30 s) in the review page.
   A small gradient-boosting model learns from that correction how much to trust the vision model versus the hand
   motion. A **gate** then checks, on the reviewed seconds and without letting the model see itself, that it really
   beats the vision model. Only then is the rest of the video recoded; otherwise Gemma's codes stay.
5. **Rows, alerts, plan** — a new row whenever either hand changes activity; rule-based method alerts from hand
   tracking and codes; the improvement planner (`agent/mejora.py`) turns the chart into seconds saved per lever.

## How accurate (measured)
Accuracy = share of (hand, second) pairs with the right activity code. Two tests, each pre-registered and looked at
**once** with the system frozen, each on a person of the KIT Bimanual dataset never used before; the dataset's labels of the first two takes of each
task (≈ 30–40 s) stand in for the engineer's review, takes 2–9 are measured.

| KIT Bimanual, new person | Constant baseline | Gemma alone | **Gilbreth** |
|---|---|---|---|
| **Subject 3, on AMD Token Factory (the shipped system)**, 2,258 hand-seconds | 41.7–41.8 % | 55.4 % | **65.1 %** (±1 s: 80.1 %) |
| · workshop (1,086) / kitchen (1,172) | 41.8 / 41.7 % | 59.3 / 51.9 % | **66.5 / 63.9 %** |
| Subject 1, lab GPU (Gemma 4-bit), 3,305 hand-seconds | — | 67.5 % | **77.1 %** (±1 s: 87.2 %) |
| · workshop (1,347) / kitchen (1,958) | 48.4 / 55.0 % | 69.6 / 66.0 % | **80.3 / 74.9 %** |

The gain over Gemma alone held from one person to the other: +9.6 and +9.7 points.

**The examples in the app, run on AMD Token Factory** (the shipped pipeline, gate on; second looks at data used
during development):
- gearbox, IMPACT operator not in the training data, first 60 s reviewed, human labels from second 60 (307
  hand-seconds): Gemma alone 70.0 % → Gilbreth **73.9 %**;
- LEGO against two batches of blind human labels (92 hand-seconds): 58.7 % → **62.0 %**.

On development data, 63–80 % of the remaining errors sit in the second next to a change of activity. Details, earlier
lab runs and everything we tried and dropped: [`docs/RESULTS.md`](docs/RESULTS.md).

## Run it
**Web app** (examples, hand tracking of your own video on CPU, and the full agent on it when an endpoint is set):
```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```
**Full agent** on AMD Token Factory (shared endpoint; your team's key in `GILBRETH_API_KEY`):
```bash
python scripts/prepare_runs.py runs lego=examples/lego/lego_480p.mp4 gearbox=examples/impact_gearbox/gearbox_480p.mp4   # CPU part
python scripts/tokenfactory_batch.py lego gearbox      # 20 requests per minute, writes docs/benchmark.json
# while Gemma-4-31B-IT is not listed: add --modelo Qwen3.8-Flash-Next --sin-razonar
```
In the app, set `GILBRETH_VLLM_URL=https://developer.amd.com.cn/radeon/api/v1`, `GILBRETH_MODEL=Gemma-4-31B-IT`,
`GILBRETH_JSON_MODE=object`, `GILBRETH_RPM=18` and `GILBRETH_API_KEY` (Streamlit secrets) to chart uploads live;
`GILBRETH_FALLBACK_MODEL=Qwen3.8-Flash-Next` covers the times Gemma is not served (see `docs/AMD.md`).

**Full agent** on your own GPU server with vLLM (see [`docs/AMD.md`](docs/AMD.md) for the MI300X setup):
```bash
vllm serve google/gemma-4-31B-it --max-model-len 16384 --limit-mm-per-prompt '{"image": 8, "video": 0}'
python agent/bimanual.py video.mp4 --salida run1 --base http://127.0.0.1:8000 --modelo google/gemma-4-31B-it --idioma en
# review the first cycle in run1/revisar.html and export the JSON (it downloads as diagrama_revisado.json), then:
python agent/bimanual.py video.mp4 --salida run1 --base http://127.0.0.1:8000 --modelo google/gemma-4-31B-it \
       --calibrar diagrama_revisado.json --calibrar-hasta 60 --idioma en
python scripts/make_example.py run1 video.mp4 examples/my_operation --title "My operation" --copy-video
```
Docker: `docker build -t gilbreth . && docker run -p 8501:8501 gilbreth`.
Wiring check without a large GPU: serve a small model with Ollama (`gemma4:e2b`) and add `--ollama --base
http://127.0.0.1:11434 --modelo gemma4:e2b`. It runs end to end on a laptop GPU; the accuracy figures above are for
the 31B model.

## Licences and data
- Code: **MIT** (this repository).
- **Motion prior** (`models/motion_prior_impact.npz`): features derived from the IMPACT dataset, **CC BY-NC-SA 4.0**,
  published separately with attribution and downloaded on use (`GILBRETH_PRIOR_URL`). Without it the agent runs in
  **MIT-pure** mode (`--sin-previo`), which learns only from your reviewed seconds and measured clearly lower
  (KIT, development: 49.8 % vs 62.4 %), because the gate cannot trust a model trained on so few seconds.
- `examples/impact_gearbox/` is **CC BY-NC-SA 4.0, not MIT**: video, frames and labels from the IMPACT dataset,
  with attribution and the changes made, in that folder's README. Non-commercial use only.
- `examples/factory_plastic/`, `factory_cardboard/` and `factory_screw/` are **CC BY 4.0**: excerpts of *Factory
  Manipulation Videos* by Procedural Robotics Inc. (Hugging Face `procedural-robotics/factory-manipulation-videos`),
  re-encoded and cut to seconds 60–210; details in [`docs/FACTORY_EXAMPLES_LICENSE.md`](docs/FACTORY_EXAMPLES_LICENSE.md).
- The LEGO example video is shared with the permission of the person filmed.
- Datasets used for measurement: IMPACT (Hugging Face `KratosWen/IMPACT`, CC BY-NC-SA 4.0) and KIT Bimanual Actions
  (Dreher, Wächter, Asfour; `bimanual-actions.humanoids.kit.edu`).

## Limits
- Observed times, not standard times: no performance rating or allowances yet; one cycle is not a standard.
- Tasks where operating means moving the hand a lot (kitchen: stirring, wiping) score lower (KIT kitchen vs workshop:
  74.9 vs 80.3 % on subject 1, 63.9 vs 66.5 % on AMD with subject 3): the learned motion confuses operation with transport, which is why the gate exists.
- The improvement plan is a scenario estimate with visible assumptions, not a measurement.

## Timeline
Preparation (data exploration, measurement protocol, first prototypes) started on 9 Oct 2026, before the kickoff.
During the event: the runs on AMD Token Factory, the improvement planner, this app and the submission material.
