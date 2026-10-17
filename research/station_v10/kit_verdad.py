"""La verdad de KIT Bimanual Actions por segundo y por cuadro, con la regla de las pruebas (versión 2): acción por
cuadro -> código (0 idle -> D; 1-4 approach/retreat/lift/place -> TR; 5 hold -> S si la otra mano opera, si no D;
6-13 -> OP); segundo s = cuadros [round(s·fps), round((s+1)·fps)), mayoría; la mano-segundo se EXCLUYE si más de la
mitad de sus cuadros es nula; empate -> el código del cuadro central."""
import json, zipfile
from collections import Counter

import rutas

OPERA = {6, 7, 8, 9, 10, 11, 12, 13}


def _por_cuadro(arr):
    out = [None] * (arr[-1] + 1)
    for i in range(0, len(arr) - 1, 2):
        for f in range(arr[i], arr[i + 2] + (1 if i + 2 == len(arr) - 1 else 0) if i + 2 < len(arr) else arr[-1]):
            out[f] = arr[i + 1]
    return out


def cuadros(tarea, toma, sujeto):
    """Código por cuadro de cada mano (None = nulo)."""
    with zipfile.ZipFile(rutas.KIT_GT) as z:
        d = json.loads(z.read(f'bimacs_rgbd_data_ground_truth/subject_{sujeto}/{tarea}/{toma}.json'))
    R, L = _por_cuadro(d['right_hand']), _por_cuadro(d['left_hand'])
    n = min(len(R), len(L))

    def cod(a, b):
        if a is None:
            return None
        if a == 5:
            return 'S' if b in OPERA else 'D'
        return 'D' if a == 0 else ('TR' if a in (1, 2, 3, 4) else 'OP')
    return [cod(R[i], L[i]) for i in range(n)], [cod(L[i], R[i]) for i in range(n)]


def verdad(tarea, toma, fps, sujeto):
    """{segundo: (md, mi, excluir_md, excluir_mi)}."""
    cr, cl = cuadros(tarea, toma, sujeto)
    n = len(cr)

    def mayoria(seq, a, b):
        cuenta = Counter(x for x in seq[a:b] if x is not None)
        nulos = sum(1 for x in seq[a:b] if x is None)
        if nulos > (b - a) / 2 or not cuenta:
            return 'D', True
        top = cuenta.most_common()
        if len(top) > 1 and top[0][1] == top[1][1]:
            centro = seq[(a + b) // 2]
            empatados = {c for c, k in top if k == top[0][1]}
            return (centro if centro in empatados else top[0][0]), False
        return top[0][0], False
    out = {}
    for s in range(int(n / fps + 0.5)):
        a, b = int(round(s * fps)), min(int(round((s + 1) * fps)), n)
        if b - a < fps / 2:
            continue
        (mr, nr), (ml, nl) = mayoria(cr, a, b), mayoria(cl, a, b)
        out[s] = (mr, ml, nr, nl)
    return out
