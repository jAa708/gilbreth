"""Revisión humana del borrador (el analista aprueba) y Excel final.

  python revision.py pagina diagrama.json video.mp4 salida.html   -> página para revisar (video + filas editables)
  python revision.py aprobar diagrama_revisado.json salida.xlsx    -> Excel final con lo que aprobó el analista

La página es la misma con la que Juan validó el minuto de oro: corregir el código de cada mano, mover inicio/fin con
I/F mirando el video, validar fila por fila y exportar el JSON."""
import datetime, json, sys
from pathlib import Path

import salidas

aqui = Path(__file__).resolve().parent


CONVENCION_ES = 'MD = mano derecha del operario; MI = izquierda'
CONVENCION_EN = 'R = right hand of the operator; L = left hand of the operator'

# Sólo se aplica al HTML inglés. La plantilla española conserva el texto y la
# estructura que usan los analistas que ya revisan diagramas con esta página.
LEYENDA_EN = '''    <div class="leyenda">
      <b>Hand orientation (from the agent's operation sheet):</b> /*CAMARA*/<br><br>
      <b>Codes:</b> TR = reach, pick up, or carry · OP = assemble or operate · TR+OP = carry and fit in the same row ·
      <b>S = ▽ hold while the OTHER hand operates</b> · <b>D = delay</b> (idle, or holding while the other hand reaches for a part) · NV = not visible.<br><br>
      <b>Shortcuts:</b> <kbd>Space</kbd> play/pause · <kbd>J</kbd>/<kbd>K</kbd> previous/next row ·
      <kbd>R</kbd> replay · <kbd>L</kbd> loop · <kbd>I</kbd>/<kbd>F</kbd> set start/end · <kbd>V</kbd> validate and continue.<br><br>
      This is an agent-generated draft. Review each row, correct either hand's code or the time boundaries (I/F),
      and validate it. Most measured errors occur at row boundaries (±1 s). Changes are saved automatically in this
      browser. When finished, <b>Export JSON</b> and pass the file to
      <code>python revision.py aprobar diagrama_revisado.json final.xlsx</code>.
    </div>'''

TEXTOS_EN = (
    ('<title>Revisar diagrama bimanual</title>', '<title>Review bimanual chart</title>'),
    ('0 validadas', '0 validated'),
    ('0 cambiadas', '0 changed'),
    ('>Exportar JSON</button>', '>Export JSON</button>'),
    ('↺ Repetir fila (R)', '↺ Replay row (R)'),
    (' bucle en la fila (L)', ' loop current row (L)'),
    ('>0,25×</option>', '>0.25×</option>'),
    ('>0,5×</option>', '>0.5×</option>'),
    ('Inicio = ahora (I)', 'Set start to now (I)'),
    ('Fin = ahora (F)', 'Set end to now (F)'),
    ('✓ Validar y siguiente (V)', '✓ Validate and next (V)'),
    ('<th>Tiempo</th><th>MD (mano derecha)</th><th>MI (mano izquierda)</th>',
     '<th>Observed time</th><th>Right hand</th><th>Left hand</th>'),
    (" + ' / ' + filas.length + ' validadas'", " + ' / ' + filas.length + ' validated'"),
    (".length + ' cambiadas'", ".length + ' changed'"),
    ('placeholder="nota (opcional)"', 'placeholder="note (optional)"'),
    ("'Prueba ciega · 8 secuencias · sin códigos ni descripciones'",
     "'Blind review · 8 sequences · no codes or descriptions'"),
    # The observation is display text. Keep its original value in the exported JSON.
    ('${f.md}', "${f.md.replace(/\\bMD:/g, 'R:').replace(/\\bMI:/g, 'L:')}"),
)


def _descripcion_en(f):
    """Use hand descriptions when available; old charts may have Spanish observations."""
    def detalle(mano, clave):
        descripcion = f.get(clave)
        if descripcion and descripcion != f.get(clave + '_es'):
            return descripcion
        return salidas.nombre(f[mano], 'en')

    return f"R: {detalle('md', 'desc_md')} · L: {detalle('mi', 'desc_mi')}"


