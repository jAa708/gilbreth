```json
{
  "hallazgos": [
    {
      "id": "H01",
      "fichero": "congelar.py",
      "linea": "15-25",
      "problema": "Selecciona s5/s6 según los archivos presentes al ejecutarse, sin fijar el estado a las 06:00 del 17-oct. También permite sobrescribir el manifiesto después del corte.",
      "gravedad": "hiere",
      "arreglo": "Guardar una instantánea verificable al corte, con zona horaria, y hacer inmutable el manifiesto."
    },
    {
      "id": "H02",
      "fichero": "congelar.py",
      "linea": "15-19",
      "problema": "El umbral cuenta cualquier */pred.json, sin comprobar que represente una de las 90 tomas canónicas ni que contenga códigos válidos. Añade además la existencia de dos NPZ como condición para incluir al sujeto, condición no prevista en la regla.",
      "gravedad": "hiere",
      "arreglo": "Validar las 90 claves y el contenido; decidir la inclusión solo con el umbral registrado y construir después los NPZ necesarios."
    },
    {
      "id": "H03",
      "fichero": "congelar.py; prueba_s4_v10.py",
      "linea": "20-24; 26-30",
      "problema": "El candado omite deliberadamente el hash del propio evaluador y no sella NPZ, predicciones Gemma, metadatos, kit.py ni el ZIP de verdad. Cambios en esos insumos pueden alterar la cifra sin disparar la comprobación.",
      "gravedad": "hiere",
      "arreglo": "Registrar y verificar hashes, versión y procedencia de todos los insumos y del evaluador antes de leer la verdad."
    },
    {
      "id": "H04",
      "fichero": "loso_final.py; prueba_s4_v10.py",
      "linea": "44-47; 38-41",
      "problema": "Ambos cargadores conservan el último vector de nombres de rasgos y lo aplican a todos los NPZ, sin comprobar igualdad de columnas y orden. Las cachés actuales sí coinciden, pero una mezcla futura de esquemas del mismo ancho sería silenciosa.",
      "gravedad": "rasguña",
      "arreglo": "Exigir igualdad exacta de nombres, orden y dimensiones para cada sujeto antes de entrenar."
    },
    {
      "id": "H05",
      "fichero": "extraer_puntos.py; cuadros.py",
      "linea": "13-14, 26-35; 47-54",
      "problema": "El extractor toma cada round(fps/10) cuadros. En 83 de las 90 tomas de s1, a 15 fps, eso da 7,5 Hz; cuadros.py interpreta ±5 índices como ±0,5 s, cuando allí son aproximadamente ±0,67 s. Los huecos sin detecciones también amplían esa ventana. S4 está a 10 Hz nominales.",
      "gravedad": "hiere",
      "arreglo": "Construir vecinos por tiempo real, o remuestrear de forma comprobable a 10 Hz; después regenerar rasgos y la cifra de desarrollo antes de la prueba."
    },
    {
      "id": "H06",
      "fichero": "construir.py; cuadros.py; sistema.py",
      "linea": "125, 138, 155-161; 54; 20, 46",
      "problema": "t_rel y pos permanecen como rasgos aunque la lista del pre-registro no los declara. En LOSO, t_rel del sujeto fuera usa dur=len(segs) obtenido de su archivo de verdad; en s4 usa duración del vídeo. En las 270 tomas s1-s3 inspeccionadas ambas duraciones coinciden, así que no se observó efecto allí.",
      "gravedad": "rasguña",
      "arreglo": "Derivar siempre la duración de metadatos del vídeo y declarar explícitamente los rasgos de posición, o retirarlos y recalcular el desarrollo antes de mirar s4."
    },
    {
      "id": "H07",
      "fichero": "loso_final.py; prueba_s4_v10.py",
      "linea": "27-34; 76-90",
      "problema": "LOSO puntúa solo filas existentes; la prueba s4 usa todas las manos-segundo válidas de la verdad y cuenta una fila ausente como error. Si faltara alguna, el 84,3 % y s4 tendrían denominadores distintos. La cobertura s4 frente a su verdad 2-9 aún no se ha leído.",
      "gravedad": "hiere",
      "arreglo": "Fijar una misma lista de claves válidas, comprobar cobertura antes del cálculo y recalcular desarrollo con esa misma regla."
    },
    {
      "id": "H08",
      "fichero": "prueba_s4_gemma_tf.py; prueba_s4_v10.py",
      "linea": "45-51, 73-84; 76-90",
      "problema": "El evaluador v9 descarta segundos sin código Gemma; el de v10 conserva toda la verdad válida y penaliza ausencias. Por ello la comparación registrada puede usar poblaciones distintas. Los 90 pred.json actuales cubren los segundos derivados del vídeo, pero el código no exige igualdad de claves con la verdad.",
      "gravedad": "hiere",
      "arreglo": "Puntuar v9, Gemma, v10 y v10-segundos con un evaluador común y el mismo conjunto de manos-segundo."
    },
    {
      "id": "H09",
      "fichero": "prueba_s4_v10.py",
      "linea": "81-94, 106-109",
      "problema": "Cada mano-segundo sin fila incrementa faltan dos veces, una por grupo y otra por total. Además, el continue impide acreditar un acierto a ±1 s mediante un vecino cuando falta únicamente la fila central.",
      "gravedad": "hiere",
      "arreglo": "Contar la ausencia una vez por clave y calcular ±1 s a partir de los vecinos disponibles, independientemente de la fila central."
    },
    {
      "id": "H10",
      "fichero": "construir.py; prueba_s4_v10.py",
      "linea": "45-54, 150-168; 34-48",
      "problema": "El candado de Gemma comprueba V is not None en las filas existentes: acredita la presencia de pred.json, no códigos por segundo y mano ni cobertura de tomas. Tampoco comprueba n_fotogramas de los puntos contra cuadros y frameCount, verificación que sí hace el evaluador v9. Los archivos s4 visibles son 90/90 y fueron generados después de Gemma; el fallo es del candado.",
      "gravedad": "hiere",
      "arreglo": "Validar las 90 tomas, cada segundo y mano, claves únicas y conteos de fotogramas antes de entrenar o puntuar."
    },
    {
      "id": "H11",
      "fichero": "prueba_s4_v10.py",
      "linea": "52-109",
      "problema": "La salida no incorpora v9, no comprueba que su prueba se haya hecho primero y no aplica el criterio registrado contra v9, por separado para v10 y v10-segundos.",
      "gravedad": "hiere",
      "arreglo": "Unir resultados por clave con v9, informar taller, cocina y total a 0 y ±1 s, y calcular ambas decisiones registradas sin reajustar el sistema."
    },
    {
      "id": "H12",
      "fichero": "prueba_s4_v10.py",
      "linea": "21-24, 63-109",
      "problema": "La barrera de una sola mirada depende de un JSON escrito después de leer y mostrar la verdad. Una interrupción previa deja vía para repetir; --otra-vez también elude la barrera.",
      "gravedad": "rasguña",
      "arreglo": "Registrar de forma atómica el comienzo de la lectura de verdad y bloquear una segunda puntuación en la ruta oficial."
    },
    {
      "id": "H13",
      "fichero": "construir.py; loso_final.py; prueba_s4_v10.py",
      "linea": "68-83; 49-59; 30-42",
      "problema": "El 84,3 % combina Gemma de corridas distintas: s1 sin atributos, s2 cribado con corrección de manos y s3 Token Factory; s4 usa Token Factory. Además, LOSO s1-s3 entrena con dos personas y s4 con al menos tres. Son diferencias de desarrollo que deben acompañar cualquier comparación directa.",
      "gravedad": "rasguña",
      "arreglo": "Informar fuentes y número de personas por cifra; si entran s5/s6, adjuntar la validación adicional prometida. Reproducir también el 83,8 % de v10-segundos con el mismo evaluador."
    },
    {
      "id": "H14",
      "fichero": "kit.py",
      "linea": "39-50, 64-89",
      "problema": "Los conversores MP4 omiten el sujeto en la clave de salida: con un origen que contenga varios sujetos, uno sobrescribe tomas de otro o se mezclan sus cuadros. El ZIP s4 disponible contiene solo subject_4, por lo que no hay evidencia de activación en esta prueba.",
      "gravedad": "rasguña",
      "arreglo": "Incluir y comprobar sujeto en la clave, exigir un único sujeto por conversión y verificar la procedencia de cada MP4."
    },
    {
      "id": "H15",
      "fichero": "prueba_s4_gemma_tf.py; prueba_s4_v10.py",
      "linea": "86-88; 102",
      "problema": "La línea base auxiliar de v9 calcula la clase mayoritaria por mano, mientras v10 junta ambas manos. Esas dos líneas base no son comparables aunque lleven el mismo nombre.",
      "gravedad": "rasguña",
      "arreglo": "Usar una sola definición y consignarla junto a los resultados."
    }
  ]
}
```

- No encontré una fuga confirmada de la verdad s4: la dominancia separa sujetos y usa solo tomas 0–1; el orden de clases y la media de probabilidades son correctos.
- Verifiqué 90 tomas s4 con vídeo, puntos y Gemma, sin etiquetas de prueba en sus NPZ. No ejecuté la prueba ni leí su verdad 2–9.
- La diferencia comprobada más importante del modelo es la cadencia de 7,5 Hz en gran parte de s1, tratada por índices como si fuera 10 Hz.
- Antes de la única mirada conviene sellar los datos, fijar el corte de las 06:00 y exigir cobertura y denominadores idénticos.
- No hay prueba de que la cifra actual sea falsa; el código todavía no produce la comparación ni la decisión registradas frente a v9.