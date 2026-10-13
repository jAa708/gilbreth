#!/usr/bin/env bash
# Colab (A100) test of Gilbreth on three factory clips from Factory Manipulation Videos (Procedural Robotics Inc.,
# CC BY 4.0): downloads only seconds 60-210 of each take, prepares them on CPU and runs the full agent against the
# vLLM server already listening on :8000. Results: /content/resultados_fabrica.zip
set -uo pipefail
cd /content
MODEL=${1:-google/gemma-4-31B-it-qat-w4a16-ct}
B=https://huggingface.co/datasets/procedural-robotics/factory-manipulation-videos/resolve/main/videos
declare -A TOMA=([plastic]=plastic_assembly_station05_worker032 [cardboard]=cardboard_manipulation_station04_worker026
                 [screw]=screw_assembly_station12_worker003)
pip install -q mediapipe opencv-python-headless openpyxl pillow scikit-learn > /dev/null 2>&1
mkdir -p clips runs
for k in "${!TOMA[@]}"; do
  [ -f "clips/$k.mp4" ] || ffmpeg -hide_banner -loglevel error -y -ss 60 -i "$B/${TOMA[$k]}.mp4" -t 150 \
    -c:v libx264 -crf 23 -preset veryfast -an "clips/$k.mp4" &
done
wait
echo "clips: $(ls clips)"
python g/scripts/prepare_runs.py runs plastic=clips/plastic.mp4 cardboard=clips/cardboard.mp4 screw=clips/screw.mp4
echo "esperando el servidor de Gemma…"
until curl -sf localhost:8000/health > /dev/null; do sleep 15; done
export GILBRETH_LATENCIAS=/content/runs/latencias.jsonl
for k in plastic cardboard screw; do
  t0=$(date +%s)
  python g/agent/bimanual.py "clips/$k.mp4" --salida "runs/$k" --base http://127.0.0.1:8000 --modelo "$MODEL" \
    --hilos 8 --idioma en > "runs/$k/log.txt" 2>&1
  echo "$k,$(( $(date +%s) - t0 ))" >> runs/tiempos.csv
  echo "$k listo en $(( $(date +%s) - t0 )) s"
done
nvidia-smi --query-gpu=name,memory.used,memory.total --format=csv,noheader > runs/gpu.txt
cd runs && zip -q -r /content/resultados_fabrica.zip tiempos.csv latencias.jsonl gpu.txt \
  */diagrama.json */errores.json */ficha.json */pred_v5_vent_agente.json */pred_final.json */filas_desc_agente.json \
  */log.txt */puntos.npz
echo FIN
