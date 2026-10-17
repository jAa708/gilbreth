"""v10 final: el sistema que se congela (el mismo código para el desarrollo dejando un sujeto fuera y para la prueba
limpia del sujeto 4).
Por segundo y por mano, la mezcla de dos modelos que aprenden de TODOS los segundos etiquetados de las otras personas
(mismas 9 tareas de KIT) + las tomas 0-1 revisadas de la persona nueva (peso CAL) + su mano dominante en lo revisado:
  a) por segundo (sistema.ajustar_predecir, nivel 1): movimiento del seguidor en el segundo, medios segundos y perfil
     a 10 Hz, vecinos ±2 s, la otra mano, los códigos y atributos de Gemma, la tarea;
  b) a 10 Hz (cuadros.py): cada muestra del seguidor con la etiqueta de SU cuadro; por segundo se promedian sus
     probabilidades (lo que separa bien los segundos de frontera, donde está el 85 % de los errores).
Probabilidad final = PESO_A · a + (1 - PESO_A) · b (si un segundo no tiene muestras, solo a); código = la más probable."""
from collections import defaultdict

import numpy as np

import sistema as si

CAL = 5.0
PESO_A = 0.5


def _matriz_cuadros(X, M, nombres, dom):
    cols = [i for i, n in enumerate(nombres) if n != 'es_derecha']
    extra = np.array([[dom.get((m[0], m[1], m[4]), np.nan), dom.get((m[0], m[1], 1 - m[4]), np.nan)] for m in M],
                     dtype=np.float32)
    return np.hstack([X[:, cols], extra])


def prob_cuadros(entreno_c, nuevo_c, nombres_c, dom, cal=CAL, semilla=0):
    """{(tarea, toma, s, mano): probabilidades} del modelo a 10 Hz para el sujeto nuevo."""
    Xc, Mc = nuevo_c
    Xn = _matriz_cuadros(Xc, Mc, nombres_c, dom)
    if entreno_c:
        Xt = np.vstack([_matriz_cuadros(X, M, nombres_c, dom) for X, M in entreno_c])
        yt = np.concatenate([np.array([m[9] for m in M]) for _, M in entreno_c])
    else:                                            # solo lo revisado de la persona nueva
        Xt, yt = np.zeros((0, Xn.shape[1]), dtype=np.float32), np.array([], dtype=object)
    ok = np.isin(yt, si.CLASES)
    yn = np.array([m[9] for m in Mc])
    rev = np.isin(yn, si.CLASES) & np.array([m[2] <= 1 for m in Mc])
    m = si.modelo(semilla).fit(np.vstack([Xt[ok], Xn[rev]]), np.concatenate([yt[ok], yn[rev]]),
                               sample_weight=np.concatenate([np.ones(ok.sum()), np.full(rev.sum(), cal)]))
    P = si.probas(m, Xn)
    acc = defaultdict(lambda: np.zeros(4))
    for p, mm in zip(P, Mc):
        acc[(mm[1], mm[2], mm[3], mm[4])] += p
    return {k: v / v.sum() for k, v in acc.items()}


def predecir(entreno_s, nuevo_s, nombres_s, entreno_c, nuevo_c, nombres_c, cal=CAL, peso_a=PESO_A):
    """Probabilidades (n, 4) por fila del sujeto nuevo (filas por segundo de construir.py), en el orden si.CLASES."""
    dom = si.dominancia(np.concatenate([M for _, M in entreno_s] + [nuevo_s[1]]) if entreno_s else nuevo_s[1])
    Pa = si.ajustar_predecir(entreno_s, nuevo_s, nombres_s, cal=cal, auto=False)
    Pb = prob_cuadros(entreno_c, nuevo_c, nombres_c, dom, cal=cal)
    out = Pa.copy()
    for i, m in enumerate(nuevo_s[1]):
        k = (m[1], m[2], m[3], m[4])
        if k in Pb:
            out[i] = peso_a * Pa[i] + (1 - peso_a) * Pb[k]
    return out
