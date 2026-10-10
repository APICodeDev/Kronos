# Lógica de Kronos y viabilidad de su reproducción en Pine Script

Fecha de evaluación: 8 de octubre de 2026.

**No resulta viable trasladar fielmente los modelos publicados de Kronos a un indicador autónomo de Pine Script.** Sí pueden trasladarse la preparación de las velas, la normalización, las métricas y determinadas reglas que se apliquen después de obtener una predicción. La generación de esa predicción depende de un tokenizador y un Transformer con millones de parámetros entrenados. Sustituirlos por indicadores técnicos, búsqueda de patrones o una red pequeña produciría otro modelo, cuya semejanza habría que demostrar.

Por esta razón no se ha desarrollado ningún archivo `.pine`. La condición solicitada era reproducir la lógica con una viabilidad fundamentada.

## Alcance y evidencias

La app evaluada es el proyecto local Kronos, con Flask, PyTorch y una interfaz de Plotly. La revisión corresponde al commit `325d4e0dce156a1612e0a271be1083ae19856a31`. Sus módulos principales son [el predictor y el tokenizador](../model/kronos.py), [las operaciones neuronales](../model/module.py), [la API de la app](../webui/app.py), [la descarga de Kraken](../webui/kraken_data.py) y [el código de la interfaz](../webui/templates/index.html).

Las pruebas numéricas se ejecutaron en un proceso independiente dentro del contenedor existente, con los pesos de Kronos-base y Kronos-Tokenizer-base ya descargados. No se modificaron la app, su modelo cargado, los datos del usuario ni los pesos. Los únicos archivos nuevos del proyecto están en `research/`.

Los resultados reproducibles están en [kronos_audit.json](kronos_audit.json) y [kronos_inference_mode.json](kronos_inference_mode.json). El [script de auditoría](audit_kronos.py) conserva el procedimiento. El entorno fue Python 3.11.17, PyTorch 2.14.1+cpu y huggingface_hub 0.33.1. Las revisiones de los pesos son:

- Predictor base: `2b554741eca47781b64468546e77fef3e85130e6`.
- Tokenizador base: `0e0117387f39004a9016484a186a908917e22426`.

Las cuentas de mini y small se obtuvieron construyendo su arquitectura con las configuraciones públicas, sin descargar sus pesos. Las pruebas de predicción utilizaron exclusivamente base. La API de estado de la app devuelve el nombre genérico `Kronos`, por lo que ese estado no identifica por sí solo el checkpoint que tiene cargado el servidor.

## Qué IA utiliza la app

La IA es el modelo financiero Kronos. La app carga sus pesos desde Hugging Face y ejecuta operaciones locales en PyTorch. Su ruta de predicción no invoca ChatGPT ni un servicio externo de razonamiento. Tampoco calcula una combinación secreta de RSI, medias móviles o soportes para construir las velas.

