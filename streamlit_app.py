"""Gilbreth: AI motion study from a workstation video.
A phone video of a manual operation goes in; a draft bimanual (left-hand / right-hand) chart, method alerts and an
improvement plan in seconds saved per unit come out, for the methods engineer to review.
Vision model: Gemma 4 31B served on AMD GPUs (AMD Token Factory, or vLLM on ROCm). Hand tracking: MediaPipe."""
import inspect, json, os, sys, tempfile
from collections import defaultdict
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ / 'agent'))
import errores, mejora  # noqa: E402

st.set_page_config(page_title='Gilbreth · AI motion study', page_icon='⏱️', layout='wide')
SIN_FLECHA = {'delta_arrow': 'off'} if 'delta_arrow' in inspect.signature(st.metric).parameters else {}

ACT = {'OP': 'Operation', 'TR+OP': 'Transport + operation', 'TR': 'Transport', 'S': 'Hold', 'D': 'Delay',
       'NV': 'Not visible'}
SYM = {'OP': '○', 'TR+OP': '○', 'TR': '⇨', 'S': '▽', 'D': 'D', 'NV': '·'}
COLORES = {'Operation': '#2e7d32', 'Transport + operation': '#66bb6a', 'Transport': '#1e88e5', 'Hold': '#fb8c00',
           'Delay': '#e53935', 'Not visible': '#9e9e9e'}
MANO_EN = {'R': 'right', 'L': 'left', 'RL': 'both', 'LR': 'both'}
RITMO_A_MANO = 60 / (284 / 60)      # minutos de trabajo manual por minuto de video, medido en el LEGO (≈ 12,7)
MUESTRA = RAIZ / 'examples' / 'factory_screw' / 'sample_20s.mp4'   # clip de muestra para quien no tiene video a mano
# reparto del tiempo de cada mano en palabras (la barra usa las 6 actividades; el texto las agrupa)
GRUPOS = (('operating', ('OP', 'TR+OP')), ('transporting', ('TR',)), ('holding or waiting', ('S', 'D')),
          ('not visible', ('NV',)))
# costo patronal por hora (verificados el 12-oct-2026; detalle en docs/SOURCES.md)
COSTOS = {
    'United States — production worker, manufacturing': (
        'USD', 39.25, 'BLS Employer Costs for Employee Compensation, June 2026: total compensation per hour worked, '
                      'manufacturing, production occupations.'),
    'Colombia — minimum-wage operator': (
        'COP', 15540, 'Own calculation from the 2026 minimum wage (COP 1,750,905, Decree 1469 of 2025) '
                      'plus transport allowance, benefits and employer contributions, over 182 h/month (42-h week); '
                      'range COP 14,921–16,839 depending on risk class and tax exemption.'),
    'Custom': ('USD', 10.0, 'Type your own cost per hour.')}


@st.cache_data
def ejemplos(huella):            # sin «_»: st.cache_data no mira los parámetros que empiezan con guion bajo
    out = {}
    orden = ['impact_gearbox', 'factory_screw', 'factory_cardboard', 'factory_plastic', 'lego']
    for d in sorted((RAIZ / 'examples').glob('*/diagrama.json'),
                    key=lambda p: (orden.index(p.parent.name) if p.parent.name in orden else len(orden), p.parent.name)):
        meta = json.loads(d.read_text(encoding='utf-8'))['meta']
        out[meta.get('title_en') or d.parent.name] = d.parent
    return out


@st.cache_data
def cargar(carpeta, huella=None):
    carpeta = Path(carpeta)
    d = json.loads((carpeta / 'diagrama.json').read_text(encoding='utf-8'))
    ev = json.loads((carpeta / 'errores.json').read_text(encoding='utf-8')) if (carpeta / 'errores.json').exists() else []
    cal = json.loads((carpeta / 'calibracion.json').read_text(encoding='utf-8')) \
        if (carpeta / 'calibracion.json').exists() else {}
    # el video del ejemplo, nunca el clip de muestra de «Try your own video» que vive en la misma carpeta
    video = carpeta / d['meta']['video'] if (carpeta / d['meta'].get('video', '-')).is_file() else \
        next(iter(p for p in sorted(carpeta.glob('*.mp4')) if not p.name.startswith('sample_')), None)
    verdad = {int(s): v for s, v in json.loads((carpeta / 'verdad.json').read_text(encoding='utf-8')).items()} \
        if (carpeta / 'verdad.json').exists() else {}
    return d, ev, cal, video, verdad


@st.cache_data
def estacion_de(carpeta, huella=None):
    """El mismo ejemplo codificado en modo estación (agent/estacion.py), si existe estacion.json."""
    f = Path(carpeta) / 'estacion.json'
    return json.loads(f.read_text(encoding='utf-8')) if f.exists() else None


@st.cache_data
def banco():
    p = RAIZ / 'docs' / 'benchmark.json'
    return json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}


def tabla_filas(filas):
    return pd.DataFrame([{
        'Time': f"{f['t0']:.0f}–{f['t1']:.0f} s",
        'Left hand': f.get('desc_mi') or ACT[f['mi']], 'L': SYM[f['mi']], 'R': SYM[f['md']],
        'Right hand': f.get('desc_md') or ACT[f['md']],
        'Left activity': ACT[f['mi']], 'Right activity': ACT[f['md']]} for f in filas])


def linea_tiempo(filas, alto=240):
    df = pd.DataFrame([{'hand': mano, 'start': f['t0'], 'end': f['t1'], 'activity': ACT[f[k]],
                        'what': f.get('desc_' + k) or ACT[f[k]]}
                       for f in filas for mano, k in (('Left hand', 'mi'), ('Right hand', 'md'))])
    escala = alt.Scale(domain=list(COLORES), range=list(COLORES.values()))
    return alt.Chart(df).mark_bar().encode(
        x=alt.X('start:Q', title='seconds', scale=alt.Scale(domain=[0, max(f['t1'] for f in filas)], nice=False)),
        x2='end:Q', y=alt.Y('hand:N', title=None, sort=['Left hand', 'Right hand']),
        color=alt.Color('activity:N', scale=escala, legend=alt.Legend(orient='top', title=None, columns=6)),
        tooltip=['hand', 'activity', 'what', 'start', 'end']).properties(height=alto)


def linea_comparada(filas, verdad, alto=300):
    """Agente vs. etiqueta humana, por mano (los segundos sin etiqueta humana quedan en blanco)."""
    filas_d = [{'hand': f'{mano} · Gilbreth', 'start': f['t0'], 'end': f['t1'], 'activity': ACT[f[k]]}
               for f in filas for mano, k in (('Left', 'mi'), ('Right', 'md'))]
    filas_d += [{'hand': f'{mano} · human', 'start': s, 'end': s + 1, 'activity': ACT[v[k]]}
                for s, v in verdad.items() for mano, k in (('Left', 'mi'), ('Right', 'md')) if not v['nulo_' + k]]
    orden = ['Left · Gilbreth', 'Left · human', 'Right · Gilbreth', 'Right · human']
    escala = alt.Scale(domain=list(COLORES), range=list(COLORES.values()))
    return alt.Chart(pd.DataFrame(filas_d)).mark_bar().encode(
        x=alt.X('start:Q', title='seconds', scale=alt.Scale(domain=[0, max(f['t1'] for f in filas)], nice=False)),
        x2='end:Q', y=alt.Y('hand:N', title=None, sort=orden),
        color=alt.Color('activity:N', scale=escala, legend=alt.Legend(orient='top', title=None, columns=6)),
        tooltip=['hand', 'activity', 'start']).properties(height=alto)


