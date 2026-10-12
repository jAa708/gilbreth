"""Guarda los 21 puntos de cada mano (MediaPipe) a 10 fps para un video: npz con t, mano (R/L), puntos (21x3).
Uso: python extraer_puntos.py VIDEO.mp4 SALIDA.npz   (el modelo de manos se baja solo la primera vez)"""
import os, sys, urllib.request
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks.python import BaseOptions
from mediapipe.tasks.python.vision import HandLandmarker, HandLandmarkerOptions, RunningMode

URL = ('https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/'
       'hand_landmarker.task')
MODELO = Path(os.environ.get('MEDIAPIPE_MODELO', Path(__file__).resolve().parent.parent / 'models' / 'hand_landmarker.task'))


def modelo():
    if not MODELO.exists():
        MODELO.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(URL, MODELO)
    return str(MODELO)


def extraer(video, salida, progreso=None):
    """progreso(fraccion) se llama cada ~2 % del video (para la app)."""
    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
    paso = max(1, round(fps / 10))
    W, H = cap.get(3), cap.get(4)
    escala = 720 / H if H > 720 else 1.0
    opts = HandLandmarkerOptions(base_options=BaseOptions(model_asset_path=modelo()), running_mode=RunningMode.VIDEO,
                                 num_hands=2, min_hand_detection_confidence=0.4, min_tracking_confidence=0.4)
    ts, manos, puntos = [], [], []
    with HandLandmarker.create_from_options(opts) as det:
        f = 0
        while True:
            ok, fr = cap.read()
            if not ok:
                break
            if f % paso == 0:
                if escala != 1.0:
                    fr = cv2.resize(fr, (round(W * escala), 720))
                h, w = fr.shape[:2]
                r = det.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB,
                                                  data=cv2.cvtColor(fr, cv2.COLOR_BGR2RGB)), int(f / fps * 1000))
                for k, lm in enumerate(r.hand_landmarks):
                    ts.append(f / fps)
                    manos.append('R' if r.handedness[k][0].category_name == 'Right' else 'L')
                    puntos.append([[p.x * w, p.y * h, p.z * w] for p in lm])
                if progreso and f % max(1, total // 50) < paso:
                    progreso(min(1.0, f / total))
            f += 1
    np.savez_compressed(salida, t=np.array(ts), mano=np.array(manos), puntos=np.array(puntos, dtype=np.float32),
                        fps=fps, n_fotogramas=f)
    return f, len(ts)


if __name__ == '__main__':
    video, salida = sys.argv[1], sys.argv[2]
    f, n = extraer(video, salida)
    print(Path(video).name, f, 'fotogramas,', n, 'detecciones ->', salida)
