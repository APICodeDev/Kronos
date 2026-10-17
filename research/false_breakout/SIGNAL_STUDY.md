# Ampliación de la investigación: señal frente a gestión

**Que fallen dos configuraciones no descarta el proyecto ni demuestra que no pueda existir una estrategia rentable. La conclusión correcta es más acotada: falta evidencia de ventaja para esta regla concreta.** Por eso se amplió el diagnóstico, separando la dirección del patrón de los TP/SL utilizados antes.

Tener más datos, conocimiento o cómputo ayuda a investigar y verificar, pero no garantiza reproducir la ventaja de un operador humano. Harían falta también sus condiciones de entrada, ejecución, costes, gestión y resultados verificables. El objetivo del proyecto se mantiene: encontrar una ventaja neta reproducible, no justificar una rentabilidad asumida de antemano.

## Trabajo realizado

Se registró [signal_study_protocol.json](signal_study_protocol.json) antes de calcular resultados. Se mantuvieron XRPUSDT perpetuo, 1H y 1x, el patrón original de 20 velas y la entrada siguiente. Se suprimieron TP/SL y se midieron cierres después de **1, 6 y 24 horas**, presentando todos los perfiles LONG/SHORT.

Cada señal se comparó con horas sin señal del mismo segmento, mes UTC, bloque de ocho horas y banda fija de volatilidad causal. Se exigieron al menos diez controles comparables y no se relajaron criterios para mejorar el resultado. Discovery conservó 530 de 538 señales; validación, las 184 disponibles. Las mismas señales elegibles se utilizaron en todos los horizontes para evitar comparar muestras diferentes según el resultado.

Se excluyeron las **1.752 horas del antiguo test antes de construir características o etiquetas**. Se utilizaron investigación hasta el 24-05-2026 y validación desde el 25-05-2026 hasta el 05-08-2026, con purga y embargo de 24 horas. Ambos segmentos ya se habían observado antes: este contraste es diagnóstico retrospectivo, no una nueva validación independiente.

## Resultados de validación

PnL medio por evento, tras las mismas comisiones y slippage previstos, sin funding; margen efectivo próximo a 1.000 USDT:

| Salida fija | LONG: 100 señales | SHORT: 84 señales |
|---|---:|---:|
| Después de 1 hora | −0,9781 USDT | −2,3383 USDT |
| Después de 6 horas | −1,9885 USDT | −1,8884 USDT |
| Después de 24 horas | −6,4942 USDT | −3,3321 USDT |

**Ninguno de los seis perfiles tiene una media neta positiva en validación.** No se reconstruye una cartera con estas sumas: los eventos pueden solaparse y mantenerlos sin stop no equivale a una estrategia con riesgo definido.

En investigación, SHORT a 24 horas tuvo una media positiva de **+0,9188 USDT**. En validación pasó a **−3,3321 USDT**. Es un ejemplo concreto de por qué encontrar un resultado favorable en una muestra no basta para declarar una ventaja.

Frente a controles, LONG a una hora mejora unos **0,7156 USDT** por evento en validación, pero sigue perdiendo en términos absolutos. Los otros cinco perfiles quedan por debajo del control. Todas las bandas descriptivas ajustadas de diferencia frente al control incluyen cero. No hay evidencia sólida aquí para afirmar que la señal aporte una ventaja explotable por sí sola.

## Qué revelan los recorridos del precio

En validación, alrededor del **60 %** de las señales de ambos sentidos alcanzaron alguna vez el precio necesario para el objetivo neto modelado dentro de 24 horas si se ignora el SL. Eso no significa un 60 % de operaciones ganadoras: el máximo favorable solo se conoce después y puede llegar tras una pérdida grande, con costes de financiación y riesgo no cubiertos.

Por ejemplo, en LONG a 24 horas, la excursión favorable mediana es aproximadamente **1,50 % del precio**, pero la adversa mediana es **2,13 %**. Ni comprar el mínimo ni vender el máximo son decisiones que puedan deducirse retrospectivamente como si estuvieran disponibles al entrar. El código mantiene esos extremos como etiquetas descriptivas y nunca los usa para seleccionar entradas o salidas ejecutables.

