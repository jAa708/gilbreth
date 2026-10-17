"""v10: el sistema entre sujetos (un solo código para el desarrollo dejando un sujeto fuera y para la prueba limpia).

Entrada: filas de construir.py (una mano en un segundo: movimiento del seguidor, códigos de Gemma, tarea) de los
sujetos de ENTRENAMIENTO (todas sus tomas, con verdad) y del sujeto NUEVO, del que solo se usan como verdad sus tomas
0-1 (las que el usuario revisa en el producto) y se predicen las demás.
1) Mano dominante: por (persona, tarea, mano), la fracción de segundos en OP en las tomas 0-1 revisadas (es lo que hace
   que un zurdo no se lea al revés). Se quita el rasgo «es la derecha».
2) Nivel 1: HistGradientBoosting de 4 clases (OP, TR, S, D) con los sujetos de entrenamiento + las tomas revisadas del
   nuevo con peso `cal`.
3) Nivel 2 (auto-contexto, opcional): otro HistGradientBoosting que además ve las probabilidades del nivel 1 en la
   misma mano (s-2..s+2) y en la otra (s-1..s+1). Todas esas probabilidades son FUERA de sujeto (cada sujeto de
   entrenamiento, predicho por un nivel 1 entrenado sin él), para que el nivel 2 no aprenda de probabilidades
   demasiado buenas.
4) Opcional: promedio de varias semillas."""
from collections import defaultdict

import numpy as np

CLASES = np.array(['OP', 'TR', 'S', 'D'])
FUERA_DE_RASGOS = ('t', 'dur', 'es_derecha')


def modelo(semilla=0, **kw):
    from sklearn.ensemble import HistGradientBoostingClassifier
    p = dict(max_leaf_nodes=31, max_iter=300, learning_rate=0.05, l2_regularization=1.0, min_samples_leaf=20,
             random_state=semilla, early_stopping=False)
    p.update(kw)
    return HistGradientBoostingClassifier(**p)


def validas(M):
    return np.array([not m[6] and m[5] in CLASES for m in M])


def dominancia(M):
    cuenta = defaultdict(lambda: [0, 0])
    for m in M:
        if m[2] <= 1 and not m[6] and m[5] in CLASES:
            c = cuenta[(m[0], m[1], m[4])]
            c[0] += m[5] == 'OP'
            c[1] += 1
    return {k: v[0] / v[1] for k, v in cuenta.items() if v[1]}


def base(X, M, nombres, dom, excluir=()):
    cols = [i for i, n in enumerate(nombres) if n not in FUERA_DE_RASGOS and not n.startswith(tuple(excluir))]
    extra = np.array([[dom.get((m[0], m[1], m[4]), np.nan), dom.get((m[0], m[1], 1 - m[4]), np.nan)] for m in M],
                     dtype=np.float32)
    return np.hstack([X[:, cols], extra])


def probas(m, X):
    P = m.predict_proba(X)
    cl = list(m.classes_)
    return P[:, [cl.index(c) for c in CLASES]]


def contexto(P, M):
    """Probabilidades del nivel 1 alrededor: misma mano s-2..s+2 (sin s) y otra mano s-1..s+1."""
    idx = {(m[0], m[1], m[2], m[3], m[4]): i for i, m in enumerate(M)}
    nan = np.full(4, np.nan)
    out = np.zeros((len(M), 4 * 7), dtype=np.float32)
    for i, m in enumerate(M):
        su, ta, to, s, j = m[0], m[1], m[2], m[3], m[4]
        partes = []
        for d in (-2, -1, 1, 2):
            o = idx.get((su, ta, to, s + d, j))
            partes.append(P[o] if o is not None else nan)
        for d in (-1, 0, 1):
            o = idx.get((su, ta, to, s + d, 1 - j))
            partes.append(P[o] if o is not None else nan)
        out[i] = np.concatenate(partes)
    return out


def autoentrenar(entreno, nuevo, nombres, umbral=0.9, peso=1.0, **kw):
    """Auto-entrenamiento en el sujeto nuevo: predice, toma como etiqueta las predicciones con probabilidad >= umbral
    en sus tomas NO revisadas (sin mirar su verdad) y vuelve a entrenar con ellas como un sujeto más (peso `peso`)."""
    P = ajustar_predecir(entreno, nuevo, nombres, **kw)
    X, M = nuevo
    seguro = (P.max(1) >= umbral) & np.array([m[2] >= 2 for m in M])
    M2 = np.empty((len(M), len(M[0])), dtype=object)    # objeto: np.array de tuplas mixtas lo volvería texto
    for i, m in enumerate(M):
        M2[i] = list(m[:5]) + ([str(CLASES[P[i].argmax()]), False] if seguro[i] else ['', True]) + list(m[7:])
    pseudo = (X, M2)                                # misma persona: su mano dominante sale de sus tomas revisadas
    return ajustar_predecir(list(entreno) + [pseudo], nuevo, nombres, **kw)