def reparto_manos(filas):
    """% del tiempo observado de cada mano en cada código, de las filas (la misma fuente que la línea de tiempo)."""
    total = sum(f['t1'] - f['t0'] for f in filas) or 1
    out = {}
    for mano, k in (('Left hand', 'mi'), ('Right hand', 'md')):
        c = defaultdict(float)
        for f in filas:
            c[f[k]] += f['t1'] - f['t0']
        out[mano] = {cod: 100 * s / total for cod, s in c.items()}
    return out


def barra_manos(filas):
    """«See the hold» de un vistazo: una barra 100 % apilada por mano con el tiempo en cada actividad."""
    datos = []
    for mano, pct in reparto_manos(filas).items():
        x = 0.0
        for cod in ACT:                      # mismo orden que la leyenda: operar → no visible
            p = pct.get(cod, 0.0)
            if p <= 0:
                continue
            datos.append({'hand': mano, 'activity': ACT[cod], 'share': round(p, 1), 'x0': x, 'x1': x + p,
                          'mid': x + p / 2, 'label': f'{p:.0f} %' if p >= 6 else ''})
            x += p
    escala = alt.Scale(domain=list(COLORES), range=list(COLORES.values()))
    base = alt.Chart(pd.DataFrame(datos)).encode(y=alt.Y('hand:N', title=None, sort=['Left hand', 'Right hand'],
                                                         axis=alt.Axis(labelFontSize=13, labelFontWeight='bold')))
    barras = base.mark_bar().encode(
        x=alt.X('x0:Q', title='% of the observed time', scale=alt.Scale(domain=[0, 100], nice=False)), x2='x1:Q',
        color=alt.Color('activity:N', scale=escala, legend=alt.Legend(orient='top', title=None, columns=3, labelFontSize=11,
                                                                    columnPadding=6, symbolSize=70)),
        tooltip=['hand', 'activity', alt.Tooltip('share:Q', title='% of time')])
    texto = base.mark_text(color='white', fontWeight='bold', fontSize=12).encode(x='mid:Q', text='label:N')
    # alto por paso: con un alto fijo de 130 px las dos bandas se aplastaban en una (visto en Chrome)
    return (barras + texto).properties(height=alt.Step(44))


def texto_manos(filas):
    """«Left hand: 5 % operating · 90 % holding or waiting», una línea por mano."""
    lineas = []
    for mano, pct in reparto_manos(filas).items():
        partes = [f'{v:.0f} % {nombre}' for nombre, cods in GRUPOS
                  if (v := sum(pct.get(c, 0.0) for c in cods)) >= 0.5]
        lineas.append(f'**{mano}:** ' + ' · '.join(partes))
    return '  \n'.join(lineas)


def ver_manos(filas):
    st.subheader('Where each hand’s time goes')
    st.altair_chart(barra_manos(filas), width="stretch")
    st.markdown(texto_manos(filas))
    st.caption('Operating = ○ operation, alone or while transporting · holding or waiting = ▽ hold + D delay. A hand '
               'that spends most of the time holding or waiting is the first place to look for a fixture or a better '
               'split of the work.')


def es_clip(meta):
    """Los ejemplos de fábrica son recortes de 150 s con varias unidades: sus tiempos son del clip, no de una unidad."""
    return meta.get('unidad') == 'clip'


def evidencia(palanca, clip):
    """La evidencia de mejora.py habla del «cycle»; en un clip con varias unidades es el clip."""
    return palanca['evidence'].replace('of the cycle', 'of the clip') if clip else palanca['evidence']


def acuerdo(cal, est=None):
    r = cal.get('acierto_vs_humano_desde_60s') or {}
    if 'gilbreth' not in r:
        return ''
    g, v = r['gilbreth'], r['gemma']
    if est:
        e = est['acierto_vs_humano_desde_60s']['estacion']
        return (f"Station mode: agreement with the human labels after the reviewed minute **{100 * e[0] / e[1]:.1f} %** of "
                f"{e[1]:,} hand-seconds (shipped mode {100 * g[0] / g[1]:.1f} %, vision model alone "
                f"{100 * v[0] / v[1]:.1f} %; a second look at this example). Seconds where the dataset gives both hands "
                f"the same verb are left out, because its labels do not say which hand holds.")
    return (f"Agreement with the human labels after the reviewed minute: **{100 * g[0] / g[1]:.1f} %** of "
            f"{g[1]:,} hand-seconds (vision model alone: {100 * v[0] / v[1]:.1f} %). Seconds where the dataset gives "
            f"both hands the same verb are left out, because its labels do not say which hand holds.")


@st.cache_data
def excel_bytes(carpeta, huella=None, huella_est=None):
    """Excel del curso; con huella_est, el del modo estación (sus filas, las alertas del diagrama entregado)."""
    import salidas
    d, ev = cargar(carpeta, huella)[:2]
    filas = estacion_de(carpeta, huella_est)['filas'] if huella_est is not None else d['filas']
    with tempfile.TemporaryDirectory() as tmp:
        ruta = Path(tmp) / 'bimanual_chart.xlsx'
        salidas.escribir_excel(filas, salidas.indicadores(filas), d['meta'], ruta, eventos=ev, idioma='en')
        return ruta.read_bytes()


def alertas_agrupadas(ev):
    por = defaultdict(list)
    for e in ev:
        por[e['tipo']].append(e)
    filas = []
    for tipo, lista in sorted(por.items(), key=lambda x: -sum(e['t1'] - e['t0'] for e in x[1])):
        manos = ''.join(sorted({c for e in lista for c in e['mano']}))
        filas.append({'Alert': errores.TITLE_EN.get(tipo, tipo), 'Hand': MANO_EN.get(manos, manos),
                      'Times': len(lista), 'Total s': round(sum(e['t1'] - e['t0'] for e in lista), 1),
                      'First at': ', '.join(f"{e['t0']:.0f} s" for e in lista[:4]) + (' …' if len(lista) > 4 else ''),
                      'What to change': errores.FIX_EN.get(tipo, '')})
    return pd.DataFrame(filas)


# ---------------------------------------------------------------------------------------------------------------- UI
st.title('⏱️ Gilbreth')
st.markdown('**AI motion study from a workstation video.** A phone video of a manual operation goes in; a draft '
            '**bimanual chart** (what each hand does, second by second), **method alerts** and an **improvement plan '
            'in seconds saved per unit** come out — for the methods engineer to review.')

EJ = ejemplos(tuple(sorted((p.parent.name, p.stat().st_mtime) for p in (RAIZ / 'examples').glob('*/diagrama.json'))))
with st.sidebar:
    st.header('Example')
    nombre = st.selectbox('Operation', list(EJ), label_visibility='collapsed')
    st.divider()
    st.markdown('**Who is it for?** Industrial and methods engineers, and plant supervisors in small and mid-size '
                'factories, who need left-hand/right-hand charts and motion-economy improvements but cannot spend '
                'an hour per video.')
    st.caption('Named after Frank and Lillian Gilbreth, who filmed workers a century ago to study their motions.')

