"""Prueba del v10 «modo estación» en IMPACT con 8 videos que nunca se usaron (v10/PREREGISTRO_V10_IMPACT.md), UNA vez.
El sistema es el congelado de KIT sin tocar (final.py, sistema.py, CAL 5, PESO_A 0,5); aquí solo se arman sus filas
con los mismos rasgos (construir.fila y cuadros.fila), con la «tarea» = desarme o reensamble.
- Estación: 11 corridas de 9 operarios (ENTRENAR + DESARROLLO 2) con los códigos de Gemma del laboratorio (11-oct) y
  toda su verdad. Mano dominante: de sus primeros 60 s, como la persona nueva.
- Prueba: 8 corridas de los 4 operarios de PRUEBA 2. Su verdad SOLO se lee en los primeros 60 s (la revisión) al armar
  las filas; desde el segundo 60 se lee después de predecir y de dejar la marca de inicio.
- Una persona nueva = un operario (sus dos corridas): 4 ajustes, cada uno con la estación + sus primeros 60 s.
- Atributos de Gemma: NO (la estación solo tiene códigos; enmienda del pre-registro antes de mirar).
- v9 = el producto: previo de IMPACT + compuerta con los primeros 60 s de cada corrida como revisión (como el ejemplo
  del engranaje). v5 = Gemma sola.
Uso: python v10/impact_v10.py --seco     (arma, comprueba y predice; no lee la verdad desde el segundo 60)
     python v10/impact_v10.py --si       (una sola vez: marca, verdad, puntuación)"""
import hashlib, importlib.util, json, os, sys, time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent
sys.path.insert(0, str(AQUI))
import construir as co  # noqa: E402  (rutas del agente, una(), fila(), leer_txt, leer_pred)
import cuadros as cu  # noqa: E402
import final  # noqa: E402
import sistema as si  # noqa: E402
import compuerta as cp, movimiento as mv, seleccion as se  # noqa: E402
from agente_v5 import _fallida  # noqa: E402
from manos import cargar, pista  # noqa: E402

_esp = importlib.util.spec_from_file_location('verdad_lab', co.LAB / 'verdad.py')
vd = importlib.util.module_from_spec(_esp)
_esp.loader.exec_module(vd)

co.TAREAS = ('Disassembly', 'Reassembly')           # la «tarea» de IMPACT (construir.fila y cuadros.fila la leen de aquí)
ATRIB = ('am1_', 'a0_', 'ap1_', 'ao0_')             # rasgos de atributos de Gemma: aquí no hay (enmienda 1)
NOMBRES_S = [n for n in co.nombres() if not n.startswith(ATRIB)]
QUEDA = np.array([not n.startswith(ATRIB) for n in co.nombres()])
IMP = Path(r'C:\Users\juand\Botv2_caches\datasets_bimanual\impact_full')
ESTACION = ['AL07EJ17_Disassembly_A_002', 'AL07EJ17_Reassembly_A_003', 'ER07AD15_Disassembly_A_002',
            'ER07AD15_Reassembly_A_001', 'KE03ER16_Disassembly_A_001', 'KI03AR28_Disassembly_A_001',
            'KJ03JM25_Disassembly_A_004', 'LE06AS03_Disassembly_A_003', 'MA07LF04_Disassembly_A_003',
            'NA07GE21_Reassembly_A_003', 'SS07EL13_Disassembly_B_005']
PRUEBA = ['ER10WE06_Disassembly_A_002', 'ER10WE06_Reassembly_A_001', 'KI05KO01_Disassembly_A_002',
          'KI05KO01_Reassembly_A_003', 'LE07UF17_Disassembly_A_001', 'LE07UF17_Reassembly_A_002',
          'TO08CO25_Disassembly_A_002', 'TO08CO25_Reassembly_A_002']
CODS_PRUEBA = RAIZ / 'banco' / 'impact_v10_prueba'
REVISADO = 60
INICIO = AQUI / 'impact_v10.inicio'
SAL = AQUI / 'resultado_impact_v10.json'

operario = lambda c: c.split('_')[0]
tarea_de = lambda c: c.split('_')[1]


def puntos(c):
    return IMP / 'puntos' / f'{c}.npz' if c in ESTACION else IMP / 'v10_prueba' / 'puntos' / f'{c}__take_0.npz'


def gemma(c):
    """{s: (md, mi)} de Gemma; sin atributos en los dos lados."""
    if c in ESTACION:
        return co.leer_txt(co.LAB / 'analisis' / f'vision_{c}.txt')
    return co.leer_pred(CODS_PRUEBA / f'{c}__take_0' / 'pred.json')


