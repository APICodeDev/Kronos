# Falso rompimiento XRPUSDT — 1H sin apalancamiento

**Experimento exploratorio sobre un año ya observado. No es una nueva validación final independiente.**

La variante 1H/1x no muestra ventaja con los costes supuestos en el tramo final exploratorio. No se justifica entrenar IA ni operar esta regla.

## Configuración fijada antes de ejecutar

Detección en velas nativas de 1H: niveles de las 20 velas anteriores (20 horas), excluyendo la actual. Entrada en la apertura de la hora siguiente. SL en extremo del barrido más un tick; TP calculado para al menos +1 % del margen efectivo tras comisiones y slippage previstos. Una sola posición por símbolo.
1x, margen virtual máximo 1.000 USDT por operación, capital inicial 10.000 USDT, sin reinversión. Comisiones 0,0006 por lado; slippage 1 bp entrada/TP/timeout y 2 bp SL, con redondeo adverso. Son hipótesis, no tarifas efectivas de cuenta.
Horizonte fijo de **6 horas = 6 velas de 1H**. No se probaron 72 horas ni se eligió un horizonte ganador. Particiones 60/20/20 por tiempo, purga del horizonte completo y embargo de 6 horas. Sin filtros HTF ni IA.

Datos UTC: 2025-10-17 00:00:00+00:00 a 2026-10-17 00:00:00+00:00 (fin excluido), 8760 velas de 1H y 105120 de 5m, sin huecos. Coincidencia OHLC 1H/agregado 5m: {'hours_compared': 8760, 'bars_per_hour': 12, 'inconsistent_hours': 0, 'max_absolute_price_difference': 0.0}.
Señales: {'LONG': 519, 'SHORT': 393, 'BOTH': 2}. Estados de todas las señales: {'EVALUABLE': 907, 'DUAL_SIGNAL': 2, 'PURGED': 2, 'INCOMPLETE': 2, 'EMBARGO': 1}. Etiquetas de todas las señales: {'SL_FIRST': 555, 'TP_FIRST': 233, 'TIMEOUT': 122, 'AMBIGUOUS': 4}.

## Resultados sin funding

| Medida | Eventos elegibles | Cartera secuencial |
|---|---:|---:|
| Operaciones | 907 | 903 |
| Media neta USDT | -1.8845 | -1.8916 |
| Mediana neta USDT | -4.1803 | -4.1865 |
| Factor de beneficio | 0.6018 | 0.6015 |
| Duración media min | 130.81 | 130.10 |
| Eventos TP/SL/timeout/ambiguos | {'SL_FIRST': 554, 'TP_FIRST': 233, 'TIMEOUT': 120} | {'SL_FIRST': 553, 'TP_FIRST': 233, 'TIMEOUT': 117} |

Cartera: PnL **-1708.0715 USDT**, ROI sobre capital inicial **-17.081%**, drawdown máximo a cierre 1H **-17.324%**. Sumar PnL de eventos solapados no constituye una cartera.

## Particiones temporales

| Tramo | Eventos | Media evento USDT | PF evento | Operaciones cartera | PnL cartera USDT |
|---|---:|---:|---:|---:|---:|
| discovery | 539 | -1.583109090426718 | 0.6604558484478887 | 537 | -857.1971816000009 |
| validation | 184 | -2.1274995692391343 | 0.5343109651201375 | 182 | -386.3862896400006 |
| test | 184 | -2.52439126347826 | 0.5053337122623188 | 184 | -464.4879924799999 |

## LONG / SHORT

| Dirección | N anual | Media anual USDT | N test | Media test USDT | PF test |
|---|---:|---:|---:|---:|---:|
| LONG | 516 | -2.3513 | 95 | -3.3658 | 0.3761852962376917 |
| SHORT | 391 | -1.2685 | 89 | -1.6263 | 0.6605719003333043 |

## Costes y financiación en test

