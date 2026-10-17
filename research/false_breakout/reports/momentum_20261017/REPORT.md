# Continuación tras ruptura confirmada — XRPUSDT, 1H, 1x

**Investigación exploratoria. Datos ya observados; antiguo test excluido. Neto provisional sin funding completo.**

La continuación registrada no supera el criterio exploratorio. No se justifica operar esta regla, entrenar IA ni añadir filtros para rescatarla; conservar la infraestructura y revisar la hipótesis con datos adicionales.

## Regla y contraste registrados antes del cálculo

LONG si el cierre supera en al menos un tick el máximo de las 20 horas completas anteriores; SHORT si cierra al menos un tick por debajo del mínimo. Entrada siguiente. Cada cierre válido cuenta como evento; no se impone un filtro de primera ruptura ni indicadores adicionales. Se reutiliza la infraestructura, no la señal de falso rompimiento.
Hipótesis: persistencia tras confirmarse una ruptura. [Liu y Tsyvinski, Risks and Returns of Cryptocurrency](https://www.nber.org/papers/w24877) documentan momentum histórico en criptomonedas. La referencia motiva la familia; no demuestra esta regla en 1H ni su rentabilidad actual.
Contraste principal: cierre fijo a 6h, LONG y SHORT por separado, con costes idénticos al control. Cierres a 1h y 24h son diagnósticos secundarios registrados; no se elige el mejor. Controles: horas sin esta nueva señal, mismo segmento/mes UTC/sesión de 8h/banda de volatilidad causal; mínimo diez por estrato. Se informa lo excluido por falta de soporte.
Cartera independiente del diagnóstico de cierre fijo: TP de +1% sobre margen efectivo tras comisiones y ejecución previstas, SL extremo de la vela de señal más un tick, timeout 6h. Máximo una posición simultánea; margen fijo máximo 1000 USDT sobre capital inicial 10000 USDT, sin reinversión, 1x. Una entrada que ya cruza el stop es inválida. No se cambia de futures a spot.
Costes supuestos: 0,06% por lado, slippage 1 bp en entrada/TP/timeout y 2 bp en SL; tick y lotes reales, redondeo adverso. Las tarifas de cuenta pueden diferir. Los fills contienen el slippage: no se resta dos veces.

Ventanas UTC: {'start': '2025-10-17 00:00:00+00:00', 'discovery_end': '2026-05-24 00:00:00+00:00', 'validation_start': '2026-05-25 00:00:00+00:00', 'research_end': '2026-08-05 00:00:00+00:00', 'excluded_test_rows': 1752}. Se excluyen 1752 horas del antiguo test antes de construir indicadores/etiquetas. Purga de 24h y embargo de 24h para todos los horizontes y la cartera. La validación utilizada ya fue examinada en estudios previos; no es nueva evidencia independiente.
Calidad de ejecución: {'hours_compared': 7008, 'bars_per_hour': 12, 'inconsistent_hours': 0, 'max_absolute_price_difference': 0.0}. Se comprueban las 12 subvelas de 5m contra cada hora elegible. Fuente anual comprobada por hash; los resultados solo abarcan hasta 2026-08-05 00:00:00+00:00 (fin excluido).

## Señal frente a horas comparables: todos los perfiles

| Tramo | Dirección | Horas | Emparejadas / señales | Neto medio señal USDT | Neto medio control USDT | Diferencia USDT |
|---|---|---:|---:|---:|---:|---:|
| discovery | LONG | 1 | 243 / 246 | -0.4819 | -1.4963 | 1.0144 |
| discovery | LONG | 6 | 243 / 246 | -0.2457 | -1.2765 | 1.0309 |
| discovery | LONG | 24 | 243 / 246 | -3.7790 | -1.8879 | -1.8912 |
| discovery | SHORT | 1 | 251 / 260 | -1.0863 | -1.2569 | 0.1706 |
| discovery | SHORT | 6 | 251 / 260 | -2.8294 | -0.8346 | -1.9948 |
| discovery | SHORT | 24 | 251 / 260 | -2.4849 | 1.0973 | -3.5822 |
| validation | LONG | 1 | 66 / 66 | -0.8767 | -1.8150 | 0.9383 |
| validation | LONG | 6 | 66 / 66 | -2.0614 | -2.4720 | 0.4106 |
| validation | LONG | 24 | 66 / 66 | -1.4417 | -3.2671 | 1.8254 |
| validation | SHORT | 1 | 89 / 90 | -3.0061 | -1.2064 | -1.7997 |
| validation | SHORT | 6 | 89 / 90 | -2.0679 | -0.1872 | -1.8807 |
| validation | SHORT | 24 | 89 / 90 | -1.4766 | 3.3349 | -4.8115 |

Medias por evento; no son rentabilidad de cartera. El control se pondera por los estratos de las señales, no por todas las horas. Los eventos pueden solaparse. MFE/MAE y alcanzar el objetivo alguna vez sin stop son diagnósticos futuros, nunca precios de salida ni filtros.

## Incertidumbre de validación

| Dirección | Horas | Banda ajustada neto, bp margen | Banda ajustada diferencia, bp margen |
|---|---:|---|---|
| LONG | 1 | [-26.910190176055647, 15.528039799579465] | [-12.333570436557483, 38.37350890112992] |
| LONG | 6 | [-87.28544866148555, 39.82564387590821] | [-63.80578265850782, 74.81168592924254] |
| LONG | 24 | [-133.38245724884058, 47.08110683497477] | [-72.48350524989581, 106.43981830090827] |
| SHORT | 1 | [-47.91448053385287, -11.423953285166315] | [-42.76818979326262, 3.390353418429064] |
| SHORT | 6 | [-43.11833116501279, 4.524535642437437] | [-44.12687615486974, 7.06573184002583] |
| SHORT | 24 | [-168.4532983221302, 87.45663301403157] | [-156.0855448749308, 12.508015152538405] |

5.000 remuestreos conjuntos de semanas UTC, semilla 20261017, recalculando controles. Bandas percentiles con cuantiles Bonferroni para seis perfiles por segmento; summary.json incluye IC descriptivos del 95%. No corrigen el historial completo de investigación. Son aproximaciones con pocas semanas de validación, extremos parciales y ventanas que cruzan bloques; no certifican una ventaja.

## Ejecución con TP/SL y cartera secuencial

| Tramo | Eventos ejecutables | Media evento USDT | TP / SL / timeout / ambiguos | Operaciones cartera | PnL cartera USDT | PF cartera |
|---|---:|---:|---|---:|---:|---:|
| discovery | 506 | -0.5214 | {'TP_FIRST': 222, 'SL_FIRST': 193, 'TIMEOUT': 91} | 405 | -303.9133 | 0.8605 |
| validation | 156 | -1.6261 | {'SL_FIRST': 60, 'TIMEOUT': 53, 'TP_FIRST': 43} | 118 | -192.7796 | 0.6736 |

Estados de candidatos elegibles temporalmente: {'EVALUABLE': 662}. Se conservan inválidos en events_1x.csv. Resoluciones: {'5m': 518}. Ambiguos finales se contabilizan y reciben SL conservador, sin regalar el TP.
Cartera conjunta de investigación y validación: -496.6929 USDT; retorno sobre 10000 USDT -4.967%; drawdown a cierre de 1H -5.151%. Se conserva el efectivo entre segmentos, sin posiciones que crucen fronteras. No mide drawdown intrabar ni garantiza pérdidas máximas ante gaps.

## Costes, pagos y financiación: validación por evento

Referencia -0.038756 − ejecución 0.387761 − comisiones 1.199538 = neto -1.626055 USDT/evento. Ejecución se descompone en slippage nominal 0.238428 y redondeo 0.149333 USDT. Son atribuciones contables sobre salidas congeladas, no reoptimizaciones de TP.
Ganador medio 7.2542 USDT; perdedor medio −8.4881; proporción positiva 43.59%; equilibrio con pagos observados 53.92%. Incluye timeouts; no equivale a tasa de TP. Pérdida neta SL planificada (cuantiles): {'0.0': 4.167276799999879, '0.1': 5.879346640000078, '0.5': 10.20282359999999, '0.9': 21.197395699999923, '1.0': 62.20698550000006}. El margen fijo no supone riesgo fijo por operación.
Tasas públicas disponibles: 2026-07-20 00:00:00+00:00 a 2026-10-17 16:00:00+00:00. Cobertura validación: {'covered': 43, 'coverage_fraction': 0.27564102564102566, 'mean_cost_estimate': -0.009382399506976745, 'mean_net_same_events_without_funding': -0.8941354869767677, 'mean_net_with_estimate': -0.8847530874697909, 'mean_net_sensitivity_low': -0.8931088093953723, 'mean_net_sensitivity_high': -0.8824375004767678, 'interior_settlements': 19, 'boundary_settlements': 7, 'tp_below_target_after_estimate': 1}. La cobertura restante no se trata como coste cero ni se extrapola. Apertura de mark 1m como aproximación; sensibilidad low/high y cobros coincidentes con entrada/salida en JSON. Los TP se calculan sin funding completo y algunos podrían bajar de +1% después de financiarse. No se ha recalculado la cartera tras ese overlay.

## Cartera por mes UTC

| Mes | Operaciones | PnL USDT | Comisiones USDT |
|---|---:|---:|---:|
| 2025-10 | 26 | -100.7816 | 31.1771 |
| 2025-11 | 60 | 43.1146 | 71.8828 |
| 2025-12 | 52 | -92.3845 | 62.2792 |
| 2026-01 | 62 | 25.4805 | 74.3263 |
| 2026-02 | 66 | 56.6166 | 79.2551 |
| 2026-03 | 55 | -88.3126 | 65.9544 |
| 2026-04 | 51 | -122.7116 | 61.0948 |
| 2026-05 | 42 | -47.9599 | 50.3628 |
| 2026-06 | 52 | -43.3505 | 62.4085 |
| 2026-07 | 54 | -128.9860 | 64.7737 |
| 2026-08 | 3 | 2.5822 | 3.5979 |

## Decisión y límites

Criterio registrado: {'enough_validation_events': True, 'both_directions_positive_at_6h': False, 'both_adjusted_bands_positive_at_6h': False, 'validation_portfolio_positive': False, 'meets_exploratory_gate': False}. Solo permitiría pasar a observación prospectiva, nunca operar automáticamente o dar la rentabilidad por demostrada. No se entrenó IA ni se seleccionaron dirección, lookback o salida según el resultado.
XRPUSDT y un solo año; tramos ya explorados y pocos regímenes. No representa todos los mercados ni invalida la rentabilidad de otros operadores. El control es observacional y no aísla todas las condiciones del mercado. Hay dependencia entre eventos y posible sesgo de selección entre investigaciones. Metadatos actuales aplicados retrospectivamente; no hay profundidad histórica, latencia, ejecuciones parciales ni funding anual completo.
Si la regla no supera el criterio, no se añaden filtros para rescatar este resultado. El siguiente avance útil requeriría una hipótesis económica diferente, registrada, o datos adicionales con un tramo realmente reservado. Si lo supera, congelar reglas y costes y observar datos posteriores no examinados antes de considerar modelos.

## Reproducción y verificación

protocol.json y config.json conservan decisiones; summary.json incluye todos los perfiles y estadísticas de cartera por dirección/segmento/mes/semana. execution/ guarda eventos, operaciones, capital y atribución de costes/funding. manifest.json incluye hashes de datos, scripts, pruebas, caché 1m, funding y salidas. command.txt repite en un directorio nuevo con --offline. Los CSV grandes permanecen locales e ignorados por Git.
python -m research.false_breakout.verify_momentum --report RUTA verifica con Decimal los cálculos, el emparejamiento, señales contra OHLC originales, ventanas temporales y cartera sin solapamientos. No se modifican informes anteriores, funciones de Kraken ni el modelo; no se envían órdenes, commits ni push.