HUELLA = (EJ[nombre] / 'diagrama.json').stat().st_mtime  # la caché se renueva si el ejemplo cambia
d, ev, cal, video, verdad = cargar(str(EJ[nombre]), HUELLA)
with st.sidebar:
    st.caption('Computed with ' + d['meta'].get('motor_en', 'Gemma 4 31B on AMD GPUs (AMD Token Factory)')
               + ' and MediaPipe hand tracking.')
    if d['meta'].get('licencia_en'):
        st.caption(d['meta']['licencia_en'])
_fe = EJ[nombre] / 'estacion.json'
EST = estacion_de(str(EJ[nombre]), _fe.stat().st_mtime if _fe.exists() else None)
MODO_EST = False
EN_VIVO = st.session_state.get('vista') == 'Try your own video'
if EN_VIVO:
    with st.sidebar:
        st.divider()
        st.caption('The sidebar describes the selected example. Your own video, or the sample, is charted from scratch '
                   'in the main panel with the shipped mode.')
elif EST:
    with st.sidebar:
        st.divider()
        # este puesto ya tiene compañeros revisados: se abre en modo estación (el modo entregado queda a un clic)
        modo = st.radio('This example: chart from', ['Station mode (reviewed coworkers)', 'Shipped mode (reviewed minute)'],
                        key=f'modo_{nombre}', help='Station mode learns from workers already reviewed at the same '
                                                   'station (agent/estacion.py). The shipped mode needs no one '
                                                   'reviewed before: it is what a brand-new station gets.')
        MODO_EST = modo.startswith('Station')
        if MODO_EST:
            st.caption(EST['meta']['estacion'] + '. The new worker: first '
                       f"{EST['meta']['revisado_hasta_s']:.0f} s reviewed, the rest coded in station mode.")
        else:
            st.caption('What a station with nobody reviewed before gets: the reviewed minute of this worker only.')
filas = EST['filas'] if MODO_EST else d['filas']
B = banco()

# navegación con estado: st.tabs vuelve a la primera pestaña en cada recarga (p. ej. al subir un video)
VISTAS = ['Overview', 'Bimanual chart', 'Improvement plan', 'Method alerts', 'Accuracy & AMD', 'Try your own video']
if hasattr(st, 'segmented_control'):
    vista = st.segmented_control('View', VISTAS, default=VISTAS[0], key='vista', label_visibility='collapsed')
else:
    vista = st.radio('View', VISTAS, horizontal=True, key='vista', label_visibility='collapsed')
vista = vista or VISTAS[0]

if vista == 'Overview':
    pot = mejora.potencial(filas)
    clip = es_clip(d['meta'])
    por = f"per {pot['tiempo_s']:.0f}-s clip" if clip else 'per unit'
    c1, c2, c3, c4 = st.columns(4)
    c1.metric('Observed clip' if clip else 'Observed time per unit', f"{pot['tiempo_s']:.0f} s")
    c2.metric('Same clip after the plan (estimate)' if clip else 'Estimated after the plan', f"{pot['nuevo_s']:.0f} s",
              f"-{pot['ahorro_pct']:.0f} %", delta_color='inverse')
    c3.metric('Output per shift (estimate)', f"+{pot['capacidad_pct']:.0f} %")
    corrida = (B.get('runs') or {}).get(d['meta'].get('run', ''))
    a_mano = d['meta'].get('minutos_a_mano') or pot['tiempo_s'] / 60 * RITMO_A_MANO
    if corrida:
        c4.metric('Agent on AMD (unattended)', f"{corrida['wall_s'] / 60:.1f} min",
                  f"vs ≈ {a_mano:.0f} min by hand (estimate)", delta_color='off', **SIN_FLECHA)
    elif d['meta'].get('minutos_a_mano'):
        c4.metric('Charting by hand (our estimate)', f"≈ {d['meta']['minutos_a_mano']:.0f} min",
                  f"for this {pot['tiempo_s'] / 60:.1f}-min video", delta_color='off', **SIN_FLECHA)
    else:
        c4.metric('Charting by hand (estimate)', f"≈ {pot['tiempo_s'] / 60 * RITMO_A_MANO:.0f} min",
                  f"at ≈ {RITMO_A_MANO:.0f} min per video-minute", delta_color='off', **SIN_FLECHA)
    st.caption(f'Charting by hand: for our course project we estimate ≈ 60 min of one person for a 4.7-min video (≈ '
               f'{RITMO_A_MANO:.0f} min per minute of video; other videos are scaled from it). Published references for related manual analyses: '
               'MTM-UAS needs ≈ 40 analyst-minutes '
               'per minute of work and MTM-1 ≈ 350 (IMD-EWD); labelling hand motions frame by frame took 79.8 min per '
               'minute of video in StrokeRehab (NeurIPS 2022). Sources: docs/SOURCES.md.')
    if clip:
        st.info(f"This example is a {pot['tiempo_s']:.0f}-second excerpt of a longer take, with several units in it. "
                f"Times are for the whole clip, not per unit, and the plan estimates the same clip of work after "
                f"the changes.")
    ver_manos(filas)
    st.subheader('Second by second')
    st.altair_chart(linea_tiempo(filas), width="stretch")
    if acuerdo(cal, EST if MODO_EST else None):
        st.success(acuerdo(cal, EST if MODO_EST else None))
    st.subheader('Top improvements')
    for p in pot['palancas'][:3]:
        st.markdown(f"- **{p['title']}** — saves ≈ **{p['segundos']:.0f} s** {por} ({p['pct']:.0f} %). "
                    f"{evidencia(p, clip)}")
    st.subheader('How it works')
    st.markdown(
        '1. **Hands** — MediaPipe tracks both hands at 10 fps; handedness comes from a ±2 s majority vote.\n'
        '2. **Operation sheet** — the vision model looks at 6 frames and writes what is assembled, where the parts '
        'and tools are, and the typical cycle. Nothing product-specific is hard-coded.\n'
        '3. **Every second** — Gemma 4 31B, served on AMD GPUs, gets 4 marked frames, a crop of each hand and '
        'hand-speed data, and returns the activity of each hand (ILO symbols: ○ operation, ⇨ transport, '
        'D delay, ▽ hold) as schema-checked JSON.\n'
        '4. **Human calibration** — the engineer corrects the first seconds, ideally the first cycle (20–50 s in the '
        'KIT tests, 60 s at IMPACT). A small model learns from that '
        'correction how much to trust the vision model vs. the hand motion, and a **gate** checks on the reviewed '
        'seconds (without seeing itself) that it really beats the vision model before recoding the rest.\n'
        '5. **Outputs** — chart rows (a new row whenever either hand changes activity), method alerts, the '
        'improvement plan in seconds saved per unit, and the Excel chart in the course format.')

