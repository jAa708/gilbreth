"""Salidas del agente: filas del diagrama (uniendo segundos iguales), indicadores, Excel en el formato del curso
(cuatro columnas de símbolos por mano, resumen con fórmulas) y una página HTML de revisión con un fotograma por fila.
Las propuestas de mejora salen de reglas de economía de movimientos aplicadas a los números, no de texto libre."""
import base64, html, json
from collections import Counter
from pathlib import Path

SIMBOLO = {'OP': 'O', 'TR+OP': 'O', 'TR': 'T', 'S': 'S', 'D': 'E', 'NV': 'E'}
NOMBRE = {'OP': 'operación', 'TR': 'transporte', 'TR+OP': 'transporte y operación', 'S': 'sostiene', 'D': 'espera',
          'NV': 'no visible'}


def mmss(t):
    return f'{int(t // 60)}:{t % 60:04.1f}'.replace('.0', '') if t % 1 else f'{int(t // 60)}:{int(t % 60):02d}'


def filas_elemento(ventanas, max_tr=1):
    """Nivel «elemento» (Mundel): si una mano transporta ≤ max_tr s e inmediatamente opera, ese transporte se une a la
    operación como TR+OP («trae y encaja»), y la otra mano que sostenía pasa de D a S (convención del curso). La OIT
    estricta (por defecto) deja transporte y operación en filas distintas salvo simultaneidad real."""
    v = [dict(o) for o in sorted(ventanas, key=lambda x: x['t0'])]
    for k, otra in (('md', 'mi'), ('mi', 'md')):
        i = 0
        while i < len(v):
            if v[i][k] == 'TR':
                j = i
                while j + 1 < len(v) and v[j + 1][k] == 'TR':
                    j += 1
                if j - i + 1 <= max_tr and j + 1 < len(v) and v[j + 1][k] in ('OP', 'TR+OP'):
                    for t in range(i, j + 1):
                        v[t][k] = 'TR+OP'
                        if v[t][otra] == 'D':
                            v[t][otra] = 'S'
                i = j + 1
            else:
                i += 1
    return v


def unir_filas(ventanas):
    """ventanas: [{'t0','t1','md','mi','crudo'}] en orden → filas del diagrama (una fila por cambio de cualquier mano)."""
    filas = []
    for v in sorted(ventanas, key=lambda x: x['t0']):
        obs = (v.get('crudo') or {}).get('observations', '')
        if filas and filas[-1]['md'] == v['md'] and filas[-1]['mi'] == v['mi'] and abs(filas[-1]['t1'] - v['t0']) < 0.01:
            filas[-1]['t1'] = v['t1']
            filas[-1]['obs'].append(obs)
            filas[-1]['ks'].append(v.get('k'))
        else:
            filas.append({'t0': v['t0'], 't1': v['t1'], 'md': v['md'], 'mi': v['mi'], 'obs': [obs], 'ks': [v.get('k')]})
    for i, f in enumerate(filas, 1):
        f['n'] = i
        f['dur'] = round(f['t1'] - f['t0'], 2)
    return filas


def indicadores(filas):
    T = sum(f['dur'] for f in filas) or 1
    out = {'duracion_s': round(T, 1), 'filas': len(filas)}
    for mano, k in (('MD', 'md'), ('MI', 'mi')):
        c = Counter()
        for f in filas:
            c[f[k]] += f['dur']
        out[mano] = {cod: round(100 * s / T, 1) for cod, s in c.most_common()}
        out[mano + '_productivo_pct'] = round(100 * (c['OP'] + c['TR+OP']) / T, 1)
        out[mano + '_improductivo_pct'] = round(100 * (c['D'] + c['S'] + c['NV']) / T, 1)
    return out


def propuestas(ind):
    """Reglas de economía de movimientos (OIT / Barnes) disparadas por los números del diagrama."""
    p = []
    for mano, otra in (('MI', 'MD'), ('MD', 'MI')):
        s, d = ind[mano].get('S', 0), ind[mano].get('D', 0)
        if s >= 25:
            p.append(f'La {"izquierda" if mano == "MI" else "derecha"} sostiene el {s:.0f} % del tiempo: un soporte o '
                     f'plantilla que sujete la pieza la libera para trabajar en simultáneo (principio: no usar la mano como '
                     f'mordaza).')
        if d >= 20:
            p.append(f'La {"izquierda" if mano == "MI" else "derecha"} espera el {d:.0f} % del tiempo: repartir el trabajo '
                     f'para que ambas manos empiecen y terminen a la vez y hagan movimientos simétricos.')
        tr = ind[mano].get('TR', 0)
        if tr >= 20:
            p.append(f'La {"izquierda" if mano == "MI" else "derecha"} transporta el {tr:.0f} % del tiempo: acercar '
                     f'piezas y herramientas al área normal de trabajo, en el orden de uso y con alimentación por gravedad.')
    if abs(ind['MD_productivo_pct'] - ind['MI_productivo_pct']) >= 30:
        p.append(f'Desbalance: la derecha opera el {ind["MD_productivo_pct"]:.0f} % y la izquierda el '
                 f'{ind["MI_productivo_pct"]:.0f} %. Revisar si la izquierda puede alimentar piezas mientras la derecha ensambla.')
    return p or ['Sin desbalances grandes: revisar fila por fila las esperas y transportes largos.']