def etiquetas(c, hasta=None):
    """Etiquetas por cuadro (BL, BR) de la corrida c. Con `hasta` (segundos) se quedan solo los primeros hasta·30
    cuadros (Codex H01: de la prueba, nada desde el segundo 60 entra en memoria antes de la marca de inicio)."""
    base = vd.IMPACT if (vd.IMPACT / 'groundTruth_TAS-BL' / f'{c}_top.txt').exists() else vd.IMPACT_COMPLETO
    bl = (base / 'groundTruth_TAS-BL' / f'{c}_top.txt').read_text().split()
    br = (base / 'groundTruth_TAS-BR' / f'{c}_top.txt').read_text().split()
    if hasta is not None:
        bl, br = bl[:hasta * 30], br[:hasta * 30]
    return bl, br


def por_segundo(bl, br):
    """Copia literal de verdad.impact_por_segundo sobre etiquetas ya leídas (en seco se comprueba que da lo mismo en las
    11 corridas de la estación)."""
    n = min(len(bl), len(br))
    cod_r, cod_l, nul_r, nul_l, amb = [], [], [], [], []
    for i in range(n):
        cr, cl = vd._clase(br[i]), vd._clase(bl[i])
        res = lambda c, otra: ('S' if otra == 'OP' else 'D') if c == 'H' else ('D' if c == 'N' else c)
        cod_r.append(res(cr, cl)), cod_l.append(res(cl, cr))
        nul_r.append(cr == 'N'), nul_l.append(cl == 'N')
        amb.append(cr == cl == 'OP' and br[i] == bl[i])
    out = {}
    for s in range(int(n / 30 + 0.5)):
        a, b = s * 30, min((s + 1) * 30, n)
        if b - a < 15:
            continue
        mr = Counter(cod_r[a:b]).most_common(1)[0][0]
        ml = Counter(cod_l[a:b]).most_common(1)[0][0]
        out[s] = (mr, ml, sum(nul_r[a:b]) > (b - a) / 2, sum(nul_l[a:b]) > (b - a) / 2, sum(amb[a:b]) > (b - a) / 2)
    return out


def cuadros_verdad(bl, br):
    """Código por cuadro (30 fps) de cada mano con la regla fija del 11-oct (verdad.impact_por_segundo); NULL = None.
    Como en KIT (cuadros.construir), la etiqueta de un cuadro válido se conserva aunque su mano-segundo quede excluida
    por mayoría NULL (Codex H05: declarado en la enmienda)."""
    res = lambda a, otra: None if a == 'N' else (('S' if otra == 'OP' else 'D') if a == 'H' else a)
    FR, FL = [], []
    for i in range(min(len(bl), len(br))):
        cr, cl = vd._clase(br[i]), vd._clase(bl[i])
        FR.append(res(cr, cl))
        FL.append(res(cl, cr))
    return FR, FL


def armar(c, verdad_hasta):
    """Filas por segundo y a 10 Hz de la corrida c. La verdad se lee solo en los segundos < verdad_hasta (None = toda).
    toma = 0 en la revisión (s < 60) y 2 después, para que dominancia() y la calibración usen solo lo revisado."""
    d = np.load(puntos(c))
    fps, nf = float(d['fps']), int(d['n_fotogramas'])
    dur = int(nf / fps + 0.5)                      # del video, no de la verdad
    sg = mv.senales(pista(*cargar(puntos(c))))
    V = gemma(c)
    bl, br = etiquetas(c, verdad_hasta)
    G = por_segundo(bl, br)
    FR, FL = cuadros_verdad(bl, br)
    lee = lambda s: verdad_hasta is None or s < verdad_hasta
    op, ta = operario(c), tarea_de(c)
    Xs, Ms = [], []
    segs = sorted(set(s for s in G if lee(s)) | set(s for s in range(dur) if not lee(s)))
    for s in segs:
        con = lee(s)
        if con and s not in G:
            continue
        toma = 0 if s < REVISADO else 2
        for j, k in enumerate('RL'):
            Xs.append(co.fila(sg, V, None, k, s, dur, ta))
            Ms.append((op, ta, toma, s, j, G[s][j] if con else '', bool(G[s][2 + j]) if con else True,
                       V.get(s, (None, None))[j] or '', True))
    Xc, Mc = [], []
    for i, t in enumerate(sg['t']):
        s = int(np.floor(t))
        con = lee(s)
        if con and s not in G:
            continue
        f = int(round(t * fps))
        for j, k in enumerate('RL'):
            yc = (FR if j == 0 else FL)[f] if con and f < len(FR) else None
            Xc.append(cu.fila(sg, V, k, i, ta, dur))
            Mc.append((op, ta, 0 if s < REVISADO else 2, s, j, G[s][j] if con else '',
                       bool(G[s][2 + j]) if con else True, V.get(s, (None, None))[j] or '', True, yc or '',
                       round(float(t), 2)))
    #  Sin atributos en ningún lado, sus 88 columnas quedarían 100 % vacías y HistGradientBoosting no puede
    #  binarlas (en KIT había atributos en 4 de 5 sujetos): se quitan (enmienda 3)
    return ((np.array(Xs, dtype=np.float32)[:, QUEDA], Ms), (np.array(Xc, dtype=np.float32), Mc),
            (sg, V, G, nf, fps))


