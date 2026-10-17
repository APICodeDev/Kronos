# Continuación tras ruptura confirmada: resultados 1H/1x

El siguiente paso está ejecutado: una hipótesis independiente de continuación, con protocolo registrado antes del cálculo, control comparable y cartera con riesgo explícito. **Esta regla tampoco demuestra una ventaja rentable con los costes supuestos. No se recomienda operarla, entrenar IA sobre ella ni añadir filtros para rescatar el backtest.** Esto descarta una configuración concreta, no la posibilidad general de construir una estrategia rentable.

## Qué se ha probado

- XRPUSDT perpetuo de Bitget, velas de 1H, nominal máximo equivalente al margen a 1x. Sigue siendo un futuro, con financiación; no es spot.
- LONG si el cierre supera por un tick el máximo de las 20 horas anteriores; SHORT si cierra un tick por debajo del mínimo. Vela actual excluida del canal. Cada cierre válido genera un evento; no se añade un filtro de primera ruptura.
- Entrada en la apertura siguiente, con lotes y ticks ejecutables. Comisión supuesta del 0,06% en cada lado; deslizamiento adverso de 1 bp en entrada/TP/timeout y 2 bp en SL. No se presupone que estas sean las tarifas de la cuenta.
- Contraste principal de señal: salida al cierre de 6 horas, frente a horas sin esa señal emparejadas por segmento, mes UTC, bloque horario de ocho horas y banda causal de volatilidad. Cierres a 1 y 24 horas son diagnósticos secundarios; no se selecciona el mejor.
- Cartera separada: TP calculado para +1% neto sobre el margen efectivo antes de funding, SL en el extremo de la vela de señal más un tick y timeout de 6 horas. Máximo una posición, margen fijo máximo de 1.000 USDT, capital inicial de 10.000 USDT, sin reinversión. El riesgo no es constante porque la distancia al SL varía.