if vista == 'Bimanual chart':
    izq, der = st.columns([3, 2])
    with izq:
        if verdad:
            st.altair_chart(linea_comparada(filas, verdad), width="stretch")
            st.caption(acuerdo(cal, EST if MODO_EST else None) or 'Gilbreth vs. the human labels of the dataset.')
        else:
            st.altair_chart(linea_tiempo(filas, 200), width="stretch")
        df = tabla_filas(filas)
        st.caption('ILO symbols: ○ operation · ⇨ transport · D delay · ▽ hold. Course convention: ▽ only while the '
                   'other hand operates; a hand that holds while the other one fetches is waiting, so it is D.')
        sel = st.dataframe(df[['Time', 'Left hand', 'L', 'R', 'Right hand']], hide_index=True,
                           width="stretch", height=460, on_select='rerun', selection_mode='single-row')
        if d['meta'].get('nota_desc_en'):
            st.caption(d['meta']['nota_desc_en'])
    fila = sel.selection.rows[0] if sel and sel.selection.rows else 0
    f = filas[fila]
    with der:
        if video:
            st.video(str(video), start_time=int(f['t0']))
        st.markdown(f"**Row {fila + 1}** · {f['t0']:.0f}–{f['t1']:.0f} s")
        que = lambda k: f" — {f[k]}" if f.get(k) else ''
        st.markdown(f"**Left hand** {SYM[f['mi']]} {ACT[f['mi']]}{que('desc_mi')}  \n"
                    f"**Right hand** {SYM[f['md']]} {ACT[f['md']]}{que('desc_md')}")
        img = EJ[nombre] / 'frames' / f'{fila:04d}.jpg'
        if img.exists() and not MODO_EST:
            st.image(str(img), caption='Frame at the middle of the row')
        if cal and MODO_EST:
            st.info(f"The first {EST['meta']['revisado_hasta_s']:.0f} s were reviewed with human labels; the rest was "
                    f"coded in station mode, learning from {EST['meta']['estacion'].split(': ')[-1]}.")
        elif cal:
            st.info(f"The first {cal.get('revisado_hasta_s', 0)} s were reviewed with human labels; the rest was coded by "
                    f"the agent. Gate: **{'the calibrated model recoded it' if cal.get('compuerta') == 'v7' else 'the vision model was kept'}**"
                    f" (it scored higher on the reviewed seconds, tested without seeing itself).")
    a, b = st.columns(2)
    a.download_button('Download the chart (Excel, course format)',
                      excel_bytes(str(EJ[nombre]), HUELLA, _fe.stat().st_mtime if MODO_EST else None),
                      'bimanual_chart_estacion.xlsx' if MODO_EST else 'bimanual_chart.xlsx', width="stretch",
                      help='Station-mode rows; the method alerts come from the shipped chart' if MODO_EST else None)
    b.download_button('Download the raw result (JSON)',
                      json.dumps(EST if MODO_EST else d, ensure_ascii=False, indent=1),
                      'diagrama_estacion.json' if MODO_EST else 'diagrama.json', width="stretch")

if vista == 'Improvement plan':
    with st.expander('Assumptions (change them)', expanded=False):
        alfa = st.slider('Share of "both hands idle" time recovered with visible instructions and staged material',
                         0.0, 1.0, 0.5, 0.05)
        beta = st.slider('Share of transport time cut by bringing materials into the normal working area',
                         0.0, 0.6, 0.3, 0.05)
    pot = mejora.potencial(filas, alfa, beta)
    clip = es_clip(d['meta'])
    por = f"per {pot['tiempo_s']:.0f}-s clip" if clip else 'per unit'
    if clip:
        st.caption(f"This example is a {pot['tiempo_s']:.0f}-second clip with several units, so every figure below is "
                   f"for the whole clip: an estimate of how long the same clip of work would take after the changes.")
    c1, c2, c3 = st.columns(3)
    c1.metric('Now (observed clip)' if clip else 'Now', f"{pot['tiempo_s']:.0f} s {'per clip' if clip else 'per unit'}")
    c2.metric('With the plan (estimate)', f"{pot['nuevo_s']:.0f} s {'per clip' if clip else 'per unit'}",
              f"-{pot['ahorro_s']:.0f} s", delta_color='inverse')
    c3.metric('Floor: time with some hand operating', f"{pot['piso_s']:.0f} s")
    if pot['palancas']:
        eje = f'Seconds saved {por}'
        dfp = pd.DataFrame([{'Change': p['title'], eje: p['segundos']} for p in pot['palancas']])
        st.altair_chart(alt.Chart(dfp).mark_bar(color='#2e7d32').encode(
            x=f'{eje}:Q', y=alt.Y('Change:N', sort='-x', title=None, axis=alt.Axis(labelLimit=420)),
            tooltip=list(dfp.columns)).properties(height=40 + 40 * len(dfp)), width="stretch")
    for p in pot['palancas']:
        with st.container(border=True):
            st.markdown(f"**{p['title']}** — ≈ **{p['segundos']:.1f} s** {por} ({p['pct']:.1f} %)")
            st.caption(f"Evidence: {evidencia(p, clip)}  \nAssumption: {p['assumption']}"
                       + (f"  \nSupport: {p['source']}" if p.get('source') else ''))
    st.subheader('What it is worth')
    pais = st.selectbox('Labour cost', list(COSTOS), help='Employer cost per hour; sources in docs/SOURCES.md')
    moneda, costo0, nota = COSTOS[pais]
    e1, e2, e3, e4 = st.columns(4)
    cap0 = 8 * 3600 / pot['tiempo_s'] if pot['tiempo_s'] else 0
    if clip:
        u = e1.number_input(f"{pot['tiempo_s']:.0f}-s clips of work per shift (today)", 1.0, 100000.0,
                            float(round(cap0, 1)), help='Each clip holds several units, so the shift is counted in '
                                                        'clip-lengths of the same work.')
    else:
        u = e1.number_input('Units per shift (today)', 1.0, 100000.0, float(round(cap0, 1)))
    h = e2.number_input('Shift length (h)', 1.0, 24.0, 8.0)
    n = e3.number_input('Shifts per year', 1, 1000, 250)
    c = e4.number_input(f'Labour cost per hour ({moneda})', 0.0, 1e6, float(costo0), key=f'costo_{pais}')
    st.caption(nota)
    eco = mejora.economia(pot, u, h, n, c)
    if eco and clip:
        st.markdown(f"If the estimate holds: the same work with **{eco['horas_ahorradas_anio']:,.0f} fewer labour hours "
                    f"a year** (≈ **{moneda} {eco['valor_anio']:,.0f}**), or the same shift doing "
                    f"**{eco['unidades_turno_despues']:,.0f}** clips’ worth of work instead of "
                    f"**{eco['unidades_turno_antes']:,.0f}** (+{pot['capacidad_pct']:.0f} % output).")
    elif eco:
        st.markdown(f"If the estimate holds: same units with **{eco['horas_ahorradas_anio']:,.0f} fewer labour hours a year** "
                    f"(≈ **{moneda} {eco['valor_anio']:,.0f}**), or the same shift producing "
                    f"**{eco['unidades_turno_despues']:,.0f}** instead of **{eco['unidades_turno_antes']:,.0f}** units.")
    st.caption('An estimate to prioritise changes, not a measurement: film several cycles after the change and run '
               'Gilbreth on them to compare the observed cycle times.')

if vista == 'Method alerts':
    st.markdown('Signals for the engineer to look at, from hand tracking plus the chart codes. They are prompts to '
                'check, not verdicts.' + (' Computed on the shipped chart.' if MODO_EST else ''))
    if ev:
        st.dataframe(alertas_agrupadas(ev), hide_index=True, width="stretch")
    else:
        st.info('No method alerts for this operation.')

