"""v10 «modo estación», el modelo a 10 Hz: una fila = una mano en una muestra del seguidor (señales instantáneas
alrededor, ±0,5 s de la propia mano y ±0,2 s de la otra, buscadas por TIEMPO; estadísticas de ventanas de 1 s; los
códigos de Gemma del segundo que contiene la muestra y vecinos; posición dentro del segundo; tarea). Objetivo: el
código del CUADRO de KIT. Para puntuar, final.py promedia por segundo las probabilidades de sus muestras.
Es el código de gilbreth_noche_15oct/v10/cuadros.py con las rutas configurables (rutas.py).
Uso: python research/station_v10/cuadros.py --sujeto 1 2 3 5 6 --prueba 4"""
import argparse, json, sys
from pathlib import Path

import numpy as np

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import construir as co  # noqa: E402  (rutas, Gemma, tareas; pone agent/ en el camino)
import kit_verdad  # noqa: E402
import movimiento as mv  # noqa: E402
import rutas  # noqa: E402
from manos import cargar, pista  # noqa: E402

SENALES = ('vis', 'vel', 'dedos', 'apert', 'pinza', 'dist_otra', 'dist_trab', 'dist_casa')


def instantaneas(sg, k, i, desde, hasta):
    """Señales de la mano k en t + d·0,1 s, la muestra más cercana a menos de 0,05 s (NaN si no hay)."""
    out = []
    t = sg['t']
    t0 = float(t[i])
    for d in range(desde, hasta + 1):
        objetivo = t0 + d * 0.1
        j = int(np.searchsorted(t, objetivo))
        cand = [x for x in (j - 1, j) if 0 <= x < len(t)]
        mejor = min(cand, key=lambda x: abs(t[x] - objetivo)) if cand else None
        ok = mejor is not None and abs(t[mejor] - objetivo) < 0.05
        for c in SENALES:
            out.append(float(sg[k][c][mejor]) if ok else np.nan)
    return out


def fila(sg, V, k, i, tarea, dur):
    t = float(sg['t'][i])
    s = int(np.floor(t))
    j = 0 if k == 'R' else 1
    otra = 'L' if k == 'R' else 'R'
    g = lambda tt, jj: (V or {}).get(tt, (None, None))[jj]
    vis = co.una(g(s, j)) + co.una(g(s - 1, j)) + co.una(g(s + 1, j)) + co.una(g(s, 1 - j))
    est = (mv.stats(sg, k, t - 0.5, t + 0.5) + mv.stats(sg, k, t - 1.5, t - 0.5) + mv.stats(sg, k, t + 0.5, t + 1.5)
           + mv.stats(sg, otra, t - 0.5, t + 0.5))
    return (instantaneas(sg, k, i, -5, 5) + instantaneas(sg, otra, i, -2, 2) + est + vis
            + [1.0 if x == tarea else 0.0 for x in co.TAREAS] + [t - s, s / max(dur, 1), 1.0 if k == 'R' else 0.0])


def nombres():
    st = mv.STATS
    n = [f'{k}{d}_{c}' for k, (a, b) in (('p', (-5, 5)), ('o', (-2, 2))) for d in range(a, b + 1) for c in SENALES]
    n += [f'v{w}_{x}' for w in ('c', 'ant', 'sig', 'otra') for x in st]
    n += [f'g{d}_{c}' for d in ('0', 'm1', 'p1', 'o0') for c in co.CODS] + list(co.TAREAS) + ['pos', 't_rel', 'es_derecha']
    return n


def construir(sujeto, tomas_con_verdad=range(10)):
    base = rutas.sujeto(sujeto)
    info = json.loads((base / 'mp4' / 'meta.json').read_text())
    X, meta = [], []
    for tarea in co.TAREAS:
        for toma in range(10):
            c = f'{tarea}__take_{toma}'
            npz = base / 'puntos' / f'{c}.npz'
            if not npz.exists() or c not in info:
                continue
            fps = info[c]['fps']
            sg = mv.senales(pista(*cargar(npz)))
            V, _ = co.gemma(sujeto, c)
            con_verdad = toma in tomas_con_verdad
            if con_verdad:
                G4 = kit_verdad.verdad(tarea, f'take_{toma}', fps, sujeto)
                FR, FL = kit_verdad.cuadros(tarea, f'take_{toma}', sujeto)
            dur = int(info[c]['cuadros'] / fps + 0.5)
            for i, t in enumerate(sg['t']):
                s = int(np.floor(t))
                if con_verdad and s not in G4:
                    continue
                f = int(round(t * fps))
                for j, k in enumerate('RL'):
                    yc = (FR if j == 0 else FL)[f] if con_verdad and f < len(FR) else None
                    X.append(fila(sg, V, k, i, tarea, dur))
                    meta.append((sujeto, tarea, toma, s, j, G4[s][j] if con_verdad else '',
                                 bool(G4[s][2 + j]) if con_verdad else True, (V or {}).get(s, (None, None))[j] or '',
                                 V is not None, yc or '', round(float(t), 2)))
    return np.array(X, dtype=np.float32), meta


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--sujeto', type=int, nargs='*', default=[1, 2, 3])
    ap.add_argument('--prueba', type=int, nargs='*', default=[])
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding='utf-8')
    rutas.SALIDA.mkdir(parents=True, exist_ok=True)
    for su in a.sujeto + a.prueba:
        X, meta = construir(su, range(10) if su not in a.prueba else (0, 1))
        np.savez_compressed(rutas.SALIDA / f'cuadros_s{su}.npz', X=X, meta=np.array(meta, dtype=object),
                            nombres=np.array(nombres()))
        print(f'sujeto {su}: {len(meta)} manos-muestra, {X.shape[1]} rasgos', flush=True)
