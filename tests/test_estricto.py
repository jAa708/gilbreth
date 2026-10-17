"""Strict mode (GILBRETH_SCHEMA=codigos + GILBRETH_JSON_MODE=schema, or GILBRETH_ESTRICTO=1), used for the MI300X
measurements: only the whole JSON object of the schema counts; anything else is a failed answer (kept and counted, never
rescued with the regex), and a server that rejects response_format stops the run instead of silently dropping the
schema. Without those switches nothing changes. No network: urllib.request.urlopen is replaced by a fake server.

Run: python -m unittest tests/test_estricto.py   (or python -m unittest discover -s tests)
"""
import contextlib, io, json, sys, unittest, urllib.error
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_esquema_codigos import AGENTE, CORTAS, cargar, correr_ventanas, ns, paquete  # noqa: E402

BIEN = {'code_right': 'OP', 'code_left': 'S'}


class Fijo:
    """Fake server that answers every request with the same text and finish_reason (or raises an HTTP error)."""

    def __init__(self, texto='', fin='stop', http=None):
        self.texto, self.fin, self.http, self.cuerpos = texto, fin, http, []

    def __call__(self, req, timeout=None):
        cuerpo = json.loads(req.data)
        self.cuerpos.append(cuerpo)
        if self.http and (self.http[1] is None or self.http[1] in cuerpo):
            raise urllib.error.HTTPError(req.full_url, self.http[0], 'Bad Request', {}, io.BytesIO(self.http[2].encode()))
        eleccion = {'message': {'content': self.texto}}
        if self.fin is not None:
            eleccion['finish_reason'] = self.fin
        resp = json.dumps({'choices': [eleccion]}).encode()
        return mock.Mock(read=lambda: resp)


def llamar(ag, srv, esquema=None):
    contenido = [{'type': 'text', 'text': 'x'}]
    with mock.patch('urllib.request.urlopen', srv), mock.patch('time.sleep'):
        return ag.llamar(ns('.'), contenido, esquema or ag.ESQUEMA_CODIGOS, 'paso', 1100)


class Activacion(unittest.TestCase):
    def test_solo_con_codigos_y_schema_o_la_variable(self):
        self.assertFalse(cargar(AGENTE).ESTRICTO)                                    # default: complete schema
        self.assertFalse(cargar(AGENTE, GILBRETH_JSON_MODE='object').ESTRICTO)      # the app on Token Factory
        self.assertFalse(cargar(AGENTE, GILBRETH_SCHEMA='codigos', GILBRETH_JSON_MODE='object').ESTRICTO)
        self.assertTrue(cargar(AGENTE, GILBRETH_SCHEMA='codigos').ESTRICTO)          # schema is the default mode
        self.assertTrue(cargar(AGENTE, GILBRETH_SCHEMA='codigos', GILBRETH_JSON_MODE='schema').ESTRICTO)
        self.assertTrue(cargar(AGENTE, GILBRETH_ESTRICTO='1').ESTRICTO)
        self.assertTrue(cargar(AGENTE, GILBRETH_ESTRICTO='1', GILBRETH_JSON_MODE='object').ESTRICTO)


