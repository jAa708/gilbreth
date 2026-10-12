"""Turn a result folder from agent/bimanual.py into an example the app can show.
Usage: python scripts/make_example.py RESULT_DIR VIDEO.mp4 examples/NAME [--title "..."] [--engine "..."]
Copies diagrama.json / errores.json / calibracion.json and extracts one 320-px frame per chart row (row midpoint)."""
import argparse, json, shutil
from pathlib import Path

import cv2

ap = argparse.ArgumentParser()
ap.add_argument('resultado'), ap.add_argument('video'), ap.add_argument('destino')
ap.add_argument('--title', default='')
ap.add_argument('--engine', default='', help='e.g. "Gemma 4 31B (BF16) on AMD Instinct MI300X (vLLM + ROCm)"')
a = ap.parse_args()
res, dst = Path(a.resultado), Path(a.destino)
(dst / 'frames').mkdir(parents=True, exist_ok=True)
for f in ('diagrama.json', 'errores.json', 'calibracion.json', 'verdad.json'):
    if (res / f).exists():
        shutil.copy(res / f, dst / f)
d = json.loads((dst / 'diagrama.json').read_text(encoding='utf-8'))
if a.title or a.engine:
    if a.title:
        d['meta']['title_en'] = a.title
    if a.engine:
        d['meta']['motor_en'] = a.engine
    (dst / 'diagrama.json').write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding='utf-8')
cap = cv2.VideoCapture(a.video)
for i, f in enumerate(d['filas']):
    cap.set(cv2.CAP_PROP_POS_MSEC, 1000 * (f['t0'] + f['t1']) / 2)
    ok, fr = cap.read()
    if ok:
        h, w = fr.shape[:2]
        cv2.imwrite(str(dst / 'frames' / f'{i:04d}.jpg'), cv2.resize(fr, (320, round(320 * h / w))),
                    [cv2.IMWRITE_JPEG_QUALITY, 80])
print(len(d['filas']), 'rows ->', dst)
