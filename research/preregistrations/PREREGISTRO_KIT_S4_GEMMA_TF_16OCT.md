# Pre-registro: el producto CON Gemma 4 en AMD Token Factory, KIT Bimanual sujeto 4 — 16-oct, 22:35

## Por qué
Gemma-4-31B-IT salió del catálogo de AMD Token Factory el 15-oct hacia las 10:39 y volvió: a las 22:30 del 16-oct
responde a texto e imagen (2 peticiones de prueba con el LEGO, no con el sujeto 4). Gemma es el modelo del producto.
El sujeto 3 dio la prueba limpia de Gemma en AMD (Gemma sola 55,4 % → Gilbreth 65,1 %); el sujeto 4 es la segunda
persona nueva. Al escribir esto ningún sistema del sujeto 4 se ha mirado: del respaldo Qwen hay 76 de 90 tomas de
códigos sin evaluar (su prueba, `prueba_s4_respaldo.py`, no se ha corrido) y de Gemma no hay nada.

## Sistema congelado
- El mismo de la prueba del sujeto 3 (`PREREGISTRO_KIT_S3_AMD_15OCT.md`, `prueba_s3_amd.py`): `banco_modelos.py
  Gemma-4-31B-IT --producto --paquetes paquetes_kit_s4 --carpeta s4_gemma_tf --tomas 0 1 2 3 4 5 6 7 8 9 --hilos 4`,
  JSON object en Token Factory, esquema completo, sin `--sin-razonar` (como en el sujeto 3).
- Agente: commit `ab7188a` del repo. Respecto a `5b3edd6` (el del sujeto 3) solo añade el modo estricto, que con estos
  ajustes no se activa; las pruebas del repo comprueban que el comportamiento es byte a byte el de `5b3edd6`.
- v9 = calibrado con el previo de IMPACT + compuerta G0. Tomas 0-1 revisadas (etiquetas del dataset), 2-9 medidas.
- Evaluación: `prueba_s4_gemma_tf.py`, copia literal de `prueba_s4_respaldo.py` (el mismo cálculo que `prueba_s3_amd.py`)
  cambiando solo la carpeta de códigos y el fichero de salida. Se corre UNA vez, cuando estén las 90 tomas.

## Se reporta (una sola mirada)
Modelo solo (v5), v7 y v9 en taller, cocina y total; ±1 s; línea base; ventanas caídas (rellenadas con el vecino) y
cuántas tomas necesitaron repetirse.

## Criterio (el de siempre)
v9 ≥ v5 en taller y en cocina, y v9 > v5 en el total.

## Orden con las demás pruebas del sujeto 4
- El respaldo Qwen (A) queda en pausa con 76/90 y se completa después; su prueba sigue siendo la suya y se mira una vez.
- Si se enciende la MI300X, B (Gemma en BF16 servida por nosotros), B-corto y C siguen como en
  `gilbreth_mi300x/PREREGISTRO_MI300X_16OCT.md`. Esta prueba no cambia nada de ese pre-registro.
- Cupo: Token Factory corta en US$1 al día (se repone a las 11:00 de Cali). Si se acaba a mitad, la corrida se reanuda
  tras la reposición con el mismo comando; nada se evalúa hasta tener las 90 tomas.
