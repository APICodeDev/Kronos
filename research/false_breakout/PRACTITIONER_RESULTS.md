# Aplicación de métodos publicados: precio, volumen, entrada y riesgo

Se buscaron fuentes de operadores y firmas y **se aplicó un proceso de selección completo** al histórico local de XRPUSDT, sin ampliar fechas ni contratos: impulso → retroceso → confirmación → invalidación → tamaño → espacio/objetivo → operar o rechazar. Las fuentes y su traducción están en [PRACTITIONER_RESEARCH.md](PRACTITIONER_RESEARCH.md); los umbrales se guardaron antes del cálculo en [practitioner_protocol.json](practitioner_protocol.json).

**No se ha demostrado una ventaja rentable.** La primera interpretación resultó excesivamente restrictiva y aceptó solo una operación. La revisión dio lugar a una segunda interpretación swing explícita, que conserva todos los planes financieros y permite superar el extremo anterior: su cartera principal gana 13,24 USDT en investigación y pierde 63,91 USDT en ocho operaciones de validación. Ambos ensayos se conservan; no se presenta el segundo como prueba independiente ni se elige un ganador.

## Qué se incorporó de las publicaciones

- Grimes: buscar un impulso y esperar el retroceso antes de entrar al reanudarse el movimiento.
- SMB: identificar niveles, observar la participación y relacionar la localización de entrada con dónde queda invalidada la idea.
- Morpheus: impulso con actividad, retroceso de menor volumen y aumento al confirmar.
- Brooks: stop basado en estructura, cantidad adaptada al riesgo y objetivo swing de al menos dos veces el riesgo.
- Bellafiore: convertir el setup en un playbook y revisar también los rechazos, no solo las operaciones ganadoras.

Los enlaces concretos están en el documento de fuentes. Son ideas publicadas, no historiales de rentabilidad auditados. La implementación combina elementos compatibles de esas publicaciones, pero **no es una reproducción completa de la discreción de sus autores**. La restricción de salir antes del extremo de la vela impulsiva es una elección nuestra y no una exigencia universal de los métodos citados.

## Datos y ejecución

Se mantienen OHLC, volumen y turnover del año existente. Para este contraste se retienen 7.008 velas de 1H hasta 2026-08-05, con 84.096 subvelas de 5m. El antiguo test permanece excluido antes de detectar oportunidades; no se han calculado sus salidas con esta familia. Investigación y validación ya estaban observadas en otros trabajos y no se llaman independientes.

Las doce subvelas coinciden con cada OHLC de 1H. La diferencia máxima de volumen agregado es 3,726 × 10⁻⁹ XRP, compatible con coma flotante. El turnover tiene redondeos nativos: diferencia absoluta máxima de 0,0005 USDT, relativa máxima inferior a 4,7 × 10⁻¹². Sin huecos, volumen ausente o relleno de datos.

Entrada siguiente, 1x, margen máximo de 1.000 USDT, capital inicial de 10.000 USDT y una sola posición. Cantidad limitada para que la pérdida prevista en SL, con comisiones y ejecución, no supere 25 USDT; un gap podría exceder ese importe. Objetivo: máximo entre +1% neto de margen y 2R netos. Horizonte fijo de mantenimiento de 24 horas sobre señales de 1H, sin probar una lista de horizontes. Comisiones supuestas del 0,06% por lado y deslizamiento adverso, sin descontarlo dos veces.

## Embudo real

| Etapa | Resultado |
|---|---:|
| Impulsos de precio detectados | 328 |
| Retrocesos con confirmación, deduplicados | 88 |
| Elegibles tras purga/embargo de 24h | 87 |
| Cumplen además las tres condiciones de volumen | 56 |
| Rechazados por espacio, sin exigir volumen | 86 de 87 |
| Rechazados por espacio, con volumen | 55 de 56 |
| Operaciones aceptadas | 1, compartida por ambos libros |
| Operaciones aceptadas en validación | 0 |

En investigación hay 69 setups estructurales, 48 con volumen; en validación, 18 estructurales, ocho con volumen. Una confirmación adicional queda fuera de las ventanas elegibles. **La falta de operaciones no procede de velas incompletas ni de falta de volumen: procede de nuestra regla de entrada/objetivo/espacio.**

No se seleccionó el libro de mejor rendimiento ni se bajaron umbrales después de observar las salidas. El único evento ejecutado es el mismo en ambas variantes; por tanto, no se puede concluir que el volumen haya mejorado o empeorado la rentabilidad.

## Qué bloquea las entradas

La revisión de los planes guardados, usando solo información anterior a la entrada, encuentra:

- En **60 de los 87** setups, el fill de entrada ya está más allá del extremo de la vela impulsiva elegida como primera barrera. Entre los 56 con volumen ocurre en 39. El movimiento puede haberse extendido entre impulso y retroceso; mantener como límite el extremo de una sola vela es especialmente restrictivo.
- Con los costes y el margen originales, el objetivo fijo de +1% por sí solo cabe antes de ese extremo en solo **cuatro de 87** casos; tres de los 56 con volumen. Es un diagnóstico de viabilidad del plan, sin calcular cómo habrían terminado operaciones rechazadas.
- Al exigir también 2R netos, solo queda **uno**. La escasez no la produce principalmente el volumen.

