"""Dónde están los datos del v10 (variables de entorno; nada de esto va en el repositorio).
- GILBRETH_KIT_VIDEOS: carpeta con s1 ... s6, cada una con mp4/meta.json y puntos/<toma>.npz (los prepara
  agent/extraer_puntos.py sobre los videos de KIT Bimanual Actions, que se bajan de KIT con su licencia).
  GILBRETH_KIT_S{N} cambia la carpeta de un sujeto.
- GILBRETH_KIT_GT: el zip de la verdad de KIT (bimacs_rgbd_data_ground_truth.zip).
- GILBRETH_GEMMA_CODES: carpeta con s1 ... s6, cada una con <toma>/pred.json (la salida de banco/agente: ventanas con
  t0, md, mi y la respuesta cruda de Gemma) o vision_<toma>.txt (formato compacto «s:md/mi»), y opcionalmente
  cruces.json ({toma: {segundo: fracción}}) si las marcas R/L de esa corrida estaban cruzadas. GILBRETH_GEMMA_S{N}
  cambia la carpeta de un sujeto.
- GILBRETH_V10_OUT: dónde escribir las filas y los resultados."""
import os
from pathlib import Path

KIT_VIDEOS = Path(os.environ.get('GILBRETH_KIT_VIDEOS', 'data/kit_videos'))
KIT_GT = Path(os.environ.get('GILBRETH_KIT_GT', 'data/kit/bimacs_rgbd_data_ground_truth.zip'))
GEMMA = Path(os.environ.get('GILBRETH_GEMMA_CODES', 'data/gemma_codes'))
SALIDA = Path(os.environ.get('GILBRETH_V10_OUT', 'runs/station_v10'))


def sujeto(n):
    return Path(os.environ.get(f'GILBRETH_KIT_S{n}', KIT_VIDEOS / f's{n}'))


def gemma(n):
    return Path(os.environ.get(f'GILBRETH_GEMMA_S{n}', GEMMA / f's{n}'))
