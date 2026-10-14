"""Agente bimanual v5 (genérico): el modelo de visión ve fotogramas marcados R/L + recortes + datos del sensor de manos,
con instrucciones de ingeniero de métodos y una FICHA DE LA OPERACIÓN que el propio modelo escribe mirando el video
(pasada de escena) o que da el usuario. Nada específico de un producto dentro del prompt.
Solo biblioteca estándar: corre contra cualquier servidor compatible con OpenAI (vLLM en Colab, MI300X de AMD, Ollama).

Uso:
  python agente_v5.py ficha     --base URL --modelo M --escena carpeta/escena --salida ficha.json
  python agente_v5.py segmentos --base URL --modelo M --paquete banco4 --conjunto dev_oro34 --ficha ficha.json
  python agente_v5.py ventanas  --base URL --modelo M --paquete carpeta --ficha ficha.json [--desde 0 --hasta 70]
Opciones: --convencion curso|oit (sostener mientras la otra mano transporta: D o S), --hilos 8, --sin-sensores,
          --sin-recortes, --etiqueta x
"""
import argparse, base64, json, os, random, re, threading, time, urllib.error, urllib.request
from collections import Counter, deque
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

CODIGOS = ['OP', 'TR', 'TR+OP', 'S', 'D', 'NV']

# ---------------------------------------------------------------- pasada de escena: la ficha de la operación
PROMPT_FICHA = """You are a senior industrial methods engineer. Before charting an operator's two hands, you look at
{n} frames taken across the whole video of ONE manual operation at a workstation. A hand tracker drew a MAGENTA box "R"
on the operator's real RIGHT hand and a CYAN box "L" on the real LEFT hand (trust the boxes).
Write the OPERATION CARD another engineer will use to chart each second of this video. Describe only what is visible:
- product: what is being assembled, disassembled, packed, inspected or prepared (one sentence).
- camera_and_operator: where the operator is in the image (top/bottom/left/right) and on which side of the IMAGE each
  hand usually appears.
- work_areas: where, in IMAGE terms (top/bottom/left/right/center), the parts and tools are taken from or left
  (supply areas), where the workpiece is worked on (work point), and where any instructions/documents are.
- objects: the workpiece, the main loose parts and the tools you can see.
- typical_cycle: the repeated sequence of hand activities (e.g. one hand fetches a part/tool while the other holds the
  workpiece, then fits/fastens it), and which hand usually holds and which usually works.
Be concrete and short (max 45 words per field)."""
ESQUEMA_FICHA = {'type': 'object', 'additionalProperties': False,
                 'required': ['product', 'camera_and_operator', 'work_areas', 'objects', 'typical_cycle'],
                 'properties': {k: {'type': 'string', 'maxLength': 400} for k in
                                ['product', 'camera_and_operator', 'work_areas', 'objects', 'typical_cycle']}}


def ficha_a_texto(f):
    return (f"- Product: {f['product']}\n- Camera and operator: {f['camera_and_operator']}\n"
            f"- Work areas: {f['work_areas']}\n- Objects: {f['objects']}\n- Typical cycle: {f['typical_cycle']}")


# ---------------------------------------------------------------- análisis de cada paso
PROMPT_PASO = """ROLE
You are a senior industrial methods engineer (ILO work study) preparing a two-handed process chart (left-hand /
right-hand chart) from a video. Your result will be compared with the chart of an experienced analyst, so be literal
and precise. Report only what you can see.

THE OPERATION (operation card)
{ficha}

HOW TO READ THE IMAGES
- A hand tracker boxed the operator's real hands: RIGHT hand = MAGENTA box "R", LEFT hand = CYAN box "L". Trust the
  boxes; do not reason about mirroring. If a box is missing, that hand was not detected in that image.
- {unidad}{imagenes}

THE WORK CYCLE (logical order of manual work)
For each part or tool: reach it -> grasp it -> bring it to the work point (TRANSPORT) -> position it -> use it or fit it
(OPERATION: assemble, insert, press, screw, tighten, loosen, cut, adjust, flip the workpiece...) -> release or put it
aside (TRANSPORT). Meanwhile the other hand often holds the workpiece like a fixture.
Logical check: a part or tool cannot be used before it is brought. A hand that starts at a supply area (or empty) and
ends at the work point with a new part or tool is TRANSPORTING, even if it ends touching the workpiece.
{sensores}
HOW TO CODE EACH HAND
- OP (operation): the hand fits, presses, inserts, screws, tightens, loosens, cuts or adjusts at the workpiece, or uses
  a tool on it; also turning/orienting the workpiece while the other hand works on it.
- TR (transport): the hand reaches for, grasps, carries or puts down a part, a tool or the workpiece (loaded or empty).
- TR+OP: in the same {paso} the hand clearly does both, a transport AND an operation, each for a large share of the time.
- S (hold): the hand holds the workpiece or a part WHILE the other hand is operating on it.
- D (delay): the hand is idle or waits; {convencion} reading, unfolding or handling instructions/documents is D for
  BOTH hands.
- NV: the hand is not visible.

PROCEDURE - do it in this order
1. Find the supply areas, the work point and any documents in the images.
2. For EACH hand: where is it in the FIRST and in the LAST image of the {paso}?
3. What does each hand grip during most of the {paso}? (workpiece / part / tool / document / nothing)
4. Did the hand travel between areas? Compare its box across the images and use the sensor data.
5. Is THIS hand the one working on the workpiece (fitting, fastening, using a tool)? Small grip changes or slight
   rotations of a hand that only holds are NOT operating.
6. If the hand only holds: is the other hand operating at that moment (S) or not (see D)?
7. Write one short "observations" sentence first, then the facts, and last the code for each hand."""

