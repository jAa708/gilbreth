# Pre-registro: el modo estación (v10) en OTRA estación, con videos que nunca se usaron — IMPACT, 17-oct, 10:40

## Pregunta (de Juan: «prueba con videos que no se hayan usado»)
El v10 se construyó y se probó en KIT (cocina y taller de laboratorio). ¿Funciona el mismo sistema, sin cambiar nada,
en una estación distinta (IMPACT: desarme y reensamble de una caja reductora con herramientas) y en videos que nunca
pasaron por Gemma, ni por el v9, ni por el v10?

## Datos
- **La estación (personas etiquetadas):** los 9 operarios de los grupos ENTRENAR y DESARROLLO 2 de
  `hackaton_prep_9oct/agente/PREREGISTRO_IMPACT_COMPLETO_11OCT.md`, con las 11 corridas suyas que ya tienen códigos
  de Gemma (corrida del laboratorio del 11-oct): AL07EJ17_Disassembly_A_002, AL07EJ17_Reassembly_A_003,
  ER07AD15_Disassembly_A_002, ER07AD15_Reassembly_A_001, KE03ER16_Disassembly_A_001, KI03AR28_Disassembly_A_001,
  KJ03JM25_Disassembly_A_004, LE06AS03_Disassembly_A_003, MA07LF04_Disassembly_A_003, NA07GE21_Reassembly_A_003,
  SS07EL13_Disassembly_B_005. Con todas sus etiquetas. KIT NO entra (es otra estación).
- **Las personas nuevas (prueba):** los 4 operarios de PRUEBA 2 (ER10WE06, KI05KO01, LE07UF17, TO08CO25). Regla
  mecánica: por operario, su primera corrida de desarme A y su primera de reensamble A (≤ 360 s, con puntos) que
  NUNCA pasaron por Gemma → ER10WE06_Disassembly_A_002, ER10WE06_Reassembly_A_001, KI05KO01_Disassembly_A_002,
  KI05KO01_Reassembly_A_003, LE07UF17_Disassembly_A_001, LE07UF17_Reassembly_A_002, TO08CO25_Disassembly_A_002,
  TO08CO25_Reassembly_A_002 (34,9 min de video). Ninguna pasó nunca por Gemma, el v9 ni el v10. Lo único que se miró
  de ellas fue, el 11-oct, el acierto agregado del clasificador de movimiento solo (el 11-oct se midió en todas las
  corridas ≤ 360 s de cada grupo); nada del v10 se decidió con IMPACT.
- Códigos de Gemma de la prueba: Gemma-4-31B-IT en AMD Token Factory, la tubería del producto (`banco_modelos.py
  --producto`). Los de la estación son de la corrida del laboratorio del 11-oct (otra versión de servicio de Gemma; se
  declara, como en KIT).

## Protocolo (el del ejemplo del engranaje en la app)
Los primeros 60 s de cada corrida de prueba hacen de revisión (su verdad se usa para calibrar y para la mano
dominante); se mide desde el segundo 60. Verdad: `verdad.impact_por_segundo` (regla fija del 11-oct: PICK_UP / PLACE /
STORE / TRANSFER → TR; HOLD → S si la otra mano opera, si no D; resto → OP), manos-segundo con mayoría NULL fuera.
Se reporta también sin los segundos de verbo conjunto (ambiguos) y a ±1 s.

## Sistemas
- Gemma sola (v5).
- v9, el producto: calibrado con el previo de IMPACT (que se entrenó con los operarios de ENTRENAR y DESARROLLO) y la
  compuerta, con los primeros 60 s como revisión.
- **v10 modo estación**: el código congelado de KIT (`final.py`, `sistema.py`, mismos hiperparámetros, CAL 5,
  PESO_A 0,5) con constructores de filas para IMPACT (mismos rasgos; la «tarea» es desarme o reensamble). Entrena con
  la estación + los primeros 60 s de la persona nueva. La mano dominante de cada persona y tarea sale de sus primeros
  60 s (en la estación, igual).
- v10-segundos (solo el modelo por segundo), como en KIT.

