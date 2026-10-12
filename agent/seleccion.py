"""El agente se mide a sí mismo en el tramo que el usuario ya revisó (minuto de oro) y elige cómo codificar el resto.
Candidatos: visión sola · movimiento calibrado · bordes (visión + movimiento calibrado) · apilado (un clasificador con
rasgos de movimiento + los códigos de la visión, calibrado). El acierto del movimiento en el tramo revisado se estima
con dos mitades (se entrena con una y se mide en la otra), para no medirse con lo que ya vio."""
import numpy as np

import fusion
import movimiento as mv

CODS = list(mv.CODIGOS)


def _una(c):
    return [1.0 if c == x else 0.0 for x in CODS] if c else [np.nan] * len(CODS)


def rasgos_vision(V, s, j):
    g = lambda t, jj: V.get(t, (None, None))[jj]
    return _una(g(s, j)) + _una(g(s - 1, j)) + _una(g(s + 1, j)) + _una(g(s, 1 - j))


def _xy(sg, V, G, segs, con_vision):
    X, y = [], []
    for s in segs:
        for k, j in (('R', 0), ('L', 1)):
            c = mv.A_CLASE.get(G[s][j])
            if c:
                X.append(mv.vector(sg, k, s) + (rasgos_vision(V, s, j) if con_vision else []))
                y.append(c)
    return np.array(X, dtype=float), np.array(y)


def entrenar(Xi, yi, sg, V, G, segs, con_vision, peso=20.0):
    Xl, yl = _xy(sg, V, G, segs, con_vision)
    if con_vision:
        Xi = np.hstack([Xi, np.full((len(Xi), 4 * len(CODS)), np.nan)])
    if len(yl):
        Xi, yi = np.vstack([Xi, Xl]), np.concatenate([yi, yl])
        w = np.concatenate([np.ones(len(Xi) - len(yl)), np.full(len(yl), peso)])
    else:
        w = np.ones(len(yi))
    return mv.nuevo_modelo().fit(Xi, yi, sample_weight=w)


def aplicar(metodo, modelo, sg, V, segs):
    if metodo == 'vision':
        return {s: V[s] for s in segs}
    if metodo == 'apilado':
        out = {}
        for s in segs:
            pr = modelo.predict(np.array([mv.vector(sg, 'R', s) + rasgos_vision(V, s, 0),
                                          mv.vector(sg, 'L', s) + rasgos_vision(V, s, 1)]))
            out[s] = (mv.a_codigo(pr[0], pr[1]), mv.a_codigo(pr[1], pr[0]))
        return out
    M = mv.predecir(modelo, sg, segs)
    if metodo == 'movimiento':
        return {s: M[s][:2] for s in segs}
    return fusion.bordes({s: V[s] for s in segs}, M, list(modelo.classes_))


METODOS = ('vision', 'movimiento', 'bordes', 'apilado')


def acierto(P, G, segs):
    return sum((P[s][0] == G[s][0]) + (P[s][1] == G[s][1]) for s in segs if s in P)


def elegir(Xi, yi, sg, V, G, cal):
    """cal = segundos revisados (con verdad G). Devuelve (método elegido, {método: aciertos estimados})."""
    cal = sorted(cal)
    a, b = cal[:len(cal) // 2], cal[len(cal) // 2:]
    est = {'vision': acierto(V, G, cal)}
    for metodo in METODOS[1:]:
        tot = 0
        for ent, med in ((a, b), (b, a)):
            m = entrenar(Xi, yi, sg, V, G, ent, metodo == 'apilado')
            tot += acierto(aplicar(metodo, m, sg, V, med), G, med)
        est[metodo] = tot
    # empate -> el método más simple (orden de METODOS)
    return max(METODOS, key=lambda k: (est[k], -METODOS.index(k))), est


def codificar(Xi, yi, sg, V, G, cal, segs):
    """Elige con el tramo revisado y codifica los segundos pedidos con el método elegido (entrenado con todo cal)."""
    metodo, est = elegir(Xi, yi, sg, V, G, cal)
    m = None if metodo == 'vision' else entrenar(Xi, yi, sg, V, G, sorted(cal), metodo == 'apilado')
    return metodo, est, aplicar(metodo, m, sg, V, segs)