**Esta revisión señala un problema de traducción del método:** hemos combinado esperar confirmación, exigir +1% neto, recompensa 2R y limitar todo el recorrido al extremo de la vela inicial. Esa combinación casi elimina la operativa. No debe presentarse como una refutación de los operadores ni como razón para pedir más datos. Cambiar el modelo de objetivo o la definición del tramo impulsivo sería otra hipótesis explícita; no se ha hecho silenciosamente para mejorar el resultado.

## Dos fichas concretas

Importes de precio en USDT por XRP; timestamps UTC.

| Campo | Aceptada: SHORT, entrada 19/01/2026 06:00 | Rechazada: LONG, entrada propuesta 24/10/2025 19:00 |
|---|---:|---:|
| Apertura de entrada | 1,9602 | 2,4899 |
| Fill tras deslizamiento/tick | 1,9600 | 2,4902 |
| Stop estructural | 1,9735 | 2,4589 |
| Objetivo calculado | 1,9249 | 2,5631 |
| Extremo previo usado como límite | 1,8392 | 2,4984 |
| Volumen relativo del impulso | 41,67 | 7,14 |
| Pérdida neta prevista en SL | 8,2928 USDT | 13,9424 USDT |
| Beneficio neto previsto en TP | 16,6102 USDT | 27,8968 USDT |
| Decisión | Entrar; acaba en SL | No entrar: el TP supera la barrera |

El rechazo muestra que volumen elevado no basta para obtener una entrada atractiva con este plan. El caso aceptado muestra que un volumen excepcional y un plan coherente tampoco garantizan ganar una operación.

Son los primeros casos por fecha de cada clase, no los escogidos por sus beneficios. [cases.json](reports/practitioner_20261017/cases.json) conserva las fichas completas. `diagnostic_setups.csv` guarda todas las oportunidades; los CSV de cada libro añaden aceptación/rechazo y resultado. Las operaciones rechazadas no tienen PnL inventado.

## Segunda interpretación: swing con objetivo de 2R

La revisión anterior exigía corregir la traducción antes de evaluar el método publicado. Se hizo dentro de este mismo trabajo: [protocolo swing](practitioner_swing_protocol.json), registrado después de ver la escasez del primer ensayo y **antes de calcular las salidas de las oportunidades rechazadas**. Brooks contempla continuación con nuevos extremos, por lo que no exige mantener el TP antes del high/low de una sola vela inicial.

No se cambiaron señales, niveles, volumen, entrada, cantidad, stop, trigger TP o mantenimiento de 24 horas. Solo se retiró el veto de superar el extremo anterior. Esta decisión tiene sesgo de selección entre interpretaciones y se declara; no es una optimización automática ni una validación nueva. El verificador comprueba la identidad de cada plan contra el CSV del primer ensayo.

| Cartera swing | Investigación: operaciones / PnL | Validación: operaciones / PnL |
|---|---:|---:|
| Estructura sin exigir volumen | 58 / +12,80 USDT | 18 / −90,58 USDT |
| **Estructura + volumen, principal** | **41 / +13,24 USDT** | **8 / −63,91 USDT** |

En la principal, los 48 eventos de investigación tienen media +0,4369 USDT y los ocho de validación −7,9882 USDT. En validación hay un TP, seis SL y un timeout; el factor de beneficio de cartera es 0,1819. Hay dos resultados con PnL positivo porque el timeout también gana una cantidad pequeña. Ganador medio +7,1050 USDT, perdedor medio −13,0192 USDT: un objetivo nominal de 2R no implica que todas las ganancias realizadas sean 2R, porque existe timeout.

La cartera principal conjunta termina en **−50,66 USDT sobre 10.000 iniciales (−0,507%)**, con drawdown a cierre de 1H de 1,327%. La de estructura termina en −77,78 USDT. Estos importes no son el año completo: se mantiene excluido el antiguo test. Las sumas de eventos solapados no se presentan como capital.

La atribución por evento de validación con volumen es:

`−6,387738 referencia − 0,399700 ejecución − 1,200713 comisiones = −7,988150 USDT`

Con esos mismos planes y salidas, quitar solo las comisiones deja −6,787438 USDT; quitar además costes de ejecución deja −6,387738 USDT. En esta muestra el problema no se reduce a las tarifas. Se conserva el SL de hasta 25 USDT previsto, sin asegurar esa pérdida máxima frente a gaps.

El intervalo percentil semanal descriptivo de la media principal en validación es [−13,9745; +0,0534] USDT, con solo siete semanas y ocho eventos. No respalda declarar ventaja ni permite una conclusión fuerte sobre el método humano. Un evento LONG pierde −16,84 USDT y siete SHORT suman −47,06 USDT; tampoco se selecciona dirección después de verlos.

El volumen reduce 18 a ocho eventos de validación y, en esta muestra, deja una media más negativa. No puede afirmarse que añadirlo mejore la selección: son grupos pequeños, dependientes y observacionales. En la variante principal, solo dos de ocho eventos tienen cobertura de funding; el resto sigue siendo desconocido. Las cifras generales son provisionales, no neto completo.

