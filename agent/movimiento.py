"""Clasificador de MOVIMIENTO por mano y por segundo, con los 21 puntos de MediaPipe.
Genérico: rasgos medidos en largos de palma (no dependen del tamaño de la imagen ni del producto).
Clases: TR (la mano se desplaza), OP (trabaja en el sitio: dedos activos, junto a la otra mano), H (quieta o
sosteniendo). El código del curso sale con la regla de siempre: H -> S si la otra mano opera, si no D.
Se entrena con IMPACT (operarios del grupo ENTRENAR, ver PREREGISTRO_IMPACT_COMPLETO_11OCT.md)."""
import json, os, urllib.request
from pathlib import Path

import numpy as np

from manos import _centro_tam

MODELOS = Path(os.environ.get('GILBRETH_MODELS', Path(__file__).resolve().parent.parent / 'models'))
# Previo de movimiento: rasgos por mano y segundo de 9 operarios de IMPACT. Es un DERIVADO de un dataset CC BY-NC-SA 4.0:
# no va dentro de este repositorio MIT; se publica aparte con esa licencia y atribución, y se baja al usarlo.
PREVIO = 'motion_prior_impact.npz'
PREVIO_URL = os.environ.get('GILBRETH_PRIOR_URL', '')


def previo(bajar=True):
    """(X, y) del previo de movimiento, o None si no está y no se puede bajar (entonces: modo «MIT puro»)."""
    p = MODELOS / PREVIO
    if not p.exists() and bajar and PREVIO_URL:
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            urllib.request.urlretrieve(PREVIO_URL, p)
        except Exception as e:
            print('   no se pudo bajar el previo de movimiento:', e)
            return None
    if not p.exists():
        return None
    d = np.load(p)
    return d['X'], d['y'].astype(str)
CODIGOS = ('TR', 'TR+OP', 'OP', 'S', 'D', 'NV')
A_CLASE = {'TR': 'TR', 'TR+OP': 'TR', 'OP': 'OP', 'S': 'H', 'D': 'H'}

PUNTAS = [4, 8, 12, 16, 20]
CLASES = ['TR', 'OP', 'H']
STATS = ['vis', 'vel_med', 'vel_p90', 'vel_max', 'dedos_med', 'dedos_p90', 'apert_med', 'apert_std', 'pinza_med',
         'dist_otra', 'dist_trab', 'dist_trab_max', 'dist_casa', 'despl']


def senales(pi):
    """Señales a 10 Hz por mano (en largos de palma)."""
    ts = np.array(sorted(pi), dtype=float)
    n = len(ts)
    c, tam, rel = {}, {}, {}
    for k in 'RL':
        c[k] = np.full((n, 2), np.nan)
        tam[k] = np.full(n, np.nan)
        rel[k] = np.full((n, 5, 2), np.nan)
        for i, t in enumerate(ts):
            p = pi[t][k]
            if p is None:
                continue
            cc, tt = _centro_tam(p)
            c[k][i], tam[k][i] = cc, tt
            rel[k][i] = (p[PUNTAS, :2] - p[0, :2]) / tt
    ref = np.nanmedian(np.concatenate([tam['R'], tam['L']]))
    ambas = ~np.isnan(c['R'][:, 0]) & ~np.isnan(c['L'][:, 0])
    juntas = ambas & (np.linalg.norm(c['R'] - c['L'], axis=1) < 1.5 * ref)
    mid = (c['R'] + c['L']) / 2
    punto = np.nanmedian(mid[juntas], axis=0) if juntas.sum() > 5 else np.nanmedian(mid, axis=0)
    out = {'t': ts, 'ref': ref}
    for k, o in (('R', 'L'), ('L', 'R')):
        dt = np.full(n, np.nan)
        dt[1:-1] = ts[2:] - ts[:-2]
        vel = np.full(n, np.nan)
        vel[1:-1] = np.linalg.norm(c[k][2:] - c[k][:-2], axis=1) / ref / dt[1:-1]
        dedos = np.full(n, np.nan)
        dedos[1:-1] = np.linalg.norm(rel[k][2:] - rel[k][:-2], axis=2).mean(axis=1) / dt[1:-1]
        casa = np.nanmedian(c[k], axis=0)
        out[k] = {'c': c[k], 'vis': ~np.isnan(c[k][:, 0]), 'vel': vel, 'dedos': dedos,
                  'apert': np.linalg.norm(rel[k], axis=2).mean(axis=1),
                  'pinza': np.linalg.norm(rel[k][:, 0] - rel[k][:, 1], axis=1),
                  'dist_otra': np.linalg.norm(c[k] - c[o], axis=1) / ref,
                  'dist_trab': np.linalg.norm(c[k] - punto, axis=1) / ref,
                  'dist_casa': np.linalg.norm(c[k] - casa, axis=1) / ref}
    return out


def _q(x, q):
    x = x[~np.isnan(x)]
    return float(np.percentile(x, q)) if len(x) else np.nan


def stats(sg, k, t0, t1):
    m = (sg['t'] >= t0) & (sg['t'] < t1)
    h = sg[k]
    if not m.any():
        return [0.0] + [np.nan] * (len(STATS) - 1)
    cc = h['c'][m]
    cc = cc[~np.isnan(cc[:, 0])]
    despl = float(np.linalg.norm(cc[-1] - cc[0]) / sg['ref']) if len(cc) >= 2 else np.nan
    return [float(h['vis'][m].mean()), _q(h['vel'][m], 50), _q(h['vel'][m], 90), _q(h['vel'][m], 100),
            _q(h['dedos'][m], 50), _q(h['dedos'][m], 90), _q(h['apert'][m], 50),
            float(np.nanstd(h['apert'][m])) if (~np.isnan(h['apert'][m])).sum() > 1 else np.nan,
            _q(h['pinza'][m], 50), _q(h['dist_otra'][m], 50), _q(h['dist_trab'][m], 50), _q(h['dist_trab'][m], 100),
            _q(h['dist_casa'][m], 50), despl]