## Enmienda (17-oct, 10:55, antes de tener un solo código de Gemma de la prueba)
Al escribir el script (`v10/impact_v10.py`) se fijan tres detalles que el texto de arriba no decía:
1. **Sin atributos de Gemma.** Los códigos de la estación (corrida del laboratorio) no guardaron atributos; si la
   prueba los llevara, el modelo solo los vería en los 60 s revisados de la persona nueva. Así que en los dos lados
   entra solo el código (los rasgos de atributos quedan vacíos, como el sujeto 1 en KIT).
2. **Persona nueva = un operario** con sus dos corridas: 4 ajustes del v10 (estación + sus primeros 60 s de cada
   corrida), igual que en KIT un sujeto con sus 9 tareas.
3. **v9 por corrida:** la compuerta decide con los primeros 60 s de esa corrida (segundos con verdad en las dos manos y
   código de Gemma), como el ejemplo del engranaje; se aplica desde el segundo 60.
Se puntúa el mismo conjunto de manos-segundo para los cuatro sistemas (verdad válida y predicción de todos).

## Enmienda 2 (17-oct, 11:00, tras la auditoría de Codex `v10/codex_impact/ultimo.md`; aún sin códigos de la prueba)
Codex no encontró fugas hacia el modelo, la mano dominante ni la compuerta. Se corrige todo lo que señaló:
- H01: de la prueba solo se leen los primeros 60 s × 30 cuadros de etiquetas antes de la marca de inicio; el resto se
  lee después (con la regla de `verdad.py` copiada y comprobada igual en las 11 corridas de la estación).
- H02: antes de la marca se valida la corrida de Gemma (modelo, `--producto`, paquetes, Token Factory, ventanas sin
  repetir) y la cobertura: si en alguna corrida falta código en más del 1 % de las manos-segundo (el tope del
  sujeto 4), la prueba NO se mide.
- H03: el script exige que `final.py`, `sistema.py`, `construir.py` y `cuadros.py` sean los congelados de KIT (sus
  hashes del sello), que el v9 venga del agente entregado y registra los hashes del previo y de los módulos.
- H04 (se declara): el v10 se ajusta por operario con los primeros 60 s de sus dos corridas y su modelo a 10 Hz usa
  etiquetas por cuadro; el v9 se calibra por corrida con etiquetas por segundo. Se comparan los dos protocolos tal como
  funcionan; el v10-segundos es la referencia con etiquetas por segundo.
- H05 (se declara): como en KIT, el modelo a 10 Hz conserva la etiqueta de un cuadro válido aunque su mano-segundo
  quede fuera por mayoría NULL (es el sistema congelado; no se cambia).
- H06: a ±1 s solo cuentan vecinos con predicción de los cuatro sistemas.
- H07: el criterio compara aciertos enteros, no porcentajes redondeados.
- H08: «sin ambiguos» se reporta también por tarea y por corrida.

## Enmienda 3 (17-oct, 11:55, ensayo en seco con el primer video; sin leer verdad desde el segundo 60)
Sin atributos en ningún lado (enmienda 1), sus 88 columnas de las filas por segundo quedan 100 % vacías y
HistGradientBoosting no puede ajustarse (en KIT había atributos en 4 de 5 sujetos). Se quitan esas 88 columnas; ninguna
otra columna está vacía ni es constante (comprobado en la estación + el primer video). `final.py` y `sistema.py` no se
tocan. Con eso, el ensayo en seco corre de punta a punta.

## Enmienda 4 (17-oct, 13:35, sin resultados: Gemma lleva 2 de 8 videos y nada se ha puntuado)
El juez simulado (Codex, `gilbreth_entrega/codex_jueces/ultimo.md`) objeta que la mejora por segundo no se traduce en
mejor diagrama (KIT s3: reparto de tiempo 10,9 frente a 10,7 puntos de Gemma). Se AÑADEN como cifras secundarias, sin
cambiar el criterio, las tres medidas del diagrama de `docs/RESULTS.md` («What the per-second figure means for the
chart»), con las funciones de `acuerdo_diagrama/acuerdo_diagrama.py`, por corrida y sobre los segundos ≥ 60 del
conjunto común, para v5, v9, v10 y v10-segundos frente a la verdad: (1) distancia media del reparto de tiempo por mano
y actividad, (2) si acierta la mano que más sostiene o espera, (3) si la palanca principal del plan coincide. Se
reportan tal como salgan.