[Informe swing completo](reports/practitioner_swing_20261017_v2/REPORT.md) · [Todos los resultados](reports/practitioner_swing_20261017_v2/summary.json) · [Verificación de planes y cuentas](reports/practitioner_swing_20261017_v2/verification.json).

## Conclusión dentro del rango actual

La búsqueda publicada sí cambia cómo se define una oportunidad: ahora importan la secuencia, el volumen, el punto de invalidación y la relación entre entrada, riesgo y recorrido. Ese proceso ya está implementado, probado y es revisable por evento.

**Todavía no se ha encontrado una estrategia rentable.** El primer ensayo no tuvo muestra operativa suficiente; el segundo sí ejecuta las configuraciones pero no mantiene el resultado positivo de investigación en validación. No sería correcto anunciar un 0% de acierto como conclusión estadística del primer ensayo, atribuir el problema a datos incompletos o asegurar que los métodos humanos no funcionan.

Se ha aplicado y comprobado la interpretación de continuación con objetivo swing, conservando el ensayo previo. No se siguen bajando umbrales ni añadiendo indicadores hasta encontrar beneficios. Cualquier nueva hipótesis debe concretar qué parte observable del juicio del operador se espera que aporte ventaja y fijarse antes de otra evaluación; no basta invocar experiencia o volumen. Se mantiene la instrucción del usuario: **no ampliar el rango de datos**. No se ha entrenado IA ni operado dinero.

## Verificación y repetición

El verificador reconstruye independientemente los 328 impulsos, las 88 confirmaciones y las decisiones de los 87/56 candidatos directamente desde OHLCV, sin importar el detector. Recalcula stop, precios adversos, riesgo, recompensa, objetivo, espacio y límites temporales. Decimal comprueba el único evento y su operación secuencial en cada libro. El evento es compartido, no dos operaciones distintas.

El error financiero máximo del evento es 1,2 × 10⁻¹⁴ USDT y el de atribución 4,6 × 10⁻¹⁴, inferiores a 0,000001. No hay cobertura de funding para la operación de enero: el −8,2928 sigue siendo provisional, no neto completo. La cobertura incompleta no se sustituye por cero conocido.

En swing, se verifican **87 planes estructurales y su subconjunto de 56 con volumen**, con 76 y 49 operaciones de cartera respectivamente. Decimal comprueba 268 filas de atribución contando eventos y sus operaciones de cartera por separado; no son 268 operaciones independientes. Error máximo de atribución: 2,7162 × 10⁻¹³ USDT. Se comprobó que las entradas, stops, tamaños y objetivos eran idénticos a los planes del primer ensayo.

**118 pruebas de investigación y 19 de interfaz/Kraken aprobadas**; Ruff sin errores. El primer ensayo se repitió sin red con **24 archivos idénticos por hash**. El sufijo `v2` del informe swing corresponde a corregir la normalización de rutas Windows en el verificador; no a cambiar la estrategia o sus resultados. Se conservó la ejecución inicial y se regeneró en un directorio nuevo.

La repetición swing sin red produce **22 archivos idénticos por hash**, incluidos los manifiestos. Otros 19 archivos de resultados coinciden exactamente entre la ejecución previa y la regenerada tras corregir el verificador. [Reproducción inicial](reports/practitioner_20261017/reproducibility.json) · [Reproducción swing y comparación](reports/practitioner_swing_20261017_v2/reproducibility.json). Los importes por operación y las rentabilidades sobre margen usan cantidades efectivas variables por el límite de riesgo; la media de rentabilidades no equivale al PnL agregado dividido por un margen constante.

[Informe generado](reports/practitioner_20261017/REPORT.md) · [Resultados](reports/practitioner_20261017/summary.json) · [Verificación](reports/practitioner_20261017/verification.json) · [Protocolo](practitioner_protocol.json).

```powershell
python -m research.false_breakout.run_practitioner --output NUEVO_DIRECTORIO
python -m research.false_breakout.verify_practitioner --report NUEVO_DIRECTORIO
python -m research.false_breakout.run_practitioner --output OTRO_DIRECTORIO --offline
python -m research.false_breakout.verify_practitioner --report OTRO_DIRECTORIO

# Segunda interpretación, sobre los planes congelados del primer ensayo.
python -m research.false_breakout.practitioner_swing --output NUEVO_SWING
python -m research.false_breakout.verify_practitioner_swing --report NUEVO_SWING
python -m research.false_breakout.practitioner_swing --output OTRO_SWING --offline

python -m pytest tests/test_practitioner_swing.py tests/test_practitioner.py tests/test_momentum.py tests/test_signal_study.py tests/test_hourly.py tests/test_economic_diagnosis.py tests/test_bitget_data.py tests/test_costs.py tests/test_false_breakout.py -q
```

Se conservan datos, código e informes anteriores, incluidos los cambios locales heredados de momentum. Sin commits ni push. Los manifiestos registran versiones y hashes del código sin commit, entradas, caché, funding y salidas; los CSV grandes permanecen locales e ignorados por Git.
