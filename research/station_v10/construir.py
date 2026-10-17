"""v10 «modo estación»: filas por mano y segundo para aprender de TODOS los segundos etiquetados de otras personas que
hacen las mismas tareas (KIT Bimanual Actions). Una fila = una mano en un segundo: movimiento del seguidor de manos
(agent/movimiento.py: la mano en s-1, s, s+1 y la otra en s; s-2 y s+2; medios segundos; perfil a 10 Hz) + los
códigos y atributos de Gemma (s-2..s+2 de esa mano, la otra en s-1..s+1) + la tarea + el tiempo relativo en la toma.
Verdad: kit_verdad.verdad, 4 códigos (OP, TR, S, D) y la marca de excluir.
Rutas: rutas.py (variables de entorno). Es el código de gilbreth_noche_15oct/v10/construir.py con las rutas
configurables; los rasgos son los mismos.
Uso: python research/station_v10/construir.py --sujeto 1 2 3 5 6 --prueba 4
     (--prueba: sujeto nuevo, del que solo se lee la verdad de sus tomas 0-1, las revisadas)"""
import argparse, json, sys
from pathlib import Path

import numpy as np

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
sys.path.insert(0, str(AQUI.parent.parent / 'agent'))
import kit_verdad  # noqa: E402
import movimiento as mv  # noqa: E402
import rutas  # noqa: E402
from manos import cargar, pista  # noqa: E402

TAREAS = ('task_1_k_cooking', 'task_2_k_cooking_with_bowls', 'task_3_k_pouring', 'task_4_k_wiping', 'task_5_k_cereals',
          'task_6_w_hard_drive', 'task_7_w_free_hard_drive', 'task_8_w_hammering', 'task_9_w_sawing')
CODS = ('OP', 'TR', 'TR+OP', 'S', 'D', 'NV')
ATRIBUTOS = {'where_first': ('supply_area', 'work_point', 'document_area', 'in_between', 'elsewhere', 'not_visible'),
             'where_last': ('supply_area', 'work_point', 'document_area', 'in_between', 'elsewhere', 'not_visible'),
             'grips': ('workpiece', 'part', 'tool', 'document', 'nothing'), 'motion': ('still', 'travel', 'fine_work')}
BOOLEANOS = ('works_on_workpiece', 'only_holds')


def leer_txt(f):
    return {int(x.split(':')[0]): tuple(x.split(':', 1)[1].split('/')) for x in Path(f).read_text().split()}


def leer_pred(f):
    p = json.loads(Path(f).read_text(encoding='utf-8'))
    V = {int(round(o['t0'])): (o['md'], o['mi']) for o in p}
    A = {}
    for o in p:
        c = o.get('crudo') or {}
        if o.get('relleno') or not isinstance(c, dict):          # ventana rellenada con el vecino: sin atributos
            continue
        A[int(round(o['t0']))] = (c.get('right_hand'), c.get('left_hand'))
    return V, A


def gemma(sujeto, c):
    """({s: (md, mi)}, {s: (atributos R, atributos L)} o None) de Gemma para la toma c; (None, None) si no hay."""
    d = rutas.gemma(sujeto)
    if (d / c / 'pred.json').exists():
        V, A = leer_pred(d / c / 'pred.json')
    elif (d / f'vision_{c}.txt').exists():                       # formato compacto: solo códigos
        V, A = leer_txt(d / f'vision_{c}.txt'), None
    else:
        return None, None
    if (d / 'cruces.json').exists():                             # marcas R/L cruzadas en esa corrida
        cr = json.loads((d / 'cruces.json').read_text(encoding='utf-8')).get(c, {})
        cruza = lambda s: cr.get(str(s), 0) > 0.5
        V = {s: ((v[1], v[0]) if cruza(s) else v) for s, v in V.items()}
        A = {s: ((v[1], v[0]) if cruza(s) else v) for s, v in A.items()} if A else A
    return V, A


def una(c):
    return [1.0 if c == x else 0.0 for x in CODS] if c else [np.nan] * len(CODS)


def una_atr(h):
    """Los atributos de una mano (dict de Gemma) en one-hot; NaN si no hay."""
    if not isinstance(h, dict):
        return [np.nan] * (sum(len(v) for v in ATRIBUTOS.values()) + len(BOOLEANOS))
    out = []
    for k, vals in ATRIBUTOS.items():
        out += [1.0 if h.get(k) == v else 0.0 for v in vals]
    return out + [1.0 if h.get(b) is True else (0.0 if h.get(b) is False else np.nan) for b in BOOLEANOS]


