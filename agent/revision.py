"""Revisión humana del borrador (el analista aprueba) y Excel final.

  python revision.py pagina diagrama.json video.mp4 salida.html   -> página para revisar (video + filas editables)
  python revision.py aprobar diagrama_revisado.json salida.xlsx    -> Excel final con lo que aprobó el analista

La página es la misma con la que Juan validó el minuto de oro: corregir el código de cada mano, mover inicio/fin con
I/F mirando el video, validar fila por fila y exportar el JSON."""
import datetime, json, sys
from pathlib import Path

import salidas

aqui = Path(__file__).resolve().parent


def pagina(diagrama, video, salida, src=None):
    d = json.loads(Path(diagrama).read_text(encoding='utf-8'))
    filas = [{'n': f['n'], 't0': f['t0'], 't1': f['t1'], 'cmd': f['md'], 'cmi': f['mi'],
              'md': ' · '.join(dict.fromkeys(o for o in f.get('obs', []) if o))[:220], 'mi': ''} for f in d['filas']]
    camara = d.get('meta', {}).get('camara', '') or 'MD = mano derecha del operario; MI = mano izquierda.'
    t = (aqui / 'plantilla_revision.html').read_text(encoding='utf-8')
    titulo = f"Revisar diagrama · {d['meta'].get('video', '')} · {len(filas)} filas"
    t = (t.replace('/*TITULO*/', titulo).replace('/*VIDEO*/', src or Path(video).name).replace('/*CAMARA*/', camara)
         .replace('/*CLAVE*/', Path(video).stem).replace('const ORIGINAL = /*DATOS*/[];',
                                                         'const ORIGINAL = ' + json.dumps(filas, ensure_ascii=False) + ';'))
    Path(salida).write_text(t, encoding='utf-8')
    print('página ->', salida, '· video:', src or Path(video).name)


def aprobar(revisado, salida_xlsx, meta_extra=None):
    r = json.loads(Path(revisado).read_text(encoding='utf-8'))
    filas = []
    for i, f in enumerate(sorted(r['filas'], key=lambda x: x['t0']), 1):
        filas.append({'n': i, 't0': f['t0'], 't1': f['t1'], 'dur': round(f['t1'] - f['t0'], 2), 'md': f['cmd'],
                      'mi': f['cmi'], 'desc_md': (f.get('nota') or salidas.NOMBRE.get(f['cmd'], f['cmd'])),
                      'desc_mi': salidas.NOMBRE.get(f['cmi'], f['cmi']), 'obs': [], 'ks': []})
    ind = salidas.indicadores(filas)
    meta = {'producto': '', 'operacion': '', 'lugar': '', 'video': r.get('video', ''),
            'fecha': datetime.date.today().isoformat(),
            'convencion_texto': f"revisado por el analista ({r.get('validadas', 0)} de {len(filas)} filas validadas, "
                                f"{sum(1 for f in r['filas'] if f.get('cambiada'))} corregidas)."}
    meta.update(meta_extra or {})
    salidas.escribir_excel(filas, ind, meta, salida_xlsx)
    print('Excel aprobado ->', salida_xlsx, json.dumps(ind, ensure_ascii=False))


if __name__ == '__main__':
    if sys.argv[1] == 'pagina':
        pagina(*sys.argv[2:5])
    else:
        aprobar(*sys.argv[2:4])