if vista == 'Accuracy & AMD':
    st.markdown('Accuracy = share of (hand, second) pairs with the right activity code. Four tests, each '
                'pre-registered and scored **once** with the system frozen, on recordings it had never seen: three new '
                'people in the KIT Bimanual dataset (the labels of the first two takes of each task, ≈ 20–50 s, stand in for the '
                'engineer’s review; takes 2–9 are measured) and one on a second dataset, IMPACT (8 runs never coded before, by '
                'operators not in the motion prior; the first 60 s of each reviewed, measured from second 60).')
    st.dataframe(pd.DataFrame([
        ['Subject 4 on AMD Token Factory (shipped system), 1,888 hand-seconds', '41.6 %', '51.5 %', '57.4 % (±1 s: 71.2 %)'],
        ['   workshop 756 · kitchen 1,132', '37.0 · 44.7 %', '56.1 · 48.5 %', '69.8 · 49.0 %'],
        ['Subject 3 on AMD Token Factory (shipped system), 2,258 hand-seconds', '41.7–41.8 %', '55.4 %', '65.1 % (±1 s: 80.1 %)'],
        ['   workshop 1,086 · kitchen 1,172', '41.8 · 41.7 %', '59.3 · 51.9 %', '66.5 · 63.9 %'],
        ['Subject 1 on a lab GPU (Gemma 4-bit), 3,305 hand-seconds', '—', '67.5 %', '77.1 % (±1 s: 87.2 %)'],
        ['   workshop 1,347 · kitchen 1,958', '48.4 · 55.0 %', '69.6 · 66.0 %', '80.3 · 74.9 %'],
        ['IMPACT, 8 runs never coded before, 4 operators not in the prior, on AMD Token Factory, 3,142 hand-seconds', '46.5 %',
         '66.5 %', '71.1 % (±1 s: 82.4 %)'],
        ['   the hand to free and the top lever match the ones from the human labels, 8 runs', '—', '8 of 8', '8 of 8'],
    ], columns=['New person', 'Constant baseline', 'Vision model alone', 'Gilbreth']),
        hide_index=True, width="stretch")
    st.caption('On development data, 63–80 % of the remaining errors sit in the second next to a change of activity. '
               'Times are observed times, not standard times (no rating or allowances). Earlier lab runs and '
               'everything we tried and dropped: docs/RESULTS.md.')
    st.markdown('**The examples in this app, run on AMD** (the shipped pipeline, gate on; second looks at data used '
                'during development)')
    st.dataframe(pd.DataFrame([
        ['Gearbox, IMPACT operator not in the training data, first 60 s reviewed (307 hand-seconds)', '70.0 %', '73.9 %'],
        ['LEGO, two batches of blind human labels (92 hand-seconds)', '58.7 %', '62.0 %'],
    ], columns=['Example', 'Vision model alone', 'Gilbreth']), hide_index=True, width="stretch")
    st.subheader('Station mode: when coworkers at the same station are already reviewed')
    st.markdown('Gilbreth learns from all the reviewed seconds of other workers doing the same task (hand motion, '
                'Gemma\'s codes and each worker\'s dominant hand), not only from the new worker\'s first minute. '
                'Run it with `python agent/estacion.py --station runs/w1 runs/w2 --new runs/w3 --reviewed-until 60`; '
                'on the gearbox example, pick **Station mode** in the sidebar.')
    st.dataframe(pd.DataFrame([
        ['KIT subject 4, clean test (5 labelled coworkers), per hand and second', '51.5 %', '57.4 %',
         '83.4 % (82.5 % with per-second labels)'],
        ['   on the chart: share of time per hand, points from the human labels', '12.5', '12.8', '6.3'],
        ['   on the chart: takes where it finds the hand that holds or waits the most', '79 %', '71 %', '92 %'],
        ['Gearbox example, IMPACT (9 reviewed coworkers), from second 60, 307 hand-seconds', '70.0 %', '73.9 %',
         '77.9 %'],
        ['IMPACT clean test, 8 new runs (same 9 coworkers), 3,142 hand-seconds', '66.5 %', '71.1 %',
         '71.3 % (per-second version, as in the app: 72.2 %)'],
    ], columns=['', 'Vision model alone', 'Shipped mode', 'Station mode']), hide_index=True, width="stretch")
    st.caption('KIT subject 4 and the IMPACT test: pre-registered, looked at once. The chart rows and the gearbox are '
               'second looks at data already used, declared as such. Outside KIT station mode tied the shipped mode: '
               'there the shipped motion prior already comes from the same 9 operators. The coworkers\' Gemma codes '
               'come partly from the lab GPU run (KIT subject 1, the IMPACT station); the new worker\'s from AMD. The gearbox figure is agent/estacion.py as '
               'shipped (per-second labels). Where nobody at the station has been reviewed yet, the shipped mode is the '
               'one to use. Details: docs/RESULTS.md.')
    st.subheader('Running on AMD')
    if B.get('runs'):
        st.markdown(f"Model **{B.get('modelo', '')}** served on **{B.get('gpu') or 'AMD GPUs'}**"
                    + (f", {B['vram_used_gb']} of {B['vram_total_gb']} GB of GPU memory in use"
                       if B.get('vram_used_gb') else '') + '.')
        st.dataframe(pd.DataFrame([{'Video': k, 'Video length (s)': v['video_s'], 'Agent wall time (s)': v['wall_s'],
                                    'Seconds of video per minute': v['video_s_per_min']}
                                   for k, v in B['runs'].items()]), hide_index=True, width="stretch")
        st.dataframe(pd.DataFrame([{'Step': k, 'Requests': v['requests'], 'Latency p50 (s)': v['p50_s'],
                                    'Latency p95 (s)': v['p95_s'], 'Prompt tokens (mean)': v['prompt_tokens_mean'],
                                    'Output tokens (mean)': v['completion_tokens_mean']}
                                   for k, v in B.get('pasos', {}).items()]), hide_index=True, width="stretch")
        st.caption('Steps: operation sheet (1 request per video), per-second coding (1 per second of video), '
                   'row descriptions (1 per chart row). Wall time covers the GPU part; hand tracking ran on CPU.'
                   + (f" Endpoint: {B['endpoint']}; wall time includes pacing to its limits, request latency and "
                      f"retries." if B.get('endpoint') else ''))
    else:
        st.markdown('Gemma 4 31B (Google DeepMind) served on **AMD GPUs** through AMD Token Factory, or self-hosted '
                    'with vLLM on ROCm. Speed figures from the AMD run will be shown here.')

def config(clave, defecto=''):
    """Variable de entorno o secreto de Streamlit (en Community Cloud la clave va en Settings → Secrets)."""
    if os.environ.get(clave):
        return os.environ[clave]
    try:
        return str(st.secrets.get(clave, defecto))
    except Exception:                      # sin secrets.toml
        return defecto


def env_agente():
    """Entorno del subproceso del agente: en Community Cloud los secretos no son variables de entorno, así que se copian
    las claves que el agente lee (clave y modo JSON del endpoint, ritmo, y de dónde bajar el previo de movimiento)."""
    env = {**os.environ, 'PYTHONIOENCODING': 'utf-8'}
    for clave in ('GILBRETH_API_KEY', 'GILBRETH_RPM', 'GILBRETH_JSON_MODE', 'GILBRETH_PRIOR_URL'):
        if config(clave):
            env[clave] = config(clave)
    return env


