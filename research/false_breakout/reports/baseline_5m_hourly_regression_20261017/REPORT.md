# Primer experimento de falsos rompimientos — Bitget XRPUSDT

**Resultados provisionales sin funding. No se ha entrenado IA ni optimizado parámetros.**

Datos: 2025-10-17 00:00:00+00:00 a 2026-10-17 00:00:00+00:00 (fin excluido), 105120 velas de 5m, 365.00 días.
Señales: {'LONG': 4935, 'SHORT': 4527, 'BOTH': 5}. Contexto incompleto: 0.0000%.

Configuración congelada antes de observar resultados; 60/20/20 por tiempo, purga del horizonte completo y embargo de 72 barras.
El conjunto final se evalúa en esta ejecución; cualquier cambio posterior exige otro tramo final sin observar.

| Escenario | Cartera: operaciones | PnL USDT | ROI capital | DD máx. cierres 5m | PF | Test: operaciones | Test: media USDT |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1x | 6288 | -9002.8869 | -90.029% | -90.045% | 0.5370150833964837 | 1227 | -1.586722677375713 |
| 3x | 2221 | -9013.2597 | -90.133% | -90.142% | 0.4363909086390912 | 0 | None |
| 5x | 1318 | -9002.3582 | -90.024% | -90.054% | 0.36475650962094225 | 0 | None |
| 10x | 748 | -8997.4937 | -89.975% | -89.988% | 0.29435572781940145 | 0 | None |

## Etiquetas y rendimiento por evento

Las etiquetas de esta tabla corresponden a todas las señales; los PnL de la tabla posterior excluyen purga/embargo e incompletos.

| Escenario | TP_FIRST | SL_FIRST | TIMEOUT | AMBIGUOUS | GAP_INVALID | Incompletos |
|---|---:|---:|---:|---:|---:|---:|
| 1x | 1290 | 7854 | 308 | 15 | 0 | 10 |
| 3x | 2659 | 6766 | 25 | 17 | 0 | 10 |
| 5x | 3232 | 6201 | 9 | 25 | 0 | 10 |
| 10x | 3919 | 5514 | 4 | 30 | 0 | 10 |

| Escenario / dirección | Ejecutados | Tasa TP evaluables | Media USDT | Mediana USDT | Ganador medio | Perdedor medio | PF | Duración min |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1x / TOTAL | 9429 | 0.1367059073072436 | -1.4423 | -2.7908 | 9.011314113459527 | -3.4702853694846127 | 0.5037552281651999 | 54.81 |
| 1x / LONG | 4918 | 0.13013420089467262 | -1.5635 | -2.8277 | 9.018382053692504 | -3.5006734034640354 | 0.4716085467569068 | 54.97 |
| 1x / SHORT | 4511 | 0.1438705386832188 | -1.3102 | -2.7364 | 9.004337845603107 | -3.4365091509679124 | 0.5401533235467438 | 54.64 |
| 3x / TOTAL | 9429 | 0.2812599427298759 | -4.3709 | -7.5615 | 10.080903439188258 | -10.053002274506493 | 0.3942649757470415 | 28.57 |
| 3x / LONG | 4918 | 0.27897519316795444 | -4.4679 | -7.6235 | 10.076368430290268 | -10.12952716670056 | 0.3872227104668403 | 28.26 |
| 3x / SHORT | 4511 | 0.28375083130126355 | -4.2652 | -7.5036 | 10.085774243756795 | -9.969080924330848 | 0.40211220189920527 | 28.90 |
| 5x / TOTAL | 9429 | 0.3419238519461237 | -7.3850 | -11.8826 | 10.177093689525845 | -16.52290541151563 | 0.3204826768630081 | 21.19 |
| 5x / LONG | 4918 | 0.3411956079707198 | -7.5311 | -11.9347 | 10.16803771901247 | -16.72233178609205 | 0.3157659716297073 | 20.68 |
| 5x / SHORT | 4511 | 0.3427178009310574 | -7.2259 | -11.8290 | 10.186940446597635 | -16.30518427340303 | 0.32576381907604735 | 21.76 |
| 10x / TOTAL | 9429 | 0.41446600912079756 | -14.7369 | -21.7613 | 10.367370193578855 | -32.51453933387679 | 0.22579670174489874 | 16.04 |
| 10x / LONG | 4918 | 0.4131760878405856 | -15.0744 | -21.8514 | 10.36393581347756 | -33.00032061496012 | 0.2213085111511548 | 15.57 |
| 10x / SHORT | 4511 | 0.4158723121259144 | -14.3689 | -21.6334 | 10.371091992483935 | -31.982668747187844 | 0.23086707520313082 | 16.54 |

## Cartera por período y costes

