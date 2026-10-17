"""Station mode at the CHART level on KIT subject 4 (second look, 17 Oct, declared as such): does the per-second gain
carry over to what the engineer reads? The three chart measures of docs/RESULTS.md (share of time per hand and activity,
which hand holds or waits the most, the plan), for Gemma alone (v5), the shipped system (v9) and station mode (v10).
- v10: recomputed from the frozen system (final.py, CAL 5, PESO_A 0.5) trained on subjects 1, 2, 3, 5 and 6 plus the
  reviewed takes 0-1 of subject 4; the script stops unless it reproduces the clean test (83.4 % of 1,888).
- v9 and v5: the per-key dump of the clean test of the shipped system (GILBRETH_S4_V9_DUMP, a JSON
  {"task|take|second|hand": {"v5 modelo solo": code, "v9 (compuerta)": code}}).
- Windows (t0, t1) from subject 4's Gemma pred.json files (rutas.gemma(4)).
Functions copied from the lab script that measured the chart for subject 3 (acuerdo_diagrama.py, 15 Oct).
It is gilbreth_noche_15oct/v10/diagrama_s4_v10.py with configurable paths. Usage: python research/station_v10/diagrama_s4.py"""
import json, os, sys
from collections import Counter
from pathlib import Path

import numpy as np

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
sys.path.insert(0, str(AQUI.parent.parent / 'agent'))
import final  # noqa: E402
import kit_verdad  # noqa: E402
import rutas  # noqa: E402
import sistema as si  # noqa: E402
from construir import TAREAS  # noqa: E402
from mejora import potencial  # noqa: E402
from salidas import unir_filas  # noqa: E402

sys.stdout.reconfigure(encoding='utf-8')
CATS = ('OP', 'TR', 'S', 'D')
A_CAT = {'OP': 'OP', 'TR': 'TR', 'TR+OP': 'TR', 'S': 'S', 'D': 'D', 'NV': 'NV'}
A_CAT_ALT = dict(A_CAT, **{'TR+OP': 'OP'})
MANOS = ('md', 'mi')
SISTEMAS = ('v5', 'v9', 'v10')
ENTRENO = [1, 2, 3, 5, 6]
DUMP = Path(os.environ.get('GILBRETH_S4_V9_DUMP', rutas.SALIDA / 's4_v9_por_clave.json'))


# ------------------------------------------------ copia literal de acuerdo_diagrama.py (15-oct)
def pct(codigos, pesos, mapa=A_CAT):
    T = sum(pesos)
    c = Counter()
    for x, w in zip(codigos, pesos):
        c[mapa[x]] += w
    return {k: 100 * c[k] / T for k in CATS + ('NV',)}


def dif(p, q):
    por = {k: abs(p[k] - q[k]) for k in CATS}
    return sum(por.values()) / len(CATS), por


def mano_mas_libre(pp):
    sd = {k: pp[k]['S'] + pp[k]['D'] for k in MANOS}
    if abs(sd['md'] - sd['mi']) < 1e-9:
        return 'empate', sd
    return max(MANOS, key=sd.get), sd


def plan(cod, segs, dur, t0):
    filas = unir_filas([{'t0': t0[s], 't1': t0[s] + dur[s], 'md': cod[s][0], 'mi': cod[s][1]} for s in segs])
    p = potencial(filas)
    pal = p['palancas'][0] if p['palancas'] else None
    return {'tiempo_s': p['tiempo_s'], 'ahorro_s': p['ahorro_s'], 'nuevo_s': p['nuevo_s'], 'ahorro_pct': p['ahorro_pct'],
            'principal': pal['titulo'] if pal else None, 'clave': pal['clave'] if pal else None,
            'principal_s': pal['segundos'] if pal else 0.0, 'n_filas': len(filas),
            'palancas': {x['clave']: x['segundos'] for x in p['palancas']}}


def medir(cods, G, nulo, segs, dur, t0):
    r = {'pct': {}, 'pct_alt': {}, 'peso': {}, 'acierto': {}}
    for j, k in enumerate(MANOS):
        sk = [s for s in segs if not nulo[s][j]]
        w = [dur[s] for s in sk]
        r['peso'][k] = sum(w)
        for nom, C in cods.items():
            r['pct'].setdefault(nom, {})[k] = pct([C[s][j] for s in sk], w) if sk else None
            r['pct_alt'].setdefault(nom, {})[k] = pct([C[s][j] for s in sk], w, A_CAT_ALT) if sk else None
            r['acierto'].setdefault(nom, [0, 0])
            r['acierto'][nom][0] += sum(C[s][j] == G[s][j] for s in sk)
            r['acierto'][nom][1] += len(sk)
    r['dif'], r['dif_alt'], r['libre'] = {}, {}, {}
    for nom in cods:
        if all(r['pct'][nom][k] is not None for k in MANOS):
            r['libre'][nom] = mano_mas_libre(r['pct'][nom])
        if nom == 'verdad':
            continue
        r['dif'][nom] = {k: dif(r['pct'][nom][k], r['pct']['verdad'][k]) for k in MANOS if r['peso'][k]}
        r['dif_alt'][nom] = {k: dif(r['pct_alt'][nom][k], r['pct_alt']['verdad'][k]) for k in MANOS if r['peso'][k]}
    ambas = [s for s in segs if not nulo[s][0] and not nulo[s][1]]
    r['n_ambas'] = len(ambas)
    r['plan'] = {nom: plan(C, ambas, dur, t0) for nom, C in cods.items()} if ambas else None
    return r