PASOS_EN = {'1/5': 'Tracking both hands (MediaPipe, CPU)', '2/5': 'Frames, hand crops and hand speed for every second',
            '3/5': 'Operation sheet: the vision model looks at 6 frames of the video',
            '4/5': 'Coding every second, hand by hand', '5/5': 'Chart rows, row descriptions and method alerts'}


def endpoint_vivo(base, modelo, espera=45):
    """Una petición mínima antes de lanzar el agente: el endpoint compartido puede estar caído (modelo experimental)."""
    import urllib.error, urllib.request
    url = base.rstrip('/') + ('/chat/completions' if base.rstrip('/').endswith('/v1') else '/v1/chat/completions')
    cab = {'Content-Type': 'application/json'}
    if config('GILBRETH_API_KEY'):
        cab['Authorization'] = 'Bearer ' + config('GILBRETH_API_KEY')
    import base64, io
    from PIL import Image
    buf = io.BytesIO()
    Image.new('RGB', (64, 64), (120, 120, 120)).save(buf, 'JPEG')      # con imagen: el texto puede pasar y la visión no
    img = 'data:image/jpeg;base64,' + base64.b64encode(buf.getvalue()).decode()
    cuerpo = json.dumps({'model': modelo, 'max_tokens': 2, 'messages': [{'role': 'user', 'content': [
        {'type': 'text', 'text': 'ok'}, {'type': 'image_url', 'image_url': {'url': img}}]}]}).encode()
    try:
        urllib.request.urlopen(urllib.request.Request(url, data=cuerpo, headers=cab), timeout=espera).read()
        return True
    except urllib.error.HTTPError as e:
        return e.code == 429                       # ocupado pero vivo: el agente sabe esperar
    except Exception:
        return False


@st.cache_data(ttl=300, show_spinner='Checking which vision model is answering on AMD…')
def elegir_motor(base, modelo, motor, respaldo, motor_respaldo):
    """Qué modelo corre la demo en vivo: Gemma si responde con imagen; si no, el respaldo configurado en el mismo
    servicio de AMD (GILBRETH_FALLBACK_MODEL). Se vuelve a mirar cada 5 min. Devuelve (modelo, motor, estado) con
    estado 'principal', 'respaldo' o 'ninguno'."""
    if endpoint_vivo(base, modelo, 20):
        return modelo, motor, 'principal'
    if respaldo and endpoint_vivo(base, respaldo, 20):
        return respaldo, motor_respaldo, 'respaldo'
    return modelo, motor, 'ninguno'


def correr_agente(vid, npz, run, base, modelo, motor, respaldo=False):
    """Corre agent/bimanual.py contra el endpoint configurado y muestra el avance; devuelve True si terminó bien."""
    import subprocess, time
    with st.spinner('Checking that the AMD endpoint is answering…'):
        vivo = endpoint_vivo(base, modelo)
    # el respaldo (Qwen) razona: se le apaga el razonamiento, como en el cribado
    extra = ['--ollama'] if respaldo and config('GILBRETH_FALLBACK_NO_REASONING', '1') == '1' else []
    if not vivo:
        st.warning('The shared AMD endpoint that serves the vision model is not answering right now (it is an '
                   'experimental service). Please try again in a while; the examples in the sidebar were computed with it.')
        return False
    env = env_agente()
    cmd = [sys.executable, str(RAIZ / 'agent' / 'bimanual.py'), str(vid), '--salida', str(run), '--base', base,
           '--modelo', modelo, '--idioma', 'en', '--hilos', config('GILBRETH_THREADS', '8'), '--puntos', str(npz)] + extra
    if config('GILBRETH_LIVE_DESC', '1') == '0':      # endpoint compartido y lento: sin la 2.ª pasada de descripciones
        cmd.append('--sin-descripciones')
    run.mkdir(parents=True, exist_ok=True)
    (run / 'motor.txt').write_text(motor, encoding='utf-8')
    (run / 'corriendo').write_text('1')
    cola, t0 = [], time.time()
    with st.status('The agent is charting your video…', expanded=True) as estado:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8',
                             errors='replace', env=env, cwd=str(RAIZ))
        for linea in p.stdout:
            cola = (cola + [linea.rstrip()])[-25:]
            if linea[:3] in PASOS_EN:
                estado.write(f'{PASOS_EN[linea[:3]]} (started at {time.time() - t0:.0f} s)'
                             + (' · one request per second of video on the shared endpoint: the long step'
                                if linea[:3] == '4/5' else ''))
                estado.update(label=f'The agent is charting your video… step {linea[:3]}: {PASOS_EN[linea[:3]]}')
        p.wait()
        (run / 'corriendo').unlink(missing_ok=True)
        ok = p.returncode == 0 and (run / 'diagrama.json').exists()
        if ok:
            (run / 'tiempo.json').write_text(json.dumps({'wall_s': round(time.time() - t0, 1)}))
            estado.update(label=f'Done in {time.time() - t0:.0f} s', state='complete', expanded=False)
        elif p.returncode == 3:
            estado.update(label='Today\'s free GPU quota for this demo is used up', state='error', expanded=False)
        else:
            estado.update(label='The agent stopped before finishing', state='error')
            st.code('\n'.join(cola))
    if p.returncode == 3:
        st.warning('The free AMD endpoint behind this demo has a daily quota, and it is used up for today. It resets at '
                   'midnight Beijing time (16:00 UTC, 11:00 in Colombia). The examples in the sidebar were computed with the full agent.')
    return ok


def previo_en(previo):
    """calibracion.json guarda el previo en español ('IMPACT' o 'ninguno (MIT puro)'); en la app va en inglés."""
    if not previo:
        return 'unknown'
    if previo.startswith('ninguno'):
        return 'none (MIT-pure mode)'
    if previo.startswith('IMPACT'):                        # 'IMPACT' o 'IMPACT (other operators)'
        return 'IMPACT motion prior' + previo[len('IMPACT'):]
    return previo


