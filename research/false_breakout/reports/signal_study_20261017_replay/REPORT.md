# ¿Aporta información la señal, aparte de sus TP/SL?

**Estudio exploratorio. No es una estrategia optimizada ni un resultado de cartera. No utiliza el antiguo segmento test.**

Se mantienen XRPUSDT perpetuo, 1H, 1x, niveles de 20 velas anteriores, entrada siguiente y costes previos. Se eliminan TP/SL para medir cierres a 1, 6 y 24 horas. Los controles son horas sin señal, del mismo segmento, mes UTC, bloque horario de ocho horas y banda fija de volatilidad causal. Se requieren diez controles por estrato; los casos sin soporte se cuentan y se excluyen, sin ampliar bandas buscando resultados.

Ventanas utilizadas: {'start': '2025-10-17 00:00:00+00:00', 'discovery_end': '2026-05-24 00:00:00+00:00', 'validation_start': '2026-05-25 00:00:00+00:00', 'research_end': '2026-08-05 00:00:00+00:00', 'excluded_test_rows': 1752}. El último 20 % se recorta antes de construir indicadores y etiquetas. Purga y embargo de 24 horas: todos los perfiles usan la misma elegibilidad temporal. Los segmentos ya se habían examinado en trabajos previos y no son una validación independiente nueva.

## Todos los perfiles registrados

| Segmento | Dirección | Horas | Señales emparejadas / totales | Neto señal USDT | Neto control emparejado USDT | Diferencia USDT |
|---|---|---:|---:|---:|---:|---:|
| discovery | LONG | 1 | 315 / 320 | -1.4156 | -1.5494 | 0.1338 |
| discovery | LONG | 6 | 315 / 320 | -0.2684 | -1.5766 | 1.3083 |
| discovery | LONG | 24 | 315 / 320 | -0.6712 | -2.9653 | 2.2940 |
| discovery | SHORT | 1 | 215 / 218 | -1.1582 | -1.4603 | 0.3021 |
| discovery | SHORT | 6 | 215 / 218 | -1.5274 | -1.3430 | -0.1845 |
| discovery | SHORT | 24 | 215 / 218 | 0.9188 | -0.5456 | 1.4644 |
| validation | LONG | 1 | 100 / 100 | -0.9781 | -1.6937 | 0.7156 |
| validation | LONG | 6 | 100 / 100 | -1.9885 | -1.6228 | -0.3657 |
| validation | LONG | 24 | 100 / 100 | -6.4942 | -4.5803 | -1.9139 |
| validation | SHORT | 1 | 84 / 84 | -2.3383 | -1.3913 | -0.9470 |
| validation | SHORT | 6 | 84 / 84 | -1.8884 | -1.2674 | -0.6210 |
| validation | SHORT | 24 | 84 / 84 | -3.3321 | 0.5089 | -3.8410 |

Importes medios por evento, margen efectivo cercano a 1.000 USDT. Controles ponderados como las señales: cada evento se compara con la media de su propio estrato. La diferencia mide asociación condicional, no causalidad ni beneficio ejecutable de cartera. No se suman eventos solapados como si fueran capital.

## Recorrido disponible y riesgo en validación

| Dirección | Horas | Fracción que alguna vez alcanzó el objetivo sin SL | MFE mediana, bp precio | MAE mediana, bp precio | Banda ajustada exceso, bp margen |
|---|---:|---:|---:|---:|---|
| LONG | 1 | 6.00% | 30.67 | 32.72 | [-12.03471925500835, 26.198955513702057] |
| LONG | 6 | 31.00% | 83.28 | 98.73 | [-26.579481164937174, 18.51224462990373] |
| LONG | 24 | 60.00% | 149.76 | 213.17 | [-86.30555462911494, 55.10802375399499] |
| SHORT | 1 | 1.19% | 25.22 | 41.25 | [-21.26400314154998, 4.823966667502179] |
| SHORT | 6 | 34.52% | 70.42 | 80.74 | [-49.55600795582, 30.846832421612376] |
| SHORT | 24 | 60.71% | 151.30 | 122.99 | [-169.84130301862643, 52.0836751222309] |

MFE/MAE son extremos que solo se conocen después. Alcanzar el precio objetivo en algún momento sin stop no significa que se pueda elegir ese máximo para salir, ni que no se haya soportado antes una pérdida grande. Ningún extremo futuro se usa como característica, filtro o precio ejecutable del backtest.

## Qué significa el contraste

Una media superior al control con una media neta negativa no constituye una oportunidad rentable. Una media positiva aislada tampoco prueba ventaja después de financiación, riesgo, límites de cartera y selección entre alternativas. Se muestran los seis perfiles dirección/horizonte por segmento, sin elegir un ganador.
Se remuestrean conjuntamente semanas UTC de señales y controles y se recalculan las medias de control por estrato. 5.000 remuestreos, semilla fija. Hay intervalos percentiles descriptivos del 95 % y una banda adicional con cuantiles Bonferroni para seis perfiles por segmento. Son aproximaciones: los bloques extremos pueden ser parciales, las ventanas cruzan semanas y el emparejamiento no controla todos los estados de mercado. No son una certificación estadística ni eliminan el sesgo de investigaciones anteriores.

## Límites y decisión

El estudio separa señal y gestión, pero no establece una estrategia rentable. No se selecciona un perfil por su mejor resultado ni se utiliza el antiguo test para volver a ajustar la regla.
El funding está excluido, especialmente material al extender el horizonte a 24 horas. No se reconstruye una cartera ni el riesgo de mantener posiciones sin SL. El control no es una prueba causal aleatoria: solo ajusta las variables de emparejamiento fijadas. Los eventos sin controles suficientes quedan fuera de las medias y su cobertura se informa. No se ha ajustado ninguna banda, horizonte o salida después de observar los resultados.
El conocimiento y el cómputo permiten contrastar más hipótesis y detectar errores; no garantizan que estos datos contengan una ventaja explotable con estos costes. Si aparece una asociación útil, el paso siguiente sería registrar una hipótesis de ejecución y validarla con datos nuevos, sin convertir retrospectivamente el mejor extremo del precio en una operación.

## Reproducibilidad

protocol.json copia las decisiones registradas antes del cálculo. summary.json incluye todos los perfiles y sus intervalos; los CSV conservan resultados de señales y controles. manifest.json registra hashes de entradas, scripts, protocolo y salidas. El comando de command.txt reproduce el estudio sin red en un directorio nuevo. Se conservan todos los experimentos anteriores.
Referencia metodológica: [Bailey y colaboradores, The Probability of Backtest Overfitting](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2326253). El trabajo explica por qué seleccionar estrategias a partir de muchos backtests puede sobreajustar; este estudio no implementa su estimador PBO ni pretende haberlo calculado.
