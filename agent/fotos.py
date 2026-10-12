"""Fotogramas marcados R/L (desde la pista de manos, no desde una detección suelta) y recortes de cada mano.
Lee el video una sola vez, en orden (rápido incluso en 4K)."""
from pathlib import Path
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from manos import cercano

COLOR = {'R': (224, 32, 192), 'L': (0, 220, 255)}
def _fuente(tam=30):
    # 🪤 en Linux (Colab, la MI300X) no hay Segoe: sin esto la letra R/L salía con la fuente por defecto de 10 px
    for ruta in (r'C:\Windows\Fonts\segoeuib.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
                 '/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf', '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf'):
        try:
            return ImageFont.truetype(ruta, tam)
        except OSError:
            pass
    try:
        return ImageFont.load_default(size=tam)
    except TypeError:
        return ImageFont.load_default()


FUENTE = _fuente()


def leer_tiempos(video, tiempos):
    """{t: imagen PIL a resolución original} para cada tiempo pedido (segundos)."""
    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS)
    pedidos = {}
    for t in tiempos:
        pedidos.setdefault(int(round(t * fps)), []).append(t)
    out, f, ultimo = {}, 0, max(pedidos) if pedidos else -1
    while f <= ultimo:
        if f in pedidos:
            ok, fr = cap.read()
            if not ok:
                break
            im = Image.fromarray(cv2.cvtColor(fr, cv2.COLOR_BGR2RGB))
            for t in pedidos[f]:
                out[t] = im
        else:
            if not cap.grab():
                break
        f += 1
    cap.release()
    return out


def escala_pista(im):
    """Los puntos de la pista están en el espacio de 720 px de alto (o el original si era menor)."""
    return im.height / 720 if im.height > 720 else 1.0


def marcar(im, manos, ancho=768):
    s = escala_pista(im)
    alto = round(im.height * ancho / im.width)
    peq = im.resize((ancho, alto), Image.LANCZOS)
    f = ancho / im.width
    dib = ImageDraw.Draw(peq)
    for lado in ('R', 'L'):
        p = manos.get(lado)
        if p is None:
            continue
        xs, ys = p[:, 0] * s * f, p[:, 1] * s * f
        caja = (xs.min() - 12, ys.min() - 12, xs.max() + 12, ys.max() + 12)
        dib.rectangle(caja, outline=COLOR[lado], width=4)
        dib.text((caja[0] + 4, caja[1] - 36), lado, font=FUENTE, fill=COLOR[lado])
    return peq


def recorte(im, p, lado, tam=448):
    s = escala_pista(im)
    xs, ys = p[:, 0] * s, p[:, 1] * s
    cx, cy = (xs.min() + xs.max()) / 2, (ys.min() + ys.max()) / 2
    l = max(xs.max() - xs.min(), ys.max() - ys.min()) * 1.9 + 40 * s
    caja = (max(0, cx - l / 2), max(0, cy - l / 2), min(im.width, cx + l / 2), min(im.height, cy + l / 2))
    rec = im.crop(caja).resize((tam, tam), Image.LANCZOS)
    ImageDraw.Draw(rec).text((8, 4), lado, font=FUENTE, fill=COLOR[lado])
    return rec


def paquete_ventanas(video, pi, ventanas, carpeta, calidad=62):
    """ventanas: [{'k', 't0', 't1'}]. Guarda k_f0..f3 (marcados) y k_crop_R/L (del 2.º fotograma)."""
    carpeta = Path(carpeta)
    (carpeta / 'img').mkdir(parents=True, exist_ok=True)
    tiempos = {}
    for v in ventanas:
        v['fotos'] = [round((v['t1'] - v['t0']) * (i + 0.5) / 4, 2) for i in range(4)]
        for i, dt in enumerate(v['fotos']):
            tiempos[(v['k'], i)] = round(v['t0'] + dt, 3)
    ims = leer_tiempos(video, sorted(set(tiempos.values())))
    for (k, i), t in tiempos.items():
        if t not in ims:
            continue
        manos = cercano(pi, t)
        marcar(ims[t], manos).save(carpeta / 'img' / f'{k:04d}_f{i}.jpg', quality=calidad)
        if i == 1:
            for lado in ('R', 'L'):
                if manos.get(lado) is not None:
                    recorte(ims[t], manos[lado], lado).save(carpeta / 'img' / f'{k:04d}_crop_{lado}.jpg', quality=calidad + 8)
    return ventanas


def fotos_escena(video, pi, carpeta, n=6, duracion=None, calidad=70):
    """n fotogramas repartidos en el video (marcados) para que el modelo escriba la ficha de la operación."""
    cap = cv2.VideoCapture(str(video))
    dur = duracion or cap.get(cv2.CAP_PROP_FRAME_COUNT) / cap.get(cv2.CAP_PROP_FPS)
    cap.release()
    ts = [round(dur * (i + 0.5) / n, 2) for i in range(n)]
    ims = leer_tiempos(video, ts)
    carpeta = Path(carpeta)
    (carpeta / 'escena').mkdir(parents=True, exist_ok=True)
    for i, t in enumerate(ts):
        marcar(ims[t], cercano(pi, t)).save(carpeta / 'escena' / f'escena_{i}.jpg', quality=calidad)
    return ts