def perfil(sg, k, s):
    """Velocidad, dedos y distancia al punto de trabajo de la mano k en 20 tramos de 0,1 s de [s-0,5, s+1,5)."""
    out = []
    t = sg['t']
    for clave in ('vel', 'dedos', 'dist_trab'):
        serie = sg[k][clave]
        for i in range(20):
            t0 = s - 0.5 + i * 0.1
            v = serie[(t >= t0) & (t < t0 + 0.1)]
            v = v[~np.isnan(v)]
            out.append(float(v.mean()) if len(v) else np.nan)
    return out


def fila(sg, V, A, k, s, dur, tarea):
    j = 0 if k == 'R' else 1
    g = lambda t, jj: (V or {}).get(t, (None, None))[jj]
    at = lambda t, jj: (A or {}).get(t, (None, None))[jj]
    vis = []
    for d in (-2, -1, 0, 1, 2):
        vis += una(g(s + d, j))
    vis += una(g(s, 1 - j)) + una(g(s - 1, 1 - j)) + una(g(s + 1, 1 - j))
    vis += una_atr(at(s - 1, j)) + una_atr(at(s, j)) + una_atr(at(s + 1, j)) + una_atr(at(s, 1 - j))
    otra = 'L' if k == 'R' else 'R'
    mov = (mv.vector(sg, k, s) + mv.stats(sg, k, s - 2, s - 1) + mv.stats(sg, k, s + 2, s + 3)
           + mv.stats(sg, otra, s - 1, s) + mv.stats(sg, otra, s + 1, s + 2))
    for a in (-0.5, 0.0, 0.5, 1.0):
        mov += mv.stats(sg, k, s + a, s + a + 0.5)
    for a in (0.0, 0.5):
        mov += mv.stats(sg, otra, s + a, s + a + 0.5)
    mov += perfil(sg, k, s)
    return mov + vis + [1.0 if t == tarea else 0.0 for t in TAREAS] + [s / max(dur, 1), float(s), float(dur)]


def nombres():
    st = mv.STATS
    m = (mv.nombres() + [f'{x}_ant2' for x in st] + [f'{x}_sig2' for x in st] + [f'otra_{x}_ant' for x in st]
         + [f'otra_{x}_sig' for x in st])
    m += [f'h{a}_{x}' for a in ('m05', '0', '05', '1') for x in st] + [f'oh{a}_{x}' for a in ('0', '05') for x in st]
    m += [f'p_{c}_{i}' for c in ('vel', 'dedos', 'dist_trab') for i in range(20)]
    v = [f'g{d}_{c}' for d in ('m2', 'm1', '0', 'p1', 'p2') for c in CODS] + [f'go{d}_{c}' for d in ('0', 'm1', 'p1')
                                                                             for c in CODS]
    atr = [f'{k}={x}' for k, vals in ATRIBUTOS.items() for x in vals] + list(BOOLEANOS)
    v += [f'a{d}_{n}' for d in ('m1', '0', 'p1', 'o0') for n in atr]
    return m + v + list(TAREAS) + ['t_rel', 't', 'dur']


def construir(sujeto, tomas_con_verdad=range(10)):
    """tomas_con_verdad: para el sujeto nuevo solo (0, 1); en las demás la verdad no se lee (y = '', excluir)."""
    base = rutas.sujeto(sujeto)
    info = json.loads((base / 'mp4' / 'meta.json').read_text())
    X, meta = [], []
    for tarea in TAREAS:
        for t in range(10):
            c = f'{tarea}__take_{t}'
            npz = base / 'puntos' / f'{c}.npz'
            if not npz.exists() or c not in info:
                continue
            sg = mv.senales(pista(*cargar(npz)))
            V, A = gemma(sujeto, c)
            dur = int(info[c]['cuadros'] / info[c]['fps'] + 0.5)
            if t in tomas_con_verdad:
                G4 = kit_verdad.verdad(tarea, f'take_{t}', info[c]['fps'], sujeto)
                segs = sorted(G4)
            else:
                segs, G4 = list(range(dur)), None
            for s in segs:
                for j, k in enumerate('RL'):
                    X.append(fila(sg, V, A, k, s, dur, tarea))
                    meta.append((sujeto, tarea, t, s, j, G4[s][j] if G4 else '', bool(G4[s][2 + j]) if G4 else True,
                                 (V or {}).get(s, (None, None))[j] or '', V is not None))
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
        np.savez_compressed(rutas.SALIDA / f'filas_s{su}.npz', X=X, meta=np.array(meta, dtype=object),
                            nombres=np.array(nombres()))
        print(f'sujeto {su}: {len(meta)} manos-segundo, {X.shape[1]} rasgos'
              + (' (verdad solo de las tomas 0-1)' if su in a.prueba else ''), flush=True)
