# Investigación de operadores: del método original a una réplica fiel

Fecha de consulta: 17-10-2026. Repositorio al comenzar: HEAD `9a86af0`, árbol limpio. Se conservan el histórico, sus particiones, 1H, 1x y todos los resultados anteriores.

**La crítica del usuario identifica un fallo real de investigación: pasé de principios generales a una mezcla de reglas propias antes de reconstruir suficientemente el proceso de los operadores.** Las pruebas anteriores conservan su valor contable para las reglas ejecutadas. No acreditan una réplica de Grimes, Raschke, Minervini ni del juicio de un trader experimentado.

Este trabajo profundiza en fuentes originales, casos publicados y decisiones completas. También revisa cuatro casos locales con el futuro oculto. **No ejecuta otra estrategia, no busca parámetros rentables y no anuncia una nueva rentabilidad.**

## 1. Evidencia: quién dice qué y qué se ha comprobado

| Operador | Material revisado | Evidencia de resultados localizada | Alcance de lo que podemos afirmar |
|---|---|---|---|
| Linda Bradford Raschke | Entrevistas de 1993, 1997, 2000 y 2004 alojadas en su web; reglamento numerado y gráficos. | Las publicaciones describen su trayectoria y su experiencia. No se ha contrastado aquí una serie independiente completa de cuentas. | Sus instrucciones y ejemplos son atribuibles. Las probabilidades que menciona no son estimaciones verificadas para XRP. |
| Adam Grimes | Artículo de ejecución de pullbacks de 2014, explicación de su método de 2023 en dos partes y cuatro ejemplos de contexto de noviembre de 2023. | Material del propio operador, sin curva de cuenta auditada comprobada en esta revisión. | Podemos reconstruir su razonamiento técnico; no convertir autoridad o gráficos seleccionados en una prueba de rentabilidad. |
| Mark Minervini | Dos entrevistas directas, crónica presencial de su taller y comunicado del organizador de la competición de 2021. | El organizador publica +334,8% en la división de acciones de cuentas de al menos un millón de dólares y explica su comprobación mediante extractos. | Es evidencia externa de ese resultado concreto, no de cada regla aislada, de todas sus cuentas o de los riesgos y costes de una réplica 1x. |

