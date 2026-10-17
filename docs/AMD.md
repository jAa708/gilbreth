# Running Gilbreth on AMD

## Option A — AMD Token Factory (what the submission uses)
Token Factory is AMD's model API catalog for the event: OpenAI-compatible endpoints running on AMD GPUs, with one
key per team. Gemma 4 31B is listed as `Gemma-4-31B-IT` (text and images).

- Base URL `https://developer.amd.com.cn/radeon/api/v1`; key in `GILBRETH_API_KEY` (never in files or the repo).
- Shared limits per team key: 20 requests per minute per account, 8 at a time, and a daily spend cap of US$1 that
  resets at midnight Beijing time (16:00 UTC; response headers `x-ratelimit-*-user-daily-usd`); 429 answers carry
  `Retry-After`. The agent keeps under the limit itself (`GILBRETH_RPM=18`) and backs off on 429.
- Only `json_object` structured output is accepted for this model, so the agent sends `GILBRETH_JSON_MODE=object` and
  puts the JSON schema in the prompt; when the daily cap is used up it stops cleanly (exit code 3).

```bash
export GILBRETH_API_KEY=...          # your team's key, in your own shell
python scripts/tokenfactory_batch.py lego gearbox plastic cardboard screw
```

Observed on 14 Oct: Gemma is marked experimental and its backend sometimes runs out of GPU memory for image
requests while text still works (HTTP 500, "GPU 0 has a total capacity of 191.69 GiB": the memory size of an AMD
Instinct MI300X). The app therefore checks the endpoint with a tiny image before a live run, and the agent retries
500/502/503/504 with backoff.

On 14 Oct that lasted from 20:21 to 00:49 (Colombia time) while other vision models on the same service kept
answering. If `GILBRETH_FALLBACK_MODEL` is set (we use `Qwen3.8-Flash-Next`, screened in `docs/RESULTS.md`: 56.9 %
against 55.3 % for Gemma on the same development seconds), the app runs the live demo on that model when Gemma fails the
image check, and says so on screen; the examples and the measurements are always Gemma's.

On 15 Oct, around 10:39 (Colombia time), `Gemma-4-31B-IT` left the Token Factory catalog (`/models` no longer lists it and
requests answer "Requested model Gemma-4-31B-IT not supported"). The five app examples, the benchmark and the KIT
subject 3 test were computed before that; the KIT subject 4 tests ran on 17 Oct, after Gemma came back. While Gemma is
not listed, the live demo runs on the fallback and says so before the upload.
It was listed again on 16 Oct at 22:20 (Colombia time), answering text and image requests, and the app picked it up on
its own (every 5 minutes it checks whether Gemma answers an image request). A full KIT subject (90 takes, about 20
minutes of video) cost about
US$0.15 of the daily quota with Gemma.

One second of video costs about 1.45 requests (one per second plus one per chart row for the descriptions; 1,390
requests for 957.7 s of video in the five examples), so a 5-minute video needs at least 24 minutes at 18 requests per
minute, plus request latency and retries on the shared endpoint (median 19.5 s per coding request on 14 Oct).

## Option B — your own AMD Instinct MI300X (AMD Developer Cloud)

The CPU part (hand tracking and per-second packages) is prepared beforehand on any computer with
`scripts/prepare_runs.py`. The VM on AMD Developer Cloud then only does the GPU part:
- the operation sheet;
- the per-second coding;
- the row descriptions.

Everything is batched in one session so the VM can be destroyed right after.

## 1. Prepare the runs (any computer, CPU)
```bash
python scripts/prepare_runs.py runs lego=lego.mp4 gearbox=gearbox.mp4 plastic=plastic.mp4 cardboard=cardboard.mp4 screw=screw.mp4
# each runs/NAME/ gets puntos.npz, ventanas.json, img/, escena/; add runs/NAME/video.mp4 (480p) and, if an engineer
# reviewed the first cycle, runs/NAME/revisado.json (the JSON exported from the review page)
```

## 2. On the VM
```bash
# copy the repo, runs/ and models/motion_prior_impact.npz; log in to Hugging Face yourself (Gemma licence accepted)
bash scripts/amd_batch.sh google/gemma-4-31B-it            # or name the runs: ... google/gemma-4-31B-it lego screw
```

The script:
1. starts vLLM on ROCm, using the image `vllm/vllm-openai-rocm:gemma4` (its entrypoint is `vllm serve`) with `--model MODEL
   --max-model-len 16384 --limit-mm-per-prompt '{"image": 8, "video": 0}'`; it stops with the server log if vLLM
   is not healthy within 40 min;
2. waits for `/health`;
3. runs `agent/bimanual.py` on every run, with `--calibrar` where a review exists and `--idioma en`;
4. logs the latency and tokens of every successful request (`GILBRETH_LATENCIAS`);
5. reads GPU memory with `rocm-smi`;
6. writes `docs/benchmark.json`, which the app shows under *Accuracy & AMD*.

- The MI300X (192 GB HBM3) fits the full **31B in BF16**. Development used the 4-bit QAT build on a 40 GB GPU.
- Do not raise the image token budget to 560: in our tests accuracy dropped (79 → 72 %).
- AITER (`VLLM_ROCM_USE_AITER=1`) is off by default; if you switch it on, compare it with a short run first.

## 3. Back on your computer
```bash
python scripts/make_example.py runs/lego runs/lego/video.mp4 examples/lego --engine "Gemma 4 31B (BF16) on AMD Instinct MI300X (vLLM + ROCm)" --copy-video
```
Then **destroy the VM**: a stopped VM keeps billing.
