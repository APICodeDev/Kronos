# Aplicación de un playbook de operadores experimentados

**1H / 1x, mismo histórico OHLCV; exploratorio, sin funding completo.**

La adaptación principal no supera el criterio registrado; no se justifica operar o entrenar IA. Revisar selección, riesgo y fidelidad de la traducción, conservando todos los resultados. Evidencia escasa: solo 0 eventos ejecutables de validación; no permiten una conclusión fuerte sobre el método humano.

## Publicación y adaptación

Se aplican impulso, retroceso y confirmación (Grimes); volumen y localización (SMB y Morpheus); stop estructural y recompensa/riesgo (Brooks); registro/revisión de un playbook (Bellafiore). No se afirma reproducir toda su discreción ni verificar sus beneficios.
Los enlaces y la correspondencia están en protocol.json y PRACTITIONER_RESEARCH.md. Los umbrales son nuestros y se fijaron antes de los resultados. No se asume que volumen alto identifique compradores institucionales: OHLCV no permite saber quién opera ni reconstruir el order book.

## Reglas congeladas

Impulso: cierre fuera del canal de las 20 horas previas por un tick y cuerpo direccional >= ATR simple previo de 20 horas. Esperar 2..6 horas; al menos una vela de retroceso, un cierre contrario y profundidad >=0,25 ATR. Los cierres mantienen el nivel roto; el extremo no cruza el origen del impulso. Primera confirmación con cuerpo a favor y cierre más allá del extremo de la vela anterior por un tick. Se conserva la confirmación antes de examinar volumen o resultados. Si coinciden impulsos, prevalece el más reciente.
structure incluye todos esos setups. price_volume exige además volumen del impulso >=1,5 veces mediana previa de 20 horas, volumen medio del retroceso menor que el del impulso y volumen de confirmación mayor que el anterior. La estructura, entrada, stop y objetivo no cambian entre libros. Es una comparación observacional del subconjunto retenido, no una prueba causal del volumen.
Entrada siguiente; SL en extremo de todo el retroceso incluida confirmación más un tick. Riesgo modelado máximo 0,25% del capital inicial, margen máximo 1000 USDT sobre 10000 USDT, 1x, sin reinversión. TP: máximo entre +1% neto del margen y 2R netos. Si no cabe antes del extremo previo del impulso, NO_SPACE y no se opera. No hay órdenes límite con fills supuestos ni máximos futuros como salida.
Horizonte fijo 24 horas, medido sobre velas de 1H; no es un cambio de temporalidad. Todas las barreras se recorren en 5m; duales recurren a 1m y, sin orden, SL conservador. Comisiones supuestas 0,06% por lado, slippage entrada/TP/timeout 1 bp y SL 2 bp, ticks/lotes adversos. El slippage se descuenta una sola vez en fills; no son tarifas efectivas de cuenta.

Ventanas y exclusión previa del antiguo test: {'start': '2025-10-17 00:00:00+00:00', 'discovery_end': '2026-05-24 00:00:00+00:00', 'validation_start': '2026-05-25 00:00:00+00:00', 'research_end': '2026-08-05 00:00:00+00:00', 'excluded_test_rows': 1752}. Purga y embargo de 24h. Los segmentos utilizados ya fueron observados; no son una nueva validación independiente. No se amplió rango ni instrumentos.
Calidad OHLC: {'hours_compared': 7008, 'bars_per_hour': 12, 'inconsistent_hours': 0, 'max_absolute_price_difference': 0.0}. Calidad de volumen: {'hours': 7008, 'missing_ohlcv': 0, 'nonpositive_volume': 0, 'max_abs_volume_difference': 3.725290298461914e-09, 'max_abs_turnover_difference': 0.0004999935626983643, 'relative_tolerance': 1e-10, 'absolute_tolerance': 1e-06}. El turnover de 1H tiene un pequeño redondeo respecto a la suma de 5m y se valida con tolerancia explícita.

## Embudo de selección y rechazo

Impulsos de estructura: 328; confirmaciones deduplicadas: 88; estados temporales: {'discovery': 69, 'validation': 18, 'EXCLUDED_WINDOW': 1}. Solo se calculan salidas dentro de las ventanas elegibles.

| Libro | Setups elegibles | Retenidos por volumen | Estados / razones de entrada |
|---|---:|---:|---|
| structure | 87 | 87 | {'NO_SPACE': 86, 'SL_FIRST': 1} |
| price_volume | 87 | 56 | {'NO_SPACE': 55, 'SL_FIRST': 1} |

