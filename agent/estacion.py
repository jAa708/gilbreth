"""Modo estación: codifica el video de un operario nuevo aprendiendo de los operarios YA REVISADOS en el mismo puesto.
Es el sistema por segundo de research/station_v10 (sistema.ajustar_predecir, el mismo código congelado de la prueba
limpia en KIT: 82,5 % en el sujeto 4 con etiquetas por segundo, que es lo que da la página de revisión) aplicado a
corridas del agente: cada corrida es una carpeta con
  - puntos.npz        el seguidor de manos (agent/extraer_puntos.py),
  - pred_final.json   las ventanas del agente (o pred.json): t0, t1, md, mi y la respuesta cruda de Gemma,
  - revisado.json     lo que el ingeniero revisó en revisar.html: {"filas": [{"t0", "t1", "md", "mi"}, ...]}.
Las corridas de la estación están revisadas enteras; la nueva, al menos sus primeros --reviewed-until segundos.
Rasgos por mano y segundo: el movimiento del seguidor (el segundo, sus mitades, el perfil a 10 Hz, los vecinos y la
otra mano), los códigos de Gemma (y sus atributos, solo si TODAS las corridas los tienen) y la mano dominante de cada
operario, sacada de sus segundos revisados. Salida: pred_estacion.json (las ventanas con md/mi del modo estación desde
--reviewed-until; antes, lo revisado) y diagrama_estacion.json (las filas del diagrama).
Uso: python agent/estacion.py --station runs/w1 runs/w2 --new runs/w3 --reviewed-until 60"""
import argparse, json, sys
from pathlib import Path

import numpy as np

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
sys.path.insert(0, str(AQUI.parent / 'research' / 'station_v10'))
import construir as co  # noqa: E402  (rasgos del v10: fila, nombres, leer_pred)
import movimiento as mv  # noqa: E402
import sistema as si  # noqa: E402  (congelado: ajustar_predecir)
from manos import cargar, pista  # noqa: E402
from salidas import unir_filas  # noqa: E402

CAL = 5.0                                       # el peso de lo revisado de la persona nueva (el del sistema congelado)
ATRIB = ('am1_', 'a0_', 'ap1_', 'ao0_')
TAREA = 'station'


def ventanas(run):
    p = run / 'pred_final.json' if (run / 'pred_final.json').exists() else run / 'pred.json'
    return json.loads(p.read_text(encoding='utf-8')), p


def etiquetas(run, hasta=None):
    """{segundo: (md, mi)} de revisado.json (el código de la fila que cubre la mitad del segundo)."""
    f = run / 'revisado.json'
    if not f.exists():
        return {}
    filas = json.loads(f.read_text(encoding='utf-8'))['filas']
    out = {}
    for r in filas:
        for s in range(int(np.floor(r['t0'])), int(np.ceil(r['t1']))):
            if r['t0'] <= s + 0.5 < r['t1'] and (hasta is None or s < hasta):
                out[s] = (r['md'], r['mi'])
    return out


def filas_corrida(run, persona, hasta=None, con_atributos=True):
    """(X, meta) por mano y segundo; meta como research/station_v10: (persona, tarea, toma, s, mano, y, excluir,
    código de Gemma, hay Gemma). toma 0 = segundo revisado (entra a la mano dominante y al entrenamiento)."""
    win, ruta = ventanas(run)
    V, A = co.leer_pred(ruta)
    sg = mv.senales(pista(*cargar(run / 'puntos.npz')))
    d = np.load(run / 'puntos.npz')
    dur = int(int(d['n_fotogramas']) / float(d['fps']) + 0.5) if 'n_fotogramas' in d else int(max(V) + 1)
    E = etiquetas(run, hasta)
    X, M = [], []
    for s in range(dur):
        for j, k in enumerate('RL'):
            X.append(co.fila(sg, V, A if con_atributos else None, k, s, dur, TAREA))
            y = E.get(s, (None, None))[j]
            M.append((persona, TAREA, 0 if s in E else 2, s, j, y or '', y not in si.CLASES,
                      V.get(s, (None, None))[j] or '', True))
    meta = np.empty((len(M), len(M[0])), dtype=object)
    for i, m in enumerate(M):
        meta[i] = list(m)
    return np.array(X, dtype=np.float32), meta, win


def con_atributos(runs):
    """Los atributos de Gemma solo entran si todas las corridas los tienen (si no, sus columnas quedan vacías en la
    estación y solo la persona nueva los traería)."""
    for run in runs:
        win, _ = ventanas(run)
        if not any(isinstance(o.get('crudo'), dict) and o['crudo'].get('right_hand') for o in win):
            return False
    return True


def codificar(estacion, nueva, revisado_hasta, cal=CAL):
    """Ventanas de la corrida nueva con el modo estación desde revisado_hasta, y las filas del diagrama."""
    usa_atr = con_atributos(list(estacion) + [nueva])
    nombres = co.nombres()
    quedan = np.array([usa_atr or not n.startswith(ATRIB) for n in nombres])
    nombres = [n for n, q in zip(nombres, quedan) if q]
    entreno = []
    for i, run in enumerate(estacion):
        X, M, _ = filas_corrida(run, f'station_{i}', None, usa_atr)
        entreno.append((X[:, quedan], M))
    Xn, Mn, win = filas_corrida(nueva, 'new', revisado_hasta, usa_atr)
    P = si.ajustar_predecir(entreno, (Xn[:, quedan], Mn), nombres, cal=cal, auto=False)
    cod = {}
    for i, m in enumerate(Mn):
        cod.setdefault(int(m[3]), [None, None])[int(m[4])] = str(si.CLASES[P[i].argmax()])
    E = etiquetas(nueva, revisado_hasta)
    salida = []
    for o in win:
        s = int(round(o['t0']))
        md_, mi_ = E.get(s) or tuple(cod.get(s, (o['md'], o['mi'])))
        salida.append({**{k: v for k, v in o.items() if k != 'crudo'}, 'md': md_, 'mi': mi_,
                       'md_agente': o['md'], 'mi_agente': o['mi'], 'revisado': s in E})
    return salida, unir_filas([dict(v) for v in salida]), {'atributos': usa_atr, 'corridas_revisadas': len(estacion)}


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description='Station mode: code a new worker from workers already reviewed at the '
                                             'same station.')
    ap.add_argument('--station', nargs='+', required=True, help='run folders of reviewed workers at this station')
    ap.add_argument('--new', required=True, help='run folder of the new worker (its revisado.json covers the start)')
    ap.add_argument('--reviewed-until', type=float, default=60, help='seconds of the new video that were reviewed')
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding='utf-8')
    nueva = Path(a.new)
    win, filas, info = codificar([Path(r) for r in a.station], nueva, a.reviewed_until)
    (nueva / 'pred_estacion.json').write_text(json.dumps(win, ensure_ascii=False, indent=1), encoding='utf-8')
    (nueva / 'diagrama_estacion.json').write_text(json.dumps({'filas': filas, 'meta': info}, ensure_ascii=False,
                                                             indent=1), encoding='utf-8')
    print(f'station mode: {len(a.station)} reviewed workers · {len(filas)} chart rows · Gemma attributes '
          f'{"used" if info["atributos"] else "left out"} → {nueva / "pred_estacion.json"}')