La cifra y el procedimiento del concurso proceden del [comunicado del organizador, 24-01-2022](https://www.businesswire.com/news/home/20220124005241/en/2021-United-States-Investing-Championship-Winners-Minervini-Smashes-Record) [M3]. No se atribuye ese rendimiento a futuros XRP ni se promete reproducirlo.

Se leyeron los textos relevantes completos de las entrevistas y artículos. Se inspeccionaron visualmente el recuadro de reglas y los gráficos de Raschke, el gráfico A-D de Grimes, y el ejemplo LULU y la crónica de ejecución del taller de Minervini. **No se afirma haber visto las treinta horas del taller ni disponer de sus materiales privados**: se leyó la crónica de un asistente, que es un tipo de evidencia distinto. [Catálogo y localizadores](sources.json).

## 2. Raschke: preparar un escenario, esperar su activación y gestionar la respuesta

En la entrevista de 1993 describe preparación previa, niveles del día anterior, elección anticipada entre operar ruptura o swing y abandono de una idea si el precio invalida lo previsto. Los indicadores le proporcionan un marco; la ejecución y la gestión completan la operación. Sus referencias de tendencia también dependen del régimen, no de una señal universal de oscilador. [Entrevista original, pp. PDF 4-5 y 8-9](https://lindaraschke.net/wp-content/uploads/2026/01/Discerning-trader.pdf) [L4].

### El reglamento publicado, no una receta atribuida por terceros

El recuadro de 1997 especifica, para LONG: ADX(14) inicialmente >30 y ascendiendo; retroceso a EMA(20), con posible descenso del ADX; orden buy-stop sobre el máximo de la barra anterior; protección en el nuevo mínimo del swing y seguimiento del stop. SHORT invierte la lógica. [AIQ Opening Bell, p. 2](https://lindaraschke.net/wp-content/uploads/2026/01/august1997.pdf) [L1].

Su caso Eaton muestra falta de avance pese al patrón aparente y deterioro relativo frente al índice. La lectura pasa a ser salir, no seguir concediendo tiempo indefinidamente. [L1, pp. 3-4](https://lindaraschke.net/wp-content/uploads/2026/01/august1997.pdf).

**Implicaciones nuestras para una réplica:** la activación del régimen y el gatillo son estados diferentes. Exigir ADX ascendiendo durante toda la corrección cambiaría la secuencia publicada. Una EMA de veinte períodos tampoco equivale al canal de máximos/mínimos de veinte horas que utilicé. La frase sobre la barra anterior requiere fijar exactamente cuándo se observa el toque y cuándo se coloca la orden; no autoriza a simular una entrada con información del cierre que todavía no existía.

### Un ejemplo temporal explícito

En diciembre de 2003, Raschke sitúa la oportunidad después de una consolidación y de un aumento de momentum. Describe el primer retroceso a EMA(20) en 30 minutos, y después una oportunidad horaria el 23 de diciembre y otra de 120 minutos el 2 de enero. La condición de fuerza debe existir en cada temporalidad. Busca continuación hacia nuevos máximos y contempla la maduración del movimiento. [Active Trader, marzo de 2004, pp. 78-79, figura 1](https://lindaraschke.net/wp-content/uploads/2026/03/raschke_pt2_0304.pdf) [L2].

El gráfico está identificado como SPX: no es un extracto de fills de una cuenta de futuros. Su leyenda usa una vez la expresión “20-day”, pero el gráfico y la explicación especifican veinte barras/períodos intradía. Esa inconsistencia editorial debe resolverse con el contexto, no convertirse en veinte días sobre una señal de 30 minutos. [L2].

### Cómo actúa después de entrar

En 2000 distingue ejecución en tendencia y en rango, observa si aparecen continuaciones y si se conservan las ganancias, toma posiciones en partes y contempla reducir cuando el precio no responde. También explica que un patrón fallido puede cambiar su sesgo, sin convertir cada stop en una inversión automática de posición. [The rituals of trading, pp. 58-64](https://lindaraschke.net/wp-content/uploads/2026/01/rituals.pdf) [L3].

**Lo que faltaba en mi implementación:** no existía una evaluación operativa de “la idea ya no se comporta como se esperaba”; solo estaban disponibles TP, SL o vencimiento. Eso es una omisión de gestión, aunque el cálculo de cada uno de esos resultados sea correcto. La fuente tampoco ofrece un algoritmo exhaustivo para cada ajuste: inventarlo y atribuírselo sería otro error.

## 3. Grimes: fuerza nueva, pausa de calidad y agotamiento son cosas distintas

Su explicación de 2014 plantea buscar fuerza y una vuelta hacia un precio medio, utilizando bandas como referencia consistente. Advierte sobre movimientos climáticos, permite gatillos en una temporalidad inferior y comenta stops con margen suficiente y salidas parciales. La geometría de un pullback por sí sola no completa el método. [How to trade pullbacks](https://www.adamhgrimes.com/trade-pullbacks/) [G1].

En 2023 explica que evalúa el desequilibrio del mercado, el carácter de la primera pausa y cuánto devuelve el precio. Diferencia fuerza reciente y sobreextensión; contempla parciales alrededor de 1R y ajustes de protección. No prescribe mi cierre total fijo a 2R. [How I Trade, parte 2](https://www.adamhgrimes.com/how-i-trade-part-2-2/) [G3].

La parte 1 insiste además en cuantificar lo que se llama contexto y compararlo con una referencia del activo. La discreción no exime de comprobar una ventaja, y una regla mecánica tampoco captura necesariamente toda la decisión. [How I Trade, parte 1](https://www.adamhgrimes.com/how-i-trade-part-1-of-2/) [G2].

### Cuatro movimientos similares, decisiones diferentes

Sus ejemplos del S&P del 29-11-2023 distinguen: A, continuidad posible pese a extensión previa; B, impulso sorpresivo con expectativa de continuación; C, subida de escasa convicción y posible corrección dentro de una estructura bajista mayor; D, movimiento que prepara un ataque al mínimo del día. El análisis incluye expectativas posteriores e invalidación, no solo el tamaño de una barra. [Context in Pullbacks, gráficos A-D](https://www.adamhgrimes.com/context-in-pullbacks-what-should-happen/) [G4].

Esos ejemplos están seleccionados y comentados retrospectivamente por el autor. Sirven para reconstruir criterios y diferencias; no son una muestra independiente para inferir su tasa de acierto. La noticia citada en B es información que no existe en nuestro CSV, mientras que la extensión, el ritmo y la posición dentro del rango sí pueden estudiarse con precios disponibles.

**Inferencia para Kronos:** tratar todo cuerpo >=1 ATR y todo volumen >=1,5 como una mejora monotónica de fuerza era una simplificación pobre. No hay respaldo para suponer que “más extremo” significa siempre “mejor continuación”. Eso todavía no justifica inventar un umbral superior ganador: primero hay que distinguir y describir los estados observables.

## 4. Minervini: seleccionar el vehículo y graduar la exposición forman parte de la estrategia

En la entrevista de 2017 explica selección de empresas y cambios en su crecimiento, categorías de candidatos y una operativa con reglas de compra, venta y violaciones. No propone medir un patrón sobre cualquier instrumento sin más selección. [Entrevista directa de Ben Hobson, 02-03-2017](https://www.stockopedia.com/content/mark-minervini-interview-a-guide-to-superperformance-from-a-stock-market-wizard-173828/) [M1].

En 2018 describe posiciones piloto y aumento de exposición si las primeras responden; también insiste en juzgar la decisión por su plan, no únicamente por el beneficio posterior. No equivale a entrar siempre con la misma exposición tras cada señal. [Entrevista directa, 17-04-2018](https://www.stockopedia.com/content/mark-minervini-interview-how-to-trade-like-a-champion-353963/) [M2].

La crónica del taller de 2020 recoge cribado, fases del precio, fuerza relativa, bases/VCP, ejecución y ventas. El gráfico LULU ilustra un cambio de fase; el asistente también relata compras y pequeñas pérdidas durante una sesión, incluido GRAY. No aporta el registro completo de órdenes y cierres necesario para reproducir exactamente esa sesión. [Crónica de Leslie Masonson, abril de 2021, pp. PDF 4-6](https://cdn.minervini.com/static/dist/mtp-review.1f8e8633.pdf) [M4].

**Aplicabilidad a nuestro proyecto:** OHLCV de un único futuro no contiene beneficios empresariales ni selección de fuerza relativa entre acciones. Copiar solamente contracción y volumen no reconstruye SEPA. Esto no es un motivo para ampliar ahora los datos contra la instrucción del usuario; es un motivo para elegir, para XRP 1H, un procedimiento cuya evidencia principal y variables pertenezcan a un mercado más comparable.

## 5. Auditoría de lo que realmente probé

Esta tabla compara nuestro código con las publicaciones. Las diferencias son de definición y fidelidad; no se eligen según si una operación posterior ganó.

| Componente | Decisión de mi ensayo | Problema identificado | Corrección de investigación |
|---|---|---|---|
| Autoría | Mezcla de fragmentos de varios operadores | No representa un método completo de ninguno. | Un autor y un setup principal por réplica. |
| Contexto | Ruptura de veinte horas con cuerpo >=1 ATR | No distingue origen, maduración y rechazo dentro de la propia barra. | Describir contexto antes del gatillo y fijar qué observación lo contradice. |
| Volumen | Mayor volumen relativo siempre favorece elegibilidad | Un extremo puede acompañar continuación o rechazo. | Estudiar precio y respuesta conjunta; no atribuir identidades institucionales a OHLCV. |
| Retroceso | Ventana de 2..6 horas y mantenimiento de un nivel | Tiempos y umbrales propios, sin correspondencia completa con las fuentes. | Separar las reglas publicadas de cada aproximación necesaria. |
| Entrada | Apertura de la hora siguiente a una confirmación | Puede alejarse de una entrada stop o de la zona de precio medio. | Reproducir la orden y su secuencia causal antes de comparar resultados. |
| Stop | Extremo del retroceso más un tick | No se ha acreditado equivalencia universal al swing protegido por cada autor. | Definir swing causalmente; sin pivotes confirmados por velas futuras. |
| Gestión | Salida total a >=2R o timeout de 24h | Excluye parciales, cambios de protección y salidas por fracaso de la premisa. | Documentar gestión y expectativas, no solo el gatillo. |
| Objetivo económico | +1% neto sobre margen, exigencia del proyecto | Mezclarlo con una regla atribuida al operador crea una falsa réplica. | Mantener la exigencia económica, medir su compatibilidad y etiquetar la adaptación. |
| Evaluación | Reutilización de segmentos conocidos | No es confirmación independiente de nuevas hipótesis. | Conservar todos los intentos y evitar presentar la mejor variante como prueba. |

Trazabilidad local: [protocolo anterior](../false_breakout/practitioner_protocol.json), [detector y ejecución](../false_breakout/practitioner.py), [configuración](../false_breakout/config_practitioner.json). No se modificaron para hacer encajar esta revisión.

### Parciales y +1%: contabilidad que deberá conservarse

No se rebaja el objetivo confirmado del usuario. Si se vende media posición a 1R y la otra mitad a 2R, el resultado bruto combinado es 1,5R; si la segunda mitad sale a precio de entrada, es 0,5R. Después faltan comisiones, slippage y financiación. Llegar al primer parcial no basta para etiquetar toda la operación como +1% neto de margen. Esto es una identidad matemática, no un resultado nuevo del histórico.

Por tanto, una futura réplica con parciales debe sumar las ejecuciones y aplicar el objetivo al margen inicial original. No puede reducir artificialmente el denominador al margen que queda abierto ni contabilizar todo el nominal como si hubiera salido al mejor precio.

## 6. Cuatro fichas locales: qué era visible antes de abrir

[Abrir el panel de gráficos](reviews_20261017/REVIEW.html). Incluye 1H, contexto 2H y diario exclusivamente cerrado, y volumen. [Metadatos y columnas permitidas](reviews_20261017/cases.json); [observaciones descriptivas](reviews_20261017/observations.json).

La selección es retrospectiva y explícita: primer caso por fecha, mayor volumen relativo del impulso, mediana de ese volumen y primer caso de validación. El programa carga una lista blanca que excluye PnL, etiquetas, fills y salidas; corta el precio antes de calcular contexto. Ocultar el futuro en el panel no borra lo que ya conocíamos de investigaciones anteriores ni lo convierte en validación independiente.

Los CSV identifican cada vela por su apertura. El corte informativo de la tabla es su cierre, una hora después de `signal_time`.

| Ficha, cierre disponible UTC | Información previa relevante | Pregunta de fidelidad pendiente |
|---|---|---|
| 24-10-2025 20:00, LONG | Cuerpo 1,31 ATR; volumen relativo 7,14; devolución del cuerpo de 81,63%. | ¿Cómo se justifica llamar consolidación que conserva bien el impulso a un retroceso tan profundo? Nuestra condición no lo distinguía. |
| 19-01-2026 07:00, SHORT | Cuerpo 3,875 ATR, rango 12,57 ATR y volumen relativo 41,67; la mecha inferior ocupa 69,16% de la barra. | ¿Es fuerza continuadora o posible clímax con rechazo? El volumen extremo no responde por sí solo. |
| 17-07-2026 00:00, SHORT | Cuerpo 2,05 ATR; volumen relativo 3,38; devolución del cuerpo de 32,88%. | ¿Es el primer retroceso de fuerza nueva y está alineado con el contexto mayor? La tabla de ratios no sustituye esa revisión. |
| 28-05-2026 03:00, SHORT | Cuerpo 1,66 ATR; volumen relativo 1,90; devolución del cuerpo de 32,89%. | ¿Qué escenario previo describe la operación y qué respuesta concreta lo invalidaría? |

Son descripciones de nuestras velas, no señales nuevas. No se propone excluir un caso porque sabemos que pierde, ni se aplica un nuevo filtro de mechas o profundidad para mejorar la curva. El objetivo es detectar que mi categoría anterior juntaba situaciones distintas sin explicar por qué.

## 7. Una réplica defendible antes del siguiente backtest

La prioridad por compatibilidad documental es **Raschke / Holy Grail en 1H**: hay reglas numeradas y un ejemplo publicado específicamente horario. No se elige por haber obtenido beneficios en nuestro histórico; no se ha calculado una nueva rentabilidad de ese método.

El entregable previo al cálculo es un protocolo de réplica que deje resueltos estos puntos:

1. **Activación y dirección:** cómo identificar fuerza nueva y primer retroceso, manteniendo separadas fuerza y dirección. Reinicios y caducidades deben declararse como elecciones si la publicación no los especifica.
2. **Momento de información:** ADX y EMA calculados con barras disponibles. Un toque intrahora no puede usar retrospectivamente la EMA del cierre de esa hora para fingir una orden anterior.
3. **Orden y fill:** qué barra define el buy/sell-stop, cuándo queda activa, cómo se cancela y cómo se trata un gap. Se dispone de 5m para ordenar la ejecución dentro de la hora sin generar señales con futuro.
4. **Swing y protección:** definición causal del extremo, algoritmo de actualización y momento efectivo de un stop nuevo. El ajuste decidido al cierre solo actúa desde que existe.
5. **Fracaso de la premisa y beneficios:** qué respuesta se espera, cómo se reconoce su ausencia y qué salidas/parciales proceden de la fuente o son aproximaciones. No imponer 2R/24h y llamarlo literal.
6. **Economía:** mantener 1x y +1% neto de margen como objetivo de evaluación; cantidades por lote, comisiones por ejecución, slippage una vez y funding conocido o explícitamente incompleto.
7. **Fidelidad y contraste:** revisar fichas y casos de referencia antes de mirar el PnL de la nueva réplica. Comparar primero si el programa reconoce las situaciones previstas; después medir todas las operaciones sin seleccionar ganadoras.

Estos puntos no son peticiones de permisos ni motivos para pedir más rango. Son requisitos concretos de implementación y de trazabilidad. La información suficiente para una réplica completa no puede darse por publicada si una fuente deja una decisión discrecional sin especificar.

## 8. Qué queda concluido y qué no

La conclusión corregida es: **los ensayos anteriores no respaldan las reglas híbridas que programé; todavía no han evaluado fielmente estos métodos completos.** La investigación profunda descubre diferencias verificables de contexto, orden, gestión y selección. No descubre por sí sola una ventaja rentable y no convierte la reputación de un trader en una prueba.

Se mantiene el rango existente y su OHLCV completo. No se entrenó IA, no se abrió otra búsqueda de parámetros, no se enviaron órdenes y no se hicieron commits ni push. El avance de este turno es documental y de auditoría causal, con una elección de réplica justificada por sus fuentes.

## Reproducibilidad de las fichas

```powershell
python -m research.trader_dossier.build_review_pack --output NUEVA_REVISION
python -m pytest tests/test_trader_review.py -q
```

El panel Plotly usa la dependencia ya existente en Docker, sin instalar nada nuevo ni reiniciar la aplicación:

```powershell
docker run --rm --entrypoint python --workdir /workspace -v C:/PROYECTOS/kronos/Kronos:/workspace:ro -v C:/PROYECTOS/kronos/Kronos/research/trader_dossier/reviews_20261017:/workspace/research/trader_dossier/reviews_20261017 kronos-kronos -m research.trader_dossier.render_review_charts --review research/trader_dossier/reviews_20261017
```

Para otra carpeta hay que adaptar ambos lados del segundo montaje y `--review`. El renderer rechaza sobrescribir el HTML existente. Las tres pruebas comprueban que cambiar cualquier OHLCV futuro no cambia las fichas, que el contexto excluye barras superiores incompletas y que la lista blanca no importa resultados. Los históricos e informes anteriores permanecen intactos.

Verificación final: 121 pruebas de datos, costes e investigación aprobadas y Ruff sin incidencias. La regeneración independiente del paquete produjo los mismos hashes para `cases.json` y sus doce CSV. [Manifest de trazabilidad](manifest.json). El HTML se generó correctamente; no se ha realizado una inspección visual en navegador de ese panel.