## Sello (17-oct, 14:40, antes de mirar el ejemplo de la caja con el modo estación)
Para el ejemplo de la app se va a correr el modo estación sobre la caja reductora (LE07UF17_Reassembly_A_004, otra
corrida de un operario de PRUEBA 2, ya usada como ejemplo desde el 14-oct). Nada de eso cambia esta prueba: el script y
el sistema quedan sellados así (sha256) y `impact_v10.py --si` debe correr con estos mismos ficheros:
- `v10/impact_v10.py` e1cd274f055c5b042075325abcfbe9dccc5e07944f394c3aa0535aff45a9d255
- `v10/construir.py` 231c3a6357464aa9db7aa017f33f88f10ea479a1df479ff620ffec5e0f2f7428
- `v10/cuadros.py` 5b73a27ce17d807f6dc8d6afca0cf68e83fb96f45ce1dcc50b5a0cb6d448b5e3
- `v10/sistema.py` ee9a98bd1feb7ae560b82765219d61c73a6cd62fc4213cf8a8f966cc3ea08b51
- `v10/final.py` 9b376b3484cf0e0da5e19e205bf1404e36ed76a9b27ec238f928ca1fe623cc99
- `agente/verdad.py` b44c11239f2526cb02776b600c5dfa772898a5dd71ab420efcb4c9948648261d

## Criterio (una sola mirada)
El v10 supera al v9 en el total de las 8 corridas (segundos ≥ 60, sin NULL). Se reportan también Gemma sola, la cifra
sin ambiguos y ±1 s, por corrida y por tarea. Nada se ajusta después de mirar.

## RESULTADO (17-oct, marca de inicio 22:22:59; una sola mirada)
Gemma: 8/8 videos, 2.094 ventanas, 0 caídas, cobertura completa. Conjunto común: 3.142 manos-segundo (70 ambiguos).

| IMPACT, segundos ≥ 60 | Gemma sola (v5) | v9 (el producto) | v10 | v10-segundos |
|---|---|---|---|---|
| Total | 66,5 % (2.090) | 71,1 % (2.233) | 71,3 % (2.239) | 72,2 % (2.268) |
| ±1 s | 78,4 % | 82,4 % | 79,6 % | 81,0 % |
| Desarme (1.296) | 68,4 % | 74,7 % | 74,0 % | 73,6 % |
| Reensamble (1.846) | 65,2 % | 68,5 % | 69,3 % | 71,2 % |
| Sin ambiguos (3.072) | 67,0 % | 71,3 % | 71,0 % | 72,1 % |

**CRITERIO (v10 > v9 en el total): SE CUMPLE por 6 manos-segundo (2.239 frente a 2.233): en la práctica, un empate.**
Compuerta del v9: eligió el modelo calibrado en 7 de 8 corridas.

Enmienda 4 (diagrama, `v10/impact_diagrama.py`; las predicciones recalculadas dan exactamente los mismos aciertos):
reparto de tiempo a 8,1 (Gemma) · 8,0 (v9) · 8,9 (v10) · 8,3 (v10-segundos) puntos de la verdad; mano que más
sostiene o espera: 8/8 en los cuatro; palanca principal: 8/8 en los cuatro; tiempo tras el plan a 8,7 · 6,7 · 6,0 · 6,3 %
del ciclo.

Lectura: fuera de KIT el producto (v9) le gana a Gemma por 4,6 puntos y, en corridas de 4-5 minutos, la decisión del
ingeniero (mano a liberar, palanca principal) sale bien en las 8 con cualquier sistema. El modo estación empata con el
producto: la ventaja de KIT no se reproduce aquí. Hipótesis (no medidas): el previo de movimiento del producto se hizo con
estos mismos 9 operarios, así que en IMPACT el v9 ya «conoce» la estación; y los códigos de Gemma de la estación son de la
corrida del laboratorio (otro servicio) y los de la prueba de AMD Token Factory.
