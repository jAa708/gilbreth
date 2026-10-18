# Pre-registro: prueba limpia EN AMD con una persona nueva (KIT Bimanual, sujeto 3) — 15-oct, 00:30, antes de bajar nada

## Por qué
La única prueba limpia del sistema entregado (KIT sujeto 1, 67,5 → 77,1 %) se corrió con Gemma 4 31B QAT de 4 bits en
una A100 de Colab. Lo que se entrega corre en AMD Token Factory (Gemma-4-31B-IT, `json_object`). Esta prueba mide el
producto tal como se entrega, en hardware AMD, sobre una persona que ningún paso del desarrollo ha visto.

## Sistema congelado (commit `5b3edd6` del repo gilbreth, sin tocar nada después de bajar el sujeto 3)
- Gemma-4-31B-IT en AMD Token Factory vía `agent/agente_v5.py` (`GILBRETH_JSON_MODE=object`, 18 peticiones por minuto):
  ficha automática por toma, ventanas de 1 s, convención del curso, regla del NV contra el seguidor, ventanas caídas
  con segunda vuelta y vecino.
- v9 = apilado calibrado con el previo de IMPACT (`models/motion_prior_impact.npz`) + compuerta estricta.

## Datos y verdad
- `bimacs_rgbd_data_subject_3.zip` de https://bimanual-actions.humanoids.kit.edu (imágenes solo para medir; no se
  redistribuyen). Las 9 tareas × 10 tomas. Video, MediaPipe y paquetes con la misma tubería que el sujeto 1
  (`datos/kit_sujeto.py`: pista v2).
- Verdad: `datos/kit.py` versión 2 (la del sujeto 1), misma regla de códigos; null excluido.
- **Revisado = tomas 0 y 1 de cada tarea** (≈ 30 s). **Prueba = tomas 2 a 9.**

## Qué se reporta (una sola mirada, todo lo que salga)
v5 (Gemma AMD sola), v7 y v9 en taller, cocina y total; ±1 s; línea base constante en todo el conjunto; peticiones
caídas y costo.

## Criterio (el mismo del sujeto 1)
v9 ≥ v5 en taller y en cocina por separado, y v9 > v5 en el total. Se publica pase o no pase.

## Si Gemma no vuelve a aceptar imágenes a tiempo
No se cambia de modelo para esta prueba. Queda preparada (paquetes listos) y se corre cuando vuelva.