## Conclusiones y continuidad del proyecto

1. La investigación anterior no debía interpretarse como abandonar la posibilidad de un sistema rentable. Lo descartado son configuraciones concretas de una familia de reversión.
2. Este nuevo contraste no respalda que baste cambiar el TP o esperar más tiempo: con cierres a tres horizontes tampoco aparece rentabilidad neta estable en validación. No prueba que ninguna gestión imaginable pueda funcionar.
3. La siguiente familia que merece formularse como hipótesis independiente es **continuación de tendencia/momentum**, en lugar de seguir suponiendo reversión por un falso rompimiento. Hay evidencia histórica de momentum en criptomonedas en [Liu y Tsyvinski, Risks and Returns of Cryptocurrency](https://www.nber.org/papers/w24877), pero sus resultados diarios/semanales y su muestra histórica no demuestran rentabilidad actual en XRPUSDT a 1H. Sirven de fundamento para una pregunta investigable, no de resultado transferible.
4. Antes de probar otra familia deben registrarse reglas, controles, gestión de riesgo, costes y criterio de abandono. El histórico examinado sirve para diseño exploratorio; una confirmación requiere un período nuevo sin examinar y suficiente cobertura de estados de mercado.
5. Se mantiene el objetivo de rentabilidad neta, pero no se presupone que más indicadores, un modelo neuronal o más búsquedas vayan a producirla. Solo una señal defendible y una gestión viable justificarían estudiar después un clasificador pequeño.

Este turno amplía la investigación y crea herramientas de contraste. **No ha descubierto todavía una estrategia rentable ni ha entrenado un modelo.** Tampoco ha probado una estrategia de momentum; esa propuesta queda diferenciada de los resultados medidos. No se ha operado dinero real ni modificado los experimentos anteriores.

## Calidad y reproducción

- **88 pruebas locales aprobadas**, incluidas 10 nuevas de causalidad, exclusión del test, ventanas completas, controles ponderados, falta de soporte y bootstrap reproducible. No se modificaron los motores de datos o ejecución existentes en este estudio.
- **39.330 filas de evaluación financiera** comprobadas mediante Decimal; **2.142 filas de señales emparejadas** contrastadas contra sus controles. Son filas repetidas por horizonte y sentido, no 39.330 operaciones independientes. Error máximo **2,108 × 10⁻¹²**, por debajo de la tolerancia de 0,000001.
- Repetición sin red: **7 archivos idénticos por hash**. Se verificaron también los hashes de los scripts y resultados previos de 1H; el trabajo heredado permanece intacto.
- Bootstrap conjunto de señales y controles por semana UTC, 5.000 remuestreos y semilla 20261017. Las bandas de seis comparaciones por segmento son aproximaciones exploratorias, no pruebas definitivas; persisten pocos bloques, dependencia entre ventanas y variables de mercado no emparejadas.
- Funding excluido, particularmente relevante a 24 horas. No se simula capital, liquidación ni el riesgo completo de mantener posiciones sin SL. El emparejamiento observacional no establece causalidad.

[Informe generado](reports/signal_study_20261017/REPORT.md) · [Todos los perfiles](reports/signal_study_20261017/summary.json) · [Verificación](reports/signal_study_20261017/verification.json) · [Hashes](reports/signal_study_20261017/manifest.json) · [Reproducción](reports/signal_study_20261017/reproducibility.json).

```powershell
python -m research.false_breakout.study_signal --output NUEVO_DIRECTORIO
python -m research.false_breakout.verify_signal_study --report NUEVO_DIRECTORIO
python -m pytest tests/test_signal_study.py tests/test_hourly.py tests/test_economic_diagnosis.py tests/test_bitget_data.py tests/test_costs.py tests/test_false_breakout.py -q
```

Todo el flujo usa datos locales y CPU, sin red ni claves privadas. Los comandos completos y versiones están en el informe. Sin commits ni push.

Referencia de método: [Bailey y colaboradores, The Probability of Backtest Overfitting](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2326253), sobre el riesgo de seleccionar estrategias a partir de múltiples backtests. No se ha implementado ni calculado su estimador PBO en este trabajo.
