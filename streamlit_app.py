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
MUESTRA_RUN = RAIZ / 'examples' / 'factory_screw' / 'sample_run'     # lo que el agente sacó de esa muestra en AMD (en vivo, 18-oct)
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
        color=alt.Color('activity:N', scale=escala, legend=alt.Legend(orient='top', title=None, columns=3)),
        tooltip=['hand', 'activity', 'what', 'start', 'end']).properties(height=alto)


def linea_comparada(filas, verdad, alto=300, quien='Gilbreth'):
    """Agente vs. etiqueta humana, por mano (los segundos sin etiqueta humana quedan en blanco)."""
    filas_d = [{'hand': f'{mano} · {quien}', 'start': f['t0'], 'end': f['t1'], 'activity': ACT[f[k]]}
               for f in filas for mano, k in (('Left', 'mi'), ('Right', 'md'))]
    filas_d += [{'hand': f'{mano} · human', 'start': s, 'end': s + 1, 'activity': ACT[v[k]]}
                for s, v in verdad.items() for mano, k in (('Left', 'mi'), ('Right', 'md')) if not v['nulo_' + k]]
    orden = [f'Left · {quien}', 'Left · human', f'Right · {quien}', 'Right · human']
    escala = alt.Scale(domain=list(COLORES), range=list(COLORES.values()))
    return alt.Chart(pd.DataFrame(filas_d)).mark_bar().encode(
        x=alt.X('start:Q', title='seconds', scale=alt.Scale(domain=[0, max(f['t1'] for f in filas)], nice=False)),
        x2='end:Q', y=alt.Y('hand:N', title=None, sort=orden),
        color=alt.Color('activity:N', scale=escala, legend=alt.Legend(orient='top', title=None, columns=3)),
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


def glosario():
    """Los términos del README (sección «Glossary»): una sola fuente para el repo y la app."""
    try:
        t = (RAIZ / 'README.md').read_text(encoding='utf-8')
        return t.split('## Glossary\n', 1)[1].split('\n## ', 1)[0].strip()
    except Exception:
        return ''


def tabla(df):
    """Tabla estática que parte el texto en líneas (st.dataframe cortaba las columnas largas en pantallas de portátil)."""
    st.table(df.astype(str).set_index(df.columns[0]))


def mostrar_alertas(ev):
    tabla(alertas_agrupadas(ev))
    st.caption("Hand(s) 'both' = it happens with the left hand and with the right hand, not necessarily at the same time. "
               "Alerts come from the hand tracking and the codes: they point to what to check on the video.")


def alertas_agrupadas(ev):
    por = defaultdict(list)
    for e in ev:
        por[e['tipo']].append(e)
    filas = []
    for tipo, lista in sorted(por.items(), key=lambda x: -sum(e['t1'] - e['t0'] for e in x[1])):
        manos = ''.join(sorted({c for e in lista for c in e['mano']}))
        filas.append({'Alert': errores.TITLE_EN.get(tipo, tipo), 'Hand(s)': MANO_EN.get(manos, manos),
                      'How many times': len(lista), 'Total time (s)': round(sum(e['t1'] - e['t0'] for e in lista), 1),
                      'Starts at (first 4)': ', '.join(f"{e['t0']:.0f} s" for e in lista[:4]) + (' …' if len(lista) > 4 else ''),
                      'What to change': errores.FIX_EN.get(tipo, '')})
    return pd.DataFrame(filas)


# ---------------------------------------------------------------------------------------------------------------- UI
st.title('⏱️ Gilbreth')
st.markdown("**Film a worker's hands at a workstation. Gilbreth shows what each hand does every second, where the "
            "time goes, and how many seconds per unit a better method would save.** Built for methods engineers and "
            "plant supervisors in small and mid-size factories: Gemma 4 31B labels the video on AMD GPUs, and the "
            "engineer reviews the start and approves the result.")

CORTO = {'impact_gearbox': 'Gearbox · vs human labels', 'factory_screw': 'Screw station · factory video',
         'factory_cardboard': 'Cardboard · factory video', 'factory_plastic': 'Plastic parts · factory video',
         'lego': 'LEGO digger · one full unit'}
EJ = ejemplos(('orden: lego al final',) + tuple(sorted((p.parent.name, p.stat().st_mtime)    # la etiqueta renueva la caché
                                                       for p in (RAIZ / 'examples').glob('*/diagrama.json'))))
with st.sidebar:
    st.header('Pick an example video')
    nombre = st.selectbox('Operation', list(EJ), label_visibility='collapsed',
                          format_func=lambda k: CORTO.get(EJ[k].name, k))
    st.caption(nombre)

HUELLA = (EJ[nombre] / 'diagrama.json').stat().st_mtime  # la caché se renueva si el ejemplo cambia
d, ev, cal, video, verdad = cargar(str(EJ[nombre]), HUELLA)
_fe = EJ[nombre] / 'estacion.json'
EST = estacion_de(str(EJ[nombre]), _fe.stat().st_mtime if _fe.exists() else None)
MODO_EST = False
EN_VIVO = st.session_state.get('vista') == 'Try your own video'
if EN_VIVO:
    for _k in [k for k in st.session_state if str(k).startswith('modo_')]:
        st.session_state[_k] = st.session_state[_k]       # un widget no dibujado perdería su estado
    with st.sidebar:
        st.divider()
        st.caption('The sidebar describes the selected example. Your own video, or the sample, is charted in the main '
                   'panel by the full agent in the default mode: the vision model, then your review of the first seconds '
                   'and the gate (for the sample, a stored run shows at once).')
elif EST:
    with st.sidebar:
        st.divider()
        # este puesto ya tiene compañeros revisados: se abre en el modo entregado y el modo estación queda a un clic
        # (así lo cuentan el video, el README y Accuracy & AMD; careo de cierre del 18-oct)
        modo = st.radio('Which human review does Gilbreth learn from?',
                        ['Station mode: also coworkers already reviewed at this station',
                         "This worker's first 60 s only (shipped mode: what any new station gets)"],
                        index=1,
                        key=f'modo_{nombre}', help='Station mode learns from workers already reviewed at the same '
                                                   'station (agent/estacion.py). The default needs no one reviewed '
                                                   'before: it is what a brand-new station gets. Every number on the '
                                                   'page follows this choice.')
        MODO_EST = modo.startswith('Station')
        if MODO_EST:
            st.caption(EST['meta']['estacion'] + '. The new worker: first '
                       f"{EST['meta']['revisado_hasta_s']:.0f} s reviewed, the rest labelled in station mode.")
filas = EST['filas'] if MODO_EST else d['filas']
with st.sidebar.expander('About, data and licence'):
    st.caption('Named after Frank and Lillian Gilbreth, who filmed workers a century ago to study their motions.')
    if not EN_VIVO:                                   # en vivo, la licencia del ejemplo no aplica al clip
        st.caption('Computed with ' + d['meta'].get('motor_en', 'Gemma 4 31B on AMD GPUs (AMD Token Factory)')
                   + ' and MediaPipe hand tracking.')
        if d['meta'].get('licencia_en'):
            st.caption(d['meta']['licencia_en'])
B = banco()

# navegación con estado: st.tabs vuelve a la primera pestaña en cada recarga (p. ej. al subir un video)
VISTAS = ['Overview', 'Bimanual chart', 'Improvement plan', 'Method alerts', 'Accuracy & AMD', 'Try your own video']
def _vista_fija():
    """Volver a pulsar la vista activa la desmarcaba (y la app saltaba a Overview): se restaura la anterior."""
    if st.session_state.get('vista') is None:
        st.session_state['vista'] = st.session_state.get('_vista_ant', VISTAS[0])
    st.session_state['_vista_ant'] = st.session_state['vista']


if hasattr(st, 'segmented_control'):
    vista = st.segmented_control('View', VISTAS, default=VISTAS[0], key='vista', label_visibility='collapsed',
                                 on_change=_vista_fija)
else:
    vista = st.radio('View', VISTAS, horizontal=True, key='vista', label_visibility='collapsed')
vista = vista or VISTAS[0]

# lo que se ve en cada ejemplo, en una frase: la portada lo dice junto al video
EJEMPLO_EN = {
    'impact_gearbox': 'A person reassembles a gearbox with tools. From IMPACT, a research dataset whose hand motions '
                      'were labelled by people; Gilbreth was never trained on this operator. The dataset\'s labels for '
                      'the first {r:.0f} s stand in for the engineer\'s review; Gilbreth learned from them and coded '
                      'the rest.',
    'factory_screw': 'A factory worker assembles small parts with a suspended power screwdriver: a {t:.0f}-second '
                     'excerpt with several units. Nobody reviewed it, so this is the first draft of the vision model.',
    'factory_cardboard': 'A worker folds cardboard boxes at a packing station: a {t:.0f}-second excerpt with several '
                         'units. Nobody reviewed it, so this is the first draft of the vision model.',
    'factory_plastic': 'A worker arranges small plastic parts in rows: a {t:.0f}-second excerpt with several units. '
                       'Nobody reviewed it, so this is the first draft of the vision model.',
    'lego': 'One full assembly of a 56-piece LEGO model (Creator 5761 Mini Digger, model 1; {t:.0f} s, one unit), '
            'filmed for our methods course. A person reviewed the first {r:.0f} s; Gilbreth coded the rest.',
}
FUENTES = 'https://github.com/jAa708/gilbreth/blob/main/docs/SOURCES.md'


def ir_a(v, muestra=False):
    """Botones de la portada: cambian de vista (y, si se pide, cargan el clip de muestra al llegar)."""
    st.session_state['vista'] = v
    st.session_state['_vista_ant'] = v
    if muestra:
        st.session_state['_auto_muestra'] = True


if vista == 'Overview':
    pot = mejora.potencial(filas)
    clip = es_clip(d['meta'])
    por = f"per {pot['tiempo_s']:.0f}-s clip" if clip else 'per unit'
    rev = (EST['meta']['revisado_hasta_s'] if MODO_EST else (cal or {}).get('revisado_hasta_s', 0)) or 0
    corrida = (B.get('runs') or {}).get(d['meta'].get('run', ''))
    a_mano = float(d['meta'].get('minutos_a_mano') or pot['tiempo_s'] / 60 * RITMO_A_MANO)
    descripcion = EJEMPLO_EN.get(EJ[nombre].name, '').format(t=pot['tiempo_s'], r=rev)
    if MODO_EST:
        descripcion += ' Shown in station mode: it also learned from coworkers already reviewed at this station.'

    # 1) lo que entra (el video) y lo que sale (cada mano, el plan), en la primera pantalla
    izq, der = st.columns([2, 3], gap='large')
    with izq:
        if video:
            st.video(str(video), muted=True)
        st.button('▶ Try it on a 20-second clip', type='primary', width='stretch', on_click=ir_a,
                  args=('Try your own video', True))
        st.caption('Tracks the hands for a few seconds, then shows the run saved from AMD; a button there runs it '
                   'again live on AMD (about 4 min).')
        st.button('Play the video with the chart beside it', width='stretch', on_click=ir_a, args=('Bimanual chart',))
        st.caption(f'**{nombre}.** {descripcion}')
    with der:
        st.markdown('##### What Gilbreth found in this video')
        quieta = {m: sum(v.get(c, 0.0) for c in ('S', 'D')) for m, v in reparto_manos(filas).items()}
        st.markdown(f"**Holding or waiting: left hand {quieta['Left hand']:.0f} %, right hand "
                    f"{quieta['Right hand']:.0f} % of the time.** "
                    f"The plan would take {'this clip' if clip else 'this unit'} from {pot['tiempo_s']:.0f} s to "
                    f"{pot['nuevo_s']:.0f} s (a projection).")
        st.altair_chart(barra_manos(filas), width="stretch")
        c1, c2 = st.columns(2)
        c1.metric(('Clip time' if clip else 'Time per unit') + ': now → with the plan',
                  f"{pot['tiempo_s']:.0f} → {pot['nuevo_s']:.0f} s",
                  f"-{pot['ahorro_pct']:.0f} % = +{pot['capacidad_pct']:.0f} % units per shift", delta_color='inverse',
                  help='Observed time, then the projection with the changes of the plan added together (never below '
                       'the time in which some hand is operating). Less time per unit and more units per shift are the '
                       'same gain. A projection until the station is filmed again.')
        c2.metric('Human review needed', f"{rev:.0f} s of {pot['tiempo_s']:.0f} s" if rev else 'none yet',
                  f"Gilbreth coded the other {pot['tiempo_s'] - rev:.0f} s" if rev else 'a first draft',
                  delta_color='off', **SIN_FLECHA,
                  help=f"Charting all {pot['tiempo_s']:.0f} s by hand: ≈ {a_mano:.0f} min (our estimate). We did not "
                       'time the review itself.')
        if pot['palancas']:
            top = pot['palancas'][0]
            nd_t = 1 if top['segundos'] < 20 else 0
            titulo = top['title'].replace(' (fixture or jig)', ' with a fixture or jig (a holder that keeps the part '
                                          'in place)')
            if 'libre_s' in top:
                porque = (f" For {top['libre_s']:.0f} s that hand only holds or waits while the other works alone "
                          f"({top['tr_s']:.0f} s fetching or carrying, {top['op_s']:.0f} s operating); with the part "
                          f"held, the fetching can overlap the operating.")
                otra = next((x for x in pot['palancas'] if 'libre_s' in x and x is not top), None)
                if otra and otra['libre_s'] > top['libre_s']:
                    porque += (f" The other hand waits longer ({otra['libre_s']:.0f} s), but meanwhile this one is mostly "
                               f"operating ({otra['op_s']:.0f} s), so less of it can overlap.")
            else:
                porque = ' ' + evidencia(top, clip)
            st.markdown(f"**Biggest saving:** {titulo} — about **{top['segundos']:.{nd_t}f} s** {por}.{porque}")
        if verdad:
            st.markdown('**How accurate:** on 8 gearbox videos it had never seen, 71.1 % of hand-seconds match the human '
                        'labels (Gemma 4 alone: 66.5 %; always guessing the most common label: 46.5 %).')
        else:
            st.markdown('**How accurate:** in four tests on recordings it had never seen, Gilbreth beat Gemma 4 alone '
                        'every time, e.g. 55.4 → 65.1 % of hand-seconds labelled like a person (table below).')
        if corrida:
            st.markdown(f"**On AMD:** Gemma 4 31B on AMD GPUs (AMD Token Factory) coded this {pot['tiempo_s']:.0f}-s video in "
                        f"{corrida['wall_s'] / 60:.1f} min with nobody watching; across the five examples the model cost "
                        f"about US$0.008 per minute of video. "
                        f"The shared endpoint's request quota sets that pace, not the method.")

    # 2) la idea, cómo funciona y si funciona
    st.divider()
    st.subheader('The idea in one minute')
    c_a, c_b = st.columns(2)
    with c_a.container(border=True):
        st.markdown('**The problem**')
        st.markdown('To improve manual work, industrial engineers draw a **bimanual chart**: step by step, what the left '
                    'and the right hand do (operate, transport, hold or wait). A hand that only holds while the other '
                    'one works is time that a fixture can give back. Charting a 4.7-minute video by hand takes about an '
                    'hour (our estimate); labelling hand motions frame by frame took about 80 min per minute of video '
                    f'in a NeurIPS 2022 dataset ([sources]({FUENTES})).')
        st.markdown('**Who it is for:** methods engineers and plant supervisors in small and mid-size factories, who '
                    'need these charts but cannot spend an hour per video.')
    with c_b.container(border=True):
        st.markdown('**How Gilbreth works**')
        st.markdown(
            '1. **Film** the station with a phone.\n'
            '2. **Track the hands**: MediaPipe, on CPU.\n'
            '3. **Code every second**: Gemma 4 31B on AMD GPUs looks at marked frames and a crop of each hand and '
            'gives each hand an activity code (operation, transport, hold or delay).\n'
            '4. **Review the start**: the engineer corrects the first cycle or minute. A small model, fitted in '
            'seconds on CPU, learns from those corrections how far to trust Gemma\'s codes against the hand '
            'motion. Gemma itself is not retrained.\n'
            '5. **Gate**: on reviewed seconds the small model did not learn from, it is compared with Gemma alone; the '
            'better of the two codes the rest of the video.\n'
            '6. **Out**: the bimanual chart (Excel), method alerts and an improvement plan in seconds per unit.')
    st.markdown('**Does it work?** Four tests on recordings the system had never seen (rows 1–4; row 4 ran on a lab '
                'GPU before the event, the others on AMD), plus station mode on the same person as row 2 (last row). '
                'Each was run once, with its pass criterion written down beforehand. Score = share of hand-seconds '
                '(one hand during one second) labelled like the human labels, counted only after the reviewed part; '
                'higher is better. Gilbreth beat Gemma 4 alone in all four tests, by 4.6 to 9.7 points.')
    tabla(pd.DataFrame([
        ['1 · KIT subject 3 (new person, workshop and kitchen tasks), on AMD', '≈ 42 %', '55.4 %', '65.1 %'],
        ['2 · KIT subject 4 (new person), on AMD', '41.6 %', '51.5 %', '57.4 %'],
        ['3 · IMPACT: 8 gearbox videos the system had never seen, on AMD', '46.5 %', '66.5 %', '71.1 %'],
        ['4 · KIT subject 1 (new person), lab GPU before the event', '48 / 55 % (workshop / kitchen)', '67.5 %', '77.1 %'],
        ['Extra · KIT subject 4 in station mode (5 coworkers at the same tasks already reviewed)', '41.6 %', '51.5 %',
         '83.4 %'],
    ], columns=['Test', 'Always guessing the most common label', 'Gemma 4 alone (no review)',
                'Gilbreth (Gemma 4 + the review)']))
    st.caption('KIT Bimanual and IMPACT are research datasets of people filmed doing hand tasks, labelled by people. '
               'On the 8 gearbox videos, station mode only tied (71.3 % against 71.1 %; the per-second version this app '
               'runs: 72.2 %). Model cost on AMD: about US$0.008 per minute of video, across the five examples. Every figure and how it was measured: the Accuracy & AMD view.')

    # 3) el detalle del ejemplo
    st.divider()
    if verdad:
        st.subheader('Second by second, against the human labels')
        st.altair_chart(linea_comparada(filas, verdad, quien='station mode' if MODO_EST else 'Gilbreth'),
                        width="stretch")
        st.caption(f"Top row of each pair: {'station mode' if MODO_EST else 'Gilbreth'}; bottom row: the dataset's own "
                   f"human labels (blank = no label for that hand). The first {rev:.0f} s are the reviewed part.")
        if acuerdo(cal, EST if MODO_EST else None):
            st.success(acuerdo(cal, EST if MODO_EST else None) + ' This is one video; the 8-video test above gives '
                       '71.1 %.')
    else:
        st.subheader('Second by second')
        st.altair_chart(linea_tiempo(filas), width="stretch")
        st.caption('Each thin stripe is one second of one hand; long orange or red stretches are holding or waiting.')
    st.subheader('Top improvements')
    for p in pot['palancas'][:3]:
        nd_p = 1 if p['segundos'] < 20 else 0          # 15.5 s y no «16 s»: como en las tarjetas del plan
        st.markdown(f"- **{p['title']}** — saves ≈ **{p['segundos']:.{nd_p}f} s** {por} ({p['pct']:.{nd_p}f} %). "
                    f"{evidencia(p, clip)} {p['assumption']}")
    st.caption('The savings add up, but the plan never goes below the time in which some hand is operating. Each change, its evidence and '
               'the assumptions you can change: the Improvement plan view.'
               + (' Times of a factory excerpt are for the whole clip, not per unit.' if clip else ''))
    with st.expander('How it works, in more detail'):
        st.markdown(
            '1. **Hands** — MediaPipe tracks both hands at 10 fps; left and right are decided by a vote over ±2 s, so '
            'the labels do not swap.\n'
            '2. **Operation sheet** — the vision model looks at 6 frames and writes what is assembled, where the parts '
            'and tools are, and the typical cycle. Nothing product-specific is hard-coded.\n'
            '3. **Every second** — Gemma 4 31B, served on AMD GPUs, gets 4 marked frames, a crop of each hand and '
            'hand-speed data, and returns the activity of each hand (ILO symbols: ○ operation, ⇨ transport, '
            'D delay, ▽ hold) as schema-checked JSON.\n'
            '4. **Human calibration** — the engineer corrects the first seconds, ideally the first cycle (20–50 s in the '
            'KIT Bimanual tests, 60 s in IMPACT). A small model learns from that correction how much to trust the '
            'vision model vs. the hand motion; it also starts from hand-motion examples of other IMPACT operators. A '
            '**gate** lets it relabel the rest only if it beats the vision model on reviewed seconds it was not trained '
            'on; otherwise the vision model\'s labels stay.\n'
            '5. **Outputs** — chart rows (a new row whenever either hand changes activity), method alerts, the '
            'improvement plan in seconds saved per unit, and the Excel chart in the course format.')

if vista == 'Bimanual chart':
    izq, der = st.columns([3, 2])
    with izq:
        if verdad:
            st.altair_chart(linea_comparada(filas, verdad, quien='station mode' if MODO_EST else 'Gilbreth'),
                            width="stretch")
            n_rev = (EST['meta']['revisado_hasta_s'] if MODO_EST else (cal or {}).get('revisado_hasta_s', 0)) or 0
            st.caption(f"In each pair of rows, the top one is {'station mode' if MODO_EST else 'Gilbreth'} and the bottom "
                       f"one the dataset's own human labels (blank = no label for that hand in that second). The first "
                       f"{n_rev:.0f} s are the reviewed part, so the agreement below is counted from there. A hand-second "
                       f"is one hand during one second.")
            st.caption(acuerdo(cal, EST if MODO_EST else None) or 'Gilbreth vs. the human labels of the dataset.')
        else:
            st.altair_chart(linea_tiempo(filas, 240), width="stretch")
        df = tabla_filas(filas)
        st.caption('ILO symbols: ○ operation · ⇨ transport · D delay · ▽ hold. Course convention: ▽ only while the '
                   'other hand operates; a hand that holds while the other one fetches is waiting, so it is D. In the '
                   'colours, light green "Transport + operation" = the hand moves while it works (counted as ○), and grey '
                   '"Not visible" = the hand is out of view or not tracked.')
        st.caption('Station mode gives codes only, without the notes in words.' if MODO_EST else
                   d['meta'].get('nota_desc_en') or 'Each hand has a code (the symbol the chart counts) and a short note in '
                   'words from a second pass of the vision model; when they disagree, the code is what counts. "Holds" '
                   'with D is not an error: holding while the other hand only fetches counts as waiting.')
        st.caption('Tick a row to play the video from that row; its frame and both hands\' codes show on the right. '
                   'L and R = the ILO symbol of each hand.')
        sel = st.dataframe(df[['Time', 'Left hand', 'L', 'R', 'Right hand']], hide_index=True,
                           width="stretch", height=460, on_select='rerun', selection_mode='single-row',
                           column_config={'Time': st.column_config.TextColumn(width='small'),
                                          'L': st.column_config.TextColumn(width='small', help='ILO symbol of the left hand'),
                                          'R': st.column_config.TextColumn(width='small', help='ILO symbol of the right hand'),
                                          'Left hand': st.column_config.TextColumn(width='medium'),
                                          'Right hand': st.column_config.TextColumn(width='medium')})
    fila = sel.selection.rows[0] if sel and sel.selection.rows else 0
    f = filas[fila]
    with der:
        if video:
            st.video(str(video), start_time=int(f['t0']))
        st.markdown(f"**Row {fila + 1}** · {f['t0']:.0f}–{f['t1']:.0f} s")
        que = lambda k: f" · *vision model's note:* {f[k]}" if f.get(k) else ''
        st.markdown(f"**Left hand** {SYM[f['mi']]} {ACT[f['mi']]}{que('desc_mi')}  \n"
                    f"**Right hand** {SYM[f['md']]} {ACT[f['md']]}{que('desc_md')}")
        img = EJ[nombre] / 'frames' / f'{fila:04d}.jpg'
        if img.exists() and not MODO_EST:
            st.image(str(img), caption='Frame at the middle of the row')
        quien_rev = ("a person: the author checked every row of that part" if 'lego' in str(EJ[nombre])
                     else "the IMPACT dataset's own human labels, standing in for the engineer")
        if cal and MODO_EST:
            st.info(f"The first {EST['meta']['revisado_hasta_s']:.0f} s were reviewed ({quien_rev}); the rest was "
                    f"coded in station mode, learning from {EST['meta']['estacion'].split(': ')[-1]}.")
        elif cal:
            est = cal.get('estimacion') or {}
            st.info(f"The first {cal.get('revisado_hasta_s', 0)} s were reviewed ({quien_rev}); Gilbreth coded the rest. "
                    f"Gate (the check that decides who codes the rest): "
                    + (f"**the model calibrated on the review recoded it**. " if cal.get('compuerta') == 'v7' else
                       f"**the vision model's codes were kept**. ")
                    + (f"On reviewed seconds it was not trained on, the calibrated model got {est.get('v7', 0)} of "
                       f"{est.get('n', 0)} hand-seconds right, the vision model alone {est.get('gemma', 0)}."
                       if est.get('n') else ''))
        else:
            st.info("Nobody reviewed this clip: the chart is the vision model's first draft (no calibration, no gate), "
                    "and there are no human labels to score it against.")
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
    c3.metric('Lowest time these changes can reach', f"{pot['piso_s']:.0f} s",
              help='Seconds in which at least one hand is operating. The plan only cuts holding, waiting and transport '
                   'time, so it never goes below this.')
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
        u = e1.number_input('Units per shift (today)', 1.0, 100000.0, float(round(cap0, 1)),
                            help=f"Prefilled as shift length ÷ observed time per unit (8 h ÷ {pot['tiempo_s']:.0f} s ≈ "
                                 f"{cap0:.0f}). Type your real figure.")
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
        mostrar_alertas(ev)
    else:
        st.info('No method alerts for this operation.')

if vista == 'Accuracy & AMD':
    if glosario():
        with st.expander('What the terms mean (station mode, gate, hand-seconds, ±1 s…)'):
            st.markdown(glosario())
    st.markdown('Accuracy = share of hand-seconds (one hand during one second) with the right activity code. Four '
                'tests, each pre-registered (rule written before looking) and scored **once** with the system frozen, on '
                'recordings it had never seen: three new people in the KIT Bimanual dataset (each person does 9 workshop '
                'or kitchen tasks, 10 times each: takes 0–9; the labels of takes 0–1, ≈ 20–50 s, stand in for the '
                'engineer’s review and takes 2–9 are scored) and one on a second dataset, IMPACT (gearbox work: 8 runs '
                'never coded before, by operators not in the motion prior; the first 60 s of each reviewed, scored from '
                'second 60).')
    tabla(pd.DataFrame([
        ['KIT subject 4 (new person), on AMD Token Factory, 1,888 hand-seconds', '41.6 %', '51.5 %', '57.4 % (±1 s: 71.2 %)'],
        ['   split: workshop tasks 756 · kitchen tasks 1,132 hand-seconds', '37.0 · 44.7 %', '56.1 · 48.5 %', '69.8 · 49.0 %'],
        ['KIT subject 3 (new person), on AMD Token Factory, 2,258 hand-seconds', '— (see split)', '55.4 %', '65.1 % (±1 s: 80.1 %)'],
        ['   split: workshop tasks 1,086 · kitchen tasks 1,172 hand-seconds', '41.8 · 41.7 %', '59.3 · 51.9 %', '66.5 · 63.9 %'],
        ['KIT subject 1, run before the event on a lab GPU (Gemma 4-bit, not AMD), 3,305 hand-seconds', '— (see split)', '67.5 %', '77.1 % (±1 s: 87.2 %)'],
        ['   split: workshop tasks 1,347 · kitchen tasks 1,958 hand-seconds', '48.4 · 55.0 %', '69.6 · 66.0 %', '80.3 · 74.9 %'],
        ['IMPACT (gearbox work), 8 runs never coded before, 4 operators not in the motion prior, on AMD Token Factory, 3,142 hand-seconds', '46.5 %',
         '66.5 %', '71.1 % (±1 s: 82.4 %)'],
        ['   improvement-plan check, 8 runs: same hand to free with a fixture and same biggest saving as a plan built '
         'from the human labels', '—', '8 of 8', '8 of 8'],
    ], columns=['New person', 'Constant baseline', 'Vision model alone', 'Gilbreth']))
    st.caption('Constant baseline: always answering the single best code for each hand, the floor to beat. Vision model '
               'alone: Gemma 4 31B with no review. Gilbreth: the vision model + a small model calibrated on the reviewed '
               'seconds + the gate (the shipped mode). ±1 s: also counted right if the human code is one second before or '
               'after.')
    st.caption('On development data, 63–80 % of the remaining errors sit in the second next to a change of activity. '
               'Times are observed times, not standard times (no rating or allowances). Earlier lab runs and '
               'everything we tried and dropped: docs/RESULTS.md.')
    st.markdown('**The examples in this app, run on AMD** (the shipped pipeline, gate on; second looks: measured on data '
                'already used during development, so weaker evidence than the tests above)')
    tabla(pd.DataFrame([
        ['Gearbox, IMPACT operator not in the training data, first 60 s reviewed (307 hand-seconds)', '70.0 %', '73.9 %'],
        ['LEGO, 92 hand-seconds labelled by a person who did not see Gilbreth\'s output (two batches)', '58.7 %', '62.0 %'],
    ], columns=['Example', 'Vision model alone', 'Gilbreth']))
    st.subheader('Station mode: when coworkers at the same station are already reviewed')
    st.markdown('Gilbreth learns from all the reviewed seconds of other workers doing the same task (hand motion, '
                'Gemma\'s codes and each worker\'s dominant hand), not only from the new worker\'s first minute. '
                'Run it with `python agent/estacion.py --station runs/w1 runs/w2 --new runs/w3 --reviewed-until 60`; '
                'on the gearbox example, pick **Station mode** in the sidebar.')
    tabla(pd.DataFrame([
        ['KIT subject 4, clean test (5 labelled coworkers), per hand and second', '51.5 %', '57.4 %',
         '83.4 % (82.5 % with per-second labels)'],
        ['   chart level: gap between each hand\'s time shares and the human labels, in points (lower is better)', '12.5',
         '12.8', '6.3'],
        ['   chart level: takes (KIT repetitions) where it picks the right hand as the one that holds or waits most',
         '79 %', '71 %', '92 %'],
        ['Gearbox example, IMPACT (9 reviewed coworkers), from second 60, 307 hand-seconds', '70.0 %', '73.9 %',
         '77.9 %'],
        ['IMPACT clean test, 8 new runs (same 9 coworkers), 3,142 hand-seconds', '66.5 %', '71.1 %',
         '72.2 % (the version this app runs; the frozen two-model version: 71.3 %)'],
    ], columns=['Test', 'Vision model alone', 'Shipped mode', 'Station mode']))
    st.caption('KIT subject 4 and the IMPACT test: pre-registered, looked at once. The chart rows and the gearbox are '
               'second looks at data already used, declared as such. Outside KIT station mode tied the shipped mode: '
               'there the shipped motion prior likely already comes from the same 9 operators (not measured). The coworkers\' Gemma codes '
               'come partly from the lab GPU run (KIT subject 1, the IMPACT station); the new worker\'s from AMD. The gearbox figure is agent/estacion.py as '
               'shipped (per-second labels). Where nobody at the station has been reviewed yet, the shipped mode is the '
               'one to use. Details: docs/RESULTS.md.')
    st.subheader('Running on AMD')
    if B.get('runs'):
        st.markdown(f"Model **{B.get('modelo', '')}** served on **{B.get('gpu') or 'AMD GPUs'}**"
                    + (f", {B['vram_used_gb']} of {B['vram_total_gb']} GB of GPU memory in use"
                       if B.get('vram_used_gb') else '') + '.')
        VIDEO_EN = {'lego': 'LEGO Mini Digger', 'gearbox': 'Gearbox (IMPACT)', 'screw': 'Screw station',
                    'plastic': 'Plastic parts', 'cardboard': 'Cardboard box'}
        PASO_EN = {'ficha': 'Operation sheet', 'paso': 'Per-second coding', 'desc': 'Row descriptions'}
        st.dataframe(pd.DataFrame([{'Video': VIDEO_EN.get(k, k), 'Video length (s)': v['video_s'], 'Agent wall time (s)': v['wall_s'],
                                    'Video seconds charted per minute of wall time': v['video_s_per_min']}
                                   for k, v in B['runs'].items()]), hide_index=True, width="stretch")
        st.dataframe(pd.DataFrame([{'Step': PASO_EN.get(k, k), 'Requests': v['requests'], 'Latency, median (s)': v['p50_s'],
                                    'Latency, slowest 5 % (s)': v['p95_s'], 'Prompt tokens (mean)': v['prompt_tokens_mean'],
                                    'Output tokens (mean)': v['completion_tokens_mean']}
                                   for k, v in B.get('pasos', {}).items()]), hide_index=True, width="stretch")
        st.caption('The agent sends about one request per second of video plus one per chart row, so the request '
                   'limit of the endpoint (below), not the GPU, sets the wall time. '
                   'Steps: operation sheet (1 request per video), per-second coding (1 per second of video), '
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


def sin_secretos(texto):
    """Defensa en profundidad: nada de lo que se muestra al visitante debe llevar la clave del endpoint."""
    k = config('GILBRETH_API_KEY')
    return texto.replace(k, '***') if k else texto


@st.cache_resource
def _turnos_vivos():
    """Estado común a todas las sesiones: el cupo diario del endpoint de AMD es de la cuenta del equipo, así que va una
    corrida en vivo a la vez y con un tope por hora (revisión de seguridad del 18-oct)."""
    import threading
    return {'lock': threading.Lock(), 'proc': None, 'reserva': 0.0, 'marcas': []}


def reservar_turno():
    """None si se puede lanzar una corrida en vivo (y la deja reservada); si no, el motivo para el visitante."""
    import time
    t, ahora = _turnos_vivos(), time.time()
    tope = int(config('GILBRETH_LIVE_MAX_PER_HOUR', '12') or 12)
    with t['lock']:
        t['marcas'] = [m for m in t['marcas'] if ahora - m < 3600]
        if (t['proc'] is not None and t['proc'].poll() is None) or ahora - t['reserva'] < 60:
            return ('Another visitor is charting a clip live right now (one live run at a time on the shared AMD '
                    'endpoint). Please try again in a few minutes.')
        if len(t['marcas']) >= tope:
            return (f'This public demo allows {tope} live runs per hour on the shared AMD endpoint, and they are used '
                    'up for now. Please try again later.')
        t['reserva'] = ahora
        t['marcas'].append(ahora)
    return None


def registrar_turno(proc):
    t = _turnos_vivos()
    with t['lock']:
        t['proc'], t['reserva'] = proc, 0.0


def seguir_agente(run, p, t0):
    """Muestra el avance del agente leyendo su bitácora y, cuando acaba, el resultado o el error. Si el visitante toca
    otro control, Streamlit corta este guion pero el agente sigue: al volver, esta función lo retoma."""
    import time
    log = run / 'agente.log'
    with st.status('The agent is charting your video…', expanded=True) as estado:
        vistos = 0
        while True:
            lineas = log.read_text(encoding='utf-8', errors='replace').splitlines() if log.exists() else []
            for linea in lineas[vistos:]:
                if linea[:3] in PASOS_EN:
                    estado.write(f'{PASOS_EN[linea[:3]]} (started at {time.time() - t0:.0f} s)'
                                 + (' · one request per second of video on the shared endpoint: the long step'
                                    if linea[:3] == '4/5' else ''))
                    estado.update(label=f'The agent is charting your video… step {linea[:3]}: {PASOS_EN[linea[:3]]}')
            vistos = len(lineas)
            if p.poll() is not None:
                break
            time.sleep(1)
        (run / 'corriendo').unlink(missing_ok=True)
        (st.session_state.get('_procs') or {}).pop(str(run), None)
        ok = p.returncode == 0 and (run / 'diagrama.json').exists()
        if ok:
            (run / 'tiempo.json').write_text(json.dumps({'wall_s': round(time.time() - t0, 1)}))
            estado.update(label=f'Done in {time.time() - t0:.0f} s', state='complete', expanded=False)
        elif p.returncode == 3:
            estado.update(label='Today\'s free GPU quota for this demo is used up', state='error', expanded=False)
        else:
            estado.update(label='The agent stopped before finishing', state='error')
            st.code(sin_secretos('\n'.join(lineas[-25:])))
    if p.returncode == 3:
        st.warning('The free AMD endpoint behind this demo has a daily quota, and it is used up for today. It resets at '
                   'midnight Beijing time (16:00 UTC, 11:00 in Colombia). The examples in the sidebar were computed with the full agent.')
    if not ok:
        st.button('Try again', key='otra_vez')
    return ok


def correr_agente(vid, npz, run, base, modelo, motor, respaldo=False):
    """Lanza agent/bimanual.py contra el endpoint configurado y sigue su avance; devuelve True si terminó bien."""
    import subprocess, time
    with st.spinner('Checking that the AMD endpoint is answering…'):
        vivo = endpoint_vivo(base, modelo)
    # el respaldo (Qwen) razona: se le apaga el razonamiento, como en el cribado
    extra = ['--ollama'] if respaldo and config('GILBRETH_FALLBACK_NO_REASONING', '1') == '1' else []
    if not vivo:
        st.warning('The shared AMD endpoint that serves the vision model is not answering right now (it is an '
                   'experimental service). Please try again in a while; the examples in the sidebar were computed with it.')
        return False
    motivo = reservar_turno()
    if motivo:
        st.info(motivo)
        return False
    env = {**env_agente(), 'PYTHONUNBUFFERED': '1'}
    cmd = [sys.executable, str(RAIZ / 'agent' / 'bimanual.py'), str(vid), '--salida', str(run), '--base', base,
           '--modelo', modelo, '--idioma', 'en', '--hilos', config('GILBRETH_THREADS', '8'), '--puntos', str(npz)] + extra
    if config('GILBRETH_LIVE_DESC', '1') == '0':      # endpoint compartido y lento: sin la 2.ª pasada de descripciones
        cmd.append('--sin-descripciones')
    run.mkdir(parents=True, exist_ok=True)
    (run / 'motor.txt').write_text(motor, encoding='utf-8')
    t0 = time.time()
    #  la salida va a un fichero y no a una tubería: si el visitante toca otro control y Streamlit corta el guion, el
    #  agente sigue y escribe su resultado (con la tubería moría en el siguiente print; revisión del 18-oct)
    with open(run / 'agente.log', 'w', encoding='utf-8') as fh:
        p = subprocess.Popen(cmd, stdout=fh, stderr=subprocess.STDOUT, env=env, cwd=str(RAIZ),
                             **({'start_new_session': True} if os.name == 'posix' else {}))
    registrar_turno(p)
    (run / 'corriendo').write_text(f'{t0:.0f}')
    st.session_state.setdefault('_procs', {})[str(run)] = (p, t0)
    return seguir_agente(run, p, t0)


def previo_en(previo):
    """calibracion.json guarda el previo en español ('IMPACT' o 'ninguno (MIT puro)'); en la app va en inglés."""
    if not previo:
        return 'unknown'
    if previo.startswith('ninguno'):
        return 'none (MIT-pure mode)'
    if previo.startswith('IMPACT'):                        # 'IMPACT' o 'IMPACT (other operators)'
        return 'IMPACT motion prior' + previo[len('IMPACT'):]
    return previo


def mostrar_resultado(run, motor, nota=None):
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
                   + ('part is the review below.' if nota is None else
                      'part, the review, opens after you chart the clip live with the button above.'))
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
        st.caption(nota or f'Computed just now by {motor}. First draft from the vision model, not yet reviewed by an engineer.')
    ver_manos(filas2)
    st.subheader('Second by second')
    st.altair_chart(linea_tiempo(filas2), width="stretch")
    st.dataframe(tabla_filas(filas2)[['Time', 'Left hand', 'L', 'R', 'Right hand']], hide_index=True,
                 width="stretch", height=380)
    if pot2['palancas']:
        st.subheader('Top improvements')
        for p in pot2['palancas'][:3]:
            st.markdown(f"- **{p['title']}** — saves ≈ **{p['segundos']:.{nd}f} s** in this clip ({p['pct']:.{nd}f} %). "
                        f"{evidencia(p, True)}")
    if ev2:
        st.subheader('Method alerts')
        mostrar_alertas(ev2)
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
    st.subheader('Review the first seconds; the gate decides whether to recode the rest')
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
            st.code(sin_secretos(p.stdout[-2000:] + p.stderr[-1000:]))
        else:
            st.rerun()


def nueva_subida(clave, nombre, datos, muestra=False):
    """Una subida, o el clip de muestra por EXACTAMENTE el mismo camino: su propio directorio temporal, el video
    dentro y su duración en st.session_state['subida']."""
    import cv2, shutil, time
    viejo = st.session_state.get('subida')
    if viejo and viejo.get('dir'):                       # la subida que esta sesión reemplaza
        shutil.rmtree(viejo['dir'], ignore_errors=True)
    for d in Path(tempfile.gettempdir()).glob('gilbreth_*'):   # subidas de sesiones cerradas hace horas
        try:
            if time.time() - d.stat().st_mtime > 6 * 3600:
                shutil.rmtree(d, ignore_errors=True)
        except OSError:
            pass
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
    st.caption('Privacy: your clip is processed on this app\'s server. For the full chart, still frames and hand crops '
               'are sent to AMD Token Factory (developer.amd.com.cn), AMD\'s hosted model service. Avoid clips that show '
               'faces or confidential work. Uploads are deleted when you replace them; older ones are cleared after six hours.')
    up = st.file_uploader('Video', type=['mp4', 'mov', 'avi', 'mkv'])
    if (st.session_state.pop('_auto_muestra', False) and up is None and MUESTRA.exists()
            and not (st.session_state.get('subida') or {}).get('muestra')):
        nueva_subida('sample:' + MUESTRA.name, MUESTRA.name, MUESTRA.read_bytes(), muestra=True)
    sub = st.session_state.get('subida') or {}
    if up is not None:
        if sub.get('clave') != f'{up.name}:{up.size}':
            sub = nueva_subida(f'{up.name}:{up.size}', up.name, up.getvalue())
    elif sub.get('muestra'):
        a, b = st.columns([5, 1], vertical_alignment='center')
        a.caption('Using our 20-second sample: a screw-assembly station from *Factory Manipulation Videos* by '
                  'Procedural Robotics Inc. (CC BY 4.0), the same take as the screw example. Below, what the full agent '
                  'charted on it on AMD. Upload your own video above to replace it.')
        if b.button('Remove the sample', key='quitar_muestra', width='stretch'):
            import shutil
            shutil.rmtree(sub.get('dir', ''), ignore_errors=True)
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
            with st.expander('Watch the sample clip', expanded=True):
                st.columns([1, 1])[0].video(str(vid))      # a lo ancho tapaba lo que el agente sacó del clip
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
        boton_vivo = False
        limite = float(config('GILBRETH_MAX_LIVE_S', '120'))
        if pi and base and not (run / 'diagrama.json').exists() and sub['dur'] > limite + 1:
            st.info(f'On this public demo the full agent charts clips of up to {limite:.0f} s (the free AMD endpoint has '
                    f'a daily quota). Trim the video to chart it; the hand tracking below works on the whole clip.')
        elif pi and base and estado != 'ninguno' and not (run / 'diagrama.json').exists():
            import time as _t
            proc = (st.session_state.get('_procs') or {}).get(str(run))
            if proc:                                  # esta sesión lanzó el agente: retomarlo (o ver cómo acabó)
                seguir_agente(run, *proc)
            elif (run / 'corriendo').exists() and _t.time() - (run / 'corriendo').stat().st_mtime < 1200:
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
                boton_vivo = True
                if st.button(f'Chart it with the full agent{" again, live" if sub.get("muestra") else ""} · {motor}',
                             type='primary'):
                    correr_agente(vid, npz, run, base, modelo, motor, estado == 'respaldo')
        if (run / 'diagrama.json').exists():
            mostrar_resultado(run, motor)
            if base:
                revisar(run, vid, npz, base, modelo, estado == 'respaldo', sub['dur'])
        elif sub.get('muestra') and (MUESTRA_RUN / 'diagrama.json').exists():
            # lo que el agente resolvió en la muestra, sin esperar: una corrida en vivo guardada (la app la rehace con el botón)
            st.subheader('What Gilbreth charted on this sample')
            st.caption('What comes next, after a live run: a table of the first seconds opens, one row per second. You pick '
                       'each hand\'s activity from a list and press «Apply my review». Gilbreth then recodes the rest on CPU '
                       'in under a minute, with no new requests to the model, and the gate keeps the vision model\'s codes '
                       'unless the calibrated one beats it on your reviewed seconds.')
            mostrar_resultado(MUESTRA_RUN, motor, nota='A stored run of the full agent on this clip: Gemma 4 31B on AMD '
                              'Token Factory, from this public app on 18 Oct 2026 (first draft, not reviewed by an '
                              'engineer; its method alerts and Excel were rebuilt on CPU from those codes).'
                              + (' Press the button above to chart it again live; results vary a little between runs.'
                                 if boton_vivo else ''))
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
                mostrar_alertas(ev_vivo)
    if not base:
        st.info('The full agent needs the vision model on an AMD GPU endpoint, which is not connected to this copy of '
                'the app. The examples in the sidebar were computed with the full agent.')
