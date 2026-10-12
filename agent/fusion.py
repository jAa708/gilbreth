"""Combina los códigos del modelo de visión (qué hace cada mano) con el clasificador de movimiento (cuándo cambia).
El modelo de visión acierta QUÉ hace la mano pero se corre ±1 s en los cambios; el movimiento ve el instante del cambio
pero no sabe qué pieza ni si hay folleto. Por eso el movimiento solo decide en los bordes y nunca inventa un código."""
CLASE = {'TR': 'TR', 'TR+OP': 'TR', 'OP': 'OP', 'S': 'H', 'D': 'H'}


def coherencia(md, mi):
    f = lambda c, otra: 'D' if c == 'S' and otra not in ('OP', 'TR+OP') else c
    return f(md, mi), f(mi, md)


def _p(clases, proba, codigo):
    c = CLASE.get(codigo)
    return float(proba[clases.index(c)]) if c in clases else -1.0


def bordes(pred, mov, clases, alcance=1):
    """pred {s: (md, mi)}; mov {s: (md, mi, proba_R, proba_L)}. En cada segundo junto a un cambio de código del modelo
    de visión (por mano), toma entre los códigos de los vecinos (±alcance s) el que el movimiento ve más probable."""
    out = {}
    for s in sorted(pred):
        nuevo = list(pred[s])
        for k in (0, 1):
            if s not in mov:
                continue
            cands = {pred[t][k] for t in range(s - alcance, s + alcance + 1) if t in pred}
            if len({CLASE.get(c) for c in cands}) < 2 or CLASE.get(pred[s][k]) is None:
                continue
            mejor = max(cands, key=lambda c: _p(clases, mov[s][2 + k], c))
            if CLASE.get(mejor) != CLASE.get(pred[s][k]) and _p(clases, mov[s][2 + k], mejor) > _p(clases, mov[s][2 + k], pred[s][k]):
                nuevo[k] = mejor
        out[s] = coherencia(*nuevo)
    return out


def confianza(pred, mov, clases, umbral=0.8):
    """Variante: el movimiento manda cuando está muy seguro (proba ≥ umbral) y discrepa en la clase."""
    out = {}
    for s in sorted(pred):
        nuevo = list(pred[s])
        if s in mov:
            for k in (0, 1):
                p = mov[s][2 + k]
                j = max(range(len(clases)), key=lambda i: p[i])
                if p[j] >= umbral and CLASE.get(pred[s][k]) is not None and clases[j] != CLASE.get(pred[s][k]):
                    nuevo[k] = clases[j] if clases[j] != 'H' else ('S' if pred[s][1 - k] in ('OP', 'TR+OP') else 'D')
        out[s] = coherencia(*nuevo)
    return out