La motivación económica es persistencia después de una ruptura confirmada. [Liu y Tsyvinski](https://www.nber.org/papers/w24877) documentan momentum histórico en criptomonedas; sus horizontes diarios/semanales no son una prueba de esta regla horaria. No se ha afirmado replicar su resultado.

El [protocolo](momentum_protocol.json) fija criterios antes de ver los resultados. No se entrenó IA ni se exploraron variantes de parámetros.

## Datos y límites temporales

Se reutiliza el histórico anual validado y se **recorta el antiguo test antes de generar indicadores o resultados**: quedan fuera las 1.752 horas desde 2026-08-05 hasta 2026-10-17. No se ha vuelto a calcular su rendimiento para esta nueva familia.

- Investigación: 2025-10-17 a 2026-05-24, fin excluido.
- Validación: entradas desde 2026-05-25; resultados completos antes de 2026-08-05.
- Purga de 24 horas antes de las fronteras y embargo de 24 horas al empezar validación. Se aplica la misma elegibilidad a todos los perfiles y a la cartera, aunque el horizonte ejecutable sea de seis horas.
- Las 7.008 horas retenidas coinciden exactamente en OHLC con sus 84.096 subvelas de 5m, doce por hora. Sin huecos ni relleno.

Estos segmentos **ya se habían observado en investigaciones anteriores**. Llamarlos validación describe su ubicación cronológica; no los convierte en una nueva prueba independiente. Hay solo once bloques semanales con eventos de validación y menos de cien señales por dirección.

## Resultado de la señal sin TP/SL

Medias por evento con margen efectivo cercano a 1.000 USDT, después de comisiones y ejecución supuestas, sin funding. Los controles se ponderan con los mismos estratos que las señales. Las señales solapadas no se suman como capital.

| Validación | LONG, 66 emparejadas | SHORT, 89 emparejadas de 90 |
|---|---:|---:|
| Cierre a 1 hora | −0,8767 USDT | −3,0061 USDT |
| **Cierre a 6 horas, principal** | **−2,0614 USDT** | **−2,0679 USDT** |
| Cierre a 24 horas | −1,4417 USDT | −1,4766 USDT |

**Los seis perfiles son negativos.** A seis horas, LONG mejora al control en +0,4106 USDT, pero sigue perdiendo. SHORT queda −1,8807 USDT por debajo de su control. Las bandas ajustadas de exceso incluyen cero en ambos sentidos. No hay una superioridad neta y consistente frente a entradas comparables.

En investigación tampoco hay un perfil neto positivo: sus seis medias están entre −0,2457 y −3,7790 USDT. No apareció un horizonte ganador que se haya ocultado o seleccionado después. El informe conserva todos los perfiles, cobertura y bandas, no solo los de seis horas.

## Resultado de TP/SL y cartera

| Medida | Investigación | Validación |
|---|---:|---:|
| Eventos ejecutables | 506 | 156 |
| TP / SL / timeout | 222 / 193 / 91 | 43 / 60 / 53 |
| Media por evento | −0,5214 USDT | −1,6261 USDT |
| Operaciones de cartera, sin solapamiento | 405 | 118 |
| PnL de cartera | −303,91 USDT | −192,78 USDT |
| Factor de beneficio de cartera | 0,8605 | 0,6736 |

En conjunto: **523 operaciones, −496,69 USDT, −4,97% sobre el capital inicial de 10.000 USDT**, con drawdown máximo observado a cierre de 1H del **5,15%**. Es el período de investigación y validación retenido, no el año completo. No debe compararse directamente con los retornos anuales de otros informes que incluían el antiguo test.

Todas las barreras se recorrieron en 5m. En esta muestra no hubo ambigüedades finales ni entradas invalidadas por gap; el tratamiento conservador y la consulta de 1m permanecen disponibles y probados. Se resolvieron en 5m 518 eventos que tocaron una barrera; los otros 144 fueron timeout. No se eligieron máximos/mínimos futuros como precio de salida.

## Por qué pierde y cuánto cambia el funding

En los 156 eventos de validación, la atribución media es:

`−0,038756 referencia − 0,387761 ejecución − 1,199538 comisiones = −1,626055 USDT`

La ejecución incluye 0,238428 USDT de deslizamiento nominal y 0,149333 USDT de redondeo. Se comprueba la identidad por fila y el deslizamiento no se resta dos veces. **Eliminar solo las comisiones todavía deja −0,426517 USDT/evento** en esas mismas salidas. El PnL de referencia prácticamente nulo tampoco demuestra ventaja bruta estable. Son sensibilidades contables con entradas y salidas congeladas, no backtests con TP recalculado.

Un 43,59% de eventos termina con PnL positivo, frente a aproximadamente 53,92% necesario con sus pagos observados. Ganador medio: +7,2542 USDT; perdedor medio: −8,4881 USDT. Incluye timeout: ese porcentaje no es la tasa de TP. La pérdida neta prevista en el SL tiene mediana de 10,2028 USDT y máximo de 62,2070 USDT; el margen fijo no equivale a riesgo fijo ni garantiza el máximo ante un gap.

El bootstrap descriptivo por once semanas produce un intervalo percentil del 95% para la media neta por evento de validación de **[−3,1106; −0,1074] USDT**. No corrige las investigaciones anteriores ni elimina la incertidumbre de un solo activo y pocos regímenes.

Las tasas públicas cubren desde 2026-07-20: solo **43 de 156 eventos de validación** tienen cobertura completa. En esos mismos 43, el neto pasa de −0,89414 a −0,88475 USDT al estimar financiación; el pequeño cobro favorable no cambia su signo. Un TP del subconjunto baja del objetivo +1% después de la estimación. El resto no se trata como funding cero. Por tanto, **el resultado global sigue siendo provisional sin financiación completa**.

El mark se aproxima con la apertura de su vela nativa de 1m, con sensibilidad por extremos y posibles cobros en instantes de entrada/salida. No reproduce el cobro exacto de una cuenta. Tampoco se modelan profundidad histórica, latencia o ejecuciones parciales, y los metadatos actuales se aplican retrospectivamente.

## ¿Vale la pena seguir?

**No merece la pena avanzar con esta configuración hacia dinero real o entrenamiento.** Falla el criterio registrado: no tiene medias positivas en ambas direcciones a seis horas, las bandas no respaldan superioridad y la cartera de validación pierde. La reversión anterior y esta continuación son dos reglas concretas que no funcionan aquí; eso no demuestra que cualquier estrategia sea imposible.

Sí puede tener sentido continuar como investigación acotada. El cuello de botella ahora es obtener evidencia nueva y una ventaja mayor que el coste de ida y vuelta, no añadir capacidad de cálculo. Los pasos razonables son:

1. **Ampliar y reservar datos antes de probar más reglas.** Intentar obtener más historia y varios contratos líquidos, registrando cobertura real, funding, tick/lote y tarifas asumidas. Separar físicamente un tramo no examinado y dejarlo fuera del proceso de diseño. El antiguo test ya conocido no recupera su independencia por cambiarle el nombre.
2. **Registrar una sola hipótesis económica nueva y su presupuesto de investigación.** Mantener la detección en 1H si se conserva esta preferencia; definir de antemano horizonte, riesgo, costes, referencia y abandono. Un horizonte de mantenimiento mayor no cambia la temporalidad de las velas, pero sería otro experimento y no un rescate escogido por este resultado.
3. **Exigir rentabilidad neta y estabilidad**, frente a controles y en cartera, con cobertura de costes suficiente y muestra por dirección/régimen; mostrar todos los intentos. Si no aparece, detener esa línea.
4. **Solo ante evidencia favorable, congelar y observar datos posteriores** en simulación. La IA o una integración operativa vendrían después de esa comprobación, si aportan una mejora medible.

No se ha iniciado esa ampliación ni elegido otra estrategia en este turno: las conclusiones anteriores corresponden al experimento realmente ejecutado. No se programaron tareas, se entrenaron modelos ni se enviaron órdenes.

## Verificación y reproducción

- **99 pruebas de investigación aprobadas**, incluidas once nuevas comprobaciones de la familia de continuación; **19 pruebas de interfaz/Kraken aprobadas** en el contenedor existente. Ruff y revisión de whitespace sin errores. Hay avisos de deprecación de pandas/Plotly en utilidades anteriores, sin fallos de prueba.
- **39.516 filas de señales/controles** verificadas con Decimal y **1.947 filas emparejadas** contrastadas; son filas repetidas por horizonte/dirección, no operaciones independientes.
- **662 eventos y 265 TP** recalculados de forma independiente; **1.185 filas de atribución** de eventos/cartera comprobadas, incluidas 69 filas con funding completo. Evento y su operación de cartera se verifican por separado.
- Conjunto completo de señales reconstruido directamente desde OHLC, sin importar el detector; se verifica la exclusión temporal y se comprueban **523 operaciones sin solapamiento**, con capital suficiente. Error financiero máximo del estudio: 2,108 × 10⁻¹²; error de acumulación de capital: 2,300 × 10⁻¹¹ USDT, inferiores a 0,000001.
- **Repetición sin red: 17 archivos idénticos por SHA-256**, incluidos informes, resumen, CSV, resoluciones y manifiestos. [Comparación reproducible](reports/momentum_20261017/reproducibility.json). El código de los experimentos anteriores permanece intacto; el único archivo anterior modificado es README.md para enlazar el nuevo trabajo.
- Los informes y el código de experimentos previos se conservan. No se hicieron commits ni push.

[Informe completo](reports/momentum_20261017/REPORT.md) · [Resultados](reports/momentum_20261017/summary.json) · [Verificación independiente](reports/momentum_20261017/momentum_verification.json) · [Hashes](reports/momentum_20261017/manifest.json).

```powershell
# Primera ejecución: solo consultas públicas cuando sean necesarias.
python -m research.false_breakout.study_momentum --output NUEVO_DIRECTORIO
python -m research.false_breakout.verify_momentum --report NUEVO_DIRECTORIO

# Repetición con datos, funding y caché conservados; otro directorio.
python -m research.false_breakout.study_momentum --output OTRO_DIRECTORIO --offline
python -m research.false_breakout.verify_momentum --report OTRO_DIRECTORIO

python -m pytest tests/test_momentum.py tests/test_signal_study.py tests/test_hourly.py tests/test_economic_diagnosis.py tests/test_bitget_data.py tests/test_costs.py tests/test_false_breakout.py -q
```

Las versiones y hashes del código sin commit están registrados en `manifest.json`; `git_head` por sí solo no identifica el nuevo código. Los CSV grandes siguen locales e ignorados por Git; conservarlos junto con `webui/uploads` para reproducir sin red. Los comandos completos están en `command.txt`.
