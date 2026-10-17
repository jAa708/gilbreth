# Pre-registro: v10 «modo estación» en KIT Bimanual sujeto 4 — 17-oct, 00:25 (el sujeto 4 sin mirar)

## Estado al escribir esto
Del sujeto 4 no se ha evaluado NADA: ni Gemma en Token Factory (`banco/s4_gemma_tf`, corriendo, 64/90 tomas), ni el
respaldo Qwen (76/90, pausado), ni el v10. Su verdad solo se ha leído en las tomas 0-1 (las revisadas del protocolo),
y únicamente al construir sus filas; las tomas 2-9 no se han leído.

## El sistema congelado (`v10/final.py`, `v10/sistema.py`, `v10/construir.py`, `v10/cuadros.py`)
- Por mano y segundo, la mezcla 50/50 de (a) un HistGradientBoosting por segundo y (b) uno a 10 Hz entrenado con la
  etiqueta del cuadro y promediado por segundo. Rasgos: movimiento del seguidor de manos (segundo, medios segundos,
  perfil a 10 Hz, vecinos ±2 s, la otra mano), códigos y atributos de Gemma (s-2..s+2 y la otra mano), tarea, y la
  **mano dominante** de esa persona en esa tarea sacada de sus tomas revisadas; sin el rasgo «es la derecha».
- Entrenamiento: todas las tomas de las personas de entrenamiento + las tomas 0-1 del sujeto 4 con peso 5 (CAL = 5,
  PESO_A = 0,5). Hiperparámetros de `sistema.modelo` (sin cambios desde el desarrollo).
- Personas de entrenamiento: KIT sujetos 1, 2 y 3, y **también 5 y 6 si a las 08:00 del 17-oct (enmienda de la 01:05) sus códigos de Gemma
  (`banco/s5_gemma_tf`, `banco/s6_gemma_tf`, tubería del producto en Token Factory) tienen ≥ 85 de 90 tomas**; si no,
  los que cumplan. La regla se aplica mecánicamente (`v10/congelar.py` escribe `congelado_v10.json`).
- Lo que el desarrollo descartó (no entra): auto-contexto, Viterbi, auto-entrenamiento, Extra Trees, red recurrente,
  corrección de priores, más peso a lo revisado.

## Evidencia de desarrollo (s1-s3, ya mirados; dejando una persona fuera; tomas 2-9)
Gemma sola 67,5 / 47,7 / 55,4 · v10 86,0 / 82,2 / 84,7 · **media 84,3 %**. Curva: con 1 persona etiquetada 83,9 %, con
2, 84,3 %. Si llegan s5 y s6, se reporta también la validación dejando uno fuera con las 5 personas (no cambia el
sistema congelado).

## La prueba (una sola mirada: `v10/prueba_s4_v10.py --si`, después de `prueba_s4_gemma_tf.py --si`)
- Se reporta: v10, Gemma sola (v5) y el producto actual (v9, de `prueba_s4_gemma_tf.py`) en taller, cocina y total,
  a 0 s y a ±1 s, sobre las tomas 2-9 con la misma verdad (kit.verdad versión 2, manos-segundo excluidas fuera).
- **Criterio: el v10 entra al producto como «modo estación» (cuando hay al menos una persona etiquetada haciendo la
  misma tarea) si su total supera al del v9 y no queda por debajo del v9 ni en taller ni en cocina.**
- La meta de Juan (> 85 %) se reporta tal cual salga, sin ajustar nada después de mirar.
- Alcance que se dice siempre: el v10 aprende de otras personas haciendo LAS MISMAS tareas en la misma escena. En un
  puesto nuevo, sin nadie etiquetado, el producto es el v9.

## Enmienda 17-oct, 00:50 (antes de mirar nada del sujeto 4)
El modelo (b) a 10 Hz aprende de la etiqueta de cada CUADRO, que KIT trae y la página de revisión de la app no da
(etiqueta por segundo). Por eso se reporta, en la misma y única mirada, una segunda cifra: **«v10-segundos» = solo
el modelo (a) por segundo** (`sistema.ajustar_predecir`, el mismo entrenamiento y las mismas personas; desarrollo
83,8 %), que es lo que funcionaría tal cual en un cliente con las etiquetas de la app. El criterio se aplica a los
dos por separado; el sistema congelado principal sigue siendo la mezcla.