## Resultados por evento y cartera

| Libro | Tramo | Eventos ejecutables | Media neta evento USDT | TP / SL / timeout | Operaciones cartera | PnL cartera USDT |
|---|---|---:|---:|---|---:|---:|
| structure | discovery | 1 | -8.2928 | {'SL_FIRST': 1} | 1 | -8.2928 |
| structure | validation | 0 | — | {} | 0 | — |

structure: retorno conjunto sobre capital inicial -0.083%; drawdown a cierre de 1H -0.083%. Intervalo descriptivo semanal de validación: {'weeks': 0, 'intervals': {'net_pnl': None}}. No incluye drawdown intrabar ni garantiza riesgo ante gaps.

| price_volume | discovery | 1 | -8.2928 | {'SL_FIRST': 1} | 1 | -8.2928 |
| price_volume | validation | 0 | — | {} | 0 | — |

price_volume: retorno conjunto sobre capital inicial -0.083%; drawdown a cierre de 1H -0.083%. Intervalo descriptivo semanal de validación: {'weeks': 0, 'intervals': {'net_pnl': None}}. No incluye drawdown intrabar ni garantiza riesgo ante gaps.

## Atribución, volumen y financiación

Resultado del subconjunto estructural que el volumen descarta: {'ALL': {'signals': 0, 'executed': 0, 'labels': {}, 'tp_rate_evaluable': None, 'mean_net_pnl': None, 'median_net_pnl': None, 'sum_net_pnl': 0.0, 'mean_margin_roi': None, 'profit_factor': None, 'winning_net_pnl_sum': 0.0, 'losing_net_pnl_sum_abs': -0.0, 'mean_winner': None, 'mean_loser': None, 'loss_quantiles': {}, 'entry_fees': 0, 'exit_fees': 0, 'mean_duration_minutes': None, 'both_touched_5m': 0, 'unresolved_execution': 0, 'incomplete': 0}, 'by_split': {}, 'by_side': {}, 'monthly': {}, 'weekly': {}}. No se escoge retrospectivamente el libro ganador; price_volume permanece como principal.
Financiación pública disponible desde 2026-07-20 00:00:00+00:00 hasta 2026-10-17 16:00:00+00:00. Solo se ajustan operaciones totalmente cubiertas; el resto es desconocido, no coste cero. Mark aproximado por apertura de 1m y sensibilidad de extremos/fronteras. El objetivo +1% y 2R son previos a financiación completa y pueden incumplirse tras el cobro. La cartera no se recalcula con el overlay.

## Decisión y revisión de casos

La adaptación principal no supera el criterio registrado; no se justifica operar o entrenar IA. Revisar selección, riesgo y fidelidad de la traducción, conservando todos los resultados. Evidencia escasa: solo 0 eventos ejecutables de validación; no permiten una conclusión fuerte sobre el método humano.
Menos de 100 eventos de validación implica evidencia escasa aunque la media sea positiva; no se modifica un umbral para aumentar artificialmente la muestra. El paso útil con este rango es revisar los motivos de aceptación/rechazo y contrastar la fidelidad de la traducción publicada. No se amplían datos por defecto ni se entrena IA.
cases.json muestra las primeras tres oportunidades de cada clase por orden temporal: operación principal, rechazo por espacio y descarte por volumen. Se eligen por fecha, no por beneficio. El diario diagnostic_setups.csv contiene todos los niveles, volúmenes y razones; events_1x.csv añade plan y resultado. Esto permite revisar la operación como una ficha de playbook.
Limitaciones: discretización propia de conceptos cualitativos, una muestra y activo, historia de investigaciones conocida, dependencia de eventos y pocos bloques. No se trasladan noticias, selección entre miles de acciones o lectura de cinta de los autores a XRP. No se demuestra la rentabilidad de un humano ni se explica toda su toma de decisiones.

## Reproducción

command.txt reproduce sin red en otro directorio con datos/caché/funding conservados. config.json y protocol.json congelan decisiones. manifest.json registra datos, fuentes locales, código, pruebas, funding, caché 1m y salidas; verify_practitioner comprueba decisiones de entrada, contabilidad Decimal, ventanas y cartera sin solapamiento. Los CSV grandes se mantienen locales. Sin entrenamiento, claves privadas, órdenes, commits ni push.
