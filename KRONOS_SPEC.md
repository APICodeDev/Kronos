# KRONOS — Especificación del proyecto y traspaso a Codex

**Versión:** 1.0  
**Fecha:** 17-10-2026  
**Idioma del proyecto y de los informes:** español  
**Repositorio de referencia:** [APICodeDev/Kronos](https://github.com/APICodeDev/Kronos)  
**Rama remota observada durante la preparación:** `master`  
**Estado:** especificación de investigación; ninguna ventaja de trading se considera demostrada.

---

## 0. Instrucción principal para Codex

Lee este documento completo antes de cambiar código. Después inspecciona el repositorio y el árbol de trabajo local; la versión local del usuario puede contener cambios posteriores a la versión remota consultada al redactar este documento.

**Tu primer objetivo no es entrenar una IA ni reescribir Kronos. Tu objetivo es aprovechar el proyecto existente para descargar y validar histórico de Bitget USDT-FUTURES y ejecutar un primer experimento reproducible que determine si un patrón sencillo de falso rompimiento tiene valor estadístico.**

Trabaja de forma incremental y comprueba los cambios con pruebas. No borres datos, no sobrescribas cambios locales del usuario, no hagas `git reset --hard`, no cambies de rama sin necesidad y no hagas commits ni push salvo petición expresa. No conectes la aplicación a órdenes reales ni implementes trading automático dentro de este primer hito.

Si un detalle no está confirmado, conviértelo en un parámetro de configuración documentado y muestra la hipótesis usada en el informe. No inventes resultados. Si el patrón no funciona, informa de ello sin adornarlo ni añadir filtros para maquillar el backtest.

## 1. Objetivo del proyecto

Construir, dentro del Kronos existente, un sistema local de investigación de trading que aprenda a distinguir oportunidades con ventaja estadística de entradas con alta probabilidad de acabar en Stop Loss.

La idea central es deliberadamente sencilla:

> No queremos que el sistema prediga cada movimiento del mercado ni genere el máximo número de señales. Queremos que identifique unas pocas situaciones reconocibles, mida qué suele suceder después y aprenda a rechazar las entradas que no merecen el riesgo.

El sistema debe poder decir **«no operar»**. Una operación con dirección aparentemente correcta no es válida si no tiene espacio suficiente para alcanzar el objetivo, si el Stop Loss razonable es demasiado amplio o si la probabilidad de éxito no está respaldada por datos.

### Objetivo económico confirmado por el usuario

El objetivo no es un movimiento del precio del 1 %. Es:

**Obtener al menos un +1 % neto de rentabilidad sobre el margen inicial asignado a la operación, después de comisiones y considerando los demás costes de ejecución pertinentes.**

En un ejemplo de margen asignado de 1.000 USDT, ese objetivo equivale a 10 USDT netos. El margen de ejemplo no debe quedar codificado como una constante inamovible.

El apalancamiento cambia el movimiento de precio requerido para lograr esa rentabilidad sobre margen. Por ello, no se debe usar un TP fijo del +1 % sobre el precio ni etiquetar una operación como ganadora únicamente porque el precio se haya movido un 1 %.

### Restricciones del entorno

- Ordenador local con Windows; procesador Intel Core i7-1255U de 12.ª generación.
- 64 GB de RAM.
- Sin GPU dedicada.
- Prioridad a procesamiento e inferencia en CPU.
- No depender de servicios LLM en la nube para ejecutar el sistema.
- Docker Desktop ya forma parte del entorno del usuario, pero los componentes de investigación también deben poder ejecutarse con Python local cuando sea razonable.
- Empezar con datos públicos de mercado; no exigir claves privadas de Bitget para descargar velas públicas.

## 2. Estado existente de Kronos que debe conservarse

Durante la preparación se revisó el repositorio conectado `APICodeDev/Kronos`. La versión local puede ser diferente; verificar siempre el estado real antes de actuar.

Elementos observados en el repositorio:

- `webui/app.py`: aplicación Flask existente.
- `webui/kraken_data.py`: módulo que descarga velas del endpoint público OHLC de Kraken y valida los datos.
- `webui/templates/` y `webui/static/`: interfaz existente.
- `webui/README.md`: documenta la interfaz, la carga de CSV/Feather, el uso del modelo y la descarga de datos de Kraken.
- `tests/test_webui_kraken.py`: pruebas del módulo de datos de Kraken y de las rutas de importación/carga.
- `compose.yaml`: servicio local en el puerto 7070, con inferencia CPU y un volumen de caché para modelos.
- `research/`: contiene auditorías y material de investigación existente.

### Limitación de la descarga existente

`webui/kraken_data.py` llama al endpoint OHLC de Kraken, descarta la vela incompleta y utiliza como máximo 719 velas cerradas por consulta. Eso es útil para la interfaz predictiva actual, pero no basta para investigar un patrón en numerosos meses de velas de 5 minutos. Además, los datos de Kraken son spot y no equivalen exactamente al mercado de futuros USDT-M de Bitget.

**No elimines ni sustituyas el módulo de Kraken.** La descarga de Bitget debe añadirse como adaptador independiente, con validación y pruebas equivalentes, sin romper la función actual.

### Precaución con las rutas de escritura

En `compose.yaml`, el directorio raíz `data/` está montado como solo lectura (`/app/data:ro`). No guardes descargas dentro de ese montaje desde el contenedor. Usa el directorio de carga persistente ya configurado en la aplicación o declara una nueva ruta/volumen escribible explícito. Comprueba cómo está configurado `UPLOAD_FOLDER` en la versión local antes de implementar.

### Mantener separados los propósitos

El modelo Kronos existente es un modelo de secuencias OHLCV orientado a la previsión de velas. Este proyecto añade investigación de entradas, resultados TP/SL y, solo si los datos justifican hacerlo, un clasificador de riesgo. No asumir que la precisión de una predicción de velas equivale a la probabilidad de que una operación alcance el TP antes del SL.

## 3. Experimento inicial: falso rompimiento y recuperación

Este experimento es una hipótesis investigable, no una estrategia validada. Su finalidad es obtener una línea base sencilla antes de entrenar modelos.

### Instrumento y temporalidades

- Mercado: `XRPUSDT` en futuros perpetuos `USDT-FUTURES` de Bitget.
- Temporalidad de detección: 5 minutos.
- Temporalidades de contexto: 15 minutos y 1 hora.
- Datos históricos preferidos: 12 meses o más si la fuente los ofrece con calidad suficiente.
- Mínimo provisional para un piloto: 6 meses. Si solo se consigue menos, el informe debe advertir expresamente que la muestra es insuficiente para concluir robustez.

El contexto de 15 min y 1 h se incorporará inicialmente para describir la situación de mercado y guardar sus valores disponibles al abrir cada señal. **No debe usarse aún como filtro para la línea base.** En una fase posterior se podrá medir, mediante comparaciones controladas, si aporta mejora real.

### Definición de una señal

Utilizar niveles de las **20 velas completas anteriores**, excluyendo la vela que genera la señal.

- `previous_high`: máximo (`high`) de las 20 velas anteriores.
- `previous_low`: mínimo (`low`) de las 20 velas anteriores.
- Usar el tamaño de tick real del contrato obtenido de los metadatos del instrumento; no inventar precisión de precios.

**Candidato SHORT (barrido de máximo):**

1. La vela de 5 minutos negocia al menos un tick por encima de `previous_high`.
2. Esa misma vela cierra estrictamente por debajo de `previous_high`.
3. La señal se confirma únicamente cuando la vela está cerrada.

**Candidato LONG (barrido de mínimo):**

1. La vela negocia al menos un tick por debajo de `previous_low`.
2. Esa misma vela cierra estrictamente por encima de `previous_low`.
3. La señal se confirma únicamente cuando la vela está cerrada.

Si una misma vela cumple las condiciones de barrido y recuperación en ambas direcciones, registrar el evento como ambiguo y excluirlo de la línea base de entradas; contabilizarlo por separado. No decidir a posteriori qué dirección habría sido mejor.

### Entrada y gestión de la operación

- Entrada simulada en la apertura de la vela siguiente a la vela de señal, nunca en el cierre de la vela que confirma el patrón.
- SHORT: Stop Loss provisional en el máximo de la vela de barrido más un tick.
- LONG: Stop Loss provisional en el mínimo de la vela de barrido menos un tick.
- El buffer de SL debe ser configurable (`stop_buffer_ticks`, inicial: `1`). La versión inicial no debe optimizar esta variable sobre el conjunto de prueba.
- Si la apertura siguiente ya ha atravesado el nivel de invalidación, registrar `GAP_INVALID` y no fingir una entrada ejecutable.
- No mover retrospectivamente el SL ni ampliar o reducir el nivel después de observar el resultado.
- No se permiten entradas repetidas en la misma dirección mientras exista una posición abierta en la simulación de cartera de línea base.
- Para calcular estadísticas por evento pueden registrarse todas las señales; para la curva de capital se necesita una simulación separada que respete una sola posición abierta por símbolo, salvo que se diseñe y justifique explícitamente otra política.

### Horizonte máximo

La duración máxima es un parámetro de investigación. Usar inicialmente `max_holding_bars = 72` velas de 5 minutos (6 horas) como hipótesis provisional, configurada y reflejada en el informe. Si no se alcanza TP o SL dentro del horizonte, etiquetar `TIMEOUT`; no clasificar automáticamente ese evento como ganador.

Puede añadirse un análisis de sensibilidad posterior (por ejemplo, horizontes de 36 y 144 velas), pero debe presentarse como análisis de sensibilidad separado, no seleccionar el horizonte ganador mirando el conjunto final de prueba.

## 4. Descarga de datos: Bitget USDT-FUTURES

Añadir un adaptador de solo lectura, recomendado `webui/bitget_data.py` o una ubicación equivalente que encaje mejor con la arquitectura local. No introducir dependencias pesadas sin necesidad.

Consultar la documentación oficial vigente de Bitget antes de codificar los parámetros definitivos:

- [Market Data API](https://www.bitget.com/docs/catalog/market/market-data)
- [Get Kline/Candlestick History](https://www.bitget.com/docs/catalog/market/market-data) — endpoint documentado `/api/v3/market/history-candles`.
- [Get Instruments](https://www.bitget.com/docs/catalog/market/market-data) — metadatos como precisión/precio mínimo, cantidad mínima y tarifas publicadas del instrumento, cuando estén disponibles.

La documentación consultada durante la preparación indica que el endpoint de histórico admite `category=USDT-FUTURES`, `symbol`, granularidad como `5m`, timestamps Unix en milisegundos y peticiones con ventanas de hasta 90 días; el máximo documentado para ese endpoint es de 100 velas por llamada. Verifica el comportamiento exacto en la documentación actual y en pruebas antes de depender de esos límites. Diseña la paginación para obtener meses de histórico de forma robusta, con fronteras temporales correctas, sin huecos ni duplicados.

### Requisitos del adaptador

1. Obtener velas históricas paginando hacia atrás o hacia delante según convenga a la API y verificando cada respuesta.
2. Admitir al menos las granularidades `5m`, `15m` y `1H`.
3. Guardar timestamps normalizados a UTC.
4. Descargar solo velas cerradas. No tratar la última vela en formación como una observación final.
5. Normalizar columnas a un esquema común: `timestamp`, `open`, `high`, `low`, `close`, `volume`, y `turnover` si existe.
6. Preservar el proveedor, símbolo, categoría, granularidad, fecha de descarga, intervalo solicitado y parámetros de consulta en metadatos de procedencia.
7. Deduplicar solo con una regla explícita; ordenar cronológicamente; comprobar huecos, duplicados, timestamps fuera de orden, valores no finitos, precios no positivos, volumen negativo y coherencia OHLC.
8. No rellenar huecos silenciosamente. Informarlos y marcar el intervalo afectado; el análisis debe poder detenerse si la discontinuidad afecta el resultado.
9. Gestionar errores HTTP/API, límites de frecuencia, timeouts y reintentos limitados con espera incremental. No realizar un bucle ilimitado ni bombardear el endpoint.
10. Guardar las respuestas o los datos normalizados de manera que una prueba se pueda repetir con los mismos datos; registrar hash del archivo final y fechas exactas cubiertas.
11. Usar exclusivamente endpoints de mercado públicos en esta fase. No pedir ni almacenar claves API para descargar velas públicas.
12. Poder descargar un rango temporal reproducible, por defecto hasta la última vela cerrada disponible.
13. Mostrar un resumen claro al finalizar: filas, primera y última vela, huecos, duplicados, timeframe, símbolo y ubicación del fichero.

Preferir Parquet para uso reiterado si PyArrow ya está disponible; producir CSV cuando facilite inspección manual. No modificar el comportamiento de la interfaz de Kraken para añadir esta funcionalidad.

## 5. Datos históricos necesarios y límites de calidad

Descargar inicialmente velas de 5 minutos y los datos de 15 minutos/1 hora que se necesiten como contexto. Puede construirse un timeframe superior a partir de 5m, pero hay que documentar cómo se resuelven los límites y comparar contra las velas nativas. No mezclar fuentes spot y futures como si fueran un mismo precio.

Para el primer experimento, OHLCV es suficiente. No convertir el order book, open interest o liquidaciones en requisitos que bloqueen la primera prueba; se podrán añadir si hay una ventaja clara que justifique el coste de datos.

Si se incorporan datos superiores:

- Solo deben utilizarse valores conocidos en el momento de la entrada.
- Una vela de 15m o 1h que aún no ha cerrado no puede aparecer como dato confirmado.
- Alinear mediante timestamps de cierre y una unión temporal causal (as-of join), sin mirar hacia adelante.
- Registrar explícitamente qué vela superior estaba disponible para cada operación.

Si la API pública no permite obtener un rango suficientemente largo o completo, no afirmar que se ha descargado un año si no es cierto. Documentar el límite y buscar una vía pública oficial alternativa, incluida la descarga histórica de Bitget si corresponde.

## 6. Etiquetado del resultado y objetivo neto de +1 %

El resultado debe representar una operación ejecutable, no la distancia bruta del precio.

### Configuración explícita y visible

Crear un archivo de configuración del experimento (por ejemplo `research/false_breakout/config.yaml`) o mecanismo equivalente con, al menos:

- `symbol: XRPUSDT`
- `category: USDT-FUTURES`
- `entry_interval: 5m`
- `context_intervals: [15m, 1H]`
- `lookback_bars: 20`
- `target_net_margin_roi: 0.01`
- `margin_usdt: 1000` como tamaño virtual inicial configurable, no fijo en código
- `leverage`: parámetro explícito y editable; si no se conoce el apalancamiento real del usuario, ejecutar escenarios separados de sensibilidad (por ejemplo 1x, 3x, 5x y 10x) y etiquetarlos como supuestos, sin declarar que un escenario es el verdadero
- `entry_fee_rate` y `exit_fee_rate`: tasas configurables; no asumir que las tarifas estándar publicadas son la tarifa efectiva de la cuenta del usuario
- supuestos de deslizamiento de entrada, salida por TP y salida por SL, configurables y expresados claramente (por ejemplo en basis points)
- funding aplicado cuando corresponde y cuando haya datos históricos fiables
- `stop_buffer_ticks: 1`
- `max_holding_bars: 72`
- timezone UTC y versiones de dependencias relevantes

Todas las tasas deben usarse como decimales (por ejemplo, `0.0002` equivale a `0.02 %`). Los informes deben imprimir la configuración de costes y apalancamiento utilizada. No llamar «neto completo» a un resultado si se han excluido costes materiales; marcarlo como provisional.

### Cálculo financiero

Para un contrato lineal USDT-M, calcular el PnL bruto en función de la cantidad ejecutable y de la diferencia entre precio de entrada y salida (con signo distinto para LONG y SHORT). Restar por separado:

- comisión de apertura y cierre, calculada sobre el nominal correspondiente a cada ejecución;
- deslizamiento, representado en los precios de ejecución o como coste explícito, pero no descontado dos veces;
- funding pagado/recibido, cuando la operación cruce un instante de financiación y existan datos apropiados;
- otros costes materialmente aplicables, si los hubiera.

La rentabilidad neta sobre margen es:

`net_margin_roi = (gross_pnl - entry_fee - exit_fee - slippage_cost - net_funding_cost - other_costs) / initial_margin_assigned`

El TP debe calcularse para que `net_margin_roi >= 0.01` con los costes de apertura y cierre previstos, no usando una aproximación fija de movimiento de precio. Tener en cuenta que el nominal de salida cambia con el precio. Se puede resolver numéricamente para asegurar el objetivo neto, con pruebas para LONG y SHORT.

La base del margen asignado debe estar definida de manera consistente (nominal de entrada dividido por apalancamiento, salvo que la especificación de la simulación indique otra política); no añadir la comisión al margen en una parte de la fórmula si no se incluye en el denominador en las demás. La cantidad, nominal, margen, apalancamiento, TP calculado, precios estimados de ejecución y desglose de costes deben quedar en los resultados de cada operación.

Si no se dispone de histórico fiable de funding, informar por separado resultados sin funding y no presentar esa cifra como neta completa. Las tarifas publicadas de instrumentos pueden ser una referencia, pero las tarifas efectivas de una cuenta pueden diferir y deberán poder configurarse.

### Etiquetas del evento

Cada candidato recibirá una etiqueta inequívoca:

- `TP_FIRST`: TP que satisface el +1 % neto alcanzado antes que SL.
- `SL_FIRST`: SL alcanzado antes que TP.
- `TIMEOUT`: ni TP ni SL alcanzados dentro del horizonte máximo.
- `AMBIGUOUS`: los datos disponibles no permiten determinar el orden.
- `GAP_INVALID`: la apertura de entrada ya atraviesa la invalidación del patrón.

Si el high/low de una misma vela atraviesa TP y SL y no puede determinarse cuál sucedió primero, buscar datos de mayor resolución si están disponibles. Si no se puede resolver, aplicar criterio conservador para el backtest de cartera (SL primero) y contabilizar el caso como ambiguo. No otorgar el resultado favorable por conveniencia.

Etiquetar `TP_FIRST` no basta por sí solo para declarar una rentabilidad real: el informe también debe calcular PnL neto ejecutable. No operar en backtest a un precio mejor que los datos permitan.

## 7. Línea base antes de usar IA

Primero implementar un detector determinista y un backtester simple. No empezar por entrenar un modelo neuronal ni por fine-tuning de Kronos.

### Informe mínimo del primer experimento

- Número de señales LONG, SHORT y ambiguas.
- Cobertura temporal y calidad del histórico.
- Resultados `TP_FIRST`, `SL_FIRST`, `TIMEOUT`, `AMBIGUOUS` y `GAP_INVALID`.
- Tasa de TP antes de SL, reportada por LONG/SHORT y total.
- PnL neto por operación y rentabilidad sobre margen.
- Expectativa neta media y mediana, factor de beneficio, drawdown máximo y distribución de pérdidas.
- Número de operaciones por semana/mes, duración media y proporción de muestras con datos incompletos.
- Resultados por período temporal, no únicamente una cifra agregada.
- Comparación entre la estrategia sin filtro y cualquier filtro futuro.
- Parámetros y supuestos completos, hash de los datos y versiones de código.

No presentar win rate sin mostrar magnitud de ganadores/perdedores, comisiones y frecuencia de operaciones. El objetivo de +1 % neto es el objetivo del TP, no una promesa de obtenerlo en cada operación.

### Comparación de cartera versus análisis por evento

Mantener dos salidas distintas:

1. **Análisis por evento:** cada señal se evalúa como oportunidad aislada para estudiar el patrón.
2. **Backtest de cartera:** simula entradas reales secuenciales; no permite múltiples posiciones simultáneas en el mismo símbolo en la línea base, respeta tiempos de ejecución y descuenta costes.

No confundir la tasa de éxito por evento con la rentabilidad de una estrategia que puede no tomar todas esas señales.

## 8. Validación: impedir el autoengaño y las filtraciones futuras

El orden cronológico es obligatorio. Como primera división de investigación, usar un segmento inicial para descubrir/ajustar la línea base, otro período posterior para validación y un último tramo intacto para la evaluación final (por ejemplo, 60/20/20 por tiempo, no por filas aleatorias).

- No mezclar al azar muestras temporales en train/validation/test.
- Purge/embargo las muestras cuyas ventanas de resultado se solapen con una frontera entre particiones; definirlo según el horizonte máximo de etiquetado.
- No ajustar parámetros con los resultados del conjunto final.
- Crear pruebas que detecten que el máximo/mínimo de referencia excluye la vela actual.
- No usar velas futuras para formar señales ni valores de indicadores calculados con datos posteriores.
- Construir velas superiores con datos disponibles a la hora de la señal; no usar una vela HTF antes de su cierre.
- Al probar ejecución, utilizar la vela siguiente a la confirmación y considerar huecos, spread/deslizamiento y las limitaciones OHLC.
- Documentar las velas donde se tocaron TP y SL dentro de la misma barra.
- Registrar todas las hipótesis de parámetros exploradas para evitar la selección silenciosa de una configuración afortunada.

Si la muestra fuera de muestra tiene menos de 100 eventos evaluables, o está concentrada en un solo régimen, declarar que la evidencia es escasa y no sacar una conclusión fuerte. El número es una regla mínima de prudencia para el informe, no garantía de significación estadística.

El resultado puede y debe ser «no se encuentra ventaja». No subir los resultados mediante la búsqueda repetida de parámetros hasta que alguno parezca rentable.

## 9. Fase de aprendizaje automático — solo si la línea base lo justifica

Una vez exista un dataset etiquetado y una línea base, evaluar si un modelo pequeño mejora la selección de entradas.

Secuencia recomendada:

1. Medir la línea base sin filtro.
2. Analizar características simples de la señal y resultados: penetración del nivel, distancia de cierre al nivel, rango de la vela, proporción de mecha/cuerpo, volatilidad local y espacio hasta la invalidación. Mantener una lista corta y causal.
3. Establecer una referencia estadística sencilla (por ejemplo regresión logística) si es pertinente.
4. Probar un modelo de árboles para CPU, como LightGBM si su instalación encaja con el entorno, sin añadirlo como dependencia obligatoria antes de que se necesite.
5. Calibrar las probabilidades únicamente con datos de validación y medir calibración en el conjunto fuera de muestra.
6. Seleccionar un umbral para la acción «operar» solo en validación; evaluar una única vez en el tramo final intacto.
7. Medir si el filtro reduce operaciones que terminan en SL sin eliminar tantas oportunidades que el rendimiento total empeore.

La IA deberá aprender de los resultados disponibles antes de la entrada. Las columnas que derivan de velas posteriores solo podrán utilizarse para crear la etiqueta, nunca como características predictivas.

### El papel de Kronos como modelo OHLCV

No se presupone que el modelo preentrenado Kronos sea el mejor clasificador de este problema. Su previsión de velas se puede estudiar como experimento adicional, comparándola sobre los mismos períodos y costes. No hacer fine-tuning de gran tamaño como primer paso; la máquina no tiene GPU dedicada y la prioridad es demostrar una ventaja con un experimento CPU pequeño.

## 10. Estructura de trabajo recomendada

Ajustar a la estructura real del repositorio después de inspeccionarla. Un posible diseño modular sería:

```text
webui/
  kraken_data.py             # Existente: mantenerlo
  bitget_data.py             # Nuevo adaptador público Bitget, si encaja
research/
  false_breakout/
    README.md
    config.yaml
    download_history.py      # O comando equivalente
    detect_signals.py
    costs.py
    label_events.py
    backtest.py
    report.py
    run_experiment.py
    reports/                 # Resultados generados; revisar .gitignore
    data/                    # Si se usa ruta local, no subir históricos grandes
 tests/
  test_bitget_data.py
  test_false_breakout.py
  test_costs.py
```

La estructura anterior es orientativa. No duplicar módulos si hay ya componentes reutilizables. Mantener lógica financiera y detección de señales en funciones puras siempre que sea posible, con pruebas unitarias. La interfaz Flask se puede ampliar más adelante; primero tiene que funcionar un flujo por línea de comandos, reproducible y fácil de depurar.

## 11. Plan de trabajo para Codex

### Fase 0 — Auditoría del entorno

1. Revisar rama, `git status`, cambios locales, README, módulos de datos, rutas de guardado, `compose.yaml`, dependencias y pruebas existentes.
2. Confirmar qué parte del estado observado aquí sigue vigente.
3. Ejecutar las pruebas existentes sin modificar comportamiento.
4. Informar de posibles diferencias entre este documento y la implementación real, preservando el trabajo del usuario.

### Fase 1 — Descargador histórico Bitget

1. Consultar documentación oficial actual de Bitget.
2. Añadir adaptador público de histórico para XRPUSDT `USDT-FUTURES`, paginado y validado.
3. Descargar 5m y los timeframes de contexto solicitados, usando persistencia escribible.
4. Generar un resumen de calidad y procedencia.
5. Añadir pruebas automatizadas con respuestas simuladas: orden, límites, paginación, respuesta vacía, vela incompleta, errores, rate limits, duplicados, huecos y valores incorrectos.
6. No requerir claves privadas ni cambiar órdenes/trading.

### Fase 2 — Detector de patrón y costes

1. Implementar la detección causal con 20 velas anteriores.
2. Implementar niveles SL/TP y cálculo neto con costes configurables.
3. Implementar etiquetas de resultado con tratamiento conservador de ambigüedades.
4. Añadir pruebas de LONG/SHORT, tick size, gaps y ambos niveles tocados en la misma vela.

### Fase 3 — Informe histórico

1. Ejecutar línea base y guardar señales y resultados en CSV/Parquet.
2. Crear informe de calidad de datos y rendimiento, con supuestos visibles.
3. Separar análisis por evento y simulación de cartera.
4. Presentar claramente limitaciones y si aún no hay muestra suficiente.

### Fase 4 — Evaluación temporal y posible modelo

Solo después de revisar la línea base, construir las divisiones cronológicas y comparar modelos simples con el patrón sin filtro. No asumir de antemano que la IA mejorará los resultados.

### Fase 5 — Integración de interfaz

Cuando el experimento CLI sea estable, valorar integrar descarga, configuración, ejecución e informes en la interfaz local existente. No es necesario rehacer el diseño ni alterar la funcionalidad de predicción actual para alcanzar los primeros hitos.

## 12. Criterios de aceptación

### Aceptación técnica

- Kronos mantiene la función existente de descarga de Kraken y pasa sus pruebas.
- Bitget descarga histórico paginado sin duplicados ni huecos silenciosos.
- El informe refleja correctamente el período disponible y los límites de la API.
- Las señales solo se confirman al cierre de la vela de señal y entran, como pronto, en la vela siguiente.
- TP y SL son válidos para LONG y SHORT; el TP se calcula para el objetivo neto sobre margen con los costes establecidos.
- Las pruebas cubren los casos ambiguos, límites de API, datos defectuosos y alineación de velas superiores.
- Se puede repetir el experimento con un conjunto de datos, configuración y versión de código registrados.
- Todo el flujo inicial funciona en CPU sin requerir GPU.
- No se envían órdenes a Bitget ni se necesitan claves privadas.

### Aceptación investigadora

No hay una tasa de acierto o rentabilidad prometida de antemano. El hito se considera cumplido cuando podemos responder, con datos y limitaciones visibles:

- ¿Cuántos falsos rompimientos detectó la regla?
- ¿Cuántos llegaron al +1 % neto sobre margen antes del SL?
- ¿Con qué costes y apalancamiento se hizo el cálculo?
- ¿Cuál es la tasa de señales no resueltas o ambiguas?
- ¿Se mantiene el resultado fuera de muestra?
- ¿Existe suficiente frecuencia de oportunidades para que merezca la pena continuar?
- ¿Un clasificador añade valor frente a la regla sin filtro?

Si la evidencia no respalda el patrón, el informe debe decirlo y recomendar parar o cambiar la hipótesis, no ampliar la complejidad automáticamente.

## 13. Entregables del primer hito

1. Adaptador histórico de Bitget con paginación y validación.
2. Tests automatizados del adaptador.
3. Configuración declarativa y reproducible del experimento.
4. Detector del patrón inicial y tests.
5. Cálculo configurable del TP que alcanza +1 % neto del margen.
6. Etiquetado TP/SL/TIMEOUT/AMBIGUOUS/GAP_INVALID.
7. Datos descargados en un directorio persistente que no esté montado como solo lectura.
8. Informe del primer backtest con configuración, calidad de datos, número de eventos, costes y resultados; no inventar datos si el endpoint o la ejecución fallan.
9. Instrucciones en español para repetir la descarga y el experimento.

## 14. Fuera del alcance inicial

- Trading automático con dinero real.
- Guardar claves de API privadas o solicitar permisos de trading/retirada.
- Reentrenar Kronos desde cero o fine-tunear una red neuronal grande.
- Añadir de entrada docenas de indicadores o filtros de mercado.
- Integrar order book histórico, liquidaciones y open interest como requisitos del primer backtest.
- Modificar Pine Script o las estrategias de TradingView del usuario.
- Prometer una tasa de acierto, beneficio o protección contra pérdidas.
- Seleccionar parámetros observando repetidamente el conjunto final de prueba.

## 15. Instrucción final de ejecución

Procede en el repositorio local que abra Codex. Primero inspecciona y conserva su estado actual; después implementa el primer hito por fases, ejecuta las pruebas y entrega un resumen concreto de archivos modificados, comandos ejecutados, resultados y limitaciones pendientes. No te limites a proponer un plan: realiza el trabajo que pueda hacerse sin datos privados ni decisiones de trading no confirmadas.

Prioridad absoluta: **datos correctos, experimento pequeño, contabilidad neta honesta y ausencia de lookahead. La complejidad solo se añade si demuestra una mejora fuera de muestra.**