CONVENCION = {
    'curso': 'holding the workpiece while the other hand is only transporting (not operating) is also D (course '
             'convention);',
    'oit': 'holding the workpiece is S even while the other hand transports (ILO convention);',
}
DONDE = ['supply_area', 'work_point', 'document_area', 'in_between', 'elsewhere', 'not_visible']
CAMPOS_MANO = {'type': 'object', 'additionalProperties': False,
               'required': ['where_first', 'where_last', 'grips', 'motion', 'works_on_workpiece', 'only_holds'],
               'properties': {'where_first': {'type': 'string', 'enum': DONDE},
                              'where_last': {'type': 'string', 'enum': DONDE},
                              'grips': {'type': 'string', 'enum': ['workpiece', 'part', 'tool', 'document', 'nothing']},
                              'motion': {'type': 'string', 'enum': ['still', 'travel', 'fine_work']},
                              'works_on_workpiece': {'type': 'boolean'},
                              'only_holds': {'type': 'boolean'}}}
ESQUEMA_PASO = {'type': 'object', 'additionalProperties': False,
                'required': ['observations', 'right_hand', 'left_hand', 'documents_in_use', 'code_right', 'code_left'],
                'properties': {'observations': {'type': 'string', 'maxLength': 300},
                               'right_hand': CAMPOS_MANO, 'left_hand': CAMPOS_MANO,
                               'documents_in_use': {'type': 'boolean'},
                               'code_right': {'type': 'string', 'enum': CODIGOS},
                               'code_left': {'type': 'string', 'enum': CODIGOS}}}


#  v6: además de los códigos, una descripción corta en español por mano (para las columnas del formato del curso) y
#  avisos de errores de método que solo se ven en la imagen. Van DESPUÉS de los códigos para no cambiar cómo los decide.
PROMPT_V6 = """
AFTER THE CODES, ALSO REPORT
- desc_right / desc_left: what each hand does, in SPANISH, max 8 words, verb first, like a methods chart
  (e.g. "Alcanza y toma pieza gris del montón", "Encaja y presiona la pieza", "Sostiene el conjunto", "Espera").
- method events in this {paso} (true ONLY if clearly visible):
  part_passes_between_hands: a part or the workpiece is handed from one hand to the other.
  searching_for_part: a hand hesitates or rummages in a supply area looking for / selecting the right part.
  removes_and_refits: a part already placed is pulled off or turned and fitted again (correction, rework).
  part_dropped_or_fumbled: a part falls, slips or is re-grasped clumsily.
  hands_crossed: one hand works on the other hand's side, crossing in front of the body or under the other arm."""
EVENTOS_V6 = ['part_passes_between_hands', 'searching_for_part', 'removes_and_refits', 'part_dropped_or_fumbled',
              'hands_crossed']
