# Pre-registro — KIT Bimanual SUJETO 1 (11-oct-2026 ~16:00 Cali, mientras baja; nada del sujeto 1 se ha visto)

- Datos: `bimacs_rgbd_data_subject_1.zip` (14,8 GB, https://bimanual-actions.humanoids.kit.edu), las 9 tareas
  (cocina task_1..task_5 y taller task_6..task_9), 10 tomas cada una. Etiquetas por mano: GT CC0 ya local.
  Otra persona distinta del sujeto 2 (en el que se diseñó la compuerta).
- Proceso idéntico al sujeto 2: PNG del zip → mp4 (`datos/kit.py mp4zip`), MediaPipe 10 fps, paquetes de ventanas de
  1 s, Gemma v5 congelada (ficha automática por toma, convención del curso, 280 tokens) en Colab.
- **Revisado = tomas 0 y 1 de cada tarea** (≈ 30 s, la regla «≥ 30 s»). **Prueba = tomas 2 a 9.**
- Verdad: la misma regla fija de `PREREGISTRO_KIT_11OCT.md` (`kit.verdad(..., sujeto=1)`); se excluyen los NULL por mano.
- Sistemas (congelados): v5 Gemma sola · v7 apilado calibrado con las tomas 0-1 · **v9 = v7 + compuerta**
  (`ELECCION_PREVIA_V9.md`) · movimiento solo (referencia). Movimiento de IMPACT: los 9 operarios de
  `modelos/movimiento_impact_XY.npz`.
- Métrica: acierto por mano y segundo en las tomas 2-9; línea base = mejor código constante por mano; también ±1 s.
- Criterio de éxito: v9 ≥ v5 en taller y en cocina por separado, y v9 > v5 en el total. Se mira UNA vez y se
  reporta tal cual, gane o pierda.
- Después de convertir a mp4 se borra el zip (Juan pidió liberar espacio).
