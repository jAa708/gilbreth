"""Paquete de ventanas de 1 s para un video: fotogramas marcados R/L + recortes + sensores + fotos de escena.
Uso: python preparar_paquete.py <video> <puntos.npz> <salida> [--desde 0 --hasta 1e9 --ventana 1.0]"""
import argparse, json, math
from pathlib import Path
import cv2

from manos import cargar, pista, sensores
from fotos import paquete_ventanas, fotos_escena

ap = argparse.ArgumentParser()
ap.add_argument('video'), ap.add_argument('npz'), ap.add_argument('salida')
ap.add_argument('--desde', type=float, default=0), ap.add_argument('--hasta', type=float, default=1e9)
ap.add_argument('--ventana', type=float, default=1.0)
a = ap.parse_args()

cap = cv2.VideoCapture(a.video)
dur = cap.get(cv2.CAP_PROP_FRAME_COUNT) / cap.get(cv2.CAP_PROP_FPS)
cap.release()
pi = pista(*cargar(a.npz))
fin = min(a.hasta, dur)
ventanas = []
k, t = 0, a.desde
while t + 0.5 * a.ventana <= fin:
    t1 = min(t + a.ventana, fin)
    ventanas.append({'k': k, 't0': round(t, 3), 't1': round(t1, 3), 'sensores': sensores(pi, t, t1)})
    k, t = k + 1, t + a.ventana
salida = Path(a.salida)
paquete_ventanas(a.video, pi, ventanas, salida)
fotos_escena(a.video, pi, salida, n=6, duracion=dur)
(salida / 'ventanas.json').write_text(json.dumps(ventanas, ensure_ascii=False), encoding='utf-8')
print(f'{len(ventanas)} ventanas de {a.ventana} s ({a.desde}-{fin:.1f} s) -> {salida}')
