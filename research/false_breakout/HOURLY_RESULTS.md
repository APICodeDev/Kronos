# Conclusiones: 1H sin apalancamiento — 17-10-2026

**La variante de 1 hora tampoco encuentra ventaja con los supuestos fijados. Mi recomendación es cerrar esta configuración, sin entrenar IA ni seguir cambiando temporalidades u horizontes buscando uno rentable.**

Se ejecutó XRPUSDT perpetuo USDT-FUTURES a 1x: 20 velas previas de 1H, entrada en apertura siguiente, SL con un tick, TP de al menos +1 % sobre el margen efectivo tras costes previstos y **seis horas de duración máxima —seis velas, no 72 horas—**. Margen máximo de 1.000 USDT, capital inicial 10.000 USDT, una posición por símbolo y sin reinversión. Se mantuvieron las comisiones y el slippage del experimento anterior. No se ensayaron otras configuraciones para escoger un resultado favorable.

## Resultados concretos

Período UTC: 17-10-2025 a 17-10-2026, fin excluido. Las 8.760 velas nativas de 1H coinciden exactamente en OHLC con sus 105.120 subvelas de 5m, sin huecos. Se detectaron 519 LONG, 393 SHORT y 2 señales duales: **914 candidatos**, 907 eventos elegibles tras exclusiones y **903 operaciones de cartera**.

| Resultado | Año completo | Tramo final exploratorio |
|---|---:|---:|
| Operaciones de cartera | 903 | 184 |
| PnL cartera sin funding | −1.708,07 USDT | −464,49 USDT |
| Media neta por evento elegible | −1,8845 USDT | −2,5244 USDT |
| Factor de beneficio por evento | 0,6018 | 0,5053 |

El capital final es **8.291,93 USDT**, una pérdida del **17,08 %** sobre el capital inicial. El drawdown máximo medido a cierre de 1H es **17,32 %**; no incluye extremos intrabar. Todos los tramos mensuales de cartera son negativos, incluidos los dos meses parciales en los extremos del intervalo. Discovery, validation y test también tienen expectativa negativa.

En el tramo final hay **42 TP_FIRST, 120 SL_FIRST y 22 TIMEOUT**. No queda ninguna ambigüedad de ejecución sin resolver en los eventos elegibles. Se recorrieron las subvelas de 5m para todas las salidas por barrera; una ambigüedad dentro de 5m necesitó datos de 1m. Los dos barridos duales y dos candidatos sin horizonte completo se excluyeron; hubo además dos candidatos purgados y uno en embargo.

## Qué cambia respecto a 5m

| Tramo final: eventos a 1x | 5m anterior | 1H actual |
|---|---:|---:|
| Eventos ejecutables | 1.893 | 184 |
| PnL medio sin funding | −1,4822 USDT | −2,5244 USDT |
| Operaciones con PnL positivo | 17,12 % | 30,98 % |
| Acierto necesario para equilibrio con pagos observados | 28,76 % | 47,04 % |
| Ganador medio | +9,0667 USDT | +8,3246 USDT |
| Perdedor medio | −3,6606 USDT | −7,3936 USDT |

El acierto incluye TIMEOUT con beneficio; no equivale a alcanzar el TP. El equilibrio mantiene el tamaño observado de ganadores y perdedores, condicionado a resultados distintos de cero: no es una probabilidad aprendida ni un umbral que pueda aplicarse directamente como filtro.

**1H reduce la actividad y la pérdida acumulada, pero empeora la pérdida por operación.** La mayor tasa de acierto no compensa que el perdedor medio se duplique. El capital dura más porque se hacen menos operaciones; eso no convierte la regla en rentable. Esta comparación modifica también la ventana de niveles de 100 minutos a 20 horas, por lo que no aísla únicamente un efecto de ruido temporal.

## No es solo un problema de comisiones

En cada evento final de 1H, en promedio:

```text
PnL a precios de referencia       −0,9683 USDT
Coste de ejecución                −0,3574 USDT
Comisiones                       −1,1986 USDT
PnL neto sin funding              −2,5244 USDT
```

El coste de ejecución contiene slippage nominal y redondeo al tick. Se comprueba que no se descuenta dos veces. A diferencia del pequeño resultado de referencia positivo visto en 5m, **en 1H la media de referencia de test ya es negativa**.

Incluso eliminando aritméticamente todas las comisiones y costes de ejecución sobre estas mismas salidas, la media seguiría siendo −0,9683 USDT. Esto es una atribución contable con barreras y salidas congeladas, no el resultado de recalcular una estrategia sin costes ni una prueba de que cualquier variante de 1H vaya a fallar.

El funding público cubre los **184 eventos finales**. Tras estimarlo, la media pasa a **−2,5263 USDT**; no cambia la conclusión. El ajuste usa tasas reales y la apertura de velas mark 1m como aproximación al precio de liquidación. Su sensibilidad favorable/desfavorable sigue siendo negativa. Dos TP originales de test quedarían por debajo del +1 % tras ese funding estimado; no necesariamente pasarían a ser pérdidas. El año completo continúa sin financiación completa y no se ha rehecho la secuencia de cartera con funding. Por ello no se presenta como neto completo.

