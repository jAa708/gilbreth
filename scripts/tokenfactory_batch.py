"""Gilbreth on AMD Token Factory: the shared Gemma 4 31B endpoint that AMD serves on its own GPUs for the hackathon.
Runs the prepared runs/ one after another (the CPU part is already done by scripts/prepare_runs.py), keeps under the
shared limit of 20 requests per minute, and writes docs/benchmark.json for the app.

The key is read from GILBRETH_API_KEY and never written anywhere.
Usage: python scripts/tokenfactory_batch.py lego gearbox plastic cardboard screw [--rpm 18] [--hilos 4]"""
import argparse, json, os, subprocess, sys, time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ap = argparse.ArgumentParser()
ap.add_argument('runs', nargs='+')
ap.add_argument('--base', default=os.environ.get('GILBRETH_VLLM_URL', 'https://developer.amd.com.cn/radeon/api/v1'))
ap.add_argument('--modelo', default=os.environ.get('GILBRETH_MODEL', 'Gemma-4-31B-IT'))
ap.add_argument('--rpm', default='18')
ap.add_argument('--hilos', default='4')
ap.add_argument('--carpeta', default=str(RAIZ / 'runs'), help='folder with the prepared runs')
ap.add_argument('--gpu', default='AMD GPUs (AMD Token Factory, shared Gemma 4 endpoint)')
a = ap.parse_args()
if not os.environ.get('GILBRETH_API_KEY'):
    sys.exit('Set GILBRETH_API_KEY first (the Token Factory key of your team).')
runs = Path(a.carpeta)
env = {**os.environ, 'PYTHONIOENCODING': 'utf-8', 'GILBRETH_JSON_MODE': 'object', 'GILBRETH_RPM': a.rpm,
       'GILBRETH_LATENCIAS': str(runs / 'latencias.jsonl')}
for r in a.runs:
    d = runs / r
    cmd = [sys.executable, str(RAIZ / 'agent' / 'bimanual.py'), str(d / 'video.mp4'), '--salida', str(d), '--base', a.base,
           '--modelo', a.modelo, '--idioma', 'en', '--hilos', a.hilos, '--puntos', str(d / 'puntos.npz')]
    if (d / 'revisado.json').exists():
        cmd += ['--calibrar', str(d / 'revisado.json')]
    t0 = time.time()
    with open(d / 'log.txt', 'w', encoding='utf-8') as log:
        p = subprocess.run(cmd, env=env, stdout=log, stderr=subprocess.STDOUT)
    seg = round(time.time() - t0)
    print(f'{r}: exit {p.returncode} in {seg} s', flush=True)
    if p.returncode == 3:
        sys.exit('Daily quota used up: run the remaining videos after it resets (midnight Beijing time, 16:00 UTC).')
    if p.returncode != 0:
        sys.exit(f'{r} failed: see {d / "log.txt"}')
    with open(runs / 'tiempos.csv', 'a', encoding='utf-8') as f:
        f.write(f'{r},{seg}\n')
res = subprocess.run([sys.executable, str(RAIZ / 'scripts' / 'benchmark_summary.py'), str(runs), a.modelo],
                     capture_output=True, text=True, check=True, encoding='utf-8')
banco = json.loads(res.stdout)
banco['gpu'] = a.gpu
banco['endpoint'] = 'AMD Token Factory (developer.amd.com.cn/radeon/api), shared, 20 requests per minute per team'
(runs / 'benchmark.json' if a.carpeta != str(RAIZ / 'runs') else RAIZ / 'docs' / 'benchmark.json').write_text(json.dumps(banco, indent=1), encoding='utf-8')
print(json.dumps(banco.get('total', {}), indent=1))
