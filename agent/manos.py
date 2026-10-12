"""Manos: puntos de MediaPipe por fotograma (modo video, 10 fps), lateralidad limpia y «sensores» por ventana.
Genérico: sirve para cualquier video cenital o frontal de un puesto de trabajo."""
import numpy as np


def cargar(npz):
    d = np.load(npz)
    return d['t'].astype(float), d['mano'].astype(str), d['puntos'].astype(float)


def _centro_tam(p):
    return p[:, :2].mean(axis=0), max(float(np.linalg.norm(p[0, :2] - p[9, :2])), 1.0)


def pista(t, mano, pts, ventana=2.0):
    """{tiempo: {'R': puntos(21x3) o None, 'L': ...}}. Versión 2 (11-oct, tras la auditoría):
    1) dos IDENTIDADES (A/B) seguidas por continuidad (cercanía a la última posición de cada una);
    2) la lateralidad de cada identidad sale de la MAYORÍA de las etiquetas de MediaPipe de esa identidad en ±ventana s.
    🪤 La versión 1 (pista_v1) corregía a MediaPipe por continuidad y, si la historia arrancaba con las manos cambiadas,
    dejaba la lateralidad equivocada durante TODA la toma (KIT, cámara frontal: tomas enteras invertidas, y Gemma
    sigue las marcas R/L). Con la mayoría, un error de MediaPipe o un cruce de identidades dura a lo sumo la ventana."""
    tiempos = np.unique(t)
    ult = {'A': None, 'B': None}
    asig = []                                     # por tiempo: {'A': (etiqueta_mp, puntos) o None, 'B': ...}
    for tt in tiempos:
        idx = np.where(t == tt)[0][:2]
        dets = [(mano[i], pts[i]) for i in idx]
        a = {'A': None, 'B': None}
        if len(dets) == 2:
            (la, pa), (lb, pb) = dets
            ca, cb = _centro_tam(pa)[0], _centro_tam(pb)[0]
            if ult['A'] is not None and ult['B'] is not None:
                directo = np.linalg.norm(ca - ult['A']) + np.linalg.norm(cb - ult['B'])
                cruzado = np.linalg.norm(ca - ult['B']) + np.linalg.norm(cb - ult['A'])
                primero_a = directo <= cruzado
            elif ult['A'] is not None or ult['B'] is not None:
                conocido = 'A' if ult['A'] is not None else 'B'
                a_cerca = np.linalg.norm(ca - ult[conocido]) <= np.linalg.norm(cb - ult[conocido])
                primero_a = a_cerca if conocido == 'A' else not a_cerca
            else:
                primero_a = True
            a['A'], a['B'] = ((la, pa), (lb, pb)) if primero_a else ((lb, pb), (la, pa))
        elif len(dets) == 1:
            l, p = dets[0]
            c = _centro_tam(p)[0]
            if ult['A'] is None and ult['B'] is None:
                k = 'A'
            elif ult['A'] is None or ult['B'] is None:
                conocido = 'A' if ult['A'] is not None else 'B'
                otro = 'B' if conocido == 'A' else 'A'
                tam = _centro_tam(p)[1]
                k = conocido if np.linalg.norm(c - ult[conocido]) < 3 * tam else otro
            else:
                k = 'A' if np.linalg.norm(c - ult['A']) <= np.linalg.norm(c - ult['B']) else 'B'
            a[k] = (l, p)
        for k in ('A', 'B'):
            if a[k] is not None:
                ult[k] = _centro_tam(a[k][1])[0]
        asig.append(a)
    # votos de MediaPipe por identidad (+1 = R, -1 = L), sumados en ±ventana s
    voto = {k: np.array([0.0 if a[k] is None else (1.0 if a[k][0] == 'R' else -1.0) for a in asig]) for k in 'AB'}
    acum = {k: np.concatenate([[0.0], np.cumsum(v)]) for k, v in voto.items()}
    ini = np.searchsorted(tiempos, tiempos - ventana, 'left')
    fin = np.searchsorted(tiempos, tiempos + ventana, 'right')
    suma = {k: acum[k][fin] - acum[k][ini] for k in 'AB'}
    out = {}
    for i, tt in enumerate(tiempos):
        a = asig[i]
        res = {'R': None, 'L': None}
        presentes = [k for k in 'AB' if a[k] is not None]
        if len(presentes) == 2:
            sa, sb = suma['A'][i], suma['B'][i]
            # A es la derecha si sus votos apuntan a R más que los de B (cubre empates y ventanas sin votos)
            a_es_r = sa > sb if sa != sb else a['A'][0] == 'R' if a['A'][0] != a['B'][0] else \
                _centro_tam(a['A'][1])[0][0] < _centro_tam(a['B'][1])[0][0]
            res['R'], res['L'] = (a['A'][1], a['B'][1]) if a_es_r else (a['B'][1], a['A'][1])
        elif len(presentes) == 1:
            k = presentes[0]
            s = suma[k][i]
            lado = 'R' if s > 0 else 'L' if s < 0 else a[k][0]
            res[lado] = a[k][1]
        out[round(float(tt), 3)] = res
    return out