def ponderado(tomas, sistema, mano=None, clave='dif'):
    num, cat, W = 0.0, Counter(), 0.0
    for r in tomas:
        for k in (MANOS if mano is None else (mano,)):
            if k not in r[clave][sistema]:
                continue
            w = r['peso'][k]
            m, por = r[clave][sistema][k]
            num += w * m
            for c in CATS:
                cat[c] += w * por[c]
            W += w
    return {'media': num / W, **{c: cat[c] / W for c in CATS}}


def libres(tomas, sis):
    co_ = em_v = em_s = 0
    tomas = [r for r in tomas if sis in r['libre'] and 'verdad' in r['libre']]
    for r in tomas:
        a, b = r['libre'][sis][0], r['libre']['verdad'][0]
        co_ += a == b
        em_s += a == 'empate'
        em_v += b == 'empate'
    return {'coinciden': co_, 'n': len(tomas), 'pct': 100 * co_ / len(tomas), 'empates_sistema': em_s,
            'empates_verdad': em_v}


def planes(tomas, sis):
    ps = [(r['plan'][sis], r['plan']['verdad']) for r in tomas if r['plan']]
    co_ = sum(a['principal'] == b['principal'] for a, b in ps)
    dn_pct = [100 * abs(a['nuevo_s'] - b['nuevo_s']) / b['tiempo_s'] for a, b in ps]
    return {'coinciden': co_, 'n': len(ps), 'pct': 100 * co_ / len(ps), 'dif_nuevo_pct_T_media': float(np.mean(dn_pct))}


# ------------------------------------------------ 1) v10 from the frozen system, checked against the clean test
S, C = {}, {}
for su in ENTRENO + [4]:
    d = np.load(rutas.SALIDA / f'filas_s{su}.npz', allow_pickle=True)
    S[su], ns = (d['X'], d['meta']), list(d['nombres'])
    d = np.load(rutas.SALIDA / f'cuadros_s{su}.npz', allow_pickle=True)
    C[su], nc = (d['X'], d['meta']), list(d['nombres'])
P = final.predecir([S[s] for s in ENTRENO], S[4], ns, [C[s] for s in ENTRENO], C[4], nc, cal=final.CAL,
                   peso_a=final.PESO_A)
V10 = {}
for i, m in enumerate(S[4][1]):
    if m[2] >= 2:
        V10[(m[1], int(m[2]), int(m[3]), int(m[4]))] = str(si.CLASES[P[i].argmax()])
volc = json.loads(DUMP.read_text(encoding='utf-8'))
V9, V5 = {}, {}
for k, d in volc.items():
    ta, t, s, j = k.split('|')
    clave = (ta, int(t), int(s), int(j))
    if 'v9 (compuerta)' in d and 'v5 modelo solo' in d:
        V9[clave], V5[clave] = d['v9 (compuerta)'], d['v5 modelo solo']
info = json.loads((rutas.sujeto(4) / 'mp4' / 'meta.json').read_text())
TOMAS, ok, n = [], 0, 0
for tarea in TAREAS:
    for t in range(2, 10):
        c = f'{tarea}__take_{t}'
        G4 = kit_verdad.verdad(tarea, f'take_{t}', info[c]['fps'], sujeto=4)
        pred = json.loads((rutas.gemma(4) / c / 'pred.json').read_text(encoding='utf-8'))
        dur = {int(round(o['t0'])): o['t1'] - o['t0'] for o in pred}
        t0 = {int(round(o['t0'])): o['t0'] for o in pred}
        segs = [s for s in sorted(G4) if s in dur and all((tarea, t, s, j) in X for X in (V10, V9, V5) for j in (0, 1))]
        for s in segs:                               # comprobación: la misma cifra de la prueba limpia
            for j in (0, 1):
                if not G4[s][2 + j]:
                    ok += V10[(tarea, t, s, j)] == G4[s][j]
                    n += 1
        G = {s: G4[s][:2] for s in segs}
        cods = {'verdad': G, **{nom: {s: (X[(tarea, t, s, 0)], X[(tarea, t, s, 1)]) for s in segs}
                                for nom, X in (('v5', V5), ('v9', V9), ('v10', V10))}}
        r = medir(cods, G, {s: (G4[s][2], G4[s][3]) for s in segs}, segs, dur, t0)
        r.update(tarea=tarea, toma=t, grupo='taller' if '_w_' in tarea else 'cocina')
        TOMAS.append(r)
print(f'v10 recalculado: {ok}/{n} = {100 * ok / n:.1f} % (prueba limpia: 83.4 % de 1.888)', flush=True)
assert n == 1888 and round(100 * ok / n, 1) == 83.4, 'el v10 recalculado no es el de la prueba limpia'

# ------------------------------------------------ 2) las tres medidas del diagrama
RES = {}
for grupo in ('total', 'taller', 'cocina'):
    sub = [r for r in TOMAS if grupo == 'total' or r['grupo'] == grupo]
    RES[grupo] = {sis: {'reparto_puntos': round(ponderado(sub, sis)['media'], 1),
                        'mano_mas_libre': libres(sub, sis), 'plan': planes(sub, sis)} for sis in SISTEMAS}
    print(f'== {grupo} ({len(sub)} tomas)')
    for sis in SISTEMAS:
        x = RES[grupo][sis]
        print(f'  {sis:<4} reparto de tiempo a {x["reparto_puntos"]} puntos de la verdad · mano que más sostiene o '
              f'espera {x["mano_mas_libre"]["pct"]:.0f} % · palanca principal {x["plan"]["pct"]:.0f} % · tiempo tras '
              f'el plan a {x["plan"]["dif_nuevo_pct_T_media"]:.1f} % del ciclo', flush=True)
(rutas.SALIDA / 'diagrama_s4.json').write_text(json.dumps(RES, ensure_ascii=False, indent=1), encoding='utf-8')
