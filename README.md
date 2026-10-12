# ⏱️ Gilbreth — AI motion study from a workstation video

**A phone video of a manual operation goes in. A draft bimanual chart, method alerts and an improvement plan in
seconds come out — for the methods engineer to review and approve.**

Built for the **AMD Developer Hackathon: ACT III** (Track 1, *Intelligent Industry*) by team **ArkhanLabs**
(Juan David Sabogal Orozco, industrial engineering student, Cali, Colombia).
Vision model: **Gemma 4 31B** served with **vLLM on an AMD Instinct MI300X (ROCm)**. Hand tracking: **MediaPipe**.

> Named after Frank and Lillian Gilbreth, who filmed workers a century ago to study and improve their motions.

## The problem
Methods engineers improve manual work (assembly, packing, kitting) with the **bimanual chart**: what the left and
right hand do, row by row (ILO symbols ○ operation, ⇨ transport, D delay, ▽ hold). Drawing it by hand from a video is
slow: about **one hour of one person for a 4.7-minute video** in our own course project. Small and mid-size factories
rarely do it at all, so they miss the classic gains: fixtures that free the holding hand, balanced hands, parts
within reach.

**Who uses Gilbreth:** industrial/methods engineers and plant supervisors. **What it improves:** time per unit of a
manual operation (and the time it takes to analyse it).

## What it produces
| Output | Example (LEGO assembly, 284 s) |
|---|---|
| Bimanual chart, second by second, as rows | 104 rows, Excel in the course format + interactive review |
| Improvement plan **in seconds per unit**, each lever with its evidence and assumption | 284 s → **≈ 227 s (−20 %)**, **+25 % output per shift**; top lever: a fixture that frees the left hand (≈ 38 s) |
| Method alerts (hands crossing, long reaches, both hands idle, hand used as a vise…) | with the fix for each |
| What it is worth | labour hours and money per year from your units, shift and wage |

The plan is an **estimate to prioritise changes**; the real saving is measured by filming again after the change and
running Gilbreth on the new video.

## How it works
1. **Hands** — MediaPipe tracks both hands at 10 fps; handedness from a ±2 s majority vote.
2. **Operation sheet** — Gemma looks at 6 frames of the whole video and writes what is assembled, where the parts,
   tools and documents are, and the typical cycle. Nothing about the product is hard-coded.
3. **Every second** — Gemma 4 31B on the MI300X gets 4 frames with the hands marked, a crop of each hand and
   hand-speed data, and returns the activity of each hand as schema-checked JSON.
4. **Human calibration (the human + AI loop)** — the engineer corrects the first cycle (≥ 30 s) in the review page.
   A small gradient-boosting model learns from that correction how much to trust the vision model versus the hand
   motion. A **gate** then checks, on the reviewed seconds and without letting the model see itself, that it really
   beats the vision model. Only then is the rest of the video recoded; otherwise Gemma's codes stay.
5. **Rows, alerts, plan** — a new row whenever either hand changes activity; rule-based method alerts from hand
   tracking and codes; the improvement planner (`agent/mejora.py`) turns the chart into seconds saved per lever.

## How accurate (measured)
Accuracy = share of (hand, second) pairs with the right activity code. Each test set was looked at **once**, with the
system frozen and the protocol written down beforehand.

| Test set | Constant baseline | Gemma alone | **Gilbreth (30–70 s reviewed)** |
|---|---|---|---|
| KIT Bimanual, **new person**, workshop + kitchen (3,305 hand-seconds) | 48–55 % | 67.5 % | **77.1 %** (±1 s: 87.2 %) |
| LEGO assembly, blind human labels (92) | — | 64.1 % | **71.7 %** |
| IMPACT assembly, 4 new operators (982) | 45.7 % | 70.0 % | **73.6 %** |

Most remaining errors are about *when* an activity starts or ends (±1 s), not *which* activity it is. Details and
everything we tried and dropped: [`docs/RESULTS.md`](docs/RESULTS.md).

## Run it
**Web app** (examples + hand tracking on your own video, CPU only):
```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```
**Full agent** on a GPU server with vLLM (see [`docs/AMD.md`](docs/AMD.md) for the MI300X setup):
```bash
vllm serve google/gemma-4-31B-it --max-model-len 16384 --limit-mm-per-prompt '{"image": 8, "video": 0}'
python agent/bimanual.py video.mp4 --salida run1 --base http://127.0.0.1:8000 --modelo google/gemma-4-31B-it --idioma en
# review the first cycle in run1/revisar.html, export revisado.json, then:
python agent/bimanual.py video.mp4 --salida run1 --base http://127.0.0.1:8000 --modelo google/gemma-4-31B-it \
       --calibrar revisado.json --calibrar-hasta 60 --idioma en
python scripts/make_example.py run1 video.mp4 examples/my_operation --title "My operation"
```
Docker: `docker build -t gilbreth . && docker run -p 8501:8501 gilbreth`.

## Licences and data
- Code: **MIT** (this repository).
- **Motion prior** (`models/motion_prior_impact.npz`): features derived from the IMPACT dataset, **CC BY-NC-SA 4.0**,
  published separately with attribution and downloaded on use (`GILBRETH_PRIOR_URL`). Without it the agent runs in
  **MIT-pure** mode (`--sin-previo`), which learns only from your reviewed seconds and measured clearly lower
  (KIT, development: 49.8 % vs 62.4 %), because the gate cannot trust a model trained on so few seconds.
- No dataset videos are included. The LEGO example video is shared with the permission of the person filmed.
- Datasets used for measurement: IMPACT (Hugging Face `KratosWen/IMPACT`, CC BY-NC-SA 4.0) and KIT Bimanual Actions
  (Dreher, Wächter, Asfour; `bimanual-actions.humanoids.kit.edu`).

## Honest limits
- Observed times, not standard times: no performance rating or allowances yet; one cycle is not a standard.
- Best on assembly and part handling from a top-down camera. In tasks where operating means moving the hand a lot
  (kitchen: stirring, wiping) the learned motion confuses operation with transport — that is why the gate exists.
- The improvement plan is an upper-bound estimate with visible assumptions, not a measurement.

## Timeline
Preparation (data exploration, measurement protocol, first prototypes) started on 9 Oct 2026, before the kickoff.
During the event: the run on AMD Developer Cloud, the improvement planner, this app and the submission material.
