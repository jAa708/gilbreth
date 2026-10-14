"""Summarise an AMD batch (scripts/amd_batch.sh) into docs/benchmark.json for the app.
Inputs in RUNS_DIR: tiempos.csv (run,wall seconds), latencias.jsonl (one line per model request), rocm_smi.json.
Usage: python scripts/benchmark_summary.py runs MODEL > docs/benchmark.json"""
import json, statistics, sys
from collections import defaultdict
from pathlib import Path

runs, modelo = Path(sys.argv[1]), sys.argv[2] if len(sys.argv) > 2 else ''
out = {'modelo': modelo, 'gpu': '', 'runs': {}, 'pasos': {}}
for linea in (runs / 'tiempos.csv').read_text().split():
    nombre, s = linea.split(',')
    if nombre == 'server_ready_s':
        out['server_ready_s'] = int(s)
        continue
    d = json.loads((runs / nombre / 'diagrama.json').read_text(encoding='utf-8'))
    video_s = d['indicadores']['duracion_s']
    out['runs'][nombre] = {'video_s': video_s, 'wall_s': int(s), 'video_s_per_min': round(60 * video_s / int(s), 1)}
por = defaultdict(list)
for linea in (runs / 'latencias.jsonl').read_text(encoding='utf-8').splitlines():
    try:
        x = json.loads(linea)
    except ValueError:                       # línea rota (escritura concurrente): se descarta
        continue
    por[x['paso']].append(x)
for paso, xs in por.items():
    lat = sorted(x['s'] for x in xs)
    out['pasos'][paso] = {'requests': len(xs), 'p50_s': round(statistics.median(lat), 2),
                          'p95_s': round(lat[min(len(lat) - 1, int(0.95 * len(lat)))], 2),
                          'prompt_tokens_mean': round(statistics.mean(x.get('prompt_tokens', 0) for x in xs)),
                          'completion_tokens_mean': round(statistics.mean(x.get('completion_tokens', 0) for x in xs))}
smi = runs / 'rocm_smi.json'
if smi.exists():
    try:
        tarjetas = json.loads(smi.read_text())
        c = next(iter(tarjetas.values()))
        out['gpu'] = c.get('Card series') or c.get('Card SKU') or ''
        usado, total = c.get('VRAM Total Used Memory (B)'), c.get('VRAM Total Memory (B)')
        if usado and total:
            out['vram_used_gb'], out['vram_total_gb'] = round(int(usado) / 1e9, 1), round(int(total) / 1e9, 1)
    except (ValueError, StopIteration, AttributeError):
        pass
tot_v = sum(r['video_s'] for r in out['runs'].values())
tot_w = sum(r['wall_s'] for r in out['runs'].values())
if tot_w:
    out['total'] = {'video_s': tot_v, 'wall_s': tot_w, 'video_s_per_min': round(60 * tot_v / tot_w, 1)}
print(json.dumps(out, indent=1))
