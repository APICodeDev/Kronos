# Diagnóstico económico de la línea base

**Conclusión: detener esta regla como candidata operativa. Conservar la infraestructura y estudiar una sola hipótesis nueva si se decide continuar. La evidencia actual no justifica entrenar IA.**

Se analizan exactamente las entradas, cantidades, barreras y salidas ya guardadas. No se cambian señales, filtros, parámetros, capital ni particiones. Test ya estaba observado: esto es diagnóstico retrospectivo, sin nueva validación independiente.

## Dónde se pierde el dinero: test por evento

| Escenario | N | PnL referencia | Slippage nominal | Redondeo tick | Comisiones | PnL neto sin funding |
|---|---:|---:|---:|---:|---:|---:|
| 1x | 1893 | 0.0840 | 0.2820 | 0.0850 | 1.1993 | -1.4822 |
| 3x | 1893 | 0.1571 | 0.8113 | 0.2604 | 3.5994 | -4.5140 |
| 5x | 1893 | 0.1919 | 1.3219 | 0.4366 | 5.9993 | -7.5659 |
| 10x | 1893 | 0.1297 | 2.5767 | 0.8825 | 11.9993 | -15.3289 |

Importes medios en USDT por operación, con margen efectivo cercano a 1.000 USDT. Identidad comprobada por fila: referencia − slippage nominal − redondeo − comisiones − otros costes = PnL original. El slippage no se descuenta dos veces.

El PnL de referencia elimina aritméticamente los costes de los fills, manteniendo salidas, cantidad y TP originales. Es una descomposición contable, no el resultado de una estrategia sin costes: recalcular sus TP podría cambiar la trayectoria y las etiquetas.

## ¿Bastaría reducir comisiones?

| Escenario test | Comisión cero, ejecución actual | Ejecución ideal, comisiones actuales | 2 bp por lado, ejecución actual | Comisión máxima por lado con ejecución actual (bp) |
|---|---:|---:|---:|---:|
| 1x | -0.2829 | -1.1153 | -0.6827 | -1.4155 |
| 3x | -0.9146 | -3.4423 | -2.1144 | -1.5245 |
| 5x | -1.5666 | -5.8074 | -3.5664 | -1.5667 |
| 10x | -3.3296 | -11.8696 | -7.3294 | -1.6649 |

Una comisión de equilibrio negativa significa que ni una tarifa cero bastaría: haría falta un rebate para esas ejecuciones. Los escenarios de 2 bp son sensibilidad aritmética; no se supone que órdenes de mercado puedan ejecutarse como maker ni que exista esa tarifa efectiva de cuenta.

## Acierto y tamaño de pérdidas

| Escenario test | Operaciones positivas | Acierto de equilibrio | Ganador medio USDT | Perdedor medio USDT | SL previsto mediano USDT | Recompensa/riesgo mediana |
|---|---:|---:|---:|---:|---:|---:|
| 1x | 17.12% | 28.76% | 9.0667 | 3.6606 | 3.2764 | 3.0615 |
| 3x | 29.27% | 51.15% | 10.0750 | 10.5501 | 9.8393 | 1.0287 |
| 5x | 35.45% | 62.98% | 10.1735 | 17.3066 | 16.4021 | 0.6242 |
| 10x | 42.26% | 76.70% | 10.3712 | 34.1396 | 32.8042 | 0.3151 |

Acierto de equilibrio = pérdida media / (ganancia media + pérdida media), condicionado a PnL distinto de cero y manteniendo la distribución de pagos observada. No es una probabilidad aprendida ni un umbral de filtro. Incluye TIMEOUT positivos y negativos; no equivale a tasa TP. El JSON separa además TP/SL resueltos y conserva las contribuciones de timeout/ambiguos.

El mayor apalancamiento acerca el TP al precio y aumenta su frecuencia, pero multiplica el nominal, las comisiones y el daño de un SL mientras el beneficio objetivo permanece aproximadamente en 10 USDT. Aumentar el acierto por sí solo no arregla esa relación.

## LONG y SHORT en test

| Escenario | Dirección | N | Referencia media | Ejecución media | Comisiones medias | Neto medio |
|---|---|---:|---:|---:|---:|---:|
| 1x | LONG | 871 | 0.2208 | 0.3619 | 1.1991 | -1.3401 |
| 1x | SHORT | 1022 | -0.0326 | 0.3713 | 1.1994 | -1.6033 |
| 3x | LONG | 871 | 0.4824 | 1.0553 | 3.5989 | -4.1717 |
| 3x | SHORT | 1022 | -0.1201 | 1.0857 | 3.5999 | -4.8057 |
| 5x | LONG | 871 | 0.2679 | 1.7362 | 5.9983 | -7.4666 |
| 5x | SHORT | 1022 | 0.1272 | 1.7775 | 6.0002 | -7.6505 |
| 10x | LONG | 871 | -0.0721 | 3.4225 | 11.9972 | -15.4917 |
| 10x | SHORT | 1022 | 0.3016 | 3.4906 | 12.0011 | -15.1901 |

## Incertidumbre y ambigüedades

