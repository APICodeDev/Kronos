# Cómo se traduce la actuación publicada de operadores a un experimento

Consulta realizada el 17-10-2026. Se mantienen XRPUSDT, el rango local ya descargado y detección en 1H/1x. No se compran cursos ni se requieren claves privadas. Este documento fija la interpretación antes de calcular los nuevos resultados; los resultados se publican por separado en PRACTITIONER_RESULTS.md.

## Fuentes originales y aplicación concreta

| Autor / publicación | Principio publicado | Aplicación comprobable |
|---|---|---|
| [Adam Grimes: Fundamental Trading Patterns](https://www.adamhgrimes.com/fundamental-trading-patterns/) y [The pullback: a trade that works](https://adamhgrimes.com/pullback-trade-works/) | Identificar fuerza previa, esperar una corrección y considerar entrada cuando se reanuda la dirección. | Impulso confirmado sobre niveles anteriores; esperar retroceso antes de la primera confirmación. |
| [SMB Training: How to improve your trading entries](https://www.smbtraining.com/blog/how-to-improve-your-trading-entries) | Analizar niveles sostenidos, actividad y localización. La distancia desde la entrada hasta la invalidación cambia el atractivo de una operación. | Nivel roto conservado, entrada siguiente, stop estructural, comprobación del espacio y recompensa/riesgo antes de abrir. |
| [Morpheus Trading: Miss the breakout? Buy the pullback](https://morpheustrading.com/blog/miss-breakout-buy-pullback/) | Ejemplo de ruptura con actividad, retroceso de volumen menor y posterior reanudación. | Volumen relativo del impulso, contracción durante el retroceso y aumento al confirmar; comparar con la misma estructura sin esas tres condiciones. |
| [Al Brooks: Learn how to trade trend channels](https://www.brookstradingcourse.com/futures-market/trade-trend-channels/) | Distinguir tendencia y rango, situar el stop según estructura, adaptar cantidad al riesgo y buscar recompensa doble en swing. | Operación a favor del impulso; stop fuera del retroceso; riesgo modelado limitado al 0,25% del capital inicial; TP neto mínimo 2R y +1% de margen. |
| [Mike Bellafiore / SMB: Finding the setups best for your trading personality](https://www.smbtraining.com/blog/finding-the-setups-best-for-your-trading-personality) | Construir un playbook, practicar un setup y medir/revisar resultados. | Diario de todas las oportunidades y rechazos; primeras fichas por orden temporal, no elegidas por rentabilidad. |

El punto común es una secuencia de decisiones: **contexto → zona → retroceso → confirmación → invalidación → tamaño → espacio/objetivo → entrada o no operar → revisión**. No todos los operadores usan los mismos indicadores o volumen. No se atribuye a Grimes la exigencia concreta de volumen de Morpheus, ni a Brooks nuestros umbrales.

Son métodos y ejemplos publicados por sus autores o firmas. Sus páginas educativas no equivalen a historiales de cuenta auditados ni prueban que una adaptación determinista sea rentable. Grimes y Brooks permiten enfoques de gestión distintos; aquí se escoge una sola versión declarada para poder medirla.

## Traducción y decisiones nuestras

[practitioner_protocol.json](practitioner_protocol.json) conserva cada umbral, las dos variantes, el criterio de evaluación y la relación con las fuentes. Los números **20 horas, 1 ATR, 2..6 horas, 0,25 ATR, 1,5 de volumen relativo, 24 horas y 0,25% de riesgo** son elecciones de implementación anteriores al resultado. No son una receta textual común a los autores ni se han ajustado hasta obtener beneficios.

Se parte de una ruptura con cuerpo amplio respecto al ATR anterior, pero no se compra esa vela. Se espera que el precio retroceda sin perder por cierre el nivel roto ni cruzar el origen del impulso. La primera confirmación rompe el extremo de la hora anterior con cuerpo a favor. La variante principal exige participación alta en el impulso, menor volumen durante el retroceso y aumento frente a la hora anterior al confirmar.

La entrada se decide con la apertura siguiente conocida, descontando ejecuciones adversas. El stop abarca todo el retroceso, incluida la confirmación. La cantidad se reduce si la pérdida prevista supera 25 USDT sobre 10.000 iniciales; también se limita el margen a 1.000 USDT a 1x. El objetivo se calcula con comisiones, ticks y deslizamiento: al menos +1% sobre margen y dos veces la pérdida neta prevista. Se rechaza si el objetivo queda más allá del extremo previo del impulso. Los gaps pueden causar pérdidas superiores a las previstas.

Esperar hasta 24 horas es una decisión explícita de mantenimiento para esta hipótesis swing; la información y las señales siguen siendo de 1H. No se comparan múltiples horizontes para elegir el mejor. Las barreras se resuelven en 5m y, si es necesario y posible, 1m. La variante sin volumen sirve como comparación de selección, manteniendo idéntico plan para cada evento compartido.

## Lo que los datos permiten y lo que no

Tenemos OHLC, volumen base y turnover por vela. La [documentación de Bitget](https://www.bitget.com/docs/catalog/market/market-data#get-klinecandlestick-history) identifica volumen base y turnover cotizado en la respuesta. Para XRPUSDT se compara volumen de XRP dentro del mismo contrato; no se trata como volumen global de todas las bolsas ni como volumen comprador/vendedor.

Antes del experimento se comprueba continuidad y coherencia OHLC de 1H con sus doce subvelas 5m, presencia/positividad de volumen y turnover, y sumas de volumen. El turnover nativo tiene redondeo respecto al agregado; la tolerancia relativa de 1e-10 y absoluta de 1e-6 queda registrada. No se modifica ni rellena ningún dato para forzar coincidencia.

No hay identidades de operadores, agresores por operación, profundidad histórica ni noticias. Por tanto, expresiones como absorción o demanda institucional no se convierten en hechos observados mediante OHLCV. La lectura cualitativa del volumen se utiliza como hipótesis, no como identificación de quién compra.

El mismo histórico conocido sirve para esta investigación. Se conserva la exclusión del último 20% anterior y la purga/embargo de 24 horas; no se llama independiente a una validación que ya fue examinada con otras reglas. Funding incompleto se mantiene como limitación de contabilidad, no como falta de volumen o velas. No se amplía el rango ni se entrenan modelos.
