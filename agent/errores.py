"""Detectores de ERRORES DE MÉTODO a partir del movimiento de las manos (MediaPipe) y de los códigos del diagrama.
Genéricos: no saben qué producto es. Cada detector devuelve eventos {tipo, mano, t0, t1, detalle}.

- cruce: una mano trabaja del lado de la otra (pasa la línea media del cuerpo más de media mano) ≥ 0,3 s.
  La línea media y el «lado de casa» de cada mano se estiman del propio video (mediana).
- fuera_de_cuadro: una mano no se ve ≥ 1 s.
- alcance_lejano: la mano se aleja del punto de trabajo más de N largos de palma (punto de trabajo = mediana de donde
  están las manos cuando trabajan juntas). Umbral a calibrar: un largo de palma (muñeca-nudillo medio) ≈ 10 cm.
- sostiene_y_viaja: la mano que sostiene (S/D) se desplaza rápido mientras la otra no opera → el conjunto viaja.
- ambas_ociosas: las dos manos en D al mismo tiempo ≥ 1 s.
- espera_sosteniendo: una mano en D sosteniendo mientras la otra solo transporta (mano usada como prensa sin trabajo).
"""
import numpy as np

from manos import _centro_tam


TITULO = {'cruce': 'Cruce de manos', 'fuera_de_cuadro': 'Mano fuera del puesto', 'alcance_lejano': 'Alcance lejano',
          'sostiene_y_viaja': 'La mano que sostiene se va a buscar (y suele entregar la pieza a la otra)', 'ambas_ociosas': 'Las dos manos sin trabajar',
          'espera_sosteniendo': 'Mano usada como prensa mientras la otra va por la pieza',
          'transferencia': 'La pieza pasa de una mano a otra', 'busqueda': 'Búsqueda o selección de piezas',
          'retrabajo': 'Retrabajo: retira y vuelve a colocar', 'torpeza': 'Pieza que se cae o se manipula torpemente',
          'instrucciones': 'Consulta de instrucciones'}
CORRECCION = {
    'cruce': 'Poner cada material del lado de la mano que lo usa (o que alimente la mano de ese lado): ningún alcance '
             'debe cruzar el cuerpo.',
    'fuera_de_cuadro': 'Revisar qué hace la mano fuera del puesto; si va por material, acercarlo al área de trabajo.',
    'alcance_lejano': 'Acercar ese material al área normal de trabajo, en el orden de uso.',
    'sostiene_y_viaja': 'Dar al conjunto un sitio fijo (soporte o plantilla) y poner la pieza del lado de la mano '
                        'que la coloca: el conjunto no viaja y la pieza no cambia de mano.',
    'ambas_ociosas': 'Si es consulta de instrucciones: ponerlas a la vista (atril o pantalla). Si es espera: preparar '
                     'el material antes.',
    'espera_sosteniendo': 'Un soporte para el conjunto libera esa mano para alimentar la siguiente pieza.',
    'transferencia': 'Que la pieza llegue directamente a la mano que la coloca (material de su lado o punto de entrega).',
    'busqueda': 'Bandejas por pieza o por paso, a la vista, para eliminar buscar y seleccionar.',
    'retrabajo': 'Guía o tope que obligue a la posición correcta; revisar la instrucción de ese paso.',
    'torpeza': 'Contenedores con paredes y piezas presentadas en la orientación de uso.',
    'instrucciones': 'Instrucciones visibles sin tocarlas (atril o pantalla a la altura de los ojos).'}


TITLE_EN = {'cruce': 'Hands cross', 'fuera_de_cuadro': 'Hand leaves the workstation', 'alcance_lejano': 'Long reach',
            'sostiene_y_viaja': 'The holding hand goes fetching (and often hands the part over)',
            'ambas_ociosas': 'Both hands idle', 'espera_sosteniendo': 'Hand used as a vise while the other fetches',
            'transferencia': 'Part passed from one hand to the other', 'busqueda': 'Searching or selecting parts',
            'retrabajo': 'Rework: removes and re-places', 'torpeza': 'Part dropped or fumbled',
            'instrucciones': 'Checking instructions'}
