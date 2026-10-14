# Running Gilbreth on AMD Developer Cloud (Instinct MI300X)

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