def escribir_excel(filas, ind, meta, ruta, eventos=None):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    wb = Workbook()
    ws = wb.active
    ws.title = 'Diagrama bimanual'
    AZUL, GRIS, AMAR = PatternFill('solid', fgColor='DBE5F1'), PatternFill('solid', fgColor='F2F2F2'), PatternFill('solid', fgColor='FFF2CC')
    fino = Side(style='thin', color='808080')
    BORDE = Border(left=fino, right=fino, top=fino, bottom=fino)
    F = lambda b=False, s=10, i=False: Font(name='Arial', size=s, bold=b, italic=i)
    C = Alignment(horizontal='center', vertical='center', wrap_text=True)
    L = Alignment(horizontal='left', vertical='center', wrap_text=True)
    for k, v in {'A': 5, 'B': 30, 'C': 22, 'D': 8, 'E': 5, 'F': 5, 'G': 5, 'H': 5, 'I': 2, 'J': 5, 'K': 5, 'L': 5, 'M': 5,
                 'N': 8, 'O': 30, 'P': 22, 'Q': 5}.items():
        ws.column_dimensions[k].width = v
    ws.merge_cells('A1:Q1')
    ws['A1'] = 'D I A G R A M A   B I M A N U A L'
    ws['A1'].font, ws['A1'].alignment, ws['A1'].fill = F(True, 14), C, AZUL
    cab = [('Diagrama núm. 1 · Hoja 1 de 1', 'Método: ACTUAL (observado en video)'),
           (f'Producto: {meta.get("producto", "")}'[:250], f'Video: {meta.get("video", "")} ({ind["duracion_s"]} s)'),
           (f'Operación: {meta.get("operacion", "")}'[:250], f'Lugar: {meta.get("lugar", "")}'[:250]),
           ('Elaborado: agente bimanual (borrador para revisión del analista)', f'Fecha: {meta.get("fecha", "")}')]
    for i, (a, b) in enumerate(cab, start=2):
        ws.merge_cells(f'A{i}:H{i}'), ws.merge_cells(f'I{i}:Q{i}')
        ws[f'A{i}'], ws[f'I{i}'] = a, b
        for c in (ws[f'A{i}'], ws[f'I{i}']):
            c.font, c.alignment = F(s=9), L
        ws.row_dimensions[i].height = 30
    h = 7
    ws.merge_cells(f'B{h}:C{h}'), ws.merge_cells(f'O{h}:P{h}')
    ws[f'A{h}'], ws[f'B{h}'], ws[f'D{h}'] = 'N.º', 'Descripción de la mano derecha (MD)', 'Tiempo (s)'
    ws[f'N{h}'], ws[f'O{h}'], ws[f'Q{h}'] = 'Tiempo (s)', 'Descripción de la mano izquierda (MI)', 'N.º'
    for cols in ('EFGH', 'JKLM'):
        for col, sym in zip(cols, ['○', '⇨', 'D', '▽']):
            ws[f'{col}{h}'] = sym
    for col in 'ABCDEFGHJKLMNOPQ':
        c = ws[f'{col}{h}']
        c.font, c.alignment, c.fill, c.border = F(True, 9), C, AZUL, BORDE
    r0 = h + 1
    for k, f in enumerate(filas):
        r = r0 + k
        ws.merge_cells(f'B{r}:C{r}'), ws.merge_cells(f'O{r}:P{r}')
        ws[f'A{r}'] = ws[f'Q{r}'] = f['n']
        ws[f'B{r}'] = f'{mmss(f["t0"])}–{mmss(f["t1"])}  {f.get("desc_md") or NOMBRE[f["md"]]}'
        ws[f'O{r}'] = f'{mmss(f["t0"])}–{mmss(f["t1"])}  {f.get("desc_mi") or NOMBRE[f["mi"]]}'
        ws[f'D{r}'] = ws[f'N{r}'] = f['dur']
        ws[f'{dict(O="E", T="F", E="G", S="H")[SIMBOLO[f["md"]]]}{r}'] = 'x'
        ws[f'{dict(O="J", T="K", E="L", S="M")[SIMBOLO[f["mi"]]]}{r}'] = 'x'
        for col in 'ABCDEFGHJKLMNOPQ':
            c = ws[f'{col}{r}']
            c.border, c.font = BORDE, F(s=9)
            c.alignment = L if col in 'BCOP' else C
            if c.value == 'x':
                c.fill, c.font = AMAR, F(True, 10)
        ws.row_dimensions[r].height = 28
    rf = r0 + len(filas) - 1
    rs = rf + 2
    ws.merge_cells(f'A{rs}:Q{rs}')
    ws[f'A{rs}'] = 'RESUMEN'
    ws[f'A{rs}'].font, ws[f'A{rs}'].alignment, ws[f'A{rs}'].fill = F(True, 11), C, AZUL
    ws[f'B{rs + 1}'], ws[f'D{rs + 1}'], ws[f'E{rs + 1}'], ws[f'J{rs + 1}'], ws[f'K{rs + 1}'] = 'Método actual', 'MD (n.º)', 'MD (s)', 'MI (n.º)', 'MI (s)'
    for i, (nom, cd, ci) in enumerate([('Operaciones ○', 'E', 'J'), ('Desplazamientos ⇨', 'F', 'K'),
                                       ('Esperas D', 'G', 'L'), ('Sostenimientos ▽', 'H', 'M')], start=rs + 2):
        ws[f'B{i}'] = nom
        ws[f'D{i}'] = f'=COUNTIF({cd}{r0}:{cd}{rf},"x")'
        ws[f'E{i}'] = f'=SUMIF({cd}{r0}:{cd}{rf},"x",$D${r0}:$D${rf})'
        ws[f'J{i}'] = f'=COUNTIF({ci}{r0}:{ci}{rf},"x")'
        ws[f'K{i}'] = f'=SUMIF({ci}{r0}:{ci}{rf},"x",$N${r0}:$N${rf})'
        for c in 'BDEJK':
            ws[f'{c}{i}'].font, ws[f'{c}{i}'].border = F(s=9), BORDE
    rp = rs + 7
    ws.merge_cells(f'A{rp}:Q{rp}')
    ws[f'A{rp}'] = 'PROPUESTAS DE MEJORA (reglas de economía de movimientos sobre los números del diagrama)'
    ws[f'A{rp}'].font, ws[f'A{rp}'].alignment, ws[f'A{rp}'].fill = F(True, 11), C, AZUL
    for i, t in enumerate(propuestas(ind), start=rp + 1):
        ws.merge_cells(f'A{i}:Q{i}')
        ws[f'A{i}'] = f'{i - rp}) {t}'
        ws[f'A{i}'].font, ws[f'A{i}'].alignment = F(s=9), L
        ws.row_dimensions[i].height = 28
    nota = rp + len(propuestas(ind)) + 2
    ws.merge_cells(f'A{nota}:Q{nota}')
    ws[f'A{nota}'] = (f'Convención: {meta.get("convencion_texto", "")} Borrador automático: el analista revisa y aprueba cada fila '
                      f'antes de usarlo. Tiempo observado (no normal ni estándar: falta la valoración del ritmo y los suplementos).')
    ws[f'A{nota}'].font, ws[f'A{nota}'].alignment = F(s=8, i=True), L
    ws.row_dimensions[nota].height = 36
    ws.freeze_panes = f'A{r0}'
    ws.page_setup.orientation = 'landscape'
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.fitToWidth, ws.page_setup.fitToHeight = 1, 0
    if eventos:
        import errores
        we = wb.create_sheet('Errores de método')
        for k, v in {'A': 5, 'B': 34, 'C': 12, 'D': 14, 'E': 10, 'F': 60}.items():
            we.column_dimensions[k].width = v
        we.merge_cells('A1:F1')
        we['A1'] = 'POSIBLES ERRORES DE MÉTODO (señales para revisar contra el video; no son veredictos)'
        we['A1'].font, we['A1'].alignment, we['A1'].fill = F(True, 12), C, AZUL
        for col, h in zip('ABCDEF', ['N.º', 'Error', 'Mano', 'Desde – hasta', 'Duración (s)', 'Corrección propuesta']):
            we[f'{col}2'] = h
            we[f'{col}2'].font, we[f'{col}2'].alignment, we[f'{col}2'].fill, we[f'{col}2'].border = F(True, 9), C, GRIS, BORDE
        for i, e in enumerate(errores.para_informe(eventos), 1):
            r = i + 2
            mano = {'R': 'derecha', 'L': 'izquierda', 'RL': 'ambas', 'LR': 'ambas'}.get(e['mano'], e['mano'])
            cuando = e['detalle'] if e.get('resumen') else f'{mmss(e["t0"])} – {mmss(e["t1"])}'
            dur = float(e['detalle'].split(' veces, ')[1].split(' s')[0]) if e.get('resumen') else round(e['t1'] - e['t0'], 1)
            vals = [i, errores.TITULO.get(e['tipo'], e['tipo']), mano, cuando, dur, errores.CORRECCION.get(e['tipo'], '')]
            for col, v in zip('ABCDEF', vals):
                c = we[f'{col}{r}']
                c.value, c.font, c.border = v, F(s=9), BORDE
                c.alignment = L if col in 'BF' else C
            we.row_dimensions[r].height = 30
    wb.save(ruta)


