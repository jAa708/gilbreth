#!/usr/bin/env bash
# Gilbreth on AMD Developer Cloud (Instinct MI300X): serve Gemma 4 31B with vLLM on ROCm and run every prepared run.
# Before running, on the VM:
#   - copy this repo, runs/ (made by scripts/prepare_runs.py) and models/motion_prior_impact.npz;
#   - log in to Hugging Face yourself (`huggingface-cli login`) with an account that accepted the Gemma licence,
#     or export HF_TOKEN in your own shell. The script never stores tokens.
# Usage: bash scripts/amd_batch.sh [MODEL] [RUN ...]
set -euo pipefail
MODEL=${1:-google/gemma-4-31B-it}
shift || true
RUNS=("$@"); [ ${#RUNS[@]} -eq 0 ] && RUNS=(lego gearbox plastic cardboard screw)
cd "$(dirname "$0")/.."
pip install -q -r requirements.txt

if ! curl -sf localhost:8000/health >/dev/null; then
  docker run -d --name gemma --network host --ipc host --device /dev/kfd --device /dev/dri --group-add video \
    --shm-size 16g -v ~/.cache/huggingface:/root/.cache/huggingface -e HF_TOKEN \
    vllm/vllm-openai-rocm:gemma4 \
    --model "$MODEL" --max-model-len 16384 --limit-mm-per-prompt '{"image": 8, "video": 0}'
  # the image's entrypoint is already `vllm serve`, so the model goes as --model
  t0=$(date +%s)
  until curl -sf localhost:8000/health >/dev/null; do
    if [ $(( $(date +%s) - t0 )) -gt 2400 ] || ! docker ps -q -f name=gemma | grep -q .; then
      echo "vLLM did not become healthy; last log lines:"; docker logs gemma 2>&1 | tail -60; exit 1
    fi
    sleep 10
  done
  echo "server_ready_s,$(( $(date +%s) - t0 ))" >> runs/tiempos.csv
fi

export GILBRETH_LATENCIAS=$PWD/runs/latencias.jsonl
for r in "${RUNS[@]}"; do
  cal=()
  [ -f "runs/$r/revisado.json" ] && cal=(--calibrar "runs/$r/revisado.json")
  t0=$(date +%s)
  python agent/bimanual.py "runs/$r/video.mp4" --salida "runs/$r" --base http://127.0.0.1:8000 --modelo "$MODEL" \
    --hilos 16 --idioma en "${cal[@]}" 2>&1 | tee "runs/$r/log.txt"
  echo "$r,$(( $(date +%s) - t0 ))" >> runs/tiempos.csv
done

rocm-smi --showproductname --showmeminfo vram --json > runs/rocm_smi.json || true
docker logs gemma 2>&1 | tail -300 > runs/vllm_log.txt || true
python scripts/benchmark_summary.py runs "$MODEL" > docs/benchmark.json
cat docs/benchmark.json
echo "Done. Copy runs/ and docs/benchmark.json back, then DESTROY the VM (stopping it keeps billing)."
