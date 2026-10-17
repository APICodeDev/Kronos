# Auditoría inicial — 17-10-2026

Se leyó `KRONOS_SPEC.md` completo antes de editar código. Rama local `master`, HEAD `923686f` (`Nuevas mejoras y adapatadas a normas de kraken`). No había diferencias en archivos versionados ni cambios staged. Había `KRONOS_SPEC.md` y 18 JSON de predicciones locales sin seguimiento, desde `prediction_20261010_174734.json` hasta `prediction_20261016_221335.json`. Se han conservado. No se cambió de rama, no se hizo commit ni push.

## Estado confirmado

- `webui/app.py` es Flask; `UPLOAD_FOLDER` se resuelve a `webui/uploads` mediante la ruta absoluta del módulo.
- `webui/kraken_data.py` conserva descarga pública de spot, caché, validación OHLC, exclusión de vela abierta y límite de 719 velas cerradas. No sirve como histórico de futuros de meses.
- `compose.yaml` mantiene CPU, puerto 7070, `data:/app/data:ro`, cargas persistentes y caché de Hugging Face. No se cambió ni reinició el servicio existente.
- La imagen Docker solo copia modelo, Flask, Kraken y recursos de interfaz; el flujo nuevo se ejecuta en Python local o montando el repositorio en un contenedor independiente, según README.
- Las auditorías anteriores de `research/` estudian inferencia/modelo/Pine; no incluyen este detector ni demuestran ventaja del patrón. Se conservaron sin cambios.
- No se encontraron archivos `AGENTS.md` en el repositorio ni en sus directorios ascendentes revisados.
- La máquina dispone de Python 3.14.3, NumPy 2.4.4, pandas 2.3.3, requests 2.32.5, PyArrow 25.0.0 y pytest 8.4.2. PyArrow permite persistir tanto CSV como Parquet sin instalar dependencias pesadas.

## Pruebas antes de integrar cambios

El Python local no tenía `plotly` ni `torch`: la colección original falló con `ModuleNotFoundError`. No se alteró su instalación global. Se utilizó la imagen existente `kronos-kronos` para verificar el repositorio real montado como solo lectura, sin interactuar con el proceso Flask en ejecución.

```powershell
docker run --rm --entrypoint python --workdir /workspace -v C:/PROYECTOS/kronos/Kronos:/workspace:ro kronos-kronos -m unittest discover -s tests -p 'test_webui_*.py'
```

Resultado: **19 pruebas OK**, 5,543 s. Advertencias existentes de Plotly/pandas sobre `to_pydatetime`, sin fallos.

Se ejecutó además la regresión real del modelo en CPU con su caché montada como solo lectura. Solo se instaló pytest en `/tmp` del contenedor efímero; no se entrenó ni ajustó ningún modelo.

```powershell
docker run --rm --entrypoint sh --workdir /workspace -e PYTHONDONTWRITEBYTECODE=1 -e OMP_NUM_THREADS=4 -v C:/PROYECTOS/kronos/Kronos:/workspace:ro -v kronos_huggingface-cache:/home/kronos/.cache/huggingface:ro kronos-kronos -c 'python -m pip install --target /tmp/test-deps pytest >/tmp/install-test.log 2>&1 && PYTHONPATH=/tmp/test-deps:/workspace python -m pytest tests/test_kronos_regression.py -q -p no:cacheprovider'
```

Resultado: **4 pruebas OK**, 127,02 s. Una advertencia de pytest sobre el `zip` usado en la parametrización existente. Ambas longitudes de contexto y ambas comprobaciones MSE pasan.

## Decisiones del primer hito

Adaptador público independiente y comandos CLI, sin cambios en Flask, Kraken, modelo, Dockerfile ni Compose. Contextos nativos para evitar hipótesis de resampling. Configuración JSON para no añadir dependencia YAML. Costes, tamaño, capital y escenarios explícitos; funding excluido y declarado provisional. Descarga reproducible de un año con fechas UTC fijas y caché. La línea base no usa filtros ni entrenamiento.

`README.md` contiene los comandos y la semántica; el informe generado conserva resultados y limitaciones. `manifest.json` registra hashes de código y datos para identificar también este trabajo sin commit. Los CSV de mercado y tablas voluminosas permanecen locales; no se guardan claves ni se envían órdenes.

## Validación de los módulos nuevos

```powershell
python -m pytest tests/test_bitget_data.py tests/test_costs.py tests/test_false_breakout.py -q
python -m ruff check webui/bitget_data.py research/false_breakout tests/test_bitget_data.py tests/test_costs.py tests/test_false_breakout.py
```

Resultado final: **50 pruebas nuevas OK**, 4,46 s; Ruff sin incidencias. Se cubren paginación, fronteras y velas cerradas, respuestas vacías, errores HTTP/API, reintentos y rate limits, huecos y duplicados contradictorios, validación OHLC, objetivo financiero LONG/SHORT con cuatro apalancamientos, cálculo manual independiente, siguiente apertura, gaps, TIMEOUT, doble barrera y resolución 1m, contextos causales, purga/embargo, cartera sin solapamiento, ejecución CLI con/sin señales, hashes y protección contra sobrescritura.

Total de la validación ejecutada: **73 pruebas aprobadas**. Los comandos, entornos y resultados se conservan también en `validation.json`. El fallo inicial del tratamiento de una página vacía se corrigió antes de generar el backtest; no se ocultó rellenando velas.

## Incidencia durante la primera ejecución histórica

El primer intento (`reports/baseline_20261017/`) calculó la tabla de eventos 1x y se detuvo al construir la curva: las filas sin salida convertían los índices de la columna de salida a float, incompatibles con `iloc`. No produjo informe ni conclusión financiera. Se conserva el CSV parcial, sin sobrescribirlo. Se corrigió mediante conversión explícita de los índices a enteros y se añadió una prueba con eventos mezclados ejecutables/sin entrada. La ejecución completa usa `reports/baseline_20261017_v1/` con idénticos parámetros; no se hicieron ajustes guiados por el rendimiento.