## Direcciones e incertidumbre

En test, LONG registra 95 eventos con media de **−3,3658 USDT** y SHORT 89 con **−1,6263 USDT**. Ambos pierden; cada dirección tiene menos de 100 eventos y no se selecciona SHORT por ser menos negativo.

El bootstrap descriptivo por 11 bloques de semana UTC, con 5.000 remuestreos y semilla fija, sitúa el intervalo del 95 % de la media neta en **−3,3317 a −1,8171 USDT**. El intervalo de referencia también queda negativo: **−1,7713 a −0,2614 USDT**. Los bloques extremos son parciales; pocos bloques, eventos solapados y una única criptomoneda limitan la generalización.

**Este es un análisis exploratorio sobre datos ya observados.** Se respetan las fronteras cronológicas 60/20/20, la purga y el embargo de seis horas, pero el antiguo test no recupera su condición de conjunto intacto. No se deben interpretar estos intervalos como garantía sobre datos futuros.

## Recomendación

1. Cerrar las configuraciones estudiadas de falso rompimiento en 5m y 1H con horizonte de seis horas. Ninguna muestra la ventaja requerida bajo sus supuestos.
2. Conservar el descargador y el banco de pruebas. No dedicar recursos ahora a entrenar Kronos o a filtrar esta regla para intentar rescatarla.
3. Si se continúa investigando, registrar una hipótesis diferente y un control simple antes de probarla. Diseñarla con el histórico ya observado y reservar datos posteriores sin examinar para la evaluación final.
4. Confirmar costes efectivos y ejecución en simulación. Exigir expectativa positiva tras costes y funding, suficiente muestra y estabilidad temporal. Si no supera ese criterio, parar también esa hipótesis.

No se han implementado esas nuevas fases ni enviado órdenes. Sigue siendo un futuro perpetuo a 1x, con funding; no se cambió a mercado spot.

## Verificación y reproducción

- **78 pruebas locales aprobadas**, incluidas 9 nuevas de 1H. **19 pruebas de Kraken/interfaz aprobadas** en contenedor independiente y repositorio read-only: 97 pruebas ejecutadas en esta fase. Ruff sin incidencias.
- Verificación Decimal independiente: **910 eventos con resultado calculado y 233 TP** cumplen la contabilidad y el objetivo previsto sin funding. Incluye tres eventos con PnL posteriormente excluidos por purga/embargo; no todos entran en la cartera.
- Atribución y funding contrastados independientemente en **1.810 filas** de eventos/cartera, con error máximo **3,6841 × 10⁻¹³ USDT**. Las filas de ambos libros pueden representar la misma operación; no constituyen muestras adicionales.
- Repetición offline: **12 archivos idénticos por hash**.
- Regresión histórica 5m: **16 archivos idénticos**, incluidos los 12 CSV de eventos/cartera/capital de los cuatro apalancamientos, el resumen y el informe. La adaptación temporal no altera los resultados anteriores. Ningún dato o informe original se sobrescribió.
- Se partió del HEAD del usuario `85d4dfe`, con árbol limpio. Se añadieron duración configurable 5m/1H, ejecución intrahora y un CLI separado; el CLI antiguo rechaza configuraciones 1H para impedir una carga accidental de 5m. Se conservó la funcionalidad anterior. Sin IA, commits ni push.

[Informe generado](reports/hourly_20261017/REPORT.md) · [Resumen estructurado](reports/hourly_20261017/summary.json) · [Configuración](config_hourly.json) · [Validación](reports/hourly_20261017/validation.json) · [Hashes y procedencia](reports/hourly_20261017/manifest.json) · [Reproducción y regresión 5m](reports/hourly_20261017/reproducibility.json).

Desde la raíz, usando el entorno del README:

```powershell
python -m research.false_breakout.run_hourly --output NUEVO_DIRECTORIO --offline
python -m research.false_breakout.verify_results --report NUEVO_DIRECTORIO
python -m research.false_breakout.verify_diagnosis --report NUEVO_DIRECTORIO --funding webui/uploads/bitget_hourly_funding_20261017
python -m pytest tests/test_hourly.py tests/test_economic_diagnosis.py tests/test_bitget_data.py tests/test_costs.py tests/test_false_breakout.py -q
```

Los dos verificadores imprimen sus comprobaciones y escriben por defecto `financial_verification.json`; guardar o renombrar la salida del primero antes de ejecutar el segundo si se desea conservar ambos JSON. En el informe entregado se conservaron por separado `tp_financial_verification.json` y `financial_verification.json`. `command.txt` explicita todas las rutas. Los datos de funding y de resolución 1m están en directorios nuevos bajo `webui/uploads`, escribibles e ignorados por Git; las tablas grandes siguen siendo locales.