Los autores describen un preentrenamiento sobre más de 12.000 millones de registros de velas de 45 mercados. Ese aprendizaje queda incorporado a los pesos; no se reconstruye leyendo solamente las 80 velas que introduce el usuario. [Artículo original de Kronos](https://arxiv.org/html/2508.02739v1).

## Recorrido exacto de los datos

### Selección de las velas y del horizonte

La interfaz fija por defecto 80 velas históricas y 120 futuras. La API admite otros tamaños positivos, de modo que 80 y 120 son una configuración de la aplicación, no una propiedad indispensable del modelo.

En modo `forecast`, el servidor utiliza las últimas filas del archivo cargado. No adquiere automáticamente nuevas cotizaciones en cada predicción. Para que la previsión parta del mercado más reciente hay que actualizar ese archivo. Un índice antiguo enviado por el navegador no selecciona otra ventana en este modo.

En modo `backtest`, toma una ventana histórica de 200 filas: 80 entran al predictor y 120 se reservan para la comparación. Los precios de estas últimas no entran en `predictor.predict`; sus timestamps sí se utilizan como calendario del horizonte. Es una comparación de pronósticos, no un backtest de operaciones con costes, capital, entradas y salidas.

El importador de Kraken elimina la última vela del endpoint porque está en formación, comprueba precios y continuidad y exige al menos 80 velas cerradas. En una réplica habría que usar el mismo mercado, intervalo, fuente y corte de vela. Las velas de otro exchange o un gráfico Heikin Ashi cambiarían la entrada.

### Seis variables por vela

El predictor trabaja con el vector:

```text
x[t] = [open, high, low, close, volume, amount]
```

Hay un matiz que el README de la interfaz no explica correctamente. El servidor excluye la columna `amount` del archivo cuando prepara la entrada, pero `KronosPredictor.predict` la reconstruye:

```text
amount[t] = volume[t] * (open[t] + high[t] + low[t] + close[t]) / 4
```

Por tanto, la IA sí recibe `amount`; recibe un importe aproximado, no necesariamente el turnover real ni el volumen multiplicado por el VWAP de Kraken. Si no hay volumen, el predictor establece volumen e importe a cero. Si se utiliza directamente la clase Python con un `amount` existente y volumen disponible, puede conservarse ese importe, lo cual difiere de la ruta de esta Web UI.

### Normalización de cada ventana

Cada una de las seis columnas se convierte a float32 y se normaliza independientemente sobre las velas de entrada:

```text
mu[j]    = media de x[:, j]
sigma[j] = desviación típica poblacional de x[:, j]
z[t, j]  = limitar((x[t, j] - mu[j]) / (sigma[j] + 0.00001), -5, 5)
```

No son retornos logarítmicos ni una normalización mediante ATR. La media y la escala quedan fijadas durante esa llamada; no se actualizan con cada vela generada. Para reproducir esta parte en Pine habría que igualar la ventana, la desviación poblacional, el epsilon y el tratamiento del volumen.

### Calendario

El predictor extrae minuto, hora, día de la semana, día del mes y mes. El día semanal de pandas empieza con lunes igual a cero. El modelo convierte estas cinco categorías en vectores entrenados y los suma a la representación de las velas.

En Kraken los timestamps se generan en UTC. Utilizar la zona horaria del exchange o Europe/Madrid sin conversión cambiaría los vectores temporales. En modo futuro la app crea fechas con el intervalo mediano del archivo; no dispone de un calendario bursátil que omita automáticamente fines de semana y festivos. Para cripto continuo esto es menos problemático que para acciones.

### Tokenizador neuronal

El tokenizador transforma los seis números normalizados en una representación de dimensión 256. La implementación contiene tres bloques Transformer en el encoder y tres en el decoder: la configuración indica cuatro, pero los bucles crean `n_enc_layers - 1` y `n_dec_layers - 1` bloques.

Su encoder usa atención causal, RMSNorm, posiciones rotatorias y capas densas con activación SiLU. Proyecta la representación a 20 componentes, normaliza ese vector y cuantiza sus signos. Cada componente cuantizada vale `-1/sqrt(20)` o `+1/sqrt(20)`.

Los 20 bits se separan en dos tokens de 10 bits: uno grueso y uno fino, con 1.024 posibilidades cada uno. Existen 1.048.576 combinaciones conjuntas. La asignación depende de proyecciones y atención entrenadas; no equivale a clasificar velas como doji, martillo o envolvente. El tokenizador puede dar una representación diferente a una misma vela si cambia su contexto anterior o la normalización de la ventana.

### Generación autoregresiva

Para cada futura vela, `auto_regressive_inference` hace lo siguiente:

1. Fusiona los embeddings de los dos tokens de cada vela anterior y añade el calendario.
2. Ejecuta los bloques del Transformer sobre la secuencia disponible.
3. Obtiene logits para el token grueso de la siguiente vela.
4. Aplica temperatura y filtrado de probabilidades y muestrea ese token.
5. Condiciona una segunda cabeza al token grueso mediante una capa de atención cruzada y muestrea el token fino.
6. Añade ambos tokens a la historia y repite para el siguiente paso.

La factorización conceptual es:

```text
P(s1 futuro, s2 futuro | historia, calendario)
  = P(s1 futuro | historia, calendario)
    * P(s2 futuro | historia, calendario, s1 futuro)
```

Los pasos posteriores dependen de los tokens previamente generados. El código actual recalcula el Transformer sobre la ventana en cada paso y no mantiene una caché de claves y valores de atención. Cuando supera el contexto máximo utiliza un buffer deslizante. Por defecto el límite es 512 en small y base, y 2.048 en mini.

### Muestreo y reconstrucción

La temperatura divide los logits antes de aplicar softmax. Una temperatura elevada aplana la distribución; no representa un porcentaje de confianza ni garantiza mejor calidad. `top_p` mantiene las opciones más probables hasta alcanzar el umbral acumulado, incluyendo la opción que lo cruza. El muestreo se realiza con `torch.multinomial`.

`sample_count` duplica el contexto para generar varias trayectorias. Al terminar, el decoder del tokenizador transforma los tokens en seis variables continuas y el código calcula la media aritmética de las trayectorias. Finalmente deshace la normalización con las medias y desviaciones originales.

El resultado mostrado con dos muestras es el promedio de dos escenarios; no es un intervalo de confianza. La app no devuelve percentiles ni las trayectorias individuales. Su decoder tampoco impone explícitamente `high >= max(open, close)`, `low <= min(open, close)` o volumen no negativo.

## Hallazgo sobre el modo de inferencia

`webui/app.py` carga ambos modelos mediante `from_pretrained`, pero ni esa función de la app ni `KronosPredictor` llaman a `.eval()`. En la versión instalada de huggingface_hub, la carga de safetensors conserva `training=True`; la auditoría lo verificó en ambos modelos. `torch.no_grad()` evita registrar gradientes, pero no desactiva el dropout.

Esto tiene dos consecuencias en esta ruta de carga:

- Kronos-base conserva dropout del 20 % en las capas feed-forward y residuales.
- La atención cruzada utiliza `is_causal=self.training`. En generación, la consulta tiene longitud uno y las claves tienen la longitud de la historia. Con la máscara causal de PyTorch, esa consulta solo atiende a la primera clave. En modo evaluación puede atender a toda la historia.

Una prueba mínima con valores `[0, 1, 2, 3]` y scores iguales devolvió `0` con máscara causal y `1.5` sin ella, reproduciendo esa diferencia de acceso. Esta semántica coincide con la [documentación de atención de PyTorch 2.14](https://docs.pytorch.org/docs/2.14/generated/torch.nn.functional.scaled_dot_product_attention.html).

Al cambiar la semilla en modo entrenamiento, la diferencia máxima entre logits gruesos fue 1,885974 y entre logits finos 3,642513. En evaluación, los logits gruesos no cambiaron con la semilla. En la ventana concreta de ocho pasos, la selección greedy terminó dando los mismos cierres en ambos modos: que el token ganador coincida no significa que coincida su distribución de probabilidades.

Antes de definir una referencia para cualquier réplica habría que decidir si se compara contra el comportamiento actual de la app o contra una inferencia con `.eval()`. Corregirlo sería un cambio funcional, no una simple limpieza. El informe identifica el problema; no ha cambiado el servidor.

## Pruebas con los pesos reales

La entrada fue la última ventana de 80 velas del archivo AVAXUSD de una hora usado por el resultado local `prediction_20261008_191209.json`. El nombre, corte temporal y hash del CSV quedan registrados en las evidencias. Las comparaciones de esta tabla emplean Kronos-base en evaluación, temperatura 1 y horizonte de ocho velas.

| Prueba | Resultado observado |
| --- | --- |
| Repetir entradas, configuración y semilla 123 | Igualdad exacta de las seis salidas |
| Cambiar la semilla de 123 a 124 con muestreo `top_p=0.9` | Diferencia máxima de cierre de 0,318301 USD |
| Cambiar la semilla con `top_k=1` | Diferencia de cierre de 0 USD |
| Retirar volumen e importe, manteniendo greedy | Diferencia máxima de cierre de 0,086851 USD |
| Desplazar seis horas el calendario histórico y futuro, manteniendo greedy | Diferencia máxima de cierre de 0,073895 USD |
| Generar 120 velas con dos trayectorias y `top_p=1` | 80,9562 segundos en CPU con cuatro hilos |

Los resultados muestran dependencia real del volumen, del calendario y del muestreo. Son experimentos sobre una ventana concreta, no una medición de rentabilidad ni de precisión general. El tiempo de CPU tampoco permite calcular directamente el tiempo de Pine; es evidencia del trabajo realizado por la implementación real.

Pasaron los 11 tests existentes de la Web UI que comprueban las ventanas de predicción y la importación de Kraken. Esos tests usan mocks para el predictor y validan el manejo de datos; no certifican la calidad de la IA.

## Tamaño y coste de los modelos

El tokenizador base tiene **3.958.042 parámetros entrenables**, equivalentes a 15.832.168 bytes en float32. Las configuraciones públicas del tokenizador 2k y del base tienen las mismas dimensiones entrenables; difieren en la agrupación del cuantizador. Necesitan sus respectivos pesos compatibles.

| Predictor | Capas | Dimensión | Parámetros del predictor | Bytes float32 del predictor |
| --- | ---: | ---: | ---: | ---: |
| mini | 4 | 256 | 4.108.032 | 16.432.128 |
| small | 8 | 512 | 24.741.376 | 98.965.504 |
| base | 12 | 832 | 102.310.592 | 409.242.368 |

Mini y su tokenizador suman unos 8,07 millones de parámetros, aproximadamente 32,26 MB de coeficientes float32. Base y su tokenizador suman aproximadamente 425,07 MB. Estas cifras excluyen activaciones, buffers, código y otras necesidades de memoria.

Las configuraciones contrastadas son [mini](https://huggingface.co/NeoQuasar/Kronos-mini/raw/main/config.json), [small](https://huggingface.co/NeoQuasar/Kronos-small/raw/main/config.json), [base en la revisión utilizada](https://huggingface.co/NeoQuasar/Kronos-base/blob/2b554741eca47781b64468546e77fef3e85130e6/config.json), [tokenizador base](https://huggingface.co/NeoQuasar/Kronos-Tokenizer-base/raw/main/config.json) y [tokenizador 2k](https://huggingface.co/NeoQuasar/Kronos-Tokenizer-2k/raw/main/config.json).

Para cuantificar el cálculo se contaron solamente las multiplicaciones y acumulaciones de las proyecciones densas de los bloques centrales. Con 80 velas iniciales y 120 futuras, la implementación procesa longitudes de 80 a 199. La cuenta por trayectoria es:

```text
MAC = capas * (4 * dimension² + 3 * dimension * dimension_FFN)
      * sum(longitudes de 80 a 199)
```

| Predictor | MAC de esas proyecciones por trayectoria |
| --- | ---: |
| mini | 43.882.905.600 |
| small | 351.063.244.800 |
| base | 1.583.075.819.520 |

Una MAC es una multiplicación y una acumulación. La cuenta excluye los productos de atención, las cabezas de salida, la capa de dependencia, el tokenizador y las funciones de activación. Dos trayectorias duplican este cálculo aritmético, aunque PyTorch las ejecute en paralelo.

Una implementación con caché de atención podría reducir considerablemente el cálculo repetido. Esta cuenta caracteriza el código actual, no una cota universal para cualquier implementación de Kronos. La caché no elimina la necesidad de disponer de todos los pesos.

## Qué permite Pine y dónde se detiene la reproducción

La documentación vigente establece 5 MB para la solicitud de compilación, 100.000 elementos por colección, 500 ms por bucle en una barra y 20 o 40 segundos para ejecutar el dataset según cuenta. Los dibujos pueden extenderse 500 barras al futuro. [Límites oficiales de Pine](https://www.tradingview.com/pine-script-docs/writing/limitations/).

El límite de colección es por objeto, no un máximo global de 100.000 pesos. Dividir matrices sería posible conceptualmente. Tampoco se deduce un límite de RAM de 5 MB: esa cifra limita el código y bibliotecas enviados al compilador. Aun con esas precisiones, incrustar millones de coeficientes publicados y evaluarlos mediante el runtime de Pine no ofrece una vía práctica fundamentada.

| Parte de la app | Viabilidad en Pine |
| --- | --- |
| Leer OHLCV de un mercado disponible y elegir 80 velas cerradas | Sí, con datos y cortes equivalentes |
| Construir el importe aproximado | Sí |
| Normalizar y limitar las seis columnas | Sí |
| Extraer categorías temporales | Sí, igualando UTC y los índices |
| Dibujar una trayectoria ya calculada de 120 velas | Sí, mediante objetos de dibujo y datos precargados |
| Calcular MAE, RMSE y MAPE cuando exista la verdad futura | Sí |
| Aplicar umbrales a una predicción disponible | Sí |
| Cargar los checkpoints de Hugging Face y ejecutar PyTorch | No hay una API nativa para ello |
| Ejecutar fielmente los modelos publicados con sus pesos y muestreo | No resulta viable como indicador autónomo estándar |

Los 120 pasos futuros no son el obstáculo principal; el núcleo neuronal y sus pesos sí lo son. Es posible programar algunas operaciones neuronales o redes pequeñas en Pine. Eso no hace viable importar estos checkpoints completos.

El namespace documentado `request.*` solicita datasets concretos, no ejecuta peticiones HTTP arbitrarias a Flask ni lee sus JSON locales. [Datos accesibles desde Pine](https://www.tradingview.com/pine-script-docs/concepts/other-timeframes-and-data/). Los webhooks envían avisos desde TradingView a una app externa; no devuelven el pronóstico al indicador. [Funcionamiento oficial de los webhooks](https://www.tradingview.com/support/solutions/43000529348-how-to-configure-webhook-alerts/).

Pine Seeds admite datos EOD, pero la creación de repositorios nuevos está suspendida. No constituye una integración intradía de libre creación para este proyecto. [Documentación oficial de Pine Seeds](https://github.com/tradingview-pine-seeds/docs).

## Qué revelan los pronósticos ya guardados

Se inspeccionaron 44 resultados locales: 29 comparaciones de 2025, dos comparaciones de 2026 y 13 previsiones futuras de 2026. Son resultados heterogéneos, con ventanas y versiones potencialmente diferentes. No forman un conjunto de evaluación independiente.

En las 31 comparaciones cuyos precios y timestamps se pudieron alinear, 10 tuvieron un MAE de cierre inferior al pronóstico constante del último cierre y 21 no lo tuvieron. Las dos comparaciones de 2026 tampoco mejoraron esa referencia:

| Archivo | MAE de cierre de Kronos | MAE del último cierre constante |
| --- | ---: | ---: |
| prediction_20261008_172220.json | 2.293,75040 | 889,80417 |
| prediction_20261008_173229.json | 0,01684 | 0,01428 |

Las magnitudes pertenecen a sus respectivos activos y no deben promediarse como si tuvieran la misma escala. Los resultados repetidos y seleccionados manualmente tampoco permiten convertir 10 de 31 en una probabilidad de éxito general.

En el conjunto de archivos se detectaron 1.540 velas predichas con inconsistencias de orden OHLC y 121 con volumen negativo. El resultado de 2026 terminado en `184311` contiene 119 volúmenes negativos; el terminado en `191209`, utilizado como referencia de entrada de la auditoría, contiene nueve velas con inconsistencias OHLC. Estos archivos prueban que tales salidas pueden aparecer; no fijan su frecuencia para el modelo evaluado en condiciones controladas.

En la Web UI, MAE, RMSE y MAPE se calculan sobre el cierre. No son un porcentaje de acierto direccional ni una medida de confianza. La función `getPredictionQuality` devuelve ceros si no hay datos reales, pero el flujo de presentación oculta la comparación en el modo futuro. Un cero sin verdad observada no sería evidencia de precisión.

## Alternativas y condiciones para desarrollarlas

### Conservar la IA original fuera de Pine

Es la vía que conserva el núcleo aprendido: realizar la inferencia en Python con los mismos checkpoints, entradas, calendario y parámetros. Puede utilizarse la interfaz actual o un gráfico propio conectado a su API. Pine podría emitir eventos hacia un servicio externo, pero esa arquitectura no introduce automáticamente la respuesta de Kronos dentro de un indicador de TradingView.

Para una referencia estable convendría fijar revisiones de pesos, aplicar `.eval()`, guardar el dataset de entrada y registrar semilla, parámetros y versión del runtime. La igualdad de muestras aleatorias exige además controlar el generador y las particularidades del backend. No basta con introducir el mismo número de semilla en dos lenguajes.

### Mostrar una predicción exportada

Un exportador podría convertir una predicción ya generada en constantes para un visor Pine. Se podrían trasladar las 120 velas concretas y situarlas desde su timestamp de origen. Cada actualización necesitaría una nueva exportación o carga de datos. Sería una reproducción de un resultado, no de la función que lo genera.

### Entrenar un sustituto pequeño

La destilación consistiría en usar Kronos como profesor y entrenar externamente un modelo mucho menor para aproximar sus salidas. Es una línea de investigación posible, pero su viabilidad y fidelidad aún no están demostradas aquí.

Antes de desarrollar Pine para ese sustituto harían falta una definición del objetivo —trayectoria, cierre a cierto horizonte o dirección—, datos de entrenamiento y prueba separados cronológicamente, una referencia estable de Kronos y una evaluación fuera de muestra por activo y régimen. Habría que comparar error frente al profesor, error frente al mercado y concordancia de decisiones. Aprender el promedio de trayectorias también difiere de aprender su distribución probabilística.

Un sustituto que quepa en Pine podría perder precisamente el contexto y las interacciones que motivan usar Kronos. Su capacidad de compilar no demostraría semejanza. No se ha entrenado ni presentado como una réplica.

## Decisión de desarrollo

El preprocesamiento y el dibujo son trasladables. El modelo completo publicado no tiene una ruta viable fundamentada hacia Pine autónomo con las capacidades y límites actuales. Por ello, la investigación termina sin implementar un supuesto Kronos en Pine.

Para conservar su lógica predictiva, el cálculo debe seguir en Python. Un visor de resultados exportados o un modelo destilado serían proyectos distintos, con requisitos y pruebas propios.