Bootstrap descriptivo por semanas UTC completas agrupadas (lunes-domingo), 5.000 remuestreos, semilla 20261017. Mantiene juntos eventos de una misma semana para evitar tratarlos como observaciones independientes. Los intervalos percentiles no garantizan estacionariedad ni generalización y proceden de pocas semanas de test.

| Escenario test | Semanas | IC 95 % media referencia | IC 95 % media neta | Media neta si todos los ambiguos de ejecución fueran TP |
|---|---:|---|---|---:|
| 1x | 11 | -0.0934 / 0.2513 | -1.6660 / -1.3062 | -1.4822 |
| 3x | 11 | -0.3238 / 0.6389 | -5.0360 / -3.9972 | -4.5140 |
| 5x | 11 | -0.3211 / 0.6812 | -8.1219 / -7.0317 | -7.5530 |
| 10x | 11 | -0.9375 / 1.1853 | -16.4969 / -14.2124 | -15.2932 |

El último escenario es solo una cota optimista de diagnóstico; las etiquetas y pérdidas conservadoras originales se conservan.

## Funding público: cobertura y estimación

Se descargaron 270 tasas entre 2026-07-20 00:00:00+00:00 y 2026-10-17 16:00:00+00:00; no hay huecos dentro del horario observado de 8 h. La retención pública documentada es de 90 días. No se extrapola al año anterior.

| Escenario test | Cobertura | Coste funding medio estimado | Neto con estimación | Sensibilidad favorable / desfavorable | Casos con entrada/salida en liquidación | TP originales bajo +1 % tras estimación |
|---|---:|---:|---:|---|---:|---:|
| 1x | 1893 | -0.000016 | -1.4822 | -1.4815 / -1.4825 | 31 | 28 |
| 3x | 1893 | -0.000190 | -4.5138 | -4.5115 / -4.5152 | 33 | 19 |
| 5x | 1893 | -0.001441 | -7.5645 | -7.5610 / -7.5665 | 29 | 13 |
| 10x | 1893 | -0.003508 | -15.3254 | -15.3189 / -15.3283 | 27 | 11 |

Coste = signo LONG/SHORT × cantidad × mark aproximado × tasa histórica. El mark usado es la apertura de la vela nativa mark de 1m del instante de liquidación, no una cotización exacta. La sensibilidad usa low/high del minuto y permite cobrar/no cobrar funding si entrada o salida coincide con el instante. Esa banda no es un intervalo de confianza ni una cota garantizada de ejecución real.
El punto central incluye únicamente instantes estrictamente interiores a la posición. Se considera posible incertidumbre al entrar/salir en el segundo de liquidación. El intercambio advierte de retardos al cobrar funding. No se reconstruyen esos retardos ni liquidaciones. El TP original se calculó sin funding: se cuentan los TP que ya no llegarían al objetivo tras este coste, sin reetiquetar el original.
Esto es una revaloración de operaciones congeladas, no una nueva cartera financiada: no cambia el capital disponible ni su secuencia. El resultado anual sigue sin funding completo y la estimación reciente no merece llamarse neto completo.

## Decisión y siguientes pasos

1. Cerrar esta versión del falso rompimiento como regla operativa. Ambas direcciones y todos los apalancamientos pierden con los supuestos fijados; los costes consumen el pequeño margen de referencia y reducir solo las tarifas no lo recupera.
2. Conservar el descargador, la validación causal y la contabilidad. El proyecto como banco de pruebas sí es reutilizable; este resultado no justifica dedicar recursos a entrenar un modelo ni operar en real.
3. Si se continúa investigando, escribir primero una única hipótesis nueva con fundamento de mercado, entradas/salidas y costes explícitos, y un control sencillo de comparación. Usar el histórico observado solo como exploración y registrar todas las variantes.
4. Recoger datos posteriores al intervalo ya observado y reservar un test cronológico que no se mire durante el diseño, con purga/embargo. Confirmar tarifas efectivas y medir ejecución en simulación antes de interpretar como real un margen pequeño.
5. Exigir expectativa positiva tras costes, suficiente muestra en test (100 eventos es solo un mínimo, no garantía), estabilidad temporal y comparación con el control. Si falla, detener esa hipótesis. Solo una regla que supere esa fase permitiría plantear un clasificador pequeño con otro test intacto.

## Reproducibilidad y límites

Se preserva el baseline original. `manifest.json` registra hashes de entradas, scripts, dependencias, tasas y mark; los CSV de diagnóstico desglosan cada operación. `summary.json` separa eventos/cartera, dirección, partición y mes. Las sumas por evento no son una curva de capital. La cartera de 3x/5x/10x ya dejó de operar antes de test; no hay operaciones de cartera finales que revalorar allí.
Las tarifas efectivas de cuenta no pueden deducirse de datos públicos. No se ha pedido ni usado una clave privada. Tampoco se han añadido filtros, seleccionado escenarios favorables, entrenado IA, enviado órdenes, hecho commits ni push.

Fuentes oficiales consultadas el 17-10-2026: [funding_api](https://www.bitget.com/docs/catalog/market/derivatives), [funding_calculation](https://www.bitget.com/en-CA/support/articles/12560603817108), [funding_timing](https://www.bitget.com/support/articles/12560603808908), [published_fees](https://www.bitget.com/support/articles/12560603892733).
