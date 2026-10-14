"""Cronometrista automático: video de un puesto de trabajo -> diagrama bimanual (borrador para revisión).

Uso (en la máquina con el video y acceso a un servidor vLLM / compatible OpenAI):
  python bimanual.py VIDEO.mp4 --salida carpeta [--base http://127.0.0.1:8000] [--modelo google/gemma-4-31B-it-qat-w4a16-ct]
         [--desde 0 --hasta 1e9] [--convencion curso|oit] [--ficha mi_ficha.json] [--hilos 8]

Pasos: 1) MediaPipe sigue las dos manos (10 fps) y corrige la lateralidad; 2) ventanas de 1 s con 4 fotogramas
marcados R/L, recortes de cada mano y datos de velocidad; 3) el modelo de visión escribe la FICHA de la operación
mirando 6 fotos del video (el usuario puede darla o corregirla); 4) el modelo codifica cada segundo por mano (OP, TR,
TR+OP, S, D, NV) siguiendo la ficha, el ciclo lógico del trabajo manual y la convención elegida; 5) se unen los
segundos iguales en filas; 6) salen el Excel en formato del curso, la página de revisión y los indicadores."""
import argparse, datetime, json, subprocess, sys
from pathlib import Path

aqui = Path(__file__).resolve().parent
sys.path.insert(0, str(aqui))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('video'), ap.add_argument('--salida', required=True)
    ap.add_argument('--base', default='http://127.0.0.1:8000')
    ap.add_argument('--modelo', default='google/gemma-4-31B-it-qat-w4a16-ct')
    ap.add_argument('--desde', type=float, default=0), ap.add_argument('--hasta', type=float, default=1e9)
    ap.add_argument('--convencion', default='curso', choices=['curso', 'oit'])
    ap.add_argument('--ficha'), ap.add_argument('--hilos', type=int, default=8)
    ap.add_argument('--puntos', help='npz de MediaPipe ya calculado (si no, se calcula)')
    ap.add_argument('--ollama', action='store_true', help='servidor Ollama (apaga el razonamiento)')
    ap.add_argument('--filas', default='oit', choices=['oit', 'elemento'], help='oit: fila por cada cambio; elemento: trae y encaja = TR+OP')
    ap.add_argument('--sin-movimiento', action='store_true', help='solo el modelo de visión (sin el clasificador de manos)')
    ap.add_argument('--calibrar', help='JSON con filas ya revisadas por el usuario (revisar.html o minuto de oro)')
    ap.add_argument('--calibrar-hasta', type=float, default=None, help='usar solo los segundos < N de ese JSON')
    ap.add_argument('--idioma', default='es', choices=['es', 'en'], help='idioma de las descripciones por fila')
    ap.add_argument('--sin-previo', action='store_true', help='no usar el previo de movimiento de IMPACT (CC BY-NC-SA): modo MIT puro')
    ap.add_argument('--sin-descripciones', action='store_true', help='sin la 2.ª pasada de descripciones (más rápido)')
    a = ap.parse_args()
    sal = Path(a.salida)
    sal.mkdir(parents=True, exist_ok=True)

    # 1) manos
    npz = Path(a.puntos) if a.puntos else sal / 'puntos.npz'
    if not npz.exists():
        print('1/5 MediaPipe: siguiendo las manos…', flush=True)
        subprocess.run([sys.executable, str(aqui / 'extraer_puntos.py'), a.video, str(npz)], check=True)
    # 2) paquete de ventanas
    if not (sal / 'ventanas.json').exists():
        print('2/5 Fotogramas, recortes y sensores por segundo…', flush=True)
        subprocess.run([sys.executable, str(aqui / 'preparar_paquete.py'), a.video, str(npz), str(sal),
                        '--desde', str(a.desde), '--hasta', str(a.hasta)], check=True)
    import agente_v5 as ag
    ns = argparse.Namespace(base=a.base, modelo=a.modelo, convencion=a.convencion, hilos=a.hilos, sin_sensores=False,
                            sin_recortes=False, ollama=a.ollama, paquete=str(sal), desde=a.desde, hasta=a.hasta,
                            etiqueta='agente', escena=str(sal / 'escena'), salida=str(sal / 'ficha.json'),
                            ficha=a.ficha or str(sal / 'ficha.json'), idioma=a.idioma)
    # 3) ficha
    if not a.ficha and not (sal / 'ficha.json').exists():
        print('3/5 Ficha de la operación (el modelo mira 6 fotos del video)…', flush=True)
        ag.cmd_ficha(ns)
        if ag.SIN_CUPO.is_set():
            print('STOP: the model endpoint says the daily quota is used up; try again after it resets.', flush=True)
            sys.exit(3)
    # 4) cada segundo
    print('4/5 Codificando cada segundo por mano…', flush=True)
    ag.cmd_ventanas(ns)
    if ag.SIN_CUPO.is_set():
        print('STOP: the model endpoint says the daily quota is used up; try again after it resets.', flush=True)
        sys.exit(3)
    pred = json.loads((sal / 'pred_v5_vent_agente.json').read_text(encoding='utf-8'))
    # 4b) v7 (ELECCION_PREVIA_V7.md): si el usuario ya revisó un tramo (minuto de oro), un clasificador por mano y
    # segundo aprende de ESE tramo (más el movimiento de 9 operarios de IMPACT) cuánto creerle a la visión y cuánto al
    # movimiento de las manos, y recodifica el resto. Sin tramo revisado se queda la visión sola (el movimiento solo
    # no generaliza a otra cámara: medido en el LEGO).
    if a.calibrar and not a.sin_movimiento:
        import numpy as np
        import movimiento as mv, seleccion as se
        from manos import cargar as cargar_npz, pista as hacer_pista
        print('   v7: calibrando con el tramo revisado…', flush=True)
        sg = mv.senales(hacer_pista(*cargar_npz(npz)))
        cal = mv.etiquetas(a.calibrar, a.calibrar_hasta)
        V = {int(round(o['t0'])): (o['md'], o['mi']) for o in pred}
        pv = None if a.sin_previo else mv.previo()
        if pv is None:
            # modo «MIT puro»: solo lo revisado. Medido (ELECCION_PREVIA_SIN_IMPACT): rinde bastante menos
            print('   sin previo de movimiento: se aprende solo de lo revisado (modo MIT puro)', flush=True)
            pv = (np.zeros((0, len(mv.vector(sg, 'R', min(cal))))), np.array([], dtype=str))
        Xi, yi = pv
        import compuerta
        clip = {'sg': sg, 'V': V, 'G': cal, 'segs': [s for s in sorted(cal) if s in V]}
        # v9: compuerta. Solo se recodifica si, en lo revisado, el v7 acierta más que Gemma sin verse a sí mismo
        usar, est = compuerta.decidir(Xi, yi, [clip])
        print(f'   compuerta: en lo revisado Gemma {est["gemma"]}/{est["n"]} · v7 {est["v7"]}/{est["n"]} → '
              f'{"se usa el v7" if usar else "se queda Gemma"}', flush=True)
        P = dict(V)
        if usar:
            mod = compuerta.entrenar_clips(Xi, yi, [clip])
            P = se.aplicar('apilado', mod, sg, V, sorted(V))
        P.update({s: c for s, c in cal.items() if s in P})          # lo que el usuario ya revisó manda
        (sal / 'calibracion.json').write_text(json.dumps({'revisado_hasta_s': max(cal) + 1 if cal else 0,
                                                          'compuerta': 'v7' if usar else 'Gemma', 'estimacion': est,
                                                          'previo': 'ninguno (MIT puro)' if not len(yi) else 'IMPACT'},
                                                         ensure_ascii=False), encoding='utf-8')
        for o in pred:
            s = int(round(o['t0']))
            o['md_vision'], o['mi_vision'] = o['md'], o['mi']
            o['md'], o['mi'] = P[s]
    # 5) salidas
    print('5/5 Diagrama, Excel y página de revisión…', flush=True)
    import salidas
    if a.filas == 'elemento':
        pred = salidas.filas_elemento(pred)
    filas = salidas.unir_filas(pred)
    # 2.ª pasada SEPARADA: descripción en español por mano y fila (meterla en la misma consulta empeoraba los códigos)
    (sal / 'pred_final.json').write_text(json.dumps(pred, ensure_ascii=False), encoding='utf-8')
    ns.pred, ns.etiqueta = str(sal / 'pred_final.json'), 'agente'
    desc = {}
    if not a.sin_descripciones:
        print('   descripciones por fila…', flush=True)
        ag.cmd_describir(ns)
        if ag.SIN_CUPO.is_set():
            print('STOP: the model endpoint says the daily quota is used up; try again after it resets.', flush=True)
            sys.exit(3)
        desc = {(d['t0'], d['t1']): d for d in json.loads((sal / 'filas_desc_agente.json').read_text(encoding='utf-8'))}
    for f in filas:
        d = desc.get((f['t0'], f['t1']), {})
        f['desc_md'] = d.get('desc_md') or salidas.nombre(f['md'], a.idioma)
        f['desc_mi'] = d.get('desc_mi') or salidas.nombre(f['mi'], a.idioma)
        der, izq = ('R', 'L') if a.idioma == 'en' else ('MD', 'MI')
        f['obs'] = [f"{der}: {f['desc_md']} · {izq}: {f['desc_mi']}"]
    ind = salidas.indicadores(filas)
    ficha = json.loads(Path(ns.ficha).read_text(encoding='utf-8'))
    meta = {'producto': ficha.get('product', ''), 'operacion': ficha.get('typical_cycle', ''),
            'lugar': ficha.get('work_areas', ''), 'video': Path(a.video).name,
            'fecha': datetime.date.today().isoformat(),
            'convencion_texto': ag.CONVENCION[a.convencion]}
    (sal / 'diagrama.json').write_text(json.dumps({'meta': meta, 'indicadores': ind, 'filas': filas}, ensure_ascii=False,
                                                  indent=1), encoding='utf-8')
    # errores de método: movimiento de las manos (MediaPipe) + códigos del diagrama
    import errores
    from manos import cargar, pista as hacer_pista, sensores as sens_de
    pi = hacer_pista(*cargar(npz))
    cod_seg = {int(round(o['t0'])): (o['md'], o['mi']) for o in pred}
    eventos = errores.detectar(pi, cod_seg, {s: sens_de(pi, s, s + 1) for s in cod_seg})
    (sal / 'errores.json').write_text(json.dumps(eventos, ensure_ascii=False, indent=1), encoding='utf-8')
    salidas.escribir_excel(filas, ind, meta, sal / 'diagrama_bimanual.xlsx', eventos=eventos, idioma=a.idioma)
    salidas.escribir_html(filas, ind, meta, sal / 'img', sal / 'revision.html', eventos=eventos, idioma=a.idioma)
    (sal / 'diagrama.json').write_text(json.dumps({'meta': {**meta, 'camara': ficha.get('camera_and_operator', '')},
                                                   'indicadores': ind, 'filas': filas}, ensure_ascii=False, indent=1),
                                       encoding='utf-8')
    import os, revision
    revision.pagina(sal / 'diagrama.json', a.video, sal / 'revisar.html',
                    src=os.path.relpath(a.video, sal).replace(os.sep, '/'), idioma=a.idioma)
    print(json.dumps(ind, ensure_ascii=False))
    print('Listo:', sal / 'diagrama_bimanual.xlsx', '·', sal / 'revision.html', '·', sal / 'revisar.html (editar y aprobar)')


if __name__ == '__main__':
    main()