ESQUEMA_PASO_V6 = json.loads(json.dumps(ESQUEMA_PASO))
ESQUEMA_PASO_V6['required'] += ['desc_right', 'desc_left', 'events']
ESQUEMA_PASO_V6['properties'].update({
    'desc_right': {'type': 'string', 'maxLength': 70}, 'desc_left': {'type': 'string', 'maxLength': 70},
    'events': {'type': 'object', 'additionalProperties': False, 'required': EVENTOS_V6,
               'properties': {e: {'type': 'boolean'} for e in EVENTOS_V6}}})


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
    return ('\nHAND-TRACKER SENSOR DATA (measured; use it to judge motion):\n' + mano('RIGHT hand', s['mano_derecha'])
            + '\n' + mano('LEFT hand', s['mano_izquierda']) + '\n' + junto + '\n')


def b64(p):
    return 'data:image/jpeg;base64,' + base64.b64encode(Path(p).read_bytes()).decode()


# Endpoints compartidos (p. ej. AMD Token Factory): ritmo máximo por minuto, salida JSON sin esquema estricto y corte
# limpio cuando se acaba el cupo del día. Todo por variables de entorno; sin ellas, el comportamiento es el de vLLM.
MODO_JSON = os.environ.get('GILBRETH_JSON_MODE', 'schema')        # schema (vLLM) | object (Token Factory)
RPM = float(os.environ.get('GILBRETH_RPM', '0') or 0)               # 0 = sin límite
_turnos, _cerrojo = deque(), threading.Lock()
SIN_CUPO = threading.Event()                                         # el endpoint dijo que no queda cupo hoy


def _turno():
    """Espera hasta que haya sitio en la ventana de 60 s (compartida por todos los hilos)."""
    if RPM <= 0:
        return
    while True:
        with _cerrojo:
            ahora = time.time()
            while _turnos and ahora - _turnos[0] > 60:
                _turnos.popleft()
            if len(_turnos) < RPM:
                _turnos.append(ahora)
                return
            espera = 60.5 - (ahora - _turnos[0])
        time.sleep(max(espera, 0.2))


def llamar(a, contenido, esquema, nombre, max_tokens=900):
    cuerpo = {'model': a.modelo, 'temperature': 0.0, 'max_tokens': max_tokens,
              'messages': [{'role': 'user', 'content': contenido}],
              'response_format': {'type': 'json_schema', 'json_schema': {'name': nombre, 'strict': True, 'schema': esquema}}}
    if MODO_JSON == 'object':                       # sin esquema estricto: el esquema va en el texto
        cuerpo['response_format'] = {'type': 'json_object'}
        cuerpo['messages'][0]['content'] = contenido + [{'type': 'text', 'text': (
            'Return ONLY one JSON object that follows this JSON Schema exactly (same keys, allowed values only):\n'
            + json.dumps(esquema, separators=(',', ':')))}]
    if getattr(a, 'ollama', False):
        cuerpo['reasoning_effort'] = 'none'
    url = a.base.rstrip('/')
    url += '/chat/completions' if url.endswith('/v1') else '/v1/chat/completions'
    cabeceras = {'Content-Type': 'application/json'}
    if os.environ.get('GILBRETH_API_KEY'):          # endpoint alojado (p. ej. AMD): la clave solo por variable de entorno
        cabeceras['Authorization'] = 'Bearer ' + os.environ['GILBRETH_API_KEY']
    fallos = 0
    for intento in range(10):
        if SIN_CUPO.is_set():
            return {'_error': 'daily quota used up'}
        _turno()
        try:
            req = urllib.request.Request(url, data=json.dumps(cuerpo).encode(), headers=cabeceras)
            t0 = time.time()
            r = json.loads(urllib.request.urlopen(req, timeout=900).read())
            if os.environ.get('GILBRETH_LATENCIAS'):          # banco: latencia y tokens de cada consulta
                with open(os.environ['GILBRETH_LATENCIAS'], 'a', encoding='utf-8') as f:
                    f.write(json.dumps({'paso': nombre, 's': round(time.time() - t0, 3), 'imagenes': sum(
                        1 for c in contenido if c.get('type') == 'image_url'), **(r.get('usage') or {})}) + '\n')
            texto = r['choices'][0]['message'].get('content') or ''
            m = re.search(r'\{.*\}', texto, re.S)
            return json.loads(m.group(0)) if m else {}
        except urllib.error.HTTPError as e:
            detalle = e.read().decode('utf-8', 'replace')[:300].lower()
            if e.code == 400 and 'response_format' in cuerpo and ('response_format' in detalle or 'schema' in detalle):
                cuerpo.pop('response_format')       # API sin salida estructurada: el JSON se saca del texto
                continue
            if e.code in (400, 402, 403, 429) and any(p in detalle for p in ('credit', 'quota', 'spend', 'insufficient')):
                SIN_CUPO.set()                      # no tiene sentido seguir: el cupo vuelve al día siguiente
                return {'_error': 'daily quota used up'}
            if e.code in (429, 502, 503):           # ritmo o saturación: esperar lo que pide el servidor
                espera = float(e.headers.get('Retry-After') or 0) or min(60, 2 ** intento)
                time.sleep(espera + random.uniform(0, 1.5))
                continue
            fallos += 1
            if fallos >= 3:
                return {'_error': f'HTTP {e.code}: {detalle[:150]}'}
            time.sleep(3)
        except Exception as e:                      # red o servidor ocupado: reintento corto
            fallos += 1
            if fallos >= 3:
                return {'_error': str(e)[:200]}
            time.sleep(3)
    return {'_error': 'too many retries'}


