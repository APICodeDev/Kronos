# Conclusiones del diagnóstico económico — 17-10-2026

**Recomendación: cerrar esta versión de la regla como candidata operativa. La infraestructura sirve para investigar, pero estos resultados no justifican seguir afinando este patrón ni entrenar IA.** Si se continúa, que sea con una sola hipótesis nueva, registrada antes de probarla, y un presupuesto de investigación limitado.

## Qué explica las pérdidas

En los **1.893 eventos ejecutables de test**, la atribución media por operación es:

| Apalancamiento supuesto | PnL a precios de referencia | Coste de ejecución, incluido tick | Comisiones | PnL neto sin funding |
|---|---:|---:|---:|---:|
| 1x | +0,0840 | 0,3669 | 1,1993 | −1,4822 |
| 3x | +0,1571 | 1,0717 | 3,5994 | −4,5140 |
| 5x | +0,1919 | 1,7585 | 5,9993 | −7,5659 |
| 10x | +0,1297 | 3,4593 | 11,9993 | −15,3289 |

Importes en USDT, para margen efectivo cercano a 1.000 USDT. El coste de ejecución incluye el deslizamiento adverso supuesto y el redondeo al tick; no es una medición de spread real. En 1x se descompone en 0,2820 USDT de slippage nominal y 0,0850 de redondeo.

Esto precisa la conclusión inicial: el PnL bruto de los fills ya era negativo antes de comisiones, pero **al eliminar aritméticamente también el coste de ejecución aparece una media de referencia ligeramente positiva**. Es demasiado pequeña para los costes modelados. No es una estrategia sin costes recalculada: se mantienen cantidades, TP, SL y salidas originales, que se diseñaron con los costes del baseline.

Esa pequeña media de referencia tampoco demuestra una ventaja: su intervalo descriptivo del 95 % en 1x es **−0,0934 a +0,2513 USDT**, mediante bootstrap agrupado por semana. En los otros tres escenarios el intervalo de referencia también contiene cero. El intervalo de la media neta queda íntegramente negativo en los cuatro. Solo hay 11 bloques semanales en test; se remuestrea todo lo observado de cada semana, y los bloques de los extremos pueden ser semanas parciales. No se supone independencia entre eventos ni estabilidad futura del mercado.

## Por qué más apalancamiento no lo arregla

| Escenario test | Operaciones con PnL positivo | Acierto necesario para equilibrio | Ganador medio | Perdedor medio |
|---|---:|---:|---:|---:|
| 1x | 17,12 % | 28,76 % | +9,0667 | −3,6606 |
| 3x | 29,27 % | 51,15 % | +10,0750 | −10,5501 |
| 5x | 35,45 % | 62,98 % | +10,1735 | −17,3066 |
| 10x | 42,26 % | 76,70 % | +10,3712 | −34,1396 |

El equilibrio se calcula como pérdida media / (ganancia media + pérdida media), manteniendo los pagos observados, condicionado a PnL distinto de cero. Incluye timeout positivos/negativos: **no es la tasa de alcanzar TP** ni una probabilidad que pueda usarse directamente como filtro.

Al aumentar el nominal con apalancamiento, crecen costes y pérdidas mientras el TP sigue buscando unos 10 USDT sobre el margen. En test, el SL previsto mediano pasa de unos 3,28 USDT en 1x a 32,80 en 10x. La mayor tasa de acierto queda lejos de compensar el tamaño de los perdedores. LONG y SHORT pierden por separado en los cuatro escenarios.

## ¿Servirían mejores comisiones, funding o resolver ambigüedades?

- **Comisiones cero con las mismas ejecuciones:** las medias de test seguirían en −0,2829 / −0,9146 / −1,5666 / −3,3296 USDT. Reducir solo la tarifa no basta en estas trayectorias. Una entrada maker distinta requeriría otra hipótesis y un modelo de ejecución; no se presume que una orden de mercado tenga tarifa maker.
- **Ejecución ideal con las comisiones actuales:** también seguiría perdiendo. El JSON guarda estos escenarios como descomposición de costes, sin elegir uno como estrategia ganadora.
- **Ambigüedades:** incluso sustituyendo por TP todas las ambigüedades de ejecución de test, las medias siguen siendo negativas. Las etiquetas conservadoras originales no se modificaron.
- **Funding:** se descargaron 270 tasas públicas, del 20-07-2026 al 17-10-2026, sin huecos en el horario de 8 h observado. Se usaron 190 velas nativas mark 1m. Cubren el test completo, pero no todo el año. La estimación deja medias de **−1,48218 / −4,51380 / −7,56447 / −15,32540 USDT**. Su efecto agregado es demasiado pequeño para cambiar la conclusión.

El funding usa el mark de apertura del minuto como aproximación, no el precio de liquidación exacto. Se muestra una sensibilidad al rango de ese minuto y a entrar/salir en el instante de liquidación. El resultado sigue siendo negativo incluso con la sensibilidad favorable. No se recalculan posiciones, capital o TP con información futura. El año completo sigue sin funding completo y las tarifas reales de cuenta continúan sin confirmar.

