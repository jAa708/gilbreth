# Running Gilbreth on AMD Developer Cloud (Instinct MI300X)

Everything runs on one VM: the video is uploaded to it, MediaPipe runs on CPU and Gemma 4 31B on the GPU.

## 1. Model server (vLLM on ROCm)
```bash
docker run -d --name gemma --network host --ipc host --device /dev/kfd --device /dev/dri \
  --group-add video --shm-size 16g -v ~/.cache/huggingface:/root/.cache/huggingface \
  vllm/vllm-openai-rocm:gemma4 \
  vllm serve google/gemma-4-31B-it --max-model-len 16384 --limit-mm-per-prompt '{"image": 8, "video": 0}'
until curl -s localhost:8000/health; do sleep 5; done; echo READY
```
- The MI300X (192 GB HBM3) fits the full **31B in BF16** (development used the 4-bit QAT build on a 40 GB GPU).
- Do not raise the image token budget to 560: in our tests accuracy dropped (79 → 72 %).
- AITER (`VLLM_ROCM_USE_AITER=1`) is compared on and off before use.

## 2. The agent
```bash
pip install -r requirements.txt
python agent/bimanual.py video.mp4 --salida run1 --base http://127.0.0.1:8000 --modelo google/gemma-4-31B-it \
       --hilos 16 --idioma en
```
Outputs in `run1/`: `diagrama.json`, `diagrama_bimanual.xlsx` (course format), `revision.html`, `revisar.html`
(edit and approve against the video), `errores.json`.

## 3. Benchmark reported to the judges
Seconds of video processed per minute, p50/p95 latency per request, GPU memory, and accuracy on the same reference
labels as development. Results go to `docs/benchmark.json` and appear in the app.