def coherencia_curso(md, mi):
    """Convención del curso aplicada al final: S solo si la otra mano opera; si no, D."""
    f = lambda c, otra: 'D' if c == 'S' and otra not in ('OP', 'TR+OP') else c
    return f(md, mi), f(mi, md)


def armar_paso(a, ficha, rutas_paso, rutas_rec, sens, dur, fotos, unidad_ventana):
    partes = [f'Images 1-{len(rutas_paso)} = this {"1-second window" if unidad_ventana else "step"} in time order, taken '
              f'at {", ".join(str(x) for x in fotos)} s after it starts.']
    if rutas_rec:
        partes.append(f'The last {len(rutas_rec)} image(s) = close-up(s) of each hand (R / L letter in the corner) at the '
                      f'moment of image 2.')
    unidad = ('You see ONE 1-second window of a continuous video (the chart is built later by joining equal seconds). '
              'Describe what each hand does during MOST of this second.' if unidad_ventana else
              f'The video was cut into steps: a new step starts every time either hand changes activity; boundaries are '
              f'rounded to the whole second, so the edges may show the neighbor activity. THIS STEP lasts {dur} s. '
              f'Describe what fills MOST of the step.')
    texto = PROMPT_PASO.format(ficha=ficha, unidad=unidad, imagenes='\n- ' + '\n- '.join(partes),
                               sensores='' if a.sin_sensores or not sens else sensores_en_texto(sens),
                               paso='second' if unidad_ventana else 'step', convencion=CONVENCION[a.convencion])
    if getattr(a, 'v6', False):
        texto += PROMPT_V6.format(paso='second' if unidad_ventana else 'step')
    return [{'type': 'text', 'text': texto}] + [{'type': 'image_url', 'image_url': {'url': b64(p)}}
                                                for p in rutas_paso + rutas_rec]


def codigos(j, a):
    if not j or '_error' in j:
        return 'D', 'D'
    md, mi = j.get('code_right', 'D'), j.get('code_left', 'D')
    if j.get('documents_in_use'):
        md = mi = 'D'
    return coherencia_curso(md, mi) if a.convencion == 'curso' else (md, mi)


def leer_ficha(ruta):
    if not ruta:
        return '- (no operation card: infer the work areas from the images)'
    p = Path(ruta)
    d = json.loads(p.read_text(encoding='utf-8'))
    return d['texto'] if 'texto' in d else ficha_a_texto(d)


