"""Enmienda 4 del pre-registro de IMPACT (13:35, antes de cualquier resultado): las medidas del DIAGRAMA, como cifras
secundarias. Corre DESPUÉS de `impact_v10.py --si` (exige su marca y su resultado) y no toca el script sellado:
recalcula las mismas predicciones con las mismas funciones y se detiene si los aciertos totales no son EXACTAMENTE los
de resultado_impact_v10.json. Luego, por corrida (8), sobre los segundos ≥ 60 con predicción de los cuatro sistemas:
(1) distancia media del reparto de tiempo por mano, (2) si acierta la mano que más sostiene o espera, (3) si coincide
la palanca principal del plan y a qué distancia queda el tiempo tras el plan. Uso: python v10/impact_diagrama.py"""
import json, sys
from collections import defaultdict
from pathlib import Path

import numpy as np

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import impact_v10 as iv  # noqa: E402
import final  # noqa: E402
import medidas_diagrama as md  # noqa: E402
import sistema as si  # noqa: E402

sys.stdout.reconfigure(encoding='utf-8')
assert iv.INICIO.exists() and iv.SAL.exists(), 'primero impact_v10.py --si (la prueba de una sola mirada)'
PRIM = json.loads(iv.SAL.read_text(encoding='utf-8'))

# ------------------------------------------------ las mismas predicciones que impact_v10.py (main)
EST_S, EST_C = defaultdict(list), defaultdict(list)
for c in iv.ESTACION:
    fs, fc, _ = iv.armar(c, None)
    EST_S[iv.operario(c)].append(fs), EST_C[iv.operario(c)].append(fc)
entreno_s = [iv.junta(v) for v in EST_S.values()]
entreno_c = [iv.junta(v) for v in EST_C.values()]
PR_S, PR_C, CLIP = defaultdict(list), defaultdict(list), {}
for c in iv.PRUEBA:
    fs, fc, CLIP[c] = iv.armar(c, iv.REVISADO)
    PR_S[iv.operario(c)].append(fs), PR_C[iv.operario(c)].append(fc)
ns, nc = iv.NOMBRES_S, iv.cu.nombres()
SIS = {n: {} for n in ('v5', 'v9', 'v10', 'v10-segundos')}
for op in sorted(PR_S):
    nuevo_s, nuevo_c = iv.junta(PR_S[op]), iv.junta(PR_C[op])
    P = final.predecir(entreno_s, nuevo_s, ns, entreno_c, nuevo_c, nc, cal=final.CAL, peso_a=final.PESO_A)
    Pseg = si.ajustar_predecir(entreno_s, nuevo_s, ns, cal=final.CAL, auto=False)
    for i, m in enumerate(nuevo_s[1]):
        if m[3] >= iv.REVISADO:
            clave = (op, m[1], m[3], m[4])
            SIS['v10'][clave] = str(si.CLASES[P[i].argmax()])
            SIS['v10-segundos'][clave] = str(si.CLASES[Pseg[i].argmax()])
Xi, yi = iv.mv.previo(bajar=False)
for c in iv.PRUEBA:
    sg, V, G, nf, fps = CLIP[c]
    dur = int(nf / fps + 0.5)
    rev = [s for s in sorted(G) if s < iv.REVISADO and s in V and not G[s][2] and not G[s][3]]
    cal = [{'sg': sg, 'V': V, 'G': {s: G[s][:2] for s in rev}, 'segs': rev}]
    usar, est = iv.cp.decidir(Xi, yi, cal)
    try:
        m7 = iv.cp.entrenar_clips(Xi, yi, cal)
    except ValueError:
        m7 = None
    segs = [s for s in range(iv.REVISADO, dur) if s in V]
    P7 = iv.se.aplicar('apilado', m7, sg, V, segs) if m7 is not None else {s: V[s] for s in segs}
    P9 = P7 if usar else {s: V[s] for s in segs}
    for s in segs:
        for j in (0, 1):
            SIS['v5'][(iv.operario(c), iv.tarea_de(c), s, j)] = V[s][j]
            SIS['v9'][(iv.operario(c), iv.tarea_de(c), s, j)] = P9[s][j]

# ------------------------------------------------ la verdad y la comprobación contra la prueba
VERDAD, COMPLETA = {}, {}
for c in iv.PRUEBA:
    COMPLETA[c] = iv.por_segundo(*iv.etiquetas(c))
    for s, g in COMPLETA[c].items():
        if s >= iv.REVISADO:
            for j in (0, 1):
                if not g[2 + j]:
                    VERDAD[(iv.operario(c), iv.tarea_de(c), s, j)] = g[j]
comun = sorted(k for k in VERDAD if all(k in SIS[n] for n in SIS))
aciertos = {n: sum(VERDAD[k] == SIS[n][k] for k in comun) for n in SIS}
print('aciertos recalculados:', aciertos, '· prueba:', PRIM['aciertos_total'], flush=True)
assert aciertos == PRIM['aciertos_total'], 'las predicciones recalculadas no son las de la prueba'

# ------------------------------------------------ las medidas del diagrama, por corrida
TOMAS = []
for c in iv.PRUEBA:
    op, ta = iv.operario(c), iv.tarea_de(c)
    G4 = COMPLETA[c]
    win = {int(round(o['t0'])): o for o in json.loads((iv.CODS_PRUEBA / f'{c}__take_0' / 'pred.json').read_text(encoding='utf-8'))}
    segs = [s for s in sorted(G4) if s >= iv.REVISADO and s in win
            and all((op, ta, s, j) in SIS[n] for n in SIS for j in (0, 1))]
    G = {s: G4[s][:2] for s in segs}
    cods = {'verdad': G, **{n: {s: (SIS[n][(op, ta, s, 0)], SIS[n][(op, ta, s, 1)]) for s in segs} for n in SIS}}
    r = md.medir(cods, G, {s: (G4[s][2], G4[s][3]) for s in segs}, segs,
                 {s: win[s]['t1'] - win[s]['t0'] for s in segs}, {s: win[s]['t0'] for s in segs})
    r['corrida'] = c
    TOMAS.append(r)
RES = {}
for n in SIS:
    RES[n] = {'reparto_puntos': round(md.ponderado(TOMAS, n)['media'], 1), 'mano_mas_libre': md.libres(TOMAS, n),
              'plan': md.planes(TOMAS, n)}
    x = RES[n]
    print(f'  {n:<13} reparto a {x["reparto_puntos"]} puntos · mano que más sostiene o espera '
          f'{x["mano_mas_libre"]["coinciden"]}/{x["mano_mas_libre"]["n"]} · palanca principal '
          f'{x["plan"]["coinciden"]}/{x["plan"]["n"]} · tiempo tras el plan a {x["plan"]["dif_nuevo_pct_T_media"]:.1f} % del ciclo',
          flush=True)
(AQUI / 'resultado_impact_diagrama.json').write_text(json.dumps(RES, ensure_ascii=False, indent=1), encoding='utf-8')