## Enmienda 17-oct, 01:10: auditoría de Codex antes de mirar (`v10/codex/ultimo.md`: 15 hallazgos, ninguna fuga)
- H05: los vecinos del modelo a 10 Hz se buscan por TIEMPO (en s1 los videos van a 15 fps y el seguidor muestrea a
  7,5 Hz). H06: la duración de la toma sale siempre del video. Con eso se rehacen las filas de s1-s4 y el desarrollo;
  la cifra de desarrollo que vale es la nueva (abajo, en «Desarrollo tras la auditoría»).
- Rasgos de posición declarados: `t_rel` (segundo / duración del video) y, a 10 Hz, `pos` (lugar dentro del segundo).
- Evaluación (H07-H12, H15): `prueba_s4_v10.py` puntúa v5, v9, v10 y v10-segundos sobre el MISMO conjunto de
  manos-segundo (verdad válida y con predicción de todos), a 0 s y ±1 s, aplica el criterio a v10 y a v10-segundos,
  exige que `prueba_s4_gemma_tf.py` se haya corrido antes (lee sus predicciones por clave) y deja una marca atómica de
  inicio antes de leer la verdad (no se puede repetir). Línea base: la clase más frecuente de cada mano, como el v9.
- Congelado (H01-H03): `congelar.py` se corre una vez, cuenta solo las 90 tomas canónicas con pred.json válido y sella
  con SHA-256 el código, los datos de cada sujeto, kit.py, la verdad y los códigos de Gemma del sujeto 4.

- Corte para incluir s5 y s6 (01:05, el sujeto 4 sin mirar): pasa de las 06:00 a las **08:00 del 17-oct**, porque
  Gemma del sujeto 6 empieza después del 5 y terminaría hacia las 06:00 (la regla y el umbral de 85 tomas no cambian).

### Desarrollo tras la auditoría (s1-s3, dejando una persona fuera, tomas 2-9; 01:20)
v10 85,9 / 82,2 / 84,6 → **84,2 %** · v10-segundos 85,2 / 82,2 / 84,0 → **83,8 %** · Gemma sola 67,5 / 47,7 / 55,4.

### Desarrollo con las 5 personas de entrenamiento (07:05, antes de congelar y de mirar el sujeto 4)
Gemma terminó s5 (03:22) y s6 (06:51), 90/90 tomas cada uno: entran por la regla. Dejando una persona fuera (4 para
entrenar), tomas 2-9: s1 86,9 · s2 82,2 · s3 85,4 · s5 84,3 · s6 86,4 → **85,0 %** (Gemma sola 67,5 / 47,7 / 55,4 /
47,5 / 49,5). El sujeto 4 se entrena con estas 5 personas.

## RESULTADO (17-oct, 07:10; una sola mirada, `resultado_prueba_s4_v10.json`)
Sujeto 4, tomas 2-9, 1.888 manos-segundo (las mismas para todos los sistemas; cobertura 1888/1888):

| Sistema | Taller | Cocina | Total | Total ±1 s |
|---|---|---|---|---|
| Gemma 4 sola (v5) | 56,1 | 48,5 | 51,5 % | 69,7 % |
| Producto v9 (Gemma + calibrado + compuerta) | 69,8 | 49,0 | 57,4 % | 71,2 % |
| **v10 (mezcla)** | 82,9 | 83,7 | **83,4 %** | 91,5 % |
| v10-segundos | 82,9 | 82,2 | 82,5 % | 91,0 % |

Criterio (total > v9 y no por debajo del v9 en taller ni en cocina): **SE CUMPLE** para v10 y para v10-segundos.
La meta de Juan (> 85 %) no se alcanza en la persona limpia (83,4 %); el desarrollo con 5 personas dio 85,0 %.
