"""GILBRETH_SCHEMA: 'completo' (default) must send exactly what the agent sent before, and 'codigos' must ask for the
two codes only with the same text and images. No network: urllib.request.urlopen is replaced by a fake server.

Run: python -m unittest tests/test_esquema_codigos.py   (or python tests/test_esquema_codigos.py)
The byte-for-byte comparison loads the agent as it was at commit REFERENCIA (last change before the switch) with git;
without git or that commit those cases are skipped.
"""
import argparse, base64, contextlib, importlib.util, io, json, os, subprocess, tempfile, unittest
from pathlib import Path
from unittest import mock

RAIZ = Path(__file__).resolve().parents[1]
AGENTE = RAIZ / 'agent' / 'agente_v5.py'
REFERENCIA = '5b3edd6'          # agent logic frozen by the 16-Oct pre-registration (system B)
_n = 0


def cargar(ruta, **entorno):
    """Imports a copy of the agent with the given environment (the switches are read at import time)."""
    global _n
    _n += 1
    viejo = {k: os.environ.get(k) for k in ('GILBRETH_SCHEMA', 'GILBRETH_JSON_MODE', 'GILBRETH_RPM',
                                            'GILBRETH_LATENCIAS', 'GILBRETH_API_KEY')}
    try:
        for k in viejo:
            os.environ.pop(k, None)
        os.environ.update(entorno)
        spec = importlib.util.spec_from_file_location(f'agente_prueba_{_n}', ruta)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    finally:
        for k, v in viejo.items():
            os.environ.pop(k, None)
            if v is not None:
                os.environ[k] = v


