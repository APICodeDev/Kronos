# Línea base de falsos rompimientos

Flujo CPU independiente de Kronos/Flask, sin entrenamiento ni órdenes. Kraken y su interfaz no se modifican. Ejecutar los comandos desde la raíz del repositorio.

El primer hito ya está ejecutado: [resultados e interpretación](RESULTS.md), [informe completo](reports/baseline_20261017_v1/REPORT.md) y [auditoría inicial](AUDIT.md). La línea base pierde dinero con los costes supuestos; no se ha añadido IA.

El [diagnóstico económico posterior](DIAGNOSIS.md) explica ejecución, comisiones, relación TP/SL y funding reciente. Incluye conclusiones, límites y comandos para repetirlo sobre las operaciones originales congeladas, sin ajustar filtros ni barreras.

## Entorno

```powershell
py -3.11 -m venv .venv
.venv/Scripts/python -m pip install -r research/false_breakout/requirements.txt
# Opcional: Parquet además de CSV
.venv/Scripts/python -m pip install pyarrow
```

Usar el mismo ejecutable en todos los comandos siguientes. Las versiones efectivamente usadas se guardan en `manifest.json`; no es necesario instalar PyTorch para investigar.

## Descargar y repetir

```powershell
python -m research.false_breakout.download_history --start 2025-10-17T00:00:00Z --end 2026-10-17T00:00:00Z --output webui/uploads/bitget_baseline_20261017
python -m research.false_breakout.run_experiment --data webui/uploads/bitget_baseline_20261017 --output research/false_breakout/reports/baseline_20261017_v1 --resolve-1m
python -m research.false_breakout.verify_results --report research/false_breakout/reports/baseline_20261017_v1
python -m pytest tests/test_bitget_data.py tests/test_costs.py tests/test_false_breakout.py -q
```

La descarga es [inicio, fin), en UTC, ajustada a límites de velas cerradas según el reloj público del servidor. Omitir `--end` termina en la última vela cerrada. Descarga las tres temporalidades nativas, sin resampling. Cada petición solicita 100 velas como máximo y una ventana muy inferior a 90 días. Usa `interval` (no `granularity`) y solo endpoints públicos v3 de mercado.

Las respuestas se cachean en `raw/`; volver a ejecutar el mismo comando reanuda las páginas pendientes. Los ficheros finales ya existentes se conservan; se comprueban rango y hash antes de reutilizarlos. Para un intervalo distinto, elegir otro directorio. Una respuesta vacía deja constancia de cobertura faltante; el experimento rechaza históricos con huecos. Los duplicados idénticos se reducen a la primera observación y se cuentan; los contradictorios detienen la descarga. Se normaliza el orden de la API y se cuenta cada retroceso. No se rellena ningún hueco.

`--resolve-1m` consulta exclusivamente los minutos de las velas que tocan ambas barreras, comprueba cobertura y concordancia OHLC con 5m y conserva las respuestas. No utiliza esos minutos para filtrar señales. Si falta resolución o ambas barreras coinciden dentro de 1m, mantiene AMBIGUOUS con SL conservador. Repetir con `--resolve-1m --offline` y otro `--output` no hace peticiones de red; una respuesta que falte en caché conserva la ambigüedad y queda documentada. No se consulta tick a tick.

Los datos se escriben bajo `webui/uploads`, ignorado por Git. En el contenedor corresponde al volumen escribible `uploaded-data`; `/app/data` sigue siendo solo lectura. La imagen existente no incluye los módulos nuevos: para ejecutar allí sin alterar el servicio, montar esta copia del repositorio, por ejemplo:

```powershell
docker run --rm --entrypoint python --workdir /workspace -v C:/PROYECTOS/kronos/Kronos:/workspace:ro -v kronos_uploaded-data:/workspace/webui/uploads kronos-kronos -m research.false_breakout.download_history --start 2025-10-17T00:00:00Z --end 2026-10-17T00:00:00Z --output webui/uploads/bitget_baseline_20261017
```

Ese volumen Docker y `webui/uploads` de Windows son ubicaciones físicas distintas; copiar explícitamente los datos si se cambia de entorno. La ruta de código y el nombre del volumen deben adaptarse al entorno. Para informes en Docker elegir un directorio montado como escribible. No es necesario reconstruir ni reiniciar Flask.

## Interpretación

`config.json` congela los supuestos antes de ejecutar: 20 barras previas, horizonte 72, SL con un tick, TP +1 % del margen efectivo, costes de mercado supuestos 0,0006 por lado, slippage 1 bp entrada/TP/timeout y 2 bp SL. No son las tarifas verificadas de la cuenta. Sensibilidad de apalancamiento predefinida 1/3/5/10x, sin seleccionar después el escenario más favorable. Margen virtual máximo 1.000 USDT por operación, capital 10.000 USDT, ambos editables. No se optimiza ningún horizonte ni filtro.

Se redondea cantidad al lote inferior y se define margen como nominal de entrada ejecutado dividido por apalancamiento. Las comisiones se restan fuera de ese margen; el denominador no incluye comisión. El slippage está en el precio ejecutado y no se descuenta otra vez. TIMEOUT cierra al final del horizonte con costes, aunque su PnL pueda ser positivo. Funding excluido explícitamente: todos los resultados son provisionales y no constituyen neto completo.

El contexto nativo 15m/1H se une por fecha de cierre, conocida en la entrada; se registra la vela disponible y nunca actúa como filtro. Señales duales se excluyen de entradas. El final sin horizonte completo no se clasifica como timeout ni ganador. Se purga el horizonte máximo completo antes de fronteras 60/20/20 por tiempo; se aplica además embargo de 72 barras al principio de validación/test. No hay ajuste de parámetros ni entrenamiento: discovery es solo el nombre del segmento inicial.

`events_*` incluye todas las señales y razones de exclusión; `portfolio_*` recoge solo entradas secuenciales válidas sin solapamiento, sin reinversión y con capital suficiente. Las señales dentro de purga/embargo no entran en cartera. Las ambiguas de ejecución se incluyen con pérdida conservadora; las ambiguas de dirección nunca se operan. `equity_*` marca a cierre 5m, con comisiones realizadas; el DD no captura los extremos intrabar ni liquidación forzosa. `summary.json` separa eventos, cartera, dirección, partición, meses y semanas. La tasa TP usa eventos EVALUABLE, incluyendo ambiguos de ejecución como no TP; las medias/PF utilizan operaciones con PnL, incluyendo TIMEOUT.

Conservar datos y caché junto a informes para repetir los resultados. `manifest.json` registra hashes SHA-256 de datos, código y artefactos; Git HEAD por sí solo no identifica cambios sin commit. Repeticiones usan un directorio de informe nuevo y `verify_results` recalcula la contabilidad sin importar el módulo financiero. El tramo test queda observado tras la primera ejecución: posteriores cambios necesitan otro conjunto final.

## Fuentes oficiales consultadas

- [Bitget Market Data: histórico, instrumentos y reloj](https://www.bitget.com/docs/catalog/market/market-data).

La documentación oficial y la respuesta real se contrastaron el 17-10-2026. Histórico: `/api/v3/market/history-candles`, 100 velas/página, ventana máxima 90 días, frecuencia publicada 20/s/IP. El cliente limita su frecuencia y aplica reintentos acotados, espera exponencial y `Retry-After` numérico hasta 60 segundos. La metainformación actual de XRPUSDT devuelve tick 0,0001, lote y mínimo de 1 XRP, mínimo nominal 5 USDT; se guarda en `instrument.json`. No se presupone que esos valores fueran idénticos todo el año.