def vector(sg, k, s, paso=1.0):
    """Rasgos de la mano k en el segundo s: la propia mano en s-1, s, s+1 y la otra mano en s."""
    o = 'L' if k == 'R' else 'R'
    a = lambda kk, t: stats(sg, kk, t, t + paso)
    return a(k, s) + a(k, s - paso) + a(k, s + paso) + a(o, s) + [1.0 if k == 'R' else 0.0]


def nombres():
    return ([f'{x}' for x in STATS] + [f'{x}_ant' for x in STATS] + [f'{x}_sig' for x in STATS] +
            [f'otra_{x}' for x in STATS] + ['es_derecha'])


def a_codigo(c, otra):
    return c if c in ('TR', 'OP') else ('S' if otra == 'OP' else 'D')


def predecir(modelo, sg, segundos):
    """{s: (md, mi, probas_R, probas_L)} con probas en el orden de modelo.classes_."""
    X = np.array([vector(sg, k, s) for s in segundos for k in 'RL'], dtype=float)
    P = modelo.predict_proba(X)
    cl = list(modelo.classes_)
    out = {}
    for i, s in enumerate(segundos):
        pr, pl = P[2 * i], P[2 * i + 1]
        cr, clz = cl[int(np.argmax(pr))], cl[int(np.argmax(pl))]
        out[s] = (a_codigo(cr, clz), a_codigo(clz, cr), pr, pl)
    return out


def nuevo_modelo():
    """Hiperparámetros de analisis/mov_entrenar.py, pero SIN «early stopping» (11-oct, auditoría): con > 10 000 filas
    sklearn apartaba en silencio un 10 % como validación, incluidos segundos que el usuario revisó. max_iter = 200 ≈ las
    185 iteraciones que elegía el early stopping."""
    import os
    from sklearn.ensemble import HistGradientBoostingClassifier
    if os.environ.get('MODELO_ES') == '1':        # variante de desarrollo: el early stopping de antes
        return HistGradientBoostingClassifier(max_depth=6, max_iter=300, learning_rate=0.06, l2_regularization=1.0,
                                              class_weight='balanced', random_state=0)
    return HistGradientBoostingClassifier(max_depth=6, max_iter=200, learning_rate=0.06, l2_regularization=1.0,
                                          class_weight='balanced', random_state=0, early_stopping=False)


def etiquetas(ruta, hasta=None):
    """{segundo: (md, mi)} desde un JSON con filas (t0, t1 y códigos): la página de revisión del agente
    (md/mi) o la del minuto de oro (cmd/cmi, con t0_abs si el clip no empieza en 0). Ignora filas sin código."""
    d = json.loads(Path(ruta).read_text(encoding='utf-8'))
    out = {}
    for f in d['filas']:
        if 'ok' in f and not (f.get('ok') or f.get('cambiada')):
            continue                      # fila que el analista no miró: no se aprende de ella
        md, mi = f.get('cmd') or f.get('md'), f.get('cmi') or f.get('mi')
        if md not in CODIGOS or mi not in CODIGOS:
            continue
        t0 = f.get('t0_abs', f['t0'])
        for s in range(int(round(t0)), int(round(t0 + f['t1'] - f['t0']))):
            if hasta is None or s < hasta:
                out[s] = (md, mi)
    return out


def modelo_entrenado(sg=None, calibracion=None, peso=20.0):
    """Clasificador listo: rasgos de IMPACT guardados (models/motion_prior_impact.npz, derivados de un dataset
    CC BY-NC-SA: no van en el repositorio MIT) + opcionalmente los segundos ya etiquetados del propio video
    (calibración: {s: (md, mi)}), con más peso porque son de ESTA operación y ESTA cámara."""
    pv = previo()
    if pv is None:
        raise FileNotFoundError(f'falta {MODELOS / PREVIO} (previo de movimiento, CC BY-NC-SA): ver README')
    X, y = pv
    w = np.ones(len(y))
    if calibracion:
        Xl, yl = [], []
        for s, (md, mi) in sorted(calibracion.items()):
            for k, c in (('R', md), ('L', mi)):
                if c in A_CLASE:
                    Xl.append(vector(sg, k, s))
                    yl.append(A_CLASE[c])
        if Xl:
            X, y = np.vstack([X, np.array(Xl, dtype=float)]), np.concatenate([y, yl])
            w = np.concatenate([w, np.full(len(yl), peso)])
    return nuevo_modelo().fit(X, y, sample_weight=w)


class Ensamble:
    """Promedio de probabilidades de varios clasificadores (p. ej. uno por cada operario que se deja fuera):
    las decisiones en los bordes dependen menos de con qué personas se entrenó."""
    def __init__(self, modelos):
        self.modelos = modelos
        self.classes_ = modelos[0].classes_

    def predict_proba(self, X):
        return np.mean([m.predict_proba(X) for m in self.modelos], axis=0)

    def predict(self, X):
        return self.classes_[self.predict_proba(X).argmax(1)]