def referencia():
    try:
        txt = subprocess.run(['git', '-C', str(RAIZ), 'show', f'{REFERENCIA}:agent/agente_v5.py'], capture_output=True,
                             check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return None
    d = Path(tempfile.mkdtemp(prefix='agente_ref_'))
    (d / 'agente_ref.py').write_bytes(txt)
    return d / 'agente_ref.py'


SENS = lambda vr, vl, vis: {'mano_derecha': {'velocidad_mediana': vr, 'velocidad_max': 1.4, 'visible_pct': vis},
                            'mano_izquierda': {'velocidad_mediana': vl, 'velocidad_max': 0.9, 'visible_pct': 80},
                            'distancia_entre_manos': 1.2}
#  One canned answer per window (k): complete answers, wrapped codes, an invalid code, documents in use, NV with a
#  visible hand and an empty answer (dropped -> copies the neighbour).
COMPLETAS = {
    0: {'observations': 'x', 'documents_in_use': False, 'code_right': 'OP', 'code_left': 'S'},
    1: {'observations': 'x', 'documents_in_use': False, 'code_right': 'TR', 'code_left': 'S'},
    2: {'observations': 'x', 'documents_in_use': True, 'code_right': 'OP', 'code_left': 'TR'},
    3: {'observations': 'x', 'documents_in_use': False, 'code_right': {'type': 'TR+OP'}, 'code_left': 'D'},
    4: {'observations': 'x', 'documents_in_use': False, 'code_right': 'NV', 'code_left': 'OP'},
    5: {'observations': 'x', 'documents_in_use': False, 'code_right': 'XX', 'code_left': 'OP'},
    6: None,
}
CORTAS = {k: (None if v is None else {'code_right': v['code_right'], 'code_left': v['code_left']})
          for k, v in COMPLETAS.items()}


def paquete():
    pq = Path(tempfile.mkdtemp(prefix='paquete_prueba_'))
    (pq / 'img').mkdir()
    vent = []
    for k in COMPLETAS:
        for i in range(4):
            (pq / 'img' / f'{k:04d}_f{i}.jpg').write_bytes(b'\xff\xd8' + f'k={k};f={i}'.encode())
        for m in 'RL':
            (pq / 'img' / f'{k:04d}_crop_{m}.jpg').write_bytes(b'\xff\xd8' + f'k={k};crop={m}'.encode())
        vent.append({'k': k, 't0': float(k), 't1': float(k + 1), 'fotos': [0.125, 0.375, 0.625, 0.875],
                     'sensores': SENS(0.3 + 0.1 * k, 1.0, 90 if k == 4 else 70)})
    (pq / 'ventanas.json').write_text(json.dumps(vent), encoding='utf-8')
    return pq


class Servidor:
    """Fake OpenAI-compatible server: records every request body and answers by the window shown in image 1."""

    def __init__(self, respuestas):
        self.respuestas, self.cuerpos = respuestas, []

    def __call__(self, req, timeout=None):
        cuerpo = json.loads(req.data)
        self.cuerpos.append({'url': req.full_url, 'cabeceras': dict(req.headers), 'cuerpo': cuerpo})
        img = next(c for c in cuerpo['messages'][0]['content'] if c.get('type') == 'image_url')
        k = int(base64.b64decode(img['image_url']['url'].split(',', 1)[1])[2:].decode().split(';')[0][2:])
        r = self.respuestas[k]
        texto = '' if r is None else 'Sure: ' + json.dumps(r)
        cuerpo_resp = json.dumps({'choices': [{'message': {'content': texto}}]}).encode()
        return mock.Mock(read=lambda: cuerpo_resp)


def ns(pq, **kw):
    base = dict(base='http://127.0.0.1:8000', modelo='m', convencion='curso', hilos=3, sin_sensores=False,
                sin_recortes=False, ollama=False, paquete=str(pq), desde=0, hasta=1e9, etiqueta='x', ficha=None)
    base.update(kw)
    return argparse.Namespace(**base)


def correr_ventanas(mod, respuestas, **kw):
    pq = paquete()
    srv = Servidor(respuestas)
    with mock.patch('urllib.request.urlopen', srv), mock.patch('time.sleep'), contextlib.redirect_stdout(io.StringIO()):
        mod.cmd_ventanas(ns(pq, **kw))
    pred = json.loads((pq / 'pred_v5_vent_x.json').read_text(encoding='utf-8'))
    orden = lambda c: json.dumps(c, sort_keys=True)
    return pred, sorted(srv.cuerpos, key=orden)


class Completo(unittest.TestCase):
    """GILBRETH_SCHEMA unset or 'completo' = the agent at REFERENCIA, byte for byte."""

    @classmethod
    def setUpClass(cls):
        cls.ref = referencia()

    def comparar(self, entorno, **kw):
        if self.ref is None:
            self.skipTest(f'git or commit {REFERENCIA} not available')
        viejo = cargar(self.ref, **entorno)
        for env_nuevo in (entorno, {**entorno, 'GILBRETH_SCHEMA': 'completo'}):
            nuevo = cargar(AGENTE, **env_nuevo)
            p0, c0 = correr_ventanas(viejo, COMPLETAS, **kw)
            p1, c1 = correr_ventanas(nuevo, COMPLETAS, **kw)
            self.assertEqual(c0, c1)                 # same URL, headers and JSON body for every request
            self.assertEqual(p0, p1)                 # same codes, fills and raw answers
            self.assertEqual(len(c1), len(COMPLETAS) + 2)   # the invalid and the empty answers are asked twice

    def test_schema(self):
        self.comparar({})

    def test_object(self):
        self.comparar({'GILBRETH_JSON_MODE': 'object'})

    def test_v6(self):
        self.comparar({}, v6=True)

    def test_oit(self):
        self.comparar({}, convencion='oit')

    def test_esquema_por_defecto(self):
        nuevo = cargar(AGENTE)
        self.assertEqual(nuevo.MODO_ESQUEMA, 'completo')
        self.assertIs(nuevo.esquema_paso(ns('.')), nuevo.ESQUEMA_PASO)
        self.assertIs(nuevo.esquema_paso(ns('.', v6=True)), nuevo.ESQUEMA_PASO_V6)


class Codigos(unittest.TestCase):
    """GILBRETH_SCHEMA=codigos: the strict schema asks for the two codes only; text and images do not change."""

    def test_esquema(self):
        ag = cargar(AGENTE, GILBRETH_SCHEMA='codigos')
        self.assertEqual(ag.ESQUEMA_CODIGOS, {
            'type': 'object', 'additionalProperties': False, 'required': ['code_right', 'code_left'],
            'properties': {'code_right': {'type': 'string', 'enum': ag.CODIGOS},
                           'code_left': {'type': 'string', 'enum': ag.CODIGOS}}})
        self.assertIs(ag.esquema_paso(ns('.')), ag.ESQUEMA_CODIGOS)
        with self.assertRaises(ValueError):
            ag.esquema_paso(ns('.', v6=True))

    def test_mismo_texto_e_imagenes(self):
        corto = cargar(AGENTE, GILBRETH_SCHEMA='codigos')
        largo = cargar(AGENTE)
        _, c_corto = correr_ventanas(corto, CORTAS)
        _, c_largo = correr_ventanas(largo, COMPLETAS)
        self.assertEqual(len(c_corto), len(c_largo))
        mensajes = lambda cs: sorted(json.dumps(c['cuerpo']['messages'], sort_keys=True) for c in cs)
        self.assertEqual(mensajes(c_corto), mensajes(c_largo))
        for c in c_corto:
            rf = c['cuerpo']['response_format']
            self.assertEqual(rf['type'], 'json_schema')
            self.assertTrue(rf['json_schema']['strict'])
            self.assertEqual(rf['json_schema']['schema'], corto.ESQUEMA_CODIGOS)
            self.assertEqual(c['cuerpo']['max_tokens'], 1100)
            self.assertEqual(c['cuerpo']['temperature'], 0.0)

    def test_object_lleva_el_esquema_corto_en_el_texto(self):
        ag = cargar(AGENTE, GILBRETH_SCHEMA='codigos', GILBRETH_JSON_MODE='object')
        _, cs = correr_ventanas(ag, CORTAS)
        for c in cs:
            self.assertEqual(c['cuerpo']['response_format'], {'type': 'json_object'})
            ultimo = c['cuerpo']['messages'][0]['content'][-1]['text']
            self.assertTrue(ultimo.endswith(json.dumps(ag.ESQUEMA_CODIGOS, separators=(',', ':'))))

    def test_codigos_con_respuesta_corta(self):
        """codigos() and the window pipeline read answers that only carry the two codes."""
        ag = cargar(AGENTE, GILBRETH_SCHEMA='codigos')
        curso, oit = ns('.'), ns('.', convencion='oit')
        self.assertEqual(ag.codigos({'code_right': 'OP', 'code_left': 'S'}, curso), ('OP', 'S'))
        self.assertEqual(ag.codigos({'code_right': 'TR', 'code_left': 'S'}, curso), ('TR', 'D'))   # course rule
        self.assertEqual(ag.codigos({'code_right': 'TR', 'code_left': 'S'}, oit), ('TR', 'S'))
        self.assertEqual(ag.codigos({'code_right': 'tr+op', 'code_left': {'type': 'D'}}, curso), ('TR+OP', 'D'))
        self.assertEqual(ag.codigos({'code_right': 'XX', 'code_left': 'OP'}, curso), ('D', 'D'))
        self.assertEqual(ag.codigos({}, curso), ('D', 'D'))
        self.assertFalse(ag._fallida({'code_right': 'NV', 'code_left': 'OP'}))
        self.assertTrue(ag._fallida({'code_right': 'NV'}))
        pred, _ = correr_ventanas(ag, CORTAS)
        got = {o['k']: (o['md'], o['mi'], bool(o.get('relleno'))) for o in pred}
        self.assertEqual(got, {0: ('OP', 'S', False), 1: ('TR', 'D', False),
                               2: ('OP', 'TR', False),      # no documents_in_use field: the codes stay
                               3: ('TR+OP', 'D', False), 4: ('D', 'OP', False),   # NV with the hand seen 90 % -> D
                               5: ('D', 'OP', True),        # invalid code = dropped: copies the nearest valid (k=4)
                               6: ('D', 'OP', True)})       # empty answer = dropped: copies the nearest valid (k=4)

    def test_valor_invalido(self):
        with self.assertRaises(ValueError):
            cargar(AGENTE, GILBRETH_SCHEMA='corto')


if __name__ == '__main__':
    unittest.main()