FIX_EN = {
    'cruce': 'Place each material on the side of the hand that uses it: no reach should cross the body.',
    'fuera_de_cuadro': 'Check what the hand does off-station; if it goes for material, bring it into the work area.',
    'alcance_lejano': 'Move that material into the normal working area, in order of use.',
    'sostiene_y_viaja': 'Give the assembly a fixed place (holder or jig) and put the part on the side of the hand that '
                        'places it: the assembly stays put and the part does not change hands.',
    'ambas_ociosas': 'If it is reading instructions: keep them in sight (stand or screen). If it is waiting: stage the '
                     'material beforehand.',
    'espera_sosteniendo': 'A holder for the assembly frees that hand to feed the next part.',
    'transferencia': 'Deliver the part straight to the hand that places it (material on its side or a drop point).',
    'busqueda': 'One bin per part or per step, in sight, to remove searching and selecting.',
    'retrabajo': 'A guide or stop that forces the right position; review the instruction for that step.',
    'torpeza': 'Containers with walls and parts presented in the orientation of use.',
    'instrucciones': 'Instructions visible without handling them (stand or screen at eye level).'}


def para_informe(eventos, max_sueltos=6):
    """Los tipos con muchos eventos (patrones de todo el ciclo) se resumen en una sola línea."""
    from collections import defaultdict
    por = defaultdict(list)
    for e in eventos:
        por[e['tipo']].append(e)
    out = []
    for tipo, lista in por.items():
        if len(lista) <= max_sueltos:
            out += lista
        else:
            total = sum(e['t1'] - e['t0'] for e in lista)
            manos = ''.join(sorted({c for e in lista for c in e['mano']}))
            out.append({'tipo': tipo, 'mano': manos, 't0': lista[0]['t0'], 't1': lista[-1]['t1'], 'resumen': True,
                        'detalle': f'{len(lista)} veces, {total:.0f} s en total (patrón de todo el ciclo)'})
    return sorted(out, key=lambda e: e['t0'])


def _serie(pi):
    ts = np.array(sorted(pi))
    R = [pi[t]['R'] for t in ts]
    L = [pi[t]['L'] for t in ts]
    cR = np.array([_centro_tam(p)[0] if p is not None else (np.nan, np.nan) for p in R])
    cL = np.array([_centro_tam(p)[0] if p is not None else (np.nan, np.nan) for p in L])
    tam = np.nanmedian([_centro_tam(p)[1] for p in R + L if p is not None])
    return ts, cR, cL, tam


def _tramos(ts, mask, minimo):
    out, ini = [], None
    for i, m in enumerate(mask):
        if m and ini is None:
            ini = i
        if (not m or i == len(mask) - 1) and ini is not None:
            fin = i if m else i - 1
            if ts[fin] - ts[ini] + 0.1 >= minimo:
                out.append((float(ts[ini]), float(ts[fin]) + 0.1))
            ini = None
    return out