| Escenario / mes UTC | Operaciones | PnL USDT | Media USDT | Comisiones USDT |
|---|---:|---:|---:|---:|
| 1x / 2025-10 | 298 | -258.5954 | -0.8678 | 357.1067 |
| 1x / 2025-11 | 699 | -892.5009 | -1.2768 | 837.6437 |
| 1x / 2025-12 | 493 | -791.3029 | -1.6051 | 590.9469 |
| 1x / 2026-01 | 540 | -695.2844 | -1.2876 | 647.3014 |
| 1x / 2026-02 | 603 | -779.1350 | -1.2921 | 723.0237 |
| 1x / 2026-03 | 510 | -560.9231 | -1.0998 | 611.4552 |
| 1x / 2026-04 | 407 | -622.6768 | -1.5299 | 488.1084 |
| 1x / 2026-05 | 441 | -742.5598 | -1.6838 | 528.8136 |
| 1x / 2026-06 | 600 | -971.9547 | -1.6199 | 719.3538 |
| 1x / 2026-07 | 429 | -671.4917 | -1.5652 | 514.4840 |
| 1x / 2026-08 | 482 | -824.6874 | -1.7110 | 578.0945 |
| 1x / 2026-09 | 565 | -687.1763 | -1.2162 | 677.5918 |
| 1x / 2026-10 | 221 | -504.5984 | -2.2833 | 264.9514 |
| 3x / 2025-10 | 390 | -1452.3890 | -3.7241 | 1403.3682 |
| 3x / 2025-11 | 842 | -3255.6014 | -3.8665 | 3029.7824 |
| 3x / 2025-12 | 725 | -3256.9625 | -4.4924 | 2609.1803 |
| 3x / 2026-01 | 264 | -1048.3068 | -3.9709 | 950.2203 |
| 5x / 2025-10 | 397 | -2629.2479 | -6.6228 | 2381.4601 |
| 5x / 2025-11 | 849 | -5780.1565 | -6.8082 | 5092.4366 |
| 5x / 2025-12 | 72 | -592.9538 | -8.2355 | 431.8695 |
| 10x / 2025-10 | 400 | -5258.6171 | -13.1465 | 4799.2962 |
| 10x / 2025-11 | 348 | -3738.8765 | -10.7439 | 4175.3442 |

## Hipótesis de ejecución y contabilidad

Entrada en apertura siguiente con slippage adverso y redondeo al tick; cantidad redondeada hacia abajo. Margen = nominal ejecutado / apalancamiento. TP resuelto incluyendo comisión de salida sobre su nominal y slippage previsto, redondeado para alcanzar al menos +1 % del margen efectivo.
SL fijo; gap de salida al peor precio entre apertura y SL. TIMEOUT liquida al cierre de la barra 72 con costes. Un gap que ya cruza TP se ejecuta al TP sin mejora favorable. Si ambos niveles se tocan, se consultan velas 1m cuando se habilita; si persiste incertidumbre, etiqueta AMBIGUOUS y pérdida por SL.
Cartera con una posición por símbolo, margen fijo sin reinversión y capital inicial configurable. Se omiten las entradas sin capital. Curva marcada a cierre 5m, comisión de apertura descontada al entrar y resto de costes al salir; DD intrabar y coste de liquidación inmediata de posiciones abiertas no incluidos.
El análisis por evento admite solapamientos y su suma de PnL no representa una cartera. Las particiones se asignan por entrada con horizonte máximo, sin utilizar la duración realizada para decidir la purga.

## Limitaciones y decisión

- Funding excluido: PnL tras comisiones y slippage, no neto completo. Ningún escenario equivale a la tarifa o al apalancamiento real de la cuenta.
- Metadatos actuales aplicados retrospectivamente: no hay histórico de cambios de tick, lotes, comisiones o límites del contrato.
- OHLC no reconstruye spread, profundidad, latencia, colas, ejecución parcial ni liquidación/mantenimiento del margen. Escenarios de apalancamiento son simulaciones provisionales.
- Una única criptomoneda y un período temporal no prueban estabilidad en otros regímenes. Los eventos solapados no son observaciones independientes.
- No se ha probado ningún clasificador: la comparación frente a IA queda fuera de este hito.

No se encuentra ventaja neta fuera de muestra en ninguno de los escenarios. No procede añadir IA ni filtros para rescatar esta hipótesis.

## Configuración exacta

```json
{
  "symbol": "XRPUSDT",
  "category": "USDT-FUTURES",
  "entry_interval": "5m",
  "context_intervals": [
    "15m",
    "1H"
  ],
  "lookback_bars": 20,
  "target_net_margin_roi": 0.01,
  "margin_usdt": 1000,
  "initial_equity_usdt": 10000,
  "leverage_scenarios": [
    1,
    3,
    5,
    10
  ],
  "entry_fee_rate": 0.0006,
  "exit_fee_rate": 0.0006,
  "entry_slippage_bps": 1,
  "tp_slippage_bps": 1,
  "sl_slippage_bps": 2,
  "timeout_slippage_bps": 1,
  "funding": "excluded_provisional",
  "other_costs_usdt": 0,
  "stop_buffer_ticks": 1,
  "max_holding_bars": 72,
  "split_fractions": [
    0.6,
    0.2,
    0.2
  ],
  "embargo_bars": 72,
  "timezone": "UTC"
}
```

## Reproducibilidad

Ver `manifest.json` para hashes de código, configuración, instrumentos, datos y versiones. `summary.json` contiene etiquetas, costes, resultados por dirección, partición, mes y semana. Los CSV conservan cada evento, operación de cartera y curva.

Repetir con el comando de `command.txt`; añadir `--offline` utiliza la caché de resolución 1m sin red. Los datos están en el directorio de cargas persistente y no se incluyen en Git.