def escribir_html(filas, ind, meta, carpeta_img, ruta, img_de=None, eventos=None):
    """Página de revisión: una tarjeta por fila con el fotograma central, los códigos y lo que vio el modelo.
    img_de(k) -> ruta del fotograma (por defecto carpeta_img/{k:04d}_f1.jpg)."""
    def img(k):
        p = Path(img_de(k)) if img_de else Path(carpeta_img) / f'{k:04d}_f1.jpg'
        return 'data:image/jpeg;base64,' + base64.b64encode(p.read_bytes()).decode() if p.exists() else ''
    tarjetas = []
    for f in filas:
        k = f['ks'][len(f['ks']) // 2]
        obs = ' · '.join(dict.fromkeys(o for o in f['obs'] if o))[:500]
        tarjetas.append(f'''<div class="t"><img src="{img(k)}" loading="lazy"><div class="d">
<b>{f["n"]}. {mmss(f["t0"])}–{mmss(f["t1"])} ({f["dur"]} s)</b><br>
MD <span class="c">{f["md"]}</span> · MI <span class="c">{f["mi"]}</span><br><small>{html.escape(obs)}</small></div></div>''')
    pct = lambda m: ' · '.join(f'{k} {v:.0f} %' for k, v in ind[m].items())
    prop = ''.join(f'<li>{html.escape(t)}</li>' for t in propuestas(ind))
    err = ''
    if eventos:
        import errores
        manos_es = {'R': 'derecha', 'L': 'izquierda', 'RL': 'ambas', 'LR': 'ambas'}
        filas_err = ''.join(f'<tr><td>{html.escape(errores.TITULO.get(e["tipo"], e["tipo"]))}</td><td>{manos_es.get(e["mano"], e["mano"])}</td>'
                            f'<td>{html.escape(e["detalle"]) if e.get("resumen") else mmss(e["t0"]) + "–" + mmss(e["t1"])}</td>'
                            f'<td>{html.escape(errores.CORRECCION.get(e["tipo"], ""))}</td></tr>'
                            for e in errores.para_informe(eventos))
        err = (f'<h2>Posibles errores de método (señales para revisar)</h2><table><tr><th>Error</th><th>Mano</th>'
               f'<th>Cuándo</th><th>Corrección propuesta</th></tr>{filas_err}</table>')
    ruta = Path(ruta)
    ruta.write_text(f'''<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Revisión del diagrama bimanual</title><style>
:root{{--f:#fff;--t:#1d2433;--b:#d9dee8;--a:#1f5fbf}}
@media (prefers-color-scheme:dark){{:root{{--f:#14171d;--t:#e6e9ef;--b:#2c3340;--a:#7fb0ff}}}}
body{{margin:0;padding:16px;font:15px/1.45 system-ui,sans-serif;background:var(--f);color:var(--t)}}
.g{{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:12px}}
.t{{border:1px solid var(--b);border-radius:10px;overflow:hidden}} .t img{{width:100%;display:block}}
.d{{padding:8px 10px}} .c{{font-weight:700;color:var(--a)}} small{{opacity:.8}}
table{{border-collapse:collapse;width:100%;margin-bottom:16px}} td,th{{border:1px solid var(--b);padding:6px 8px;text-align:left;vertical-align:top}}
</style></head><body><h1>Diagrama bimanual: revisión</h1>
<p>{html.escape(meta.get("producto", ""))}<br>{ind["filas"]} filas · {ind["duracion_s"]} s · MD: {pct("MD")} · MI: {pct("MI")}</p>
<h2>Propuestas</h2><ul>{prop}</ul>{err}<h2>Filas</h2><div class="g">{"".join(tarjetas)}</div></body></html>''', encoding='utf-8')


if __name__ == '__main__':
    import sys
    pred = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    filas = unir_filas(pred)
    ind = indicadores(filas)
    print(json.dumps(ind, ensure_ascii=False))
    print(propuestas(ind))
