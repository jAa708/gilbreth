"""v10 «modo estación»: validación dejando una persona fuera sobre las filas de construir.py y cuadros.py (en
rutas.SALIDA). Por cada persona fuera: entrena con las demás + sus tomas 0-1 revisadas y mide sus tomas 2-9 (código
exacto por mano y segundo, manos-segundo excluidas fuera). Con --curva: el acierto según cuántas personas etiquetadas
hay para entrenar. Es gilbreth_noche_15oct/v10/loso_final.py con las rutas configurables.
Uso: python research/station_v10/validar.py --sujetos 1 2 3 5 6 [--curva]"""
import argparse, itertools, json, sys, time
from pathlib import Path

import numpy as np

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import final  # noqa: E402
import rutas  # noqa: E402
import sistema as si  # noqa: E402

sys.stdout.reconfigure(encoding='utf-8')


def cargar(prefijo, su):
    d = np.load(rutas.SALIDA / f'{prefijo}_s{su}.npz', allow_pickle=True)
    return (d['X'], d['meta']), list(d['nombres'])


def puntuar(P, M):
    y = np.array([m[5] for m in M])
    pred = si.CLASES[P.argmax(1)]
    gm = np.array([m[7] for m in M])
    prueba = si.validas(M) & np.array([m[2] >= 2 for m in M])
    grupo = np.array(['taller' if '_w_' in m[1] else 'cocina' for m in M])
    r = {}
    for g in ('taller', 'cocina', 'total'):
        sel = prueba & ((grupo == g) if g != 'total' else True)
        r[g] = round(100 * np.mean(pred[sel] == y[sel]), 1)
        r['gemma_' + g] = round(100 * np.mean(gm[sel] == y[sel]), 1)
    r['n'] = int(prueba.sum())
    return r


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--sujetos', type=int, nargs='+', default=[1, 2, 3])
    ap.add_argument('--curva', action='store_true')
    a = ap.parse_args()
    S, C, ns, nc = {}, {}, None, None
    for su in a.sujetos:
        S[su], ns = cargar('filas', su)
        C[su], nc = cargar('cuadros', su)
    tabla = {}
    for f in a.sujetos:
        t0 = time.time()
        otros = [s for s in a.sujetos if s != f]
        tabla[f] = puntuar(final.predecir([S[s] for s in otros], S[f], ns, [C[s] for s in otros], C[f], nc), S[f][1])
        print(f'fuera s{f}: v10 {tabla[f]["total"]:.1f} (taller {tabla[f]["taller"]:.1f} · cocina {tabla[f]["cocina"]:.1f}) '
              f'· Gemma {tabla[f]["gemma_total"]:.1f} · {tabla[f]["n"]} manos-seg · {time.time() - t0:.0f} s', flush=True)
    media = float(np.mean([tabla[f]['total'] for f in tabla]))
    print(f'MEDIA dejando una persona fuera ({len(a.sujetos) - 1} para entrenar): {media:.1f} %', flush=True)
    curva = {}
    if a.curva:
        for k in range(1, len(a.sujetos)):
            vals = [puntuar(final.predecir([S[s] for s in comb], S[f], ns, [C[s] for s in comb], C[f], nc), S[f][1])['total']
                    for f in a.sujetos for comb in itertools.combinations([s for s in a.sujetos if s != f], k)]
            curva[k] = (round(float(np.mean(vals)), 1), len(vals))
            print(f'curva: {k} persona(s) etiquetada(s) -> {curva[k][0]:.1f} % (media de {curva[k][1]} pruebas)', flush=True)
    (rutas.SALIDA / f'validacion_{"_".join(map(str, a.sujetos))}.json').write_text(
        json.dumps({'por_sujeto': tabla, 'media': media, 'curva': curva}, indent=1), encoding='utf-8')