def pista_v1(t, mano, pts):
    """Versión 1 (hasta el 11-oct): lateralidad corregida por continuidad. Se conserva para reproducir cifras viejas.
    🪤 MediaPipe repite a veces la misma mano (0,2 % en el LEGO, ~5 % en IMPACT): se reasigna por cercanía a la
    última posición conocida de cada mano; si no hay historia, la etiqueta de MediaPipe manda."""
    out, ult = {}, {'R': None, 'L': None}
    for tt in np.unique(t):
        idx = np.where(t == tt)[0]
        dets = [(mano[i], pts[i]) for i in idx][:2]
        asign = {'R': None, 'L': None}
        if len(dets) == 2:
            (la, pa), (lb, pb) = dets
            ca, cb = _centro_tam(pa)[0], _centro_tam(pb)[0]
            if ult['R'] is not None and ult['L'] is not None:
                directo = np.linalg.norm(ca - ult['R']) + np.linalg.norm(cb - ult['L'])
                cruzado = np.linalg.norm(ca - ult['L']) + np.linalg.norm(cb - ult['R'])
                if la != lb:          # etiquetas distintas: se respetan salvo que la continuidad diga claro lo contrario
                    a_es_r = (la == 'R')
                    costo_mp = directo if a_es_r else cruzado
                    costo_otro = cruzado if a_es_r else directo
                    if costo_otro < 0.5 * costo_mp:
                        a_es_r = not a_es_r
                else:
                    a_es_r = directo <= cruzado
            else:
                a_es_r = (la == 'R') if la != lb else ca[0] < cb[0]
            asign['R'], asign['L'] = (pa, pb) if a_es_r else (pb, pa)
        elif len(dets) == 1:
            l, p = dets[0]
            c, tam = _centro_tam(p)
            otro = 'L' if l == 'R' else 'R'
            if (ult[l] is not None and ult[otro] is not None and np.linalg.norm(c - ult[l]) > 3 * tam
                    and np.linalg.norm(c - ult[otro]) < tam):
                l = otro
            asign[l] = p
        for k in ('R', 'L'):
            if asign[k] is not None:
                ult[k] = _centro_tam(asign[k])[0]
        out[round(float(tt), 3)] = asign
    return out


def cercano(pi, t, tol=0.12):
    """Las manos del instante de la pista más cercano a t (o vacío si no hay muestra a menos de tol s)."""
    ts = np.array(sorted(pi))
    if not len(ts):
        return {'R': None, 'L': None}
    j = int(np.argmin(np.abs(ts - t)))
    return pi[ts[j]] if abs(ts[j] - t) <= tol else {'R': None, 'L': None}


def sensores(pi, t0, t1):
    """Velocidad (largos de mano por segundo), visibilidad y distancia entre manos en [t0, t1)."""
    ts = [tt for tt in sorted(pi) if t0 <= tt < t1]
    out = {}
    for k, clave in (('R', 'mano_derecha'), ('L', 'mano_izquierda')):
        vis = [tt for tt in ts if pi[tt][k] is not None]
        vels = []
        for a, b in zip(vis, vis[1:]):
            (ca, sa), (cb, sb) = _centro_tam(pi[a][k]), _centro_tam(pi[b][k])
            vels.append(float(np.linalg.norm(cb - ca)) / ((sa + sb) / 2) / max(b - a, 1e-3))
        out[clave] = {'visible_pct': round(100 * len(vis) / max(len(ts), 1)),
                      'velocidad_mediana': round(float(np.median(vels)), 2) if vels else None,
                      'velocidad_max': round(float(np.max(vels)), 2) if vels else None}
    dist = []
    for tt in ts:
        if pi[tt]['R'] is not None and pi[tt]['L'] is not None:
            (cr, sr), (cl, sl) = _centro_tam(pi[tt]['R']), _centro_tam(pi[tt]['L'])
            dist.append(float(np.linalg.norm(cr - cl)) / ((sr + sl) / 2))
    out['distancia_entre_manos'] = round(float(np.median(dist)), 2) if dist else None
    return out


def sensores_en_texto(s):
    def mano(nombre, d):
        if d['velocidad_mediana'] is None:
            return f'- {nombre}: not detected by the tracker.'
        v = d['velocidad_mediana']
        txt = ('mostly in place (small movements)' if v < 0.6 else
               ('moving moderately' if v < 0.9 else 'traveling across the table (fast)'))
        return (f'- {nombre}: {txt} (median speed {v} hand-lengths/s, peak {d["velocidad_max"]}), '
                f'visible in {d["visible_pct"]} % of samples.')
    dist = s.get('distancia_entre_manos')
    junto = '' if dist is None else ('- The two hands are close together (likely on the same object).' if dist < 1.5
                                     else '- The two hands are apart.') + f' (median distance {dist} hand-lengths)'
    return ('HAND-TRACKER SENSOR DATA for this step (measured; use it to judge motion):\n' + mano('RIGHT hand', s['mano_derecha'])
            + '\n' + mano('LEFT hand', s['mano_izquierda']) + '\n' + junto)