def mostrar_resultado(run, motor):
    if (run / 'motor.txt').exists():
        motor = (run / 'motor.txt').read_text(encoding='utf-8')
    d2 = json.loads((run / 'diagrama.json').read_text(encoding='utf-8'))
    ev2 = json.loads((run / 'errores.json').read_text(encoding='utf-8')) if (run / 'errores.json').exists() else []
    filas2 = d2['filas']
    pot2 = mejora.potencial(filas2)
    wall = json.loads((run / 'tiempo.json').read_text())['wall_s'] if (run / 'tiempo.json').exists() else None
    c1, c2, c3, c4 = st.columns(4)
    nd = 1 if pot2['tiempo_s'] < 60 else 0           # en un clip corto, 20 → 18 s junto a −12 % parecía un error
    c1.metric('Observed clip', f"{pot2['tiempo_s']:.{nd}f} s")
    c2.metric('Estimated after the plan', f"{pot2['nuevo_s']:.{nd}f} s", f"-{pot2['ahorro_pct']:.{nd}f} %",
              delta_color='inverse')
    c3.metric('Output per shift (estimate)', f"+{pot2['capacidad_pct']:.{nd}f} %")
    if wall:
        c4.metric('Agent wall time (unattended)', f'{wall:.0f} s')
        st.caption('The agent runs unattended on the shared AMD endpoint, paced by its request limit; the engineer\'s '
                   'part is the review below.')
    cal2 = json.loads((run / 'calibracion.json').read_text(encoding='utf-8')) if (run / 'calibracion.json').exists() else None
    if cal2:
        est = cal2.get('estimacion') or {}
        recodifico = cal2.get('compuerta') == 'v7'
        st.caption(f"Computed by {motor}; you reviewed the first {cal2.get('revisado_hasta_s', 0)} s. "
                   f"Gate: **{'the calibrated model recoded the rest' if recodifico else 'vision model kept for the rest'}** "
                   f"(on your reviewed seconds, held out: vision model {est.get('gemma', 0)}/{est.get('n', 0)}, calibrated "
                   f"{est.get('v7', 0)}/{est.get('n', 0)}; motion prior: {previo_en(cal2.get('previo'))}).")
        if not recodifico:
            st.caption('On these reviewed seconds the calibrated model did not beat the vision model, so its codes stay '
                       'for the rest; your corrections are kept. In our tests the engineer reviewed 20–60 s.')
    else:
        st.caption(f'Computed just now by {motor}. First draft from the vision model, not yet reviewed by an engineer.')
    ver_manos(filas2)
    st.subheader('Second by second')
    st.altair_chart(linea_tiempo(filas2), width="stretch")
    st.dataframe(tabla_filas(filas2)[['Time', 'Left hand', 'L', 'R', 'Right hand']], hide_index=True,
                 width="stretch", height=380)
    if pot2['palancas']:
        st.subheader('Top improvements')
        for p in pot2['palancas'][:3]:
            st.markdown(f"- **{p['title']}** — saves ≈ **{p['segundos']:.{nd}f} s** in this clip ({p['pct']:.0f} %). "
                        f"{p['evidence']}")
    if ev2:
        st.subheader('Method alerts')
        st.dataframe(alertas_agrupadas(ev2), hide_index=True, width="stretch")
    a, b = st.columns(2)
    if (run / 'diagrama_bimanual.xlsx').exists():
        a.download_button('Download the chart (Excel)', (run / 'diagrama_bimanual.xlsx').read_bytes(),
                          'bimanual_chart.xlsx', width="stretch")
    b.download_button('Download the raw result (JSON)', json.dumps(d2, ensure_ascii=False, indent=1), 'diagrama.json',
                      width="stretch")


CODIGO_DE = {v: k for k, v in ACT.items()}


def revisar(run, vid, npz, base, modelo, respaldo, dur):
    """El lazo humano + IA en la demo en vivo: el ingeniero corrige los primeros segundos del borrador y el agente recodifica
    el resto con el modelo calibrado, solo si la compuerta ve que acierta más que el modelo de visión en lo revisado.
    Reutiliza las ventanas ya codificadas: no hace ninguna petición nueva al modelo."""
    import subprocess
    vent = run / 'pred_v5_vent_agente.json'
    if not vent.exists():
        return
    borrador = {int(round(o['t0'])): (o['md'], o['mi']) for o in json.loads(vent.read_text(encoding='utf-8'))}
    st.subheader('Review the first seconds, then let the agent recode the rest')
    st.caption('Correct what each hand does in the first seconds (the first cycle, if it fits). The agent learns from your '
               'corrections how far to trust the vision model and how far the hand motion; a gate keeps the vision '
               'model unless the calibrated one scores higher on your reviewed seconds, tested without seeing itself.')
    tope = max(6, min(60, int(dur)))
    n = st.slider('Seconds to review', 5, tope, min(30, max(5, int(0.4 * dur))), key='rev_n')   # deja algo que recodificar
    df = pd.DataFrame([{'Second': f'{s}–{s + 1} s', 'Left hand': ACT.get(borrador[s][1], borrador[s][1]),
                        'Right hand': ACT.get(borrador[s][0], borrador[s][0])} for s in sorted(borrador) if s < n])
    opciones = list(ACT.values())
    izq, der = st.columns([3, 2])
    with der:                         # el video al lado del editor: se revisa mirando, también con un video propio
        st.video(str(vid))
        st.caption('Play the clip while you correct the rows on the left.')
    with izq:
        ed = st.data_editor(df, hide_index=True, width="stretch", disabled=['Second'], key=f'rev_tabla_{n}',
                            column_config={'Left hand': st.column_config.SelectboxColumn(options=opciones, required=True),
                                           'Right hand': st.column_config.SelectboxColumn(options=opciones, required=True)})
    cambios = sum((ed['Left hand'] != df['Left hand']) | (ed['Right hand'] != df['Right hand']))
    if st.button(f'Apply my review ({cambios} row{"" if cambios == 1 else "s"} changed) and let the gate decide the rest',
                 type='primary'):
        filas_rev = [{'t0': float(s), 't1': float(s + 1), 'md': CODIGO_DE[r['Right hand']], 'mi': CODIGO_DE[r['Left hand']]}
                     for s, (_, r) in zip(sorted(x for x in borrador if x < n), ed.iterrows())]
        (run / 'revisado.json').write_text(json.dumps({'filas': filas_rev}, ensure_ascii=False), encoding='utf-8')
        env = env_agente()     # como correr_agente; sin GILBRETH_PRIOR_URL, en la nube (sin models/) caería al MIT puro
        cmd = [sys.executable, str(RAIZ / 'agent' / 'bimanual.py'), str(vid), '--salida', str(run), '--base', base,
               '--modelo', modelo, '--idioma', 'en', '--puntos', str(npz), '--reusar-ventanas', '--sin-descripciones',
               '--calibrar', str(run / 'revisado.json')] + (['--ollama'] if respaldo else [])
        with st.spinner('Calibrating on your review and checking the rest (CPU, no new model requests)…'):
            p = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', env=env,
                               cwd=str(RAIZ))
        if p.returncode != 0:
            st.error('The recode stopped before finishing.')
            st.code(p.stdout[-2000:] + p.stderr[-1000:])
        else:
            st.rerun()


def nueva_subida(clave, nombre, datos, muestra=False):
    """Una subida, o el clip de muestra por EXACTAMENTE el mismo camino: su propio directorio temporal, el video
    dentro y su duración en st.session_state['subida']."""
    import cv2
    tmp = Path(tempfile.mkdtemp(prefix='gilbreth_'))
    vid = tmp / ('video' + Path(nombre).suffix.lower())
    vid.write_bytes(datos)
    cap = cv2.VideoCapture(str(vid))
    n_cuadros, fps = cap.get(cv2.CAP_PROP_FRAME_COUNT), cap.get(cv2.CAP_PROP_FPS) or 0
    cap.release()
    st.session_state['subida'] = {'clave': clave, 'dir': str(tmp), 'video': str(vid),
                                  'dur': n_cuadros / fps if fps else 0, 'muestra': muestra}
    return st.session_state['subida']


