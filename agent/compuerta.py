"""Compuerta del v7: ¿conviene recodificar este video con el apilado calibrado o dejar a Gemma sola?
Se decide SOLO con lo que el usuario revisó (sin mirar nada más): se estima el acierto del apilado en los segundos
revisados sin dejarlo verse a sí mismo (deja-un-clip-fuera si hay varios clips revisados; dos mitades si hay uno) y se
compara con el acierto de Gemma en esos mismos segundos. Gana el v7 solo si acierta MÁS (empate → Gemma, lo simple).
Motivo (11-oct): el v7 gana en ensamble/taller pero pierde en cocina, donde operar es mover mucho la mano.

Un «clip» es un tramo revisado: {'sg': movimiento.senales(...), 'V': {s: (md, mi)} de Gemma,
'G': {s: (md, mi)} revisado por el usuario, 'segs': [segundos revisados válidos]}."""
import numpy as np

import movimiento as mv
import seleccion as se


def entrenar_clips(Xi, yi, clips, peso=20.0):
    Xs, ys = [], []
    for c in clips:
        X, y = se._xy(c['sg'], c['V'], c['G'], c['segs'], True)
        if len(y):
            Xs.append(X)
            ys.append(y)
    if not ys:
        raise ValueError('ningún segundo revisado utilizable: no se puede calibrar')
    Xb = np.hstack([Xi, np.full((len(Xi), 4 * len(se.CODS)), np.nan)])
    Xl, yl = np.vstack(Xs), np.concatenate(ys)
    return mv.nuevo_modelo().fit(np.vstack([Xb, Xl]), np.concatenate([yi, yl]),
                                 sample_weight=np.concatenate([np.ones(len(yi)), np.full(len(yl), peso)]))


def _pliegues(clips):
    if len(clips) >= 2:
        return [([c for j, c in enumerate(clips) if j != i], [clips[i]]) for i in range(len(clips))]
    c = clips[0]
    a, b = c['segs'][:len(c['segs']) // 2], c['segs'][len(c['segs']) // 2:]
    return [([{**c, 'segs': a}], [{**c, 'segs': b}]), ([{**c, 'segs': b}], [{**c, 'segs': a}])]


def estimar(Xi, yi, clips):
    """Aciertos de Gemma y del v7 (estimado sin verse) en lo revisado, y los discordantes: b = solo el v7 acierta,
    c = solo Gemma acierta (por mano y segundo)."""
    ok5 = ok7 = n = b = c_ = 0
    for ent, med in _pliegues(clips):
        if not any(len(c['segs']) for c in ent) or not any(len(c['segs']) for c in med):
            continue
        m = entrenar_clips(Xi, yi, ent)
        for c in med:
            P = se.aplicar('apilado', m, c['sg'], c['V'], c['segs'])
            for s in c['segs']:
                for k in (0, 1):
                    a7, a5 = P[s][k] == c['G'][s][k], c['V'][s][k] == c['G'][s][k]
                    ok7 += a7; ok5 += a5; n += 1
                    b += a7 and not a5
                    c_ += a5 and not a7
    return {'gemma': ok5, 'v7': ok7, 'n': n, 'b': b, 'c': c_}


def decidir(Xi, yi, clips, criterio='estricto'):
    """criterio 'estricto': v7 si acierta más que Gemma en lo revisado. 'mcnemar': v7 solo si su ventaja supera el ruido
    de la muestra revisada: (b - c) > √(b + c), con b, c los discordantes (≈ una desviación típica, prueba de McNemar)."""
    try:
        est = estimar(Xi, yi, clips)
    except ValueError:
        return False, {'gemma': 0, 'v7': 0, 'n': 0, 'b': 0, 'c': 0}     # sin revisión utilizable → Gemma
    if criterio == 'estricto':
        return est['v7'] > est['gemma'], est
    return (est['b'] - est['c']) > (est['b'] + est['c']) ** 0.5, est
