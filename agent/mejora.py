"""Potencial de mejora EN SEGUNDOS a partir del diagrama bimanual (filas con t0, t1, md, mi).

Tres palancas sobre segundos que no se solapan, cada una con su supuesto a la vista (el usuario los cambia):
1. Liberar la mano que sostiene o espera (soporte, plantilla o reparto del trabajo). Mientras una mano está en S o D,
   la otra alterna transportar y operar; con la mano libre, los transportes se hacen en paralelo con las operaciones
   → ahorro = min(transporte, operación) de la otra mano en esos tramos. Es una cota superior: supone que la mano
   libre alcanza el material.
2. Las dos manos sin trabajar (las dos en S o D: buscar, leer instrucciones, esperar) → se recupera una fracción α
   (por defecto 50 %: instrucciones a la vista, material preparado).
3. Transportes en la ruta crítica (alguna mano transporta y ninguna opera), descontado lo ya paralelizado en 1 →
   acercar el material al área normal de trabajo recorta una fracción β (por defecto 30 %).

El total nunca baja del tiempo en que alguna mano opera. Es una estimación para priorizar; el ahorro real se mide
volviendo a grabar la operación después del cambio."""

OPERA = {'OP', 'TR+OP'}
TRABAJA = OPERA | {'TR'}
LIBRE = {'S', 'D'}
MANO = {'md': 'derecha', 'mi': 'izquierda'}
HAND = {'md': 'right', 'mi': 'left'}


def _dur(f):
    return f['t1'] - f['t0']


def potencial(filas, alfa=0.5, beta=0.3):
    T = sum(_dur(f) for f in filas)
    palancas = []
    par_total = 0.0
    for x, y in (('mi', 'md'), ('md', 'mi')):
        libre = sum(_dur(f) for f in filas if f[x] in LIBRE and f[y] in TRABAJA)
        tr = sum(_dur(f) for f in filas if f[x] in LIBRE and f[y] == 'TR')
        op = sum(_dur(f) for f in filas if f[x] in LIBRE and f[y] in OPERA)
        s = min(tr, op)
        par_total += s
        if s > 0:
            palancas.append({
                'clave': f'liberar_{x}', 'segundos': s,
                'titulo': f'Liberar la mano {MANO[x]} (soporte o plantilla)',
                'title': f'Free the {HAND[x]} hand (fixture or jig)',
                'evidencia': f'La {MANO[x]} sostiene o espera {libre:.0f} s mientras la {MANO[y]} trabaja; en ese '
                             f'tiempo la {MANO[y]} transporta {tr:.0f} s y opera {op:.0f} s, una cosa detrás de otra.',
                'evidence': f'The {HAND[x]} hand holds or waits {libre:.0f} s while the {HAND[y]} hand works; meanwhile '
                            f'the {HAND[y]} hand transports {tr:.0f} s and operates {op:.0f} s, one after the other.',
                'supuesto': f'Con la {MANO[x]} libre, ella trae la siguiente pieza mientras la {MANO[y]} opera: '
                            f'se ahorra min(transporte, operación).',
                'assumption': f'With the {HAND[x]} hand free, it fetches the next part while the {HAND[y]} hand '
                              f'operates: saves min(transport, operation). Upper bound.'})
    ociosas = sum(_dur(f) for f in filas if f['md'] in LIBRE and f['mi'] in LIBRE)
    if ociosas > 0:
        palancas.append({
            'clave': 'ambas_ociosas', 'segundos': alfa * ociosas,
            'titulo': 'Quitar los tramos con las dos manos sin trabajar',
            'title': 'Remove the stretches where both hands are idle',
            'evidencia': f'Las dos manos sostienen o esperan {ociosas:.0f} s (buscar, leer instrucciones, esperar).',
            'evidence': f'Both hands hold or wait for {ociosas:.0f} s (searching, reading instructions, waiting).',
            'supuesto': f'Instrucciones a la vista y material preparado recuperan el {alfa:.0%} de ese tiempo.',
            'assumption': f'Visible instructions and pre-staged material recover {alfa:.0%} of that time.'})
    tr_crit = sum(_dur(f) for f in filas
                  if 'TR' in (f['md'], f['mi']) and f['md'] not in OPERA and f['mi'] not in OPERA)
    resto = max(0.0, tr_crit - par_total)
    if resto > 0:
        palancas.append({
            'clave': 'acercar', 'segundos': beta * resto,
            'titulo': 'Acercar el material al área normal de trabajo',
            'title': 'Bring materials into the normal working area',
            'evidencia': f'{tr_crit:.0f} s del ciclo son solo transporte (ninguna mano opera); {resto:.0f} s quedan '
                         f'después de liberar la mano.',
            'evidence': f'{tr_crit:.0f} s of the cycle are transport only (no hand operating); {resto:.0f} s remain '
                        f'after freeing the hand.',
            'supuesto': f'Material en el orden de uso y al alcance recorta el {beta:.0%} de esos transportes.',
            'assumption': f'Materials within reach and in order of use cut {beta:.0%} of those transports.'})
    piso = sum(_dur(f) for f in filas if f['md'] in OPERA or f['mi'] in OPERA)
    bruto = sum(p['segundos'] for p in palancas)
    ahorro = min(bruto, max(0.0, T - piso))
    for p in palancas:
        p['segundos'] = round(p['segundos'] * (ahorro / bruto if bruto else 0), 1)
        p['pct'] = round(100 * p['segundos'] / T, 1) if T else 0.0
    palancas.sort(key=lambda p: -p['segundos'])
    return {'tiempo_s': round(T, 1), 'ahorro_s': round(ahorro, 1), 'nuevo_s': round(T - ahorro, 1),
            'ahorro_pct': round(100 * ahorro / T, 1) if T else 0.0,
            'capacidad_pct': round(100 * (T / (T - ahorro) - 1), 1) if T > ahorro else 0.0,
            'piso_s': round(piso, 1), 'alfa': alfa, 'beta': beta, 'palancas': palancas}


def economia(pot, unidades_por_turno=None, horas_turno=8.0, turnos_por_anio=250, costo_hora=5.0):
    """Lo que vale el ahorro: más unidades con el mismo turno, o menos horas para las mismas unidades."""
    T, N = pot['tiempo_s'], pot['nuevo_s']
    if not T or not N:
        return {}
    capacidad_antes = horas_turno * 3600 / T
    u = unidades_por_turno or capacidad_antes
    horas_ahorradas = u * (T - N) / 3600 * turnos_por_anio
    return {'unidades_turno_antes': round(capacidad_antes, 1), 'unidades_turno_despues': round(horas_turno * 3600 / N, 1),
            'horas_ahorradas_anio': round(horas_ahorradas, 1), 'valor_anio': round(horas_ahorradas * costo_hora, 2)}


if __name__ == '__main__':
    import json, sys
    d = json.loads(open(sys.argv[1], encoding='utf-8').read())
    p = potencial(d['filas'])
    print(json.dumps({k: v for k, v in p.items() if k != 'palancas'}, ensure_ascii=False))
    for x in p['palancas']:
        print(f"- {x['titulo']}: {x['segundos']} s ({x['pct']} %) · {x['evidencia']} · {x['supuesto']}")
    print(economia(p))
