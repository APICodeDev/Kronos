# Resultado del primer hito — 17-10-2026

**La regla base no encuentra ventaja con los costes supuestos. No procede entrenar IA ni añadir filtros para intentar rescatar este resultado.** Esto describe el experimento realizado, no demuestra que ningún patrón alternativo pueda funcionar.

Se conservó el trabajo local y se añadieron el adaptador público Bitget, descarga CLI, detector causal, cálculo financiero, etiquetado, cartera y generación de informes. No se modificaron Kraken, Flask, el modelo ni la configuración Docker. No hubo commits, push, claves privadas ni órdenes.

## Evidencia descargada

XRPUSDT perpetuo USDT-FUTURES, desde **17-10-2025 00:00 UTC hasta 17-10-2026 00:00 UTC**, fin excluido:

| Temporalidad nativa | Velas cerradas | Huecos | Duplicados |
|---|---:|---:|---:|
| 5m | 105.120 | 0 | 0 |
| 15m | 35.040 | 0 | 0 |
| 1H | 8.760 | 0 | 0 |

Los datos, las respuestas originales y Parquet/CSV permanecen en `webui/uploads/bitget_baseline_20261017/`. Los hashes y la procedencia están en los metadatos y el manifiesto. Se detectaron **4.935 LONG, 4.527 SHORT y 5 señales duales**, excluidas de entradas. El contexto disponible de 15m/1H fue completo para las señales y solo se usó como descripción. Diez candidatos finales no disponían de horizonte completo y no se contabilizaron como ganadores ni timeout.

## Rendimiento

Costes supuestos: 0,0006 por lado; slippage de 1 bp en entrada/TP/timeout y 2 bp en SL, con redondeo adverso al tick. Margen máximo configurable de 1.000 USDT por operación; capital inicial 10.000 USDT. Horizonte 72 barras, SL con un tick de buffer, TP de al menos +1 % del margen efectivamente asignado. Los cuatro apalancamientos se fijaron antes de observar resultados; no se selecciona uno a posteriori.

| Escenario | Operaciones de cartera | PnL cartera USDT | ROI sobre capital inicial | Eventos ejecutables en test | Media test por evento USDT | PF test por evento |
|---|---:|---:|---:|---:|---:|---:|
| 1x | 6.288 | −9.002,89 | −90,029 % | 1.893 | −1,4822 | 0,5115 |
| 3x | 2.221 | −9.013,26 | −90,133 % | 1.893 | −4,5140 | 0,3951 |
| 5x | 1.318 | −9.002,36 | −90,024 % | 1.893 | −7,5659 | 0,3228 |
| 10x | 748 | −8.997,49 | −89,975 % | 1.893 | −15,3289 | 0,2224 |

Las cuatro carteras dejan de poder financiar otra operación del tamaño configurado; conservan aproximadamente 1.000 USDT, no un saldo cero. En **3x/5x/10x esto ocurre antes de test**, por lo que no tienen operaciones de cartera fuera de muestra. El análisis por evento sí evalúa las 1.893 oportunidades finales en cada escenario, como entradas aisladas, sin limitación de capital ni solapamiento. No se debe interpretar su suma de PnL como rentabilidad de una cartera ejecutable.

En 1x la cartera toma 1.227 operaciones en test, con PnL medio de −1,5867 USDT. Su PnL anual bruto, ya con slippage en los precios, es −1.464,01 USDT; las comisiones suman 7.538,88 USDT. Por tanto, las pérdidas no se explican únicamente por las comisiones. Todos los meses de cartera 1x terminan negativos con estos supuestos.

La evaluación utiliza 60/20/20 por tiempo, purga del horizonte máximo en las fronteras y embargo de 72 barras. No hubo entrenamiento, optimización de horizonte, buffer o filtros. El segmento final ya está observado: cualquier hipótesis posterior necesita otro test sin observar.

## Verificación y reproducción

- **73 pruebas aprobadas:** 50 nuevas, 19 de interfaz/Kraken y 4 regresiones reales del modelo en CPU. Ruff y `git diff --check` sin incidencias. Ver [auditoría](AUDIT.md) y [validación](validation.json).
- Recomputación independiente con `Decimal`: **37.808 eventos con PnL**, incluidos los que después excluye la partición; **11.100 TP** verificados. Error máximo absoluto **2,08 × 10⁻¹² USDT**, inferior a la tolerancia de 0,000001 USDT. Todos los TP cumplen el objetivo sobre margen tras comisiones y deslizamiento modelados. Ver [verificación financiera](reports/baseline_20261017_v1/financial_verification.json).
- Se consultaron **222 ventanas de 1m**, todas completas y coherentes con OHLC de 5m. Las ambigüedades que persistieron dentro del minuto se mantuvieron como AMBIGUOUS y SL conservador. El detalle está en `resolution_1m.json`.
- El informe generado conserva todas las etiquetas, operaciones, curva, configuración y hashes. La repetición offline usa la misma caché, sin red; su comparación está en `reproducibility.json` junto al informe.
- El intento inicial se conserva como incompleto: un fallo de índices de pandas al construir la cartera se corrigió y cubrió con una prueba. No se cambiaron parámetros tras ese fallo.

Comandos de descarga, ejecución, verificación y repetición: [README](README.md). Informe completo: [REPORT.md](reports/baseline_20261017_v1/REPORT.md). Desglose por dirección, partición, mes y semana: [summary.json](reports/baseline_20261017_v1/summary.json). Código, datos y artefactos: [manifest.json](reports/baseline_20261017_v1/manifest.json).

## Límites reales

Los resultados son **provisionales sin funding**; no representan neto completo. Las tarifas son hipótesis, no tarifas verificadas de la cuenta. Se aplicaron los metadatos actuales de tick/lote a todo el año; no se dispone de su historia. No se reconstruyen spread, profundidad, latencia, ejecución parcial, mantenimiento de margen ni liquidación forzosa. El drawdown marca a cierre de 5m y no recoge extremos intrabar. Una única criptomoneda y eventos solapados no permiten afirmar independencia o generalización a otros regímenes.

El Python local no tenía dependencias de la interfaz/modelo; esas pruebas se ejecutaron en la imagen Docker existente, con el repositorio y caché montados como solo lectura. Pandas emitió una advertencia de futura conversión de tipos en un contador de ambigüedades; no falló ningún cálculo y los resultados quedaron contrastados por la repetición e implementación decimal independientes.