if vista == 'Try your own video':
    base, modelo = config('GILBRETH_VLLM_URL'), config('GILBRETH_MODEL', 'google/gemma-4-31B-it')
    motor = config('GILBRETH_ENGINE', 'Gemma 4 31B on AMD GPUs (AMD Token Factory)')
    estado = 'principal'
    if base:
        respaldo = config('GILBRETH_FALLBACK_MODEL')
        modelo, motor, estado = elegir_motor(base, modelo, motor, respaldo,
                                             config('GILBRETH_FALLBACK_ENGINE', f'{respaldo} on AMD GPUs (AMD Token Factory)'))
        if estado == 'respaldo':
            st.info(f'Gemma 4 is not answering on the shared AMD Token Factory right now (it was removed from the '
                    f'catalogue on 15 Oct and listed again on 16 Oct), so live runs use **{motor}**, the best of the vision '
                    f'models we screened on AMD. {config("GILBRETH_FALLBACK_NOTE", "")} Every example in this app, the KIT '
                    'tests on subjects 3 and 4 and the IMPACT test were computed with Gemma 4 31B on AMD.')
        elif estado == 'ninguno':
            st.warning('The shared AMD endpoint is not answering right now (it is an experimental service), so the full '
                       'agent cannot run at the moment. Hand tracking below still works; please try again in a while.')
    st.markdown('Upload a short top-down video of a workstation (≤ 2 min). Hand tracking runs here on CPU'
                + (f'; the full chart is computed by **{motor}**.' if base else
                   ' and gives a first look at each hand. The full chart needs the vision model on the AMD GPU server.'))
    up = st.file_uploader('Video', type=['mp4', 'mov', 'avi', 'mkv'])
    sub = st.session_state.get('subida') or {}
    if up is not None:
        if sub.get('clave') != f'{up.name}:{up.size}':
            sub = nueva_subida(f'{up.name}:{up.size}', up.name, up.getvalue())
    elif sub.get('muestra'):
        a, b = st.columns([5, 1], vertical_alignment='center')
        a.caption('Using our 20-second sample: a screw-assembly station from *Factory Manipulation Videos* by '
                  'Procedural Robotics Inc. (CC BY 4.0), the same take as the screw example. Upload your own video '
                  'above to replace it.')
        if b.button('Remove the sample', key='quitar_muestra', width='stretch'):
            st.session_state.pop('subida', None)
            st.rerun()
    elif MUESTRA.exists() and st.button('No clip at hand? Use our 20-second sample (factory screw station, CC BY 4.0)',
                                        key='usar_muestra'):
        nueva_subida('sample:' + MUESTRA.name, MUESTRA.name, MUESTRA.read_bytes(), muestra=True)
        st.rerun()                       # la siguiente corrida ya la trata como subida (con el botón para quitarla)
    if up is not None or sub.get('muestra'):      # una subida o el clip de muestra: desde aquí, el mismo camino
        import extraer_puntos
        from manos import cargar as cargar_npz, pista, sensores
        tmp, vid = Path(sub['dir']), Path(sub['video'])
        npz, run = tmp / 'puntos.npz', tmp / 'run'
        if sub.get('muestra'):
            with st.expander('Watch the sample clip'):
                st.video(str(vid))
        if sub['dur'] > 121:
            st.error(f"This video is {sub['dur']:.0f} s long. Please upload 2 minutes or less.")
            st.stop()
        if sub['dur'] < 6:
            st.error('This video is under 6 seconds, or its length could not be read. Please upload a clip of 6 s to '
                     '2 minutes.')
            st.stop()
        if not npz.exists():
            barra = st.progress(0.0, 'Tracking hands…')
            sub['manos'] = extraer_puntos.extraer(vid, npz, lambda x: barra.progress(x, 'Tracking hands…'))
            barra.empty()
        if sub.get('manos'):
            st.caption(f"Hand tracking (MediaPipe, CPU): {sub['manos'][0]} video frames, tracked at 10 fps; "
                       f"{sub['manos'][1]} hand detections.")
        pi = pista(*cargar_npz(npz))
        limite = float(config('GILBRETH_MAX_LIVE_S', '120'))
        if pi and base and not (run / 'diagrama.json').exists() and sub['dur'] > limite + 1:
            st.info(f'On this public demo the full agent charts clips of up to {limite:.0f} s (the free AMD endpoint has '
                    f'a daily quota). Trim the video to chart it; the hand tracking below works on the whole clip.')
        elif pi and base and estado != 'ninguno' and not (run / 'diagrama.json').exists():
            import time as _t
            if (run / 'corriendo').exists() and _t.time() - (run / 'corriendo').stat().st_mtime < 1200:
                st.info('The agent is still working on this video. Wait a moment and press the button below.')
                st.button('Refresh')
            else:
                if (run / 'corriendo').exists():         # una corrida de hace más de 20 min que no terminó
                    (run / 'corriendo').unlink(missing_ok=True)
                    st.warning('The last run did not finish; press the button to try again.')
                ritmo = float(config('GILBRETH_LIVE_REQ_PER_MIN', '0') or 0)
                if ritmo:
                    pide = sub['dur'] + 1 + (0 if config('GILBRETH_LIVE_DESC', '1') == '0' else sub['dur'] / 2)
                    st.caption(f'One request per second of video on a shared endpoint: about {pide / ritmo:.0f} min '
                               f'for this {sub["dur"]:.0f}-second clip.')
                if st.button(f'Chart it with the full agent · {motor}', type='primary'):
                    correr_agente(vid, npz, run, base, modelo, motor, estado == 'respaldo')
        if (run / 'diagrama.json').exists():
            mostrar_resultado(run, motor)
            if base:
                revisar(run, vid, npz, base, modelo, estado == 'respaldo', sub['dur'])
        elif not pi:
            st.warning('No hands found. Film from above, with both hands and the work area in view.')
        else:
            dur = int(max(pi)) + 1
            filas_vivo = []
            for s in range(dur):
                sen = sensores(pi, s, s + 1)
                fila = {'t0': float(s), 't1': float(s + 1)}
                for k, clave in (('md', 'mano_derecha'), ('mi', 'mano_izquierda')):
                    v = sen[clave]['velocidad_mediana']
                    fila[k] = 'NV' if v is None else ('S' if v < 0.6 else ('TR+OP' if v < 0.9 else 'TR'))
                filas_vivo.append(fila)
            nombres = {'NV': 'Not visible', 'S': 'Still / fine work', 'TR+OP': 'Moving', 'TR': 'Travelling'}
            dfv = pd.DataFrame([{'hand': m, 'start': f['t0'], 'end': f['t1'], 'motion': nombres[f[k]]}
                                for f in filas_vivo for m, k in (('Left hand', 'mi'), ('Right hand', 'md'))])
            st.altair_chart(alt.Chart(dfv).mark_bar().encode(
                x=alt.X('start:Q', title='seconds'), x2='end:Q', y=alt.Y('hand:N', title=None),
                color=alt.Color('motion:N', scale=alt.Scale(
                    domain=list(nombres.values()), range=['#9e9e9e', '#fb8c00', '#66bb6a', '#1e88e5'])),
                tooltip=['hand', 'motion', 'start']).properties(height=200), width="stretch")
            st.caption('Motion only (speed in hand-lengths per second). This is not yet the bimanual chart: telling '
                       '"hold" from "operate" needs the vision model.')
            ev_vivo = errores.detectar(pi)
            if ev_vivo:
                st.dataframe(alertas_agrupadas(ev_vivo), hide_index=True, width="stretch")
    if not base:
        st.info('The full agent needs the vision model on an AMD GPU endpoint, which is not connected to this copy of '
                'the app. The examples in the sidebar were computed with the full agent.')
