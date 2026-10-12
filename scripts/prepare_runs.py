"""CPU part of the pipeline for several videos at once (steps 1-2 of agent/bimanual.py): hand tracking and per-second
packages. The GPU part (operation sheet, per-second coding, descriptions) then runs on the vLLM server with
agent/bimanual.py pointing at the same result folders, which skips the steps already done.
Usage: python scripts/prepare_runs.py runs NAME=VIDEO.mp4 [NAME=VIDEO.mp4 ...]"""
import subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

AG = Path(__file__).resolve().parent.parent / 'agent'
base = Path(sys.argv[1])
trabajos = [a.split('=', 1) for a in sys.argv[2:]]


def preparar(nombre, video):
    sal = base / nombre
    sal.mkdir(parents=True, exist_ok=True)
    npz = sal / 'puntos.npz'
    if not npz.exists():
        subprocess.run([sys.executable, str(AG / 'extraer_puntos.py'), video, str(npz)], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if not (sal / 'ventanas.json').exists():
        subprocess.run([sys.executable, str(AG / 'preparar_paquete.py'), video, str(npz), str(sal)], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return nombre, len(list((sal / 'img').glob('*_f1.jpg')))


with ThreadPoolExecutor(len(trabajos)) as ex:
    for nombre, n in ex.map(lambda t: preparar(*t), trabajos):
        print(f'{nombre}: {n} windows ready')