def pagina(diagrama, video, salida, src=None, idioma='es'):
    if idioma not in ('es', 'en'):
        raise ValueError("idioma debe ser 'es' o 'en'")
    d = json.loads(Path(diagrama).read_text(encoding='utf-8'))
    filas = [{'n': f['n'], 't0': f['t0'], 't1': f['t1'], 'cmd': f['md'], 'cmi': f['mi'],
              'md': (_descripcion_en(f) if idioma == 'en' else
                     ' · '.join(dict.fromkeys(o for o in f.get('obs', []) if o))[:220]),
              'mi': ''} for f in d['filas']]
    camara = d.get('meta', {}).get('camara', '') or (
        "R = operator's right hand; L = operator's left hand." if idioma == 'en'
        else 'MD = mano derecha del operario; MI = mano izquierda.')
    t = (aqui / 'plantilla_revision.html').read_text(encoding='utf-8')
    if idioma == 'en':
        inicio = t.index('    <div class="leyenda">')
        fin = t.index('    </div>', inicio) + len('    </div>')
        t = t[:inicio] + LEYENDA_EN + t[fin:]
        for original, traduccion in TEXTOS_EN:
            if original not in t:
                raise ValueError(f'Falta texto en la plantilla de revisión: {original}')
            t = t.replace(original, traduccion)
    titulo = (f"Review chart · {d['meta'].get('video', '')} · {len(filas)} rows" if idioma == 'en'
              else f"Revisar diagrama · {d['meta'].get('video', '')} · {len(filas)} filas")
    t = (t.replace('/*IDIOMA*/', idioma).replace('/*CONVENCION*/', CONVENCION_EN if idioma == 'en' else CONVENCION_ES)
         .replace('/*TITULO*/', titulo).replace('/*VIDEO*/', src or Path(video).name).replace('/*CAMARA*/', camara)
         .replace('/*CLAVE*/', Path(video).stem).replace('const ORIGINAL = /*DATOS*/[];',
                                                         'const ORIGINAL = ' + json.dumps(filas, ensure_ascii=False) + ';'))
    Path(salida).write_text(t, encoding='utf-8')
    print('review page ->' if idioma == 'en' else 'página ->', salida, '· video:', src or Path(video).name)


def aprobar(revisado, salida_xlsx, meta_extra=None, idioma=None):
    r = json.loads(Path(revisado).read_text(encoding='utf-8'))
    idioma = idioma or ('en' if r.get('convencion') == CONVENCION_EN else 'es')
    if idioma not in ('es', 'en'):
        raise ValueError("idioma debe ser 'es' o 'en'")
    nombres = salidas.NOMBRE_EN if idioma == 'en' else salidas.NOMBRE
    filas = []
    for i, f in enumerate(sorted(r['filas'], key=lambda x: x['t0']), 1):
        filas.append({'n': i, 't0': f['t0'], 't1': f['t1'], 'dur': round(f['t1'] - f['t0'], 2), 'md': f['cmd'],
                      'mi': f['cmi'], 'desc_md': (f.get('nota') or nombres.get(f['cmd'], f['cmd'])),
                      'desc_mi': nombres.get(f['cmi'], f['cmi']),
                      'obs': [], 'ks': []})
    ind = salidas.indicadores(filas)
    if idioma == 'en':
        convencion = (f"reviewed by the analyst ({r.get('validadas', 0)} of {len(filas)} rows validated, "
                      f"{sum(1 for f in r['filas'] if f.get('cambiada'))} corrected).")
    else:
        convencion = (f"revisado por el analista ({r.get('validadas', 0)} de {len(filas)} filas validadas, "
                      f"{sum(1 for f in r['filas'] if f.get('cambiada'))} corregidas).")
    meta = {'producto': '', 'operacion': '', 'lugar': '', 'video': r.get('video', ''),
            'fecha': datetime.date.today().isoformat(),
            'convencion_texto': convencion}
    meta.update(meta_extra or {})
    salidas.escribir_excel(filas, ind, meta, salida_xlsx, idioma=idioma)
    print('Approved Excel ->' if idioma == 'en' else 'Excel aprobado ->', salida_xlsx,
          json.dumps(ind, ensure_ascii=False))


if __name__ == '__main__':
    if sys.argv[1] == 'pagina':
        pagina(*sys.argv[2:5])
    else:
        aprobar(*sys.argv[2:4])
