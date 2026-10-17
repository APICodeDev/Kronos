"""HTML Plotly sin red, solo fichas preentrada; ejecutable en la imagen existente."""
import argparse
from pathlib import Path
import html
import json

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--review', required=True)
    args = parser.parse_args()
    folder = Path(args.review)
    output = folder / 'REVIEW.html'
    if output.exists():
        raise FileExistsError('No sobrescribir el panel de revisión.')
    summary = json.loads((folder / 'cases.json').read_text(encoding='utf-8'))
    parts = ['<!doctype html><html lang="es"><meta charset="utf-8"><title>Revisión de contexto previo</title>',
             '<style>body{font:16px system-ui;max-width:1400px;margin:32px auto;padding:0 16px;color:#182332;background:#f5f7fa}section{background:white;padding:20px;margin:24px 0;border-radius:12px}h1{font-size:28px}h2{font-size:21px}.note{background:#fff4d6;padding:14px}p{line-height:1.6}a{color:#125aa0}</style>',
             '<h1>Qué podía verse antes de la entrada</h1>',
             '<p class="note">Auditoría retrospectiva de cuatro casos del mismo histórico. El futuro, los fills y el resultado de cada operación están ocultos. No es una validación ciega independiente ni una nueva estrategia.</p>',
             '<p>1H conserva la temporalidad de señal. El contexto 2H y diario usa exclusivamente velas completas construidas con las horas ya cerradas. La EMA(20) sirve de referencia descriptiva; no activa una operación.</p>']
    include_js = True
    for case in summary['cases']:
        name = case['case_id']
        parts.append(f'<section><h2>{html.escape(name)} · {html.escape(case["side"])} · corte {html.escape(case["asof"])}</h2>')
        parts.append(f'<p>Cuerpo del impulso: {case["impulse_body_atr"]:.2f} ATR previos. Volumen relativo: {case["impulse_relative_volume"]:.2f}. Devolución del cuerpo durante el retroceso: {case["giveback_fraction_of_impulse_body"]:.1%}. Son descripciones conocidas al corte, no probabilidades.</p>')
        figure = make_subplots(rows=4, cols=1, shared_xaxes=False, row_heights=[.19, .25, .4, .16],
                               subplot_titles=['Diario cerrado', 'Contexto 2H cerrado', 'Señal 1H, hasta el cierre de confirmación', 'Volumen de las velas 1H'], vertical_spacing=.06)
        for row, interval in [(1, '1D'), (2, '2H'), (3, '1H')]:
            frame = pd.read_csv(folder / f'{name}_{interval}.csv', parse_dates=['timestamp', 'available_at'])
            if (frame.available_at > pd.Timestamp(case['asof'])).any():
                raise AssertionError('Gráfico con una vela aún no disponible.')
            figure.add_trace(go.Candlestick(x=frame.timestamp, open=frame.open, high=frame.high, low=frame.low,
                                            close=frame.close, name=interval, showlegend=False), row=row, col=1)
            if interval == '1H':
                figure.add_trace(go.Scatter(x=frame.timestamp, y=frame.ema20, name='EMA 20, descriptiva', line={'color': '#d69000', 'width': 1.5}), row=3, col=1)
                figure.add_trace(go.Bar(x=frame.timestamp, y=frame.volume, name='Volumen XRP', marker_color='#607ea2', showlegend=False), row=4, col=1)
                figure.add_hline(y=case['level'], line_dash='dot', line_color='#2563eb', row=3, col=1)
                figure.add_hline(y=case['stop'], line_dash='dash', line_color='#b42318', row=3, col=1)
        figure.update_xaxes(rangeslider_visible=False)
        figure.update_layout(height=1000, template='plotly_white', margin={'l': 65, 'r': 25, 't': 45, 'b': 30},
                             legend={'orientation': 'h'}, dragmode='pan')
        parts.append(figure.to_html(full_html=False, include_plotlyjs=True if include_js else False,
                                   config={'displaylogo': False, 'scrollZoom': False}))
        include_js = False
        parts.append('<p>Nivel roto: línea azul. Stop estructural del plan anterior: línea roja. Preguntas: ¿fuerza nueva o posible clímax?, ¿primer retroceso o secuencia avanzada?, ¿se conservan las ganancias?, ¿el contexto contradice la dirección?, ¿qué respuesta invalidaría la idea? El gráfico no decide las respuestas por el beneficio posterior.</p></section>')
    parts.append('</html>')
    output.write_text('\n'.join(parts), encoding='utf-8')
    print(output)


if __name__ == '__main__':
    main()