def extra_trees(entreno, nuevo, nombres, cal=5.0, n=400):
    """Otro tipo de modelo para mezclar: Extra Trees sobre los mismos rasgos (NaN -> -1)."""
    from sklearn.ensemble import ExtraTreesClassifier
    Mn = nuevo[1]
    dom = dominancia(np.concatenate([e[1] for e in entreno] + [Mn]) if entreno else Mn)
    B = [base(X, M, nombres, dom) for X, M in entreno]
    Bn = base(nuevo[0], Mn, nombres, dom)
    ok = [validas(M) for _, M in entreno]
    rev = validas(Mn) & np.array([m[2] <= 1 for m in Mn])
    X = np.vstack([B[i][ok[i]] for i in range(len(B))] + [Bn[rev]])
    Y = np.concatenate([np.array([m[5] for m in entreno[i][1]])[ok[i]] for i in range(len(B))]
                       + [np.array([m[5] for m in Mn])[rev]])
    W = np.concatenate([np.ones(len(Y) - rev.sum()), np.full(rev.sum(), cal)])
    m = ExtraTreesClassifier(n_estimators=n, min_samples_leaf=3, max_features=0.3, n_jobs=-1, random_state=0)
    m.fit(np.nan_to_num(X, nan=-1.0), Y, sample_weight=W)
    return probas(m, np.nan_to_num(Bn, nan=-1.0))


def ajustar_predecir(entreno, nuevo, nombres, cal=5.0, auto=True, semillas=(0,), hp=None, excluir=()):
    """entreno: lista de (X, M) por sujeto de entrenamiento; nuevo: (X, M) del sujeto nuevo (su verdad solo se lee en
    las tomas 0-1). Devuelve las probabilidades (n, 4) para TODAS las filas del nuevo."""
    hp = hp or {}
    Mn = nuevo[1]
    dom = dominancia(np.concatenate([e[1] for e in entreno] + [Mn]) if entreno else Mn)
    B = [base(X, M, nombres, dom, excluir) for X, M in entreno]
    Bn = base(nuevo[0], Mn, nombres, dom, excluir)
    ok = [validas(M) for _, M in entreno]
    y = [np.array([m[5] for m in M]) for _, M in entreno]
    rev = validas(Mn) & np.array([m[2] <= 1 for m in Mn])
    yn = np.array([m[5] for m in Mn])

    def nivel1(sujetos, con_cal, semilla):
        sujetos = list(sujetos)
        X = np.vstack([B[i][ok[i]] for i in sujetos]) if sujetos else np.zeros((0, Bn.shape[1]), dtype=np.float32)
        Y = np.concatenate([y[i][ok[i]] for i in sujetos]) if sujetos else np.array([], dtype=object)
        W = np.ones(len(Y))
        if con_cal and rev.any():
            X, Y = np.vstack([X, Bn[rev]]), np.concatenate([Y, yn[rev]])
            W = np.concatenate([W, np.full(rev.sum(), cal)])
        return modelo(semilla, **hp).fit(X, Y, sample_weight=W)

    salida = np.zeros((len(Mn), 4))
    for semilla in semillas:
        m1 = nivel1(range(len(B)), True, semilla)
        P1n = probas(m1, Bn)
        if not auto:
            salida += P1n
            continue
        # probabilidades fuera de sujeto: cada sujeto de entrenamiento con un nivel 1 que no lo vio; el nuevo con uno
        # entrenado sin sus tomas revisadas (las revisadas también entran al nivel 2 con probabilidades que no las vieron)
        P1 = [probas(nivel1([j for j in range(len(B)) if j != i], False, semilla), B[i]) for i in range(len(B))]
        P1n_fuera = probas(nivel1(range(len(B)), False, semilla), Bn)
        C = [contexto(P1[i], entreno[i][1]) for i in range(len(B))]
        Cn_rev = contexto(P1n_fuera, Mn)
        X2 = np.vstack([np.hstack([B[i], P1[i], C[i]])[ok[i]] for i in range(len(B))])
        Y2 = np.concatenate([y[i][ok[i]] for i in range(len(B))])
        W2 = np.ones(len(Y2))
        if rev.any():
            X2 = np.vstack([X2, np.hstack([Bn, P1n_fuera, Cn_rev])[rev]])
            Y2 = np.concatenate([Y2, yn[rev]])
            W2 = np.concatenate([W2, np.full(rev.sum(), cal)])
        m2 = modelo(semilla, **hp).fit(X2, Y2, sample_weight=W2)
        salida += probas(m2, np.hstack([Bn, P1n, contexto(P1n, Mn)]))
    return salida / len(semillas)