Hay una consecuencia para el objetivo económico: en 1x, **28 TP originales de test** caerían por debajo del +1 % sobre margen al descontar el funding estimado. El beneficio no se vuelve necesariamente negativo, pero deja de cumplir ese objetivo. Cualquier hipótesis futura deberá reservar costes de financiación con información disponible al entrar y evaluar después el resultado realizado, sin conocer de antemano las tasas futuras.

## ¿Vale la pena seguir?

**Con esta regla, mi recomendación es parar.** Los resultados no justifican entrenar Kronos, buscar decenas de filtros, aumentar apalancamiento ni preparar trading real. Tampoco prueban que todo patrón de falso rompimiento sea imposible; descartan la combinación concreta de entrada, gestión y costes estudiada.

**Con el proyecto, tiene sentido conservar lo construido como banco de pruebas.** Ya permite rechazar hipótesis con datos públicos, causalidad y contabilidad comprobada. Solo dedicaría un siguiente ciclo acotado a una hipótesis diferente con una razón de mercado clara; no hay evidencia actual que permita prometer que vaya a compensar el tiempo invertido.

Los siguientes pasos, si se decide continuar, serían:

1. Archivar este experimento y sus diagnósticos como resultado negativo, manteniendo las reglas y salidas originales.
2. Establecer recogida incremental de velas, tasas y mark, y reservar un tramo posterior no examinado. El año utilizado y su antiguo test sirven ya como datos exploratorios; no vuelven a ser un test intacto.
3. Escribir una única hipótesis nueva y un control simple antes de ejecutarlos: motivo, entrada, invalidación, horizonte, tamaño, tratamiento de costes y criterio explícito de abandono. Registrar todas las variantes que se exploren.
4. Confirmar manualmente la tarifa efectiva de cuenta y comprobar ejecución en simulación. Si el resultado depende de unos pocos céntimos de margen o de conseguir fills maker no demostrados, no considerarlo operable.
5. Validar cronológicamente con purga/embargo, costes y financiación realistas, suficientes bloques temporales y regímenes, y comparar con el control. Cien eventos finales es solo un mínimo de prudencia, no una garantía estadística. Si no aparece expectativa positiva tras costes, cerrar también esa hipótesis.
6. Solo si aparece una línea base defendible, evaluar un clasificador pequeño con un nuevo test reservado. No se ha iniciado ninguna de estas nuevas fases en este trabajo.

## Qué se ha ejecutado y dónde comprobarlo

- **69 pruebas locales aprobadas:** las 50 de la línea base y 19 del diagnóstico; Ruff sin incidencias.
- **19 pruebas de interfaz/Kraken aprobadas** en contenedor independiente, con el repositorio como solo lectura. El servicio existente y el modelo no se modificaron.
- Recomputación independiente con Decimal de **48.291 filas** de eventos/cartera, de las que **10.486 tienen cobertura de funding**; algunas operaciones aparecen tanto en eventos como en cartera y no son muestras independientes adicionales. Error máximo **3,664 × 10⁻¹² USDT**. Las filas sin cobertura nunca se trataron como coste cero.
- Repetición del diagnóstico con entradas locales y sin consultas de red; el resultado de la comparación por hash se conserva en `reproducibility.json` junto al informe.

[Informe generado](reports/diagnosis_20261017/REPORT.md) · [Resultados estructurados](reports/diagnosis_20261017/summary.json) · [Verificación independiente](reports/diagnosis_20261017/financial_verification.json) · [Procedencia y hashes](reports/diagnosis_20261017/manifest.json).

## Comandos reproducibles

Desde la raíz del repositorio, con el entorno de investigación del README:

```powershell
python -m research.false_breakout.funding_data --baseline research/false_breakout/reports/baseline_20261017_v1 --output webui/uploads/bitget_economic_diagnosis_20261017
python -m research.false_breakout.economic_diagnosis --baseline research/false_breakout/reports/baseline_20261017_v1 --funding webui/uploads/bitget_economic_diagnosis_20261017 --output NUEVO_DIRECTORIO
python -m research.false_breakout.verify_diagnosis --report NUEVO_DIRECTORIO --funding webui/uploads/bitget_economic_diagnosis_20261017
python -m pytest tests/test_economic_diagnosis.py tests/test_bitget_data.py tests/test_costs.py tests/test_false_breakout.py -q
```

El primer comando reutiliza los CSV existentes tras verificar sus hashes; con `--offline` también permite reanudar desde caché sin red. Para recoger datos posteriores debe usarse otro directorio. El segundo comando funciona exclusivamente con ficheros locales y siempre exige un directorio de informe nuevo. No se sobrescriben los resultados originales.

La única ampliación del adaptador existente permite el endpoint público `history-fund-rate` dentro de su lista de lectura. La API no proporciona las tarifas efectivas privadas de la cuenta. No se han pedido claves, enviado órdenes, hecho commits ni push.

Fuentes oficiales contrastadas: [retención de funding](https://www.bitget.com/docs/catalog/market/derivatives), [cálculo con mark](https://www.bitget.com/en-CA/support/articles/12560603817108), [incertidumbre temporal de cobro](https://www.bitget.com/support/articles/12560603808908) y [tarifas públicas de referencia](https://www.bitget.com/support/articles/12560603892733).