Por evento: referencia -0.968337 − ejecución 0.357449 (slippage 0.264907, tick 0.092542) − comisiones 1.198605 = neto -2.524391 USDT.
Operaciones con PnL positivo: 30.978%; equilibrio con pagos observados: 47.038%. Ganador medio 8.3246, perdedor medio −7.3936 USDT. Incluye timeout, no equivale a tasa TP.
Comisión cero con estas mismas ejecuciones: -1.325786 USDT/evento. Son ajustes contables sobre salidas congeladas, no un nuevo backtest con otros TP.
Funding: 184/184 eventos de test cubiertos. Coste medio estimado 0.0019500651489130437 USDT; neto tras estimación -2.5263413286271743 USDT; sensibilidad favorable/desfavorable -2.5193348525396733 / -2.532511382775543 USDT. TP originales de test que bajarían del +1 % tras funding estimado: 2.
Las tasas son públicas, pero el mark se aproxima por la apertura de su vela nativa 1m. El punto central solo carga funding en instantes estrictamente interiores; la sensibilidad incorpora low/high del minuto y posibles cobros en entradas/salidas coincidentes. No son cotizaciones ni cobros exactos. Se mantienen etiquetas y cartera sin funding; el ajuste no recalcula su elegibilidad por capital. El año sigue sin funding completo.

## Incertidumbre y comparación con 5m

Bootstrap descriptivo por 11 bloques de semana UTC (extremos parciales), 5.000 remuestreos, semilla 20261017. IC 95 % media neta de eventos test: [-3.3317472928328518, -1.817120452622504]; referencia: [-1.7713003562549556, -0.2613824799231703]. No se supone independencia entre señales solapadas; pocos bloques y un solo año limitan la inferencia.
Referencia histórica 5m/1x, mismo horizonte y costes: {'test_events': 1893, 'test_mean_net': -1.4821991406761748, 'test_profit_factor': 0.51147523313734, 'capital_return': -0.9002886886860022, 'portfolio_trades': 6288}. Cambian la ventana de niveles de 100 minutos a 20 horas y las oportunidades; esto no aísla solo un cambio de ruido o frecuencia.
En 1H, test tiene 184 eventos y 184 operaciones de cartera. El tramo ya se conocía por investigaciones anteriores y no se considera prueba independiente, aunque se mantengan las fronteras cronológicas.

## Cartera por mes UTC

| Mes | Operaciones | PnL USDT | Comisiones USDT |
|---|---:|---:|---:|
| 2025-10 | 35 | -58.7683 | 41.9010 |
| 2025-11 | 84 | -128.2993 | 100.6428 |
| 2025-12 | 70 | -65.1878 | 83.9389 |
| 2026-01 | 69 | -146.5943 | 82.6763 |
| 2026-02 | 71 | -41.4872 | 85.0703 |
| 2026-03 | 83 | -142.6081 | 99.5502 |
| 2026-04 | 74 | -138.0295 | 88.7241 |
| 2026-05 | 67 | -121.3542 | 80.2996 |
| 2026-06 | 75 | -215.5491 | 89.8896 |
| 2026-07 | 83 | -186.1316 | 99.5742 |
| 2026-08 | 73 | -154.5918 | 87.4957 |
| 2026-09 | 78 | -202.6249 | 93.5484 |
| 2026-10 | 41 | -106.8454 | 49.0986 |

## Ejecución, límites y reproducción

Se comprueban las 12 velas de 5m por cada hora y su OHLC contra la vela nativa. Todas las salidas por barrera se recorren en 5m, incluyendo gaps adversos en aperturas de 5m. Si ambos niveles coinciden dentro de 5m, se consulta 1m; si sigue sin orden, etiqueta AMBIGUOUS y SL conservador. El timeout cierra al acabar la sexta hora con costes. No se usan subvelas para generar señales ni filtrar entradas.
Capital a cierre de 1H: no mide drawdown intrabar ni liquidación. Metadatos actuales aplicados retrospectivamente, tarifas de cuenta desconocidas, sin modelar profundidad, latencia o ejecución parcial. La muestra es una sola criptomoneda y los resultados son provisionales sin financiación exacta. 1x sigue siendo un futuro perpetuo y conserva funding; no se han usado precios spot.
La configuración está en config.json; summary.json contiene eventos, cartera, costes, meses/semanas y particiones. manifest.json registra código, versiones y hashes de entradas/salidas. command.txt permite repetir con otro directorio de salida. --offline solo usa caché. Los CSV grandes se conservan localmente. No se modifican los experimentos previos ni se entrena IA ni se envían órdenes.
Resoluciones: {'5m': 787, '1m': 1}. Las ambigüedades de dirección, purga/embargo e incompletos están separadas de las operaciones ejecutables.