class Validacion(unittest.TestCase):
    """Each answer is judged as a whole; one request per call (a failed answer is not retried inside llamar)."""

    @classmethod
    def setUpClass(cls):
        cls.ag = cargar(AGENTE, GILBRETH_SCHEMA='codigos', GILBRETH_JSON_MODE='schema')

    def test_respuesta_buena(self):
        for texto in (json.dumps(BIEN), ' \n' + json.dumps(BIEN) + '\n'):
            srv = Fijo(texto)
            self.assertEqual(llamar(self.ag, srv), BIEN)
            self.assertEqual(len(srv.cuerpos), 1)

    def test_respuestas_malas_quedan_fallidas(self):
        casos = {
            'texto antes del JSON': (('Sure: ' + json.dumps(BIEN)), 'stop'),
            'cortada por max_tokens': (json.dumps(BIEN), 'length'),
            'sin finish_reason': (json.dumps(BIEN), None),
            'clave de más': (json.dumps({**BIEN, 'observations': 'x'}), 'stop'),
            'clave de menos': (json.dumps({'code_right': 'OP'}), 'stop'),
            'código en minúsculas': (json.dumps({'code_right': 'op', 'code_left': 'S'}), 'stop'),
            'código envuelto': (json.dumps({'code_right': {'type': 'OP'}, 'code_left': 'S'}), 'stop'),
            'código inventado': (json.dumps({'code_right': 'XX', 'code_left': 'S'}), 'stop'),
            'lista': ('[1, 2]', 'stop'),
            'vacía': ('', 'stop'),
            'dos objetos': (json.dumps(BIEN) + json.dumps(BIEN), 'stop'),
        }
        for nombre, (texto, fin) in casos.items():
            with self.subTest(nombre):
                srv = Fijo(texto, fin)
                j = llamar(self.ag, srv)
                self.assertTrue(j.get('_invalida'), j)
                self.assertTrue(j['_error'].startswith('respuesta inválida (modo estricto)'), j)
                self.assertTrue(self.ag._fallida(j))
                self.assertEqual(self.ag.codigos(j, ns('.')), ('D', 'D'))
                self.assertEqual(len(srv.cuerpos), 1)

    def test_sin_modo_estricto_se_rescata_como_antes(self):
        obj = cargar(AGENTE, GILBRETH_SCHEMA='codigos', GILBRETH_JSON_MODE='object')
        self.assertEqual(llamar(obj, Fijo('Sure: ' + json.dumps(BIEN), None)), BIEN)

    def test_esquema_completo_con_la_variable(self):
        ag = cargar(AGENTE, GILBRETH_ESTRICTO='1')
        mano = {'where_first': 'work_point', 'where_last': 'work_point', 'grips': 'tool', 'motion': 'fine_work',
                'works_on_workpiece': True, 'only_holds': False}
        completa = {'observations': 'x', 'right_hand': mano, 'left_hand': mano, 'documents_in_use': False, **BIEN}
        self.assertEqual(llamar(ag, Fijo(json.dumps(completa)), ag.ESQUEMA_PASO), completa)
        sin_mano = {k: v for k, v in completa.items() if k != 'left_hand'}
        self.assertTrue(llamar(ag, Fijo(json.dumps(sin_mano)), ag.ESQUEMA_PASO).get('_invalida'))

    def test_ficha(self):
        ag = cargar(AGENTE, GILBRETH_ESTRICTO='1')
        ficha = {k: 'x' for k in ag.ESQUEMA_FICHA['required']}
        pq = paquete()
        (pq / 'escena').mkdir()
        (pq / 'escena' / '0.jpg').write_bytes(b'\xff\xd8escena')
        for texto, esperado in ((json.dumps(ficha), ag.ficha_a_texto(ficha)), ('Sure: ' + json.dumps(ficha), '- (card failed)')):
            a = ns(pq, escena=str(pq / 'escena'), salida=str(pq / 'ficha.json'))
            with mock.patch('urllib.request.urlopen', Fijo(texto)), contextlib.redirect_stdout(io.StringIO()):
                ag.cmd_ficha(a)
            self.assertEqual(json.loads((pq / 'ficha.json').read_text(encoding='utf-8'))['texto'], esperado)


class Rechazo(unittest.TestCase):
    """HTTP 400 about response_format: strict mode stops; otherwise the old fallback (drop the schema) stays."""

    ERROR = (400, 'response_format', '{"error": "response_format json_schema is not supported"}')

    def test_estricto_para_la_corrida(self):
        ag = cargar(AGENTE, GILBRETH_SCHEMA='codigos', GILBRETH_JSON_MODE='schema')
        srv = Fijo(json.dumps(BIEN), http=self.ERROR)
        with self.assertRaises(RuntimeError) as e:
            llamar(ag, srv)
        self.assertIn('vLLM rechazó json_schema', str(e.exception))
        self.assertEqual(len(srv.cuerpos), 1)
        #  the whole window pipeline stops too (no request is ever sent without the schema)
        srv = Fijo(json.dumps(BIEN), http=self.ERROR)
        with mock.patch('urllib.request.urlopen', srv), mock.patch('time.sleep'), \
                contextlib.redirect_stdout(io.StringIO()), self.assertRaises(RuntimeError):
            ag.cmd_ventanas(ns(paquete()))
        self.assertTrue(srv.cuerpos and all('response_format' in c for c in srv.cuerpos))

    def test_otro_400_no_para(self):
        ag = cargar(AGENTE, GILBRETH_SCHEMA='codigos', GILBRETH_JSON_MODE='schema')
        j = llamar(ag, Fijo(http=(400, None, '{"error": "image too large"}')))
        self.assertTrue(j['_error'].startswith('HTTP 400') and ag._fallida(j))

    def test_sin_estricto_sigue_como_antes(self):
        ag = cargar(AGENTE)                                   # complete schema + json_schema (system B as delivered)
        self.assertFalse(ag.ESTRICTO)
        srv = Fijo('Sure: ' + json.dumps(BIEN), None, http=self.ERROR)
        self.assertEqual(llamar(ag, srv, ag.ESQUEMA_PASO), BIEN)
        self.assertEqual(['response_format' in c for c in srv.cuerpos], [True, False])


class Ventanas(unittest.TestCase):
    def test_fallidas_registradas_y_contadas(self):
        """Failed answers stay in the raw answer (marked _invalida), are asked once more (2nd pass) and copy the
        nearest valid second for the chart, exactly like a dropped answer."""
        ag = cargar(AGENTE, GILBRETH_SCHEMA='codigos', GILBRETH_JSON_MODE='schema')
        pred, cuerpos = correr_ventanas(ag, CORTAS, limpio=True)
        fallidas = sorted(o['k'] for o in pred if ag._fallida(o['crudo']))
        self.assertEqual(fallidas, [3, 5, 6])                 # wrapped code, invalid code, empty answer
        self.assertTrue(all(o.get('relleno') for o in pred if o['k'] in fallidas))
        self.assertTrue(all(o['crudo']['_invalida'] for o in pred if o['k'] in fallidas))
        self.assertEqual(len(cuerpos), len(CORTAS) + len(fallidas))


if __name__ == '__main__':
    unittest.main()