# ---------------------------------------------------------------- comandos
def cmd_ficha(a):
    escenas = sorted(Path(a.escena).glob('*.jpg'))
    contenido = [{'type': 'text', 'text': PROMPT_FICHA.format(n=len(escenas))}] + [
        {'type': 'image_url', 'image_url': {'url': b64(p)}} for p in escenas]
    f = llamar(a, contenido, ESQUEMA_FICHA, 'ficha', 1200)
    f['texto'] = ficha_a_texto(f) if 'product' in f else '- (card failed)'
    Path(a.salida).write_text(json.dumps(f, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f['texto'])


def correr(a, items, armar):
    t = time.time()
    with ThreadPoolExecutor(a.hilos) as ex:
        esquema = ESQUEMA_PASO_V6 if getattr(a, 'v6', False) else ESQUEMA_PASO
        crudos = list(ex.map(lambda it: llamar(a, armar(it), esquema, 'paso', 1100), items))
    return crudos, time.time() - t


def cmd_segmentos(a):
    """Cortes humanos (como el banco v4): paquete con img/{n:03d}_f0..3, crops, sensores.json, tiempos.json."""
    pq = Path(a.paquete)
    filas = json.loads((pq / f'{a.conjunto}.json').read_text(encoding='utf-8'))
    sens = json.loads((pq / 'sensores.json').read_text(encoding='utf-8'))
    tie = json.loads((pq / 'tiempos.json').read_text(encoding='utf-8'))
    ficha = leer_ficha(a.ficha)

    def armar(r):
        n = r['n']
        paso = [pq / 'img' / f'{n:03d}_f{i}.jpg' for i in range(4)]
        rec = [] if a.sin_recortes else [p for p in (pq / 'img' / f'{n:03d}_crop_R.jpg', pq / 'img' / f'{n:03d}_crop_L.jpg') if p.exists()]
        return armar_paso(a, ficha, paso, rec, sens[str(n)], tie[str(n)]['dur'], tie[str(n)]['fotos'], False)
    crudos, seg = correr(a, filas, armar)
    nombre = f'v5_seg_{a.conjunto}_{a.etiqueta}'
    (pq / f'crudo_{nombre}.json').write_text(json.dumps(dict(zip([r['n'] for r in filas], crudos)), ensure_ascii=False), encoding='utf-8')
    for variante in ('modelo', 'final'):
        ok = tot = 0
        conf = Counter()
        pred = []
        for r, j in zip(filas, crudos):
            md, mi = codigos(j, a) if variante == 'final' else (j.get('code_right', 'D'), j.get('code_left', 'D'))
            pred.append(f"{r['n']}:{md}/{mi}")
            for p, real in ((md, r['cmd']), (mi, r['cmi'])):
                ok += p == real
                tot += 1
                if p != real:
                    conf[f'{real}->{p}'] += 1
        print(f'RESUMEN {nombre} [{variante}]: exacto {ok}/{tot} ({100 * ok / tot:.1f} %) · {seg:.0f} s · '
              f'errores {dict(conf.most_common(6))}')
        print(f'PRED_{variante}', ' '.join(pred))


def cmd_ventanas(a):
    """Segmentación automática: ventanas de 1 s. Paquete con ventanas.json ([{k,t0,t1,fotos,sensores}]) e img/."""
    pq = Path(a.paquete)
    vent = [v for v in json.loads((pq / 'ventanas.json').read_text(encoding='utf-8'))
            if a.desde <= v['t0'] < a.hasta]
    ficha = leer_ficha(a.ficha)

    def armar(v):
        k = v['k']
        paso = [p for p in (pq / 'img' / f'{k:04d}_f{i}.jpg' for i in range(4)) if p.exists()]
        rec = [] if a.sin_recortes else [p for p in (pq / 'img' / f'{k:04d}_crop_R.jpg', pq / 'img' / f'{k:04d}_crop_L.jpg') if p.exists()]
        return armar_paso(a, ficha, paso, rec, v.get('sensores'), round(v['t1'] - v['t0'], 2), v['fotos'], True)
    crudos, seg = correr(a, vent, armar)
    out = [{'k': v['k'], 't0': v['t0'], 't1': v['t1'], 'md': codigos(j, a)[0], 'mi': codigos(j, a)[1], 'crudo': j}
           for v, j in zip(vent, crudos)]
    nombre = f'v5_vent_{a.etiqueta}'
    (pq / f'pred_{nombre}.json').write_text(json.dumps(out, ensure_ascii=False), encoding='utf-8')
    print(f'RESUMEN {nombre}: {len(out)} ventanas en {seg:.0f} s; vacías {sum(1 for o in out if not o["crudo"] or "_error" in o["crudo"])}')
    print('PRED', ' '.join(f"{o['t0']:g}:{o['md']}/{o['mi']}" for o in out))


def filas_de(pred):
    """Une segundos con el mismo par de códigos en filas del diagrama."""
    filas = []
    for o in sorted(pred, key=lambda x: x['t0']):
        if filas and (filas[-1]['md'], filas[-1]['mi']) == (o['md'], o['mi']) and abs(filas[-1]['t1'] - o['t0']) < 0.01:
            filas[-1]['t1'] = o['t1']
            filas[-1]['ks'].append(o['k'])
        else:
            filas.append({'t0': o['t0'], 't1': o['t1'], 'md': o['md'], 'mi': o['mi'], 'ks': [o['k']]})
    return filas


def sensores_union(vs):
    """Sensores de una fila a partir de los de sus ventanas (mediana de medianas, máximo de picos)."""
    out = {}
    for mano in ('mano_derecha', 'mano_izquierda'):
        meds = sorted(v['sensores'][mano]['velocidad_mediana'] for v in vs if v['sensores'][mano]['velocidad_mediana'] is not None)
        picos = [v['sensores'][mano]['velocidad_max'] for v in vs if v['sensores'][mano]['velocidad_max'] is not None]
        out[mano] = {'visible_pct': round(sum(v['sensores'][mano]['visible_pct'] for v in vs) / len(vs)),
                     'velocidad_mediana': meds[len(meds) // 2] if meds else None,
                     'velocidad_max': max(picos) if picos else None}
    ds = sorted(v['sensores']['distancia_entre_manos'] for v in vs if v['sensores'].get('distancia_entre_manos') is not None)
    out['distancia_entre_manos'] = ds[len(ds) // 2] if ds else None
    return out


def cmd_refinar(a):
    """2.ª pasada: cada fila de varios segundos se vuelve a clasificar entera (como un paso), con 4 fotogramas repartidos
    en toda la fila. Las filas de 1 s quedan como estaban."""
    pq = Path(a.paquete)
    vent = {v['k']: v for v in json.loads((pq / 'ventanas.json').read_text(encoding='utf-8'))}
    pred = json.loads(Path(a.pred).read_text(encoding='utf-8'))
    filas = [f for f in filas_de(pred)]
    largas = [f for f in filas if len(f['ks']) >= 2]
    ficha = leer_ficha(a.ficha)

    def armar(f):
        fotos = [(k, i) for k in f['ks'] for i in range(4)]
        sel = [fotos[round(j * (len(fotos) - 1) / 3)] for j in range(4)]
        paso = [pq / 'img' / f'{k:04d}_f{i}.jpg' for k, i in sel]
        km = f['ks'][len(f['ks']) // 2]
        rec = [] if a.sin_recortes else [p for p in (pq / 'img' / f'{km:04d}_crop_R.jpg', pq / 'img' / f'{km:04d}_crop_L.jpg') if p.exists()]
        tiempos = [round(vent[k]['t0'] + vent[k]['fotos'][i] - f['t0'], 2) for k, i in sel]
        return armar_paso(a, ficha, paso, rec, sensores_union([vent[k] for k in f['ks']]), round(f['t1'] - f['t0'], 2),
                          tiempos, False)
    crudos, seg = correr(a, largas, armar)
    nuevo = {o['k']: dict(o) for o in pred}
    cambios = 0
    for f, j in zip(largas, crudos):
        md, mi = codigos(j, a)
        if (md, mi) != (f['md'], f['mi']):
            cambios += 1
        for k in f['ks']:
            nuevo[k]['md'], nuevo[k]['mi'] = md, mi
            nuevo[k]['crudo_fila'] = j
    out = [nuevo[k] for k in sorted(nuevo)]
    nombre = f'v5_ref_{a.etiqueta}'
    (pq / f'pred_{nombre}.json').write_text(json.dumps(out, ensure_ascii=False), encoding='utf-8')
    print(f'RESUMEN {nombre}: {len(filas)} filas, {len(largas)} re-clasificadas en {seg:.0f} s, {cambios} cambiaron')


PROMPT_DESC = """You are a senior industrial methods engineer writing the descriptions of a two-handed process chart.

THE OPERATION (operation card)
{ficha}

The images show ONE row of the chart, {dur} s long, in time order (RIGHT hand = MAGENTA box "R", LEFT hand = CYAN
box "L"). The codes of this row are already decided: RIGHT hand = {cmd} ({dmd}); LEFT hand = {cmi} ({dmi}).
Do not change them. Write:
- desc_right / desc_left: what each hand does in this row, in {idioma}, max 8 words, verb first, like a methods chart
  (e.g. {ejemplos}).
- method events seen in this row (true ONLY if clearly visible):
  part_passes_between_hands: a part or the workpiece is handed from one hand to the other.
  searching_for_part: a hand hesitates or rummages in a supply area looking for / selecting the right part.
  removes_and_refits: a part already placed is pulled off or turned and fitted again (correction, rework).
  part_dropped_or_fumbled: a part falls, slips or is re-grasped clumsily.
  hands_crossed: one hand works on the other hand's side, crossing in front of the body or under the other arm.
Write one short observation first."""
IDIOMA_DESC = {
    'es': {'idioma': 'SPANISH',
           'ejemplos': '"Alcanza y toma pieza gris del montón", "Encaja y presiona la pieza", "Sostiene el conjunto", '
                       '"Espera"'},
    'en': {'idioma': 'ENGLISH',
           'ejemplos': '"Reaches for and grasps grey part from pile", "Fits and presses the part", '
                       '"Holds the assembly", "Waits"'}}
ESQUEMA_DESC = {'type': 'object', 'additionalProperties': False,
                'required': ['observation', 'desc_right', 'desc_left', 'events'],
                'properties': {'observation': {'type': 'string', 'maxLength': 250},
                               'desc_right': {'type': 'string', 'maxLength': 70},
                               'desc_left': {'type': 'string', 'maxLength': 70},
                               'events': ESQUEMA_PASO_V6['properties']['events']}}


def cmd_describir(a):
    """2.ª pasada SEPARADA (no toca los códigos): por cada fila del diagrama, descripción en español por mano y avisos
    de errores de método. (Meterlo en la misma consulta que los códigos los empeoró: medido el 11-oct.)"""
    pq = Path(a.paquete)
    pred = json.loads(Path(a.pred).read_text(encoding='utf-8'))
    filas = filas_de(pred)
    ficha = leer_ficha(a.ficha)

    def armar(f):
        fotos = [(k, i) for k in f['ks'] for i in range(4)]
        sel = [fotos[round(j * (len(fotos) - 1) / 3)] for j in range(4)] if len(fotos) >= 4 else fotos
        rutas = [p for p in (pq / 'img' / f'{k:04d}_f{i}.jpg' for k, i in sel) if p.exists()]
        km = f['ks'][len(f['ks']) // 2]
        rutas += [p for p in (pq / 'img' / f'{km:04d}_crop_R.jpg', pq / 'img' / f'{km:04d}_crop_L.jpg') if p.exists()]
        texto = PROMPT_DESC.format(ficha=ficha, dur=round(f['t1'] - f['t0'], 2), cmd=f['md'], cmi=f['mi'],
                                   dmd=DESC.get(f['md'], ''), dmi=DESC.get(f['mi'], ''),
                                   **IDIOMA_DESC[getattr(a, 'idioma', 'es')])
        return [{'type': 'text', 'text': texto}] + [{'type': 'image_url', 'image_url': {'url': b64(p)}} for p in rutas]
    t = time.time()
    with ThreadPoolExecutor(a.hilos) as ex:
        resp = list(ex.map(lambda f: llamar(a, armar(f), ESQUEMA_DESC, 'desc', 600), filas))
    out = [{'t0': f['t0'], 't1': f['t1'], 'md': f['md'], 'mi': f['mi'], 'desc_md': r.get('desc_right', ''),
            'desc_mi': r.get('desc_left', ''), 'events': r.get('events', {}), 'obs': r.get('observation', '')}
           for f, r in zip(filas, resp)]
    nombre = f'filas_desc_{a.etiqueta}'
    (pq / f'{nombre}.json').write_text(json.dumps(out, ensure_ascii=False), encoding='utf-8')
    print(f'RESUMEN {nombre}: {len(out)} filas descritas en {time.time() - t:.0f} s')


DESC = {'OP': 'OPERATING (fitting, pressing, fastening or using a tool on the workpiece)',
        'TR': 'TRANSPORTING (reaching for, grasping, carrying or putting down a part, a tool or the workpiece)',
        'TR+OP': 'bringing a part AND fitting it',
        'S': 'HOLDING the workpiece while the other hand works on it',
        'D': 'IDLE or WAITING (or only holding while the other hand fetches, or handling documents)',
        'NV': 'NOT VISIBLE'}
PROMPT_BORDE = """You are a senior industrial methods engineer checking WHEN an activity change happens in a two-handed
process chart.

THE OPERATION (operation card)
{ficha}

The 8 images are consecutive moments of a continuous video, in time order, 0.25 s apart (2 seconds in total).
A hand tracker boxed the operator's real hands: RIGHT hand = MAGENTA box "R", LEFT hand = CYAN box "L".

Look ONLY at the {mano} hand. A first pass said that during images 1-4 this hand was {a}, and during images 5-8 it was
{b}. Find the image where the second activity really STARTS:
- answer 1-8 = the first image showing the second activity;
- answer 0 if the hand keeps doing the first activity in all 8 images;
- answer 9 if it is already doing the second activity in all 8 images.
Write one short observation first."""
ESQUEMA_BORDE = {'type': 'object', 'additionalProperties': False, 'required': ['observation', 'start_image'],
                 'properties': {'observation': {'type': 'string', 'maxLength': 250},
                                'start_image': {'type': 'integer', 'enum': list(range(10))}}}


def cmd_bordes(a):
    """Afina los bordes: en cada cambio de código de una mano entre el segundo s-1 y s, el modelo mira los 8 fotogramas
    de esos dos segundos (cada 0,25 s) y dice dónde empieza la actividad nueva. Si empieza en la primera mitad de s-1,
    s-1 pasa a la nueva; si empieza en la segunda mitad de s (o no cambia), s vuelve a la anterior."""
    pq = Path(a.paquete)
    pred = sorted(json.loads(Path(a.pred).read_text(encoding='utf-8')), key=lambda o: o['t0'])
    ficha = leer_ficha(a.ficha)
    bordes = []
    for i in range(1, len(pred)):
        for k, clave, mano in ((0, 'md', 'RIGHT'), (1, 'mi', 'LEFT')):
            x, y = pred[i - 1][clave], pred[i][clave]
            if x != y and 'NV' not in (x, y):
                bordes.append((i, k, clave, mano, x, y))

    def armar(b):
        i, k, clave, mano, x, y = b
        rutas = [pq / 'img' / f'{pred[j]["k"]:04d}_f{f}.jpg' for j in (i - 1, i) for f in range(4)]
        texto = PROMPT_BORDE.format(ficha=ficha, mano=mano, a=DESC[x], b=DESC[y])
        return [{'type': 'text', 'text': texto}] + [{'type': 'image_url', 'image_url': {'url': b64(p)}} for p in rutas if p.exists()]
    t = time.time()
    with ThreadPoolExecutor(a.hilos) as ex:
        resp = list(ex.map(lambda b: llamar(a, armar(b), ESQUEMA_BORDE, 'borde', 400), bordes))
    nuevo = [dict(o) for o in pred]
    tocados, cambios = set(), Counter()
    for b, j in zip(bordes, resp):
        i, k, clave, mano, x, y = b
        f = j.get('start_image') if isinstance(j, dict) else None
        if f is None:
            continue
        if f in (1, 2, 9) and (i - 1, clave) not in tocados:      # lo nuevo ya domina el segundo anterior
            nuevo[i - 1][clave] = y
            tocados.add((i - 1, clave))
            cambios['antes'] += 1
        elif f in (0, 7, 8) and (i, clave) not in tocados:        # lo anterior domina el segundo actual
            nuevo[i][clave] = x
            tocados.add((i, clave))
            cambios['despues'] += 1
        else:
            cambios['igual'] += 1
    if a.convencion == 'curso':
        for o in nuevo:
            o['md'], o['mi'] = coherencia_curso(o['md'], o['mi'])
    nombre = f'v5_bordes_{a.etiqueta}'
    (pq / f'pred_{nombre}.json').write_text(json.dumps(nuevo, ensure_ascii=False), encoding='utf-8')
    print(f'RESUMEN {nombre}: {len(bordes)} bordes en {time.time() - t:.0f} s · {dict(cambios)}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('comando', choices=['ficha', 'segmentos', 'ventanas', 'refinar', 'bordes', 'describir'])
    ap.add_argument('--pred')
    ap.add_argument('--base', default='http://127.0.0.1:8000')
    ap.add_argument('--modelo', default='google/gemma-4-31B-it-qat-w4a16-ct')
    ap.add_argument('--escena'), ap.add_argument('--salida'), ap.add_argument('--paquete'), ap.add_argument('--ficha')
    ap.add_argument('--conjunto', default='dev_oro34')
    ap.add_argument('--desde', type=float, default=0), ap.add_argument('--hasta', type=float, default=1e9)
    ap.add_argument('--convencion', default='curso', choices=['curso', 'oit'])
    ap.add_argument('--hilos', type=int, default=8)
    ap.add_argument('--sin-sensores', action='store_true'), ap.add_argument('--sin-recortes', action='store_true')
    ap.add_argument('--ollama', action='store_true')
    ap.add_argument('--v6', action='store_true', help='descripciones en español por mano y avisos de errores')
    ap.add_argument('--etiqueta', default='x')
    a = ap.parse_args()
    {'ficha': cmd_ficha, 'segmentos': cmd_segmentos, 'ventanas': cmd_ventanas, 'refinar': cmd_refinar,
     'bordes': cmd_bordes, 'describir': cmd_describir}[a.comando](a)


if __name__ == '__main__':
    main()
