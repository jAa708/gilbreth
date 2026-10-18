"""How much review does station mode need? (DEVELOPMENT, 17 Oct; subject 4 is not touched.)
Station mode needs coworkers reviewed at the same station; how many minutes of ONE coworker are enough? For each pair
(new person t, coworker c) of KIT subjects 1, 2, 3, 5 and 6: the shipped per-second system (sistema.ajustar_predecir,
per-second labels as the review page exports them, CAL 5) learns from the first k takes of each task of the coworker
plus the reviewed takes 0-1 of t, and is scored on takes 2-9 of t (exact code per hand and second, the usual metric).
k = 1, 2, 4, 10. It also reports how many seconds of the coworker's video that is, per task.
It is gilbreth_noche_15oct/v10/cuanta_revision.py with configurable paths (rutas.py).
Usage: python research/station_v10/cuanta_revision.py [subjects]   (no arguments: all five; the 17 Oct run was one
process per new person, summed in resultado_cuanta_revision_todos.json: k=1 81.9 %, 2 82.4 %, 4 82.7 %, 10 83.3 %)"""
import json, sys, time
from collections import defaultdict
from pathlib import Path

import numpy as np

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import rutas  # noqa: E402
import sistema as si  # noqa: E402

sys.stdout.reconfigure(encoding='utf-8')
DEV = [1, 2, 3, 5, 6]
KS = [1, 2, 4, 10]   # without a coworker (k = 0) it is the shipped mode; not fitted here (empty columns)
S = {}
for su in DEV:
    d = np.load(rutas.SALIDA / f'filas_s{su}.npz', allow_pickle=True)
    S[su], ns = (d['X'], d['meta']), list(d['nombres'])


def recorta(su, k):
    X, M = S[su]
    sel = np.array([m[2] < k for m in M])
    return X[sel], M[sel]


def puntua(P, M):
    y = np.array([m[5] for m in M])
    ok = si.validas(M) & np.array([m[2] >= 2 for m in M])
    return int((si.CLASES[P.argmax(1)][ok] == y[ok]).sum()), int(ok.sum())


segundos = {k: np.mean([sum(1 for m in S[c][1] if m[2] < k) / 2 / 9 for c in DEV]) for k in KS if k}
print('seconds of coworker video per task:', {k: round(v, 1) for k, v in segundos.items()}, flush=True)
RES = defaultdict(lambda: [0, 0])
t0 = time.time()
PERSONAS = [int(x) for x in sys.argv[1:]] or DEV
for t in PERSONAS:
    nuevo = S[t]
    for c in DEV:
        if c == t:
            continue
        for k in KS:
            x, n = puntua(si.ajustar_predecir([recorta(c, k)], nuevo, ns, cal=5.0, auto=False), nuevo[1])
            RES[k][0] += x; RES[k][1] += n
    print(f'  subject {t} done ({time.time() - t0:.0f} s)', flush=True)
for k in KS:
    x, n = RES[k]
    print(f'k = {k:>2} takes per task of the coworker ({segundos.get(k, 0):.0f} s per task): {100 * x / n:.1f} %', flush=True)
(rutas.SALIDA / ('resultado_cuanta_revision' + ''.join(f'_{t}' for t in PERSONAS) + '.json')).write_text(json.dumps(
    {'acierto': {k: [RES[k][0], RES[k][1], round(100 * RES[k][0] / RES[k][1], 1)] for k in KS},
     'segundos_por_tarea': segundos}, indent=1), encoding='utf-8')