def detectar(pi, codigos=None, sensores_seg=None, n_alcance=4.0):
    """pi: pista de manos; codigos: {segundo: (md, mi)}; sensores_seg: {segundo: sensores()}."""
    ts, cR, cL, tam = _serie(pi)
    ev = []
    ambas = ~np.isnan(cR[:, 0]) & ~np.isnan(cL[:, 0])
    medio = np.nanmedian((cR[ambas, 0] + cL[ambas, 0]) / 2)
    lado = {'R': np.sign(np.nanmedian(cR[:, 0] - medio)), 'L': np.sign(np.nanmedian(cL[:, 0] - medio))}
    # cruce: las manos invierten su orden habitual en la imagen (una pasa por delante o por debajo de la otra).
    # Más robusto que una línea media fija: el operario se corre en la silla y el punto de trabajo cambia.
    orden = np.sign(np.nanmedian(cR[ambas, 0] - cL[ambas, 0]))
    invertidas = np.zeros(len(ts), bool)
    invertidas[ambas] = (cR[ambas, 0] - cL[ambas, 0]) * orden < -0.3 * tam
    for t0, t1 in _tramos(ts, invertidas, 0.3):
        # ¿cuál cruzó? la que más se alejó de su posición habitual
        i0, i1 = np.searchsorted(ts, t0), np.searchsorted(ts, t1)
        dR = abs(np.nanmedian(cR[i0:i1, 0]) - np.nanmedian(cR[ambas, 0]))
        dL = abs(np.nanmedian(cL[i0:i1, 0]) - np.nanmedian(cL[ambas, 0]))
        ev.append({'tipo': 'cruce', 'mano': 'R' if dR >= dL else 'L', 't0': t0, 't1': t1,
                   'detalle': 'las manos se cruzan: una pasa al lado de la otra'})
    # fuera de cuadro
    for mano, c in (('R', cR), ('L', cL)):
        for t0, t1 in _tramos(ts, np.isnan(c[:, 0]), 1.0):
            ev.append({'tipo': 'fuera_de_cuadro', 'mano': mano, 't0': t0, 't1': t1, 'detalle': 'la mano no se ve'})
    # alcance lejano: punto de trabajo = mediana de las manos cuando están juntas
    juntas = ambas & (np.linalg.norm(cR - cL, axis=1) < 1.5 * tam)
    punto = np.nanmedian(((cR + cL) / 2)[juntas], axis=0) if juntas.any() else np.nanmedian((cR + cL) / 2, axis=0)
    for mano, c in (('R', cR), ('L', cL)):
        lejos = np.linalg.norm(c - punto, axis=1) > n_alcance * tam
        for t0, t1 in _tramos(ts, np.nan_to_num(lejos, nan=0).astype(bool), 0.3):
            ev.append({'tipo': 'alcance_lejano', 'mano': mano, 't0': t0, 't1': t1,
                       'detalle': f'a más de {n_alcance:g} palmas (~{10 * n_alcance:.0f} cm) del punto de trabajo'})
    # reglas sobre los códigos
    if codigos:
        segs = sorted(codigos)
        def tramos_cod(cond, minimo=1):
            out, ini = [], None
            for s in segs + [None]:
                ok = s is not None and cond(s)
                if ok and ini is None:
                    ini = s
                if not ok and ini is not None:
                    fin = prev
                    if fin - ini + 1 >= minimo:
                        out.append((ini, fin + 1))
                    ini = None
                prev = s
            return out
        for t0, t1 in tramos_cod(lambda s: codigos[s] == ('D', 'D')):
            ev.append({'tipo': 'ambas_ociosas', 'mano': 'RL', 't0': t0, 't1': t1,
                       'detalle': 'las dos manos en espera (o con el folleto)'})
        # la mano que normalmente sostiene es la que más tiempo pasa en S
        sostenedora = max((0, 1), key=lambda k: sum(1 for s in segs if codigos[s][k] == 'S'))
        for k, mano in ((0, 'R'), (1, 'L')):
            for t0, t1 in tramos_cod(lambda s: codigos[s][k] == 'D' and codigos[s][1 - k] == 'TR'):
                ev.append({'tipo': 'espera_sosteniendo', 'mano': mano, 't0': t0, 't1': t1,
                           'detalle': 'sostiene y espera mientras la otra va por la pieza'})
        k, mano = sostenedora, 'RL'[sostenedora]
        clave = 'mano_derecha' if k == 0 else 'mano_izquierda'
        for t0, t1 in tramos_cod(lambda s: codigos[s][k] in ('TR', 'TR+OP') and codigos[s][1 - k] in ('D', 'NV', 'S')
                                 and (not sensores_seg or (sensores_seg[s][clave]['velocidad_mediana'] or 0) >= 0.6)):
            ev.append({'tipo': 'sostiene_y_viaja', 'mano': mano, 't0': t0, 't1': t1,
                       'detalle': 'la mano que suele sostener el conjunto se va a buscar (el conjunto viaja)'})
    return sorted(ev, key=lambda e: e['t0'])