def junta(partes):
    X = np.vstack([p[0] for p in partes])
    M = np.empty((sum(len(p[1]) for p in partes), len(partes[0][1][0])), dtype=object)
    i = 0
    for p in partes:
        for m in p[1]:
            M[i] = list(m)
            i += 1
    return X, M


def validar_gemma(c):
    """Codex H02: la corrida de Gemma es la pre-registrada (modelo, tubería del producto, paquetes, Token Factory), una
    ventana por segundo sin repetir, códigos válidos en las dos manos y cobertura ≥ 99 % de los segundos del video (el
    mismo tope del sujeto 4: ≤ 1 % de manos-segundo sin código). Devuelve (ventanas, caídas, manos-segundo sin código)."""
    man = json.loads((CODS_PRUEBA / 'corrida.json').read_text(encoding='utf-8'))
    assert man['modelo'] == 'Gemma-4-31B-IT' and man['producto'] and man['tomas'] == [0], man
    assert Path(man['paquetes']).name == 'paquetes_impact_v10' and 'developer.amd.com' in man['base'], man
    pred = json.loads((CODS_PRUEBA / f'{c}__take_0' / 'pred.json').read_text(encoding='utf-8'))
    t0s = [int(round(o['t0'])) for o in pred]
    assert len(t0s) == len(set(t0s)), f'{c}: ventanas repetidas'
    d = np.load(puntos(c))
    dur = int(int(d['n_fotogramas']) / float(d['fps']) + 0.5)
    V = {int(round(o['t0'])): (o['md'], o['mi']) for o in pred}
    sin = sum(1 for s in range(dur) for j in (0, 1) if V.get(s, (None, None))[j] not in co.CODS)
    return len(pred), sum(1 for o in pred if _fallida(o['crudo'])), sin, 2 * dur


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    SECO = '--seco' in sys.argv
    if '--si' not in sys.argv and not SECO:
        sys.exit('la prueba se mira una vez: añade --si (o --seco para armar y predecir sin leer la verdad)')
    if not SECO and (INICIO.exists() or SAL.exists()):
        sys.exit(f'la prueba ya se empezó ({INICIO}): es una sola vez')
    sha = lambda f: hashlib.sha256(Path(f).read_bytes()).hexdigest()
    # Codex H03: el sistema es el congelado de KIT; el v9 es el del agente entregado con su previo
    SELLO = json.loads((AQUI / 'congelado_v10.json').read_text(encoding='utf-8'))['sello']
    for m in (final, si, co, cu):
        assert SELLO.get(m.__file__) == sha(m.__file__), f'{m.__file__} no es el congelado de KIT'
    AGENTE = Path(r'C:\Users\juand\Botv2_caches\gilbreth\agent')
    import manos  # noqa: E402
    for m in (mv, cp, se, manos):
        assert Path(m.__file__).parent == AGENTE, f'{m.__name__} viene de {m.__file__}'
    assert not os.environ.get('GILBRETH_MODELS') and not os.environ.get('MODELO_ES'), 'variables de entorno cambiadas'
    CODIGO = {str(f): sha(f) for f in [Path(m.__file__) for m in (final, si, co, cu, mv, cp, se, manos, vd)]
              + [Path(__file__), mv.MODELOS / mv.PREVIO]}
    print('código:', {Path(k).name: v[:12] for k, v in CODIGO.items()}, flush=True)

    # ------------------------------------------------------------ 1) filas (la verdad de la prueba, solo s < 60)
    t0 = time.time()
    for c in ESTACION:                              # la copia de la regla de verdad da lo mismo que verdad.py
        assert por_segundo(*etiquetas(c)) == vd.impact_por_segundo(c), c
    EST_S, EST_C = defaultdict(list), defaultdict(list)
    for c in ESTACION:
        fs, fc, _ = armar(c, None)
        EST_S[operario(c)].append(fs), EST_C[operario(c)].append(fc)
    entreno_s = [junta(v) for v in EST_S.values()]
    entreno_c = [junta(v) for v in EST_C.values()]
    PR_S, PR_C, CLIP = defaultdict(list), defaultdict(list), {}
    faltan = [c for c in PRUEBA if not (CODS_PRUEBA / f'{c}__take_0' / 'pred.json').exists()]
    assert SECO or not faltan, f'faltan los códigos de Gemma de {faltan}'
    if faltan:                                      # solo en seco: se ensaya con las corridas que ya tienen Gemma
        print('seco sin Gemma de', faltan, flush=True)
        PRUEBA = [c for c in PRUEBA if c not in faltan]
    GEMMA = {}
    for c in PRUEBA:
        GEMMA[c] = validar_gemma(c)
        fs, fc, CLIP[c] = armar(c, REVISADO)
        PR_S[operario(c)].append(fs), PR_C[operario(c)].append(fc)
    vent, caidas = sum(g[0] for g in GEMMA.values()), sum(g[1] for g in GEMMA.values())
    malos = {c: f'{g[2]}/{g[3]}' for c, g in GEMMA.items() if g[2] > 0.01 * g[3]}
    print('Gemma por corrida (ventanas, caídas, manos-segundo sin código, manos-segundo):', GEMMA, flush=True)
    if malos:                                       # se abstiene ANTES de la marca: la prueba no se gasta
        sys.exit(f'cobertura de Gemma por debajo del 99 % en {malos}: no se mide')
    ns, nc = NOMBRES_S, cu.nombres()
    n_est = sum(len(M) for _, M in entreno_s)
    print(f'estación: {len(entreno_s)} operarios, {n_est} manos-segundo, '
          f'{sum(len(M) for _, M in entreno_c)} manos-muestra · prueba: {vent} ventanas de Gemma, {caidas} caídas '
          f'({time.time() - t0:.0f} s)', flush=True)
    for op in PR_S:
        for M in (junta(PR_S[op])[1], junta(PR_C[op])[1]):
            for m in M:
                assert m[3] < REVISADO or (m[5] == '' and m[6]), f'verdad leída fuera de la revisión: {m[:5]}'
    for c, (sg, V, G, nf, fps) in CLIP.items():
        assert all(s < REVISADO for s in G), c

    # ------------------------------------------------------------ 2) v10 y v10-segundos por operario (sin verdad ≥ 60 s)
    SIS = {n: {} for n in ('v5', 'v9', 'v10', 'v10-segundos')}
    for op in sorted(PR_S):
        nuevo_s, nuevo_c = junta(PR_S[op]), junta(PR_C[op])
        P = final.predecir(entreno_s, nuevo_s, ns, entreno_c, nuevo_c, nc, cal=final.CAL, peso_a=final.PESO_A)
        Pseg = si.ajustar_predecir(entreno_s, nuevo_s, ns, cal=final.CAL, auto=False)
        for i, m in enumerate(nuevo_s[1]):
            if m[3] >= REVISADO:
                clave = (op, m[1], m[3], m[4])
                SIS['v10'][clave] = str(si.CLASES[P[i].argmax()])
                SIS['v10-segundos'][clave] = str(si.CLASES[Pseg[i].argmax()])
    # v9 (el producto) y v5, por corrida, con la revisión = primeros 60 s
    Xi, yi = mv.previo(bajar=False)
    DECIDE = {}
    for c in PRUEBA:
        sg, V, G, nf, fps = CLIP[c]
        dur = int(nf / fps + 0.5)
        rev = [s for s in sorted(G) if s < REVISADO and s in V and not G[s][2] and not G[s][3]]
        cal = [{'sg': sg, 'V': V, 'G': {s: G[s][:2] for s in rev}, 'segs': rev}]
        usar, est = cp.decidir(Xi, yi, cal)
        try:
            m7 = cp.entrenar_clips(Xi, yi, cal)
        except ValueError:
            m7 = None
        segs = [s for s in range(REVISADO, dur) if s in V]
        P7 = se.aplicar('apilado', m7, sg, V, segs) if m7 is not None else {s: V[s] for s in segs}
        P9 = P7 if usar else {s: V[s] for s in segs}
        DECIDE[c] = {'gemma': est['gemma'], 'v7': est['v7'], 'n': est['n'], 'usa': 'v7' if usar else 'Gemma'}
        for s in segs:
            for j in (0, 1):
                SIS['v5'][(operario(c), tarea_de(c), s, j)] = V[s][j]
                SIS['v9'][(operario(c), tarea_de(c), s, j)] = P9[s][j]
    print('compuerta del v9 por corrida:', DECIDE, flush=True)
    if SECO:
        print('seco:', {n: dict(Counter(v.values())) for n, v in SIS.items()}, '· no se lee la verdad ≥ 60 s')
        sys.exit(0)

    # ------------------------------------------------------------ 3) marca atómica y la verdad desde el segundo 60
    os.close(os.open(INICIO, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
    INICIO.write_text(time.strftime('%Y-%m-%d %H:%M:%S'), encoding='utf-8')
    VERDAD, AMB = {}, set()
    for c in PRUEBA:
        completa = por_segundo(*etiquetas(c))
        assert completa == vd.impact_por_segundo(c), c
        assert {s: g for s, g in completa.items() if s < REVISADO} == CLIP[c][2], f'{c}: la revisión no cuadra'
        for s, g in completa.items():
            if s < REVISADO:
                continue
            for j in (0, 1):
                if not g[2 + j]:
                    VERDAD[(operario(c), tarea_de(c), s, j)] = g[j]
                    if g[4]:
                        AMB.add((operario(c), tarea_de(c), s, j))
    comun = sorted(k for k in VERDAD if all(k in SIS[n] for n in SIS))
    con_todos = {k for k in SIS['v10'] if all(k in SIS[n] for n in SIS)}
    cobertura = {n: sum(1 for k in VERDAD if k in SIS[n]) for n in SIS}

    def acierta(n, k, tol):
        """A ±1 s solo cuentan vecinos con predicción de los cuatro sistemas (Codex H06)."""
        op, ta, s, j = k
        return VERDAD[k] in [SIS[n][(op, ta, u, j)] for u in range(s - tol, s + tol + 1) if (op, ta, u, j) in con_todos]

    RES, ACIERTOS = {}, {}
    grupos = [('total', lambda k: True), ('desarme', lambda k: k[1] == 'Disassembly'),
              ('reensamble', lambda k: k[1] == 'Reassembly')]
    grupos += [(c, lambda k, c=c: (k[0], k[1]) == (operario(c), tarea_de(c))) for c in PRUEBA]
    grupos += [(f'{g} sin ambiguos', lambda k, f=f: f(k) and k not in AMB) for g, f in list(grupos)]   # Codex H08
    for nombre, f in grupos:
        claves = [k for k in comun if f(k)]
        r = RES[nombre] = {'n': len(claves)}
        if not claves:
            continue
        for n in SIS:
            for tol, suf in ((0, ''), (1, ' ±1 s')):
                x = sum(acierta(n, k, tol) for k in claves)
                ACIERTOS[(nombre, n + suf)] = x
                r[n + suf] = round(100 * x / len(claves), 1)
        porm = defaultdict(Counter)
        for k in claves:
            porm[k[3]][VERDAD[k]] += 1
        r['linea_base'] = round(100 * sum(x.most_common(1)[0][1] for x in porm.values()) / len(claves), 1)
        print(f'== {nombre} ({r["n"]} manos-seg, línea base {r["linea_base"]} %): Gemma sola {r["v5"]} · v9 {r["v9"]} · '
              f'v10 {r["v10"]} · v10-segundos {r["v10-segundos"]}  |  ±1 s: Gemma {r["v5 ±1 s"]} · v9 {r["v9 ±1 s"]} · '
              f'v10 {r["v10 ±1 s"]} · v10-segundos {r["v10-segundos ±1 s"]}', flush=True)
    CRIT = ACIERTOS[('total', 'v10')] > ACIERTOS[('total', 'v9')]           # aciertos enteros (Codex H07)
    print(f'CRITERIO PRE-REGISTRADO (v10 > v9 en el total): {"SE CUMPLE" if CRIT else "NO SE CUMPLE"} '
          f'({ACIERTOS[("total", "v10")]} frente a {ACIERTOS[("total", "v9")]} aciertos de {RES["total"]["n"]})')
    print(f'cobertura sobre {len(VERDAD)} manos-segundo con verdad válida: {cobertura} · conjunto común {len(comun)} · '
          f'ambiguos {len(AMB)}')
    SAL.write_text(json.dumps({'resultados': RES, 'criterio': CRIT,
                               'aciertos_total': {n: ACIERTOS[('total', n)] for n in SIS}, 'cobertura': cobertura,
                               'comun': len(comun), 'verdad_valida': len(VERDAD), 'compuerta_v9': DECIDE,
                               'codigo': CODIGO, 'gemma': GEMMA}, ensure_ascii=False, indent=1), encoding='utf-8')
