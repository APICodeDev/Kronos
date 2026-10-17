"""Experimento exploratorio 1H/1x, horizonte seis horas, ejecución 5m/1m."""
import argparse
import importlib.metadata
import json
import platform
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

from webui.bitget_data import sha256
from .backtest import attach_context, barrier, detect_signals, label_event, partition, simulate_portfolio
from .costs import validate_config
from .economic_diagnosis import attribute_costs, clustered_ci, overlay_funding, stats
from .funding_data import download as download_funding
from .run_experiment import MinuteResolver, load_history, metrics, period_metrics


def validate_execution_data(hourly, fine, tick):
    fine = fine.set_index('timestamp')
    aggregated = fine.resample('1h').agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'})
    counts = fine.resample('1h').size()
    if not aggregated.index.equals(pd.DatetimeIndex(hourly.timestamp)) or not (counts == 12).all():
        raise ValueError('Las velas 5m no cubren exactamente las horas nativas.')
    delta = np.abs(aggregated.to_numpy() - hourly[['open', 'high', 'low', 'close']].to_numpy())
    if not np.isfinite(delta).all() or (delta > tick / 2).any():
        raise ValueError('Inconsistencia OHLC entre 1H y 5m; no se simula sobre datos contradictorios.')
    return {'hours_compared': len(hourly), 'bars_per_hour': 12, 'inconsistent_hours': 0,
            'max_absolute_price_difference': float(delta.max())}


class HourlyResolver:
    def __init__(self, fine, minute_resolver):
        self.fine = fine.set_index('timestamp', drop=False)
        self.minute_resolver = minute_resolver
        self.notes = {}
        self.last_resolution = None
        self.last_both_touched_5m = False

    def __call__(self, bar, side, stop, target):
        end = bar.timestamp + pd.Timedelta(hours=1)
        children = self.fine.loc[bar.timestamp:end - pd.Timedelta(nanoseconds=1)]
        if len(children) != 12:
            raise ValueError('Hora de ejecución sin sus 12 velas cerradas de 5m.')
        for child in children.itertuples(index=False):
            touch = barrier(child, side, stop, target)
            if touch is None:
                continue
            label, reference, at_open = touch
            exit_time = child.timestamp if at_open else child.timestamp + pd.Timedelta(minutes=5)
            self.last_resolution = '5m'
            self.last_both_touched_5m = label == 'AMBIGUOUS'
            if label == 'AMBIGUOUS':
                result = self.minute_resolver(child, side, stop, target)
                if result is not None:
                    label, reference, exit_time = result
                    self.last_resolution = '1m' if label != 'AMBIGUOUS' else '1m_AMBIGUOUS'
                else:
                    self.last_resolution = '5m_AMBIGUOUS'
            key = f'{bar.timestamp.isoformat()}|{side}|{stop:.8f}|{target:.8f}'
            self.notes[key] = {'label': label, 'exit_time': str(exit_time), 'resolution': self.last_resolution,
                               'both_touched_5m': self.last_both_touched_5m}
            return label, reference, exit_time
        raise AssertionError('La vela 1H toca una barrera que no aparece en sus velas 5m.')


def summarize_book(frame):
    return {'ALL': metrics(frame),
            'by_split': {split: metrics(group) for split, group in frame.groupby('split')},
            'by_side': {side: metrics(group) for side, group in frame.groupby('side')},
            'monthly': period_metrics(frame, 'MS'), 'weekly': period_metrics(frame, 'W-MON')}


def report(output, summary):
    event, portfolio = summary['events'], summary['portfolio']
    test = event['by_split'].get('test', {})
    test_port = portfolio['by_split'].get('test', {})
    lines = ['# Falso rompimiento XRPUSDT — 1H sin apalancamiento', '',
             '**Experimento exploratorio sobre un año ya observado. No es una nueva validación final independiente.**', '',
             summary['conclusion'], '',
             '## Configuración fijada antes de ejecutar', '',
             'Detección en velas nativas de 1H: niveles de las 20 velas anteriores (20 horas), excluyendo la actual. Entrada en la apertura de la hora siguiente. SL en extremo del barrido más un tick; TP calculado para al menos +1 % del margen efectivo tras comisiones y slippage previstos. Una sola posición por símbolo.',
             '1x, margen virtual máximo 1.000 USDT por operación, capital inicial 10.000 USDT, sin reinversión. Comisiones 0,0006 por lado; slippage 1 bp entrada/TP/timeout y 2 bp SL, con redondeo adverso. Son hipótesis, no tarifas efectivas de cuenta.',
             'Horizonte fijo de **6 horas = 6 velas de 1H**. No se probaron 72 horas ni se eligió un horizonte ganador. Particiones 60/20/20 por tiempo, purga del horizonte completo y embargo de 6 horas. Sin filtros HTF ni IA.', '',
             f"Datos UTC: {summary['start']} a {summary['end']} (fin excluido), {summary['data_quality']['1H']['rows']} velas de 1H y {summary['data_quality']['5m']['rows']} de 5m, sin huecos. Coincidencia OHLC 1H/agregado 5m: {summary['execution_validation']}.",
             f"Señales: {summary['signals_by_side']}. Estados de todas las señales: {summary['evaluation_status_counts']}. Etiquetas de todas las señales: {summary['all_candidates']['labels']}.", '',
             '## Resultados sin funding', '',
             '| Medida | Eventos elegibles | Cartera secuencial |', '|---|---:|---:|',
             f"| Operaciones | {event['ALL']['executed']} | {portfolio['ALL']['executed']} |",
             f"| Media neta USDT | {event['ALL']['mean_net_pnl']:.4f} | {portfolio['ALL']['mean_net_pnl']:.4f} |",
             f"| Mediana neta USDT | {event['ALL']['median_net_pnl']:.4f} | {portfolio['ALL']['median_net_pnl']:.4f} |",
             f"| Factor de beneficio | {event['ALL']['profit_factor']:.4f} | {portfolio['ALL']['profit_factor']:.4f} |",
             f"| Duración media min | {event['ALL']['mean_duration_minutes']:.2f} | {portfolio['ALL']['mean_duration_minutes']:.2f} |",
             f"| Eventos TP/SL/timeout/ambiguos | {event['ALL']['labels']} | {portfolio['ALL']['labels']} |", '',
             f"Cartera: PnL **{portfolio['ALL']['sum_net_pnl']:.4f} USDT**, ROI sobre capital inicial **{summary['capital_return']:.3%}**, drawdown máximo a cierre 1H **{summary['max_drawdown']:.3%}**. Sumar PnL de eventos solapados no constituye una cartera.", '',
             '## Particiones temporales', '', '| Tramo | Eventos | Media evento USDT | PF evento | Operaciones cartera | PnL cartera USDT |',
             '|---|---:|---:|---:|---:|---:|']
    for split in ['discovery', 'validation', 'test']:
        e = event['by_split'].get(split, {})
        p = portfolio['by_split'].get(split, {})
        lines.append(f"| {split} | {e.get('executed', 0)} | {e.get('mean_net_pnl')} | {e.get('profit_factor')} | {p.get('executed', 0)} | {p.get('sum_net_pnl')} |")
    lines += ['', '## LONG / SHORT', '', '| Dirección | N anual | Media anual USDT | N test | Media test USDT | PF test |', '|---|---:|---:|---:|---:|---:|']
    for side in ['LONG', 'SHORT']:
        all_side = summary['diagnosis']['events']['ALL'][side]
        test_side = summary['diagnosis']['events']['test'][side]
        lines.append(f"| {side} | {all_side['n']} | {all_side['mean_net']:.4f} | {test_side['n']} | {test_side['mean_net']:.4f} | {summary['test_by_side'][side]['profit_factor']} |")
    lines += ['', '## Costes y financiación en test', '']
    costs = summary['diagnosis']['events']['test']['ALL']
    funding = costs['funding']
    lines += [f"Por evento: referencia {costs['mean_reference_pnl']:.6f} − ejecución {costs['mean_execution_cost']:.6f} (slippage {costs['mean_nominal_slippage']:.6f}, tick {costs['mean_tick_rounding']:.6f}) − comisiones {costs['mean_fees']:.6f} = neto {costs['mean_net']:.6f} USDT.",
              f"Operaciones con PnL positivo: {costs['positive_rate_nonzero']:.3%}; equilibrio con pagos observados: {costs['break_even_positive_rate_nonzero']:.3%}. Ganador medio {costs['mean_winner']:.4f}, perdedor medio −{costs['mean_loser_abs']:.4f} USDT. Incluye timeout, no equivale a tasa TP.",
              f"Comisión cero con estas mismas ejecuciones: {costs['mean_gross_after_execution']:.6f} USDT/evento. Son ajustes contables sobre salidas congeladas, no un nuevo backtest con otros TP.",
              f"Funding: {funding['covered']}/{costs['n']} eventos de test cubiertos. Coste medio estimado {funding.get('mean_cost_estimate')} USDT; neto tras estimación {funding.get('mean_net_with_estimate')} USDT; sensibilidad favorable/desfavorable {funding.get('mean_net_sensitivity_high')} / {funding.get('mean_net_sensitivity_low')} USDT. TP originales de test que bajarían del +1 % tras funding estimado: {funding.get('tp_below_target_after_estimate')}.",
              'Las tasas son públicas, pero el mark se aproxima por la apertura de su vela nativa 1m. El punto central solo carga funding en instantes estrictamente interiores; la sensibilidad incorpora low/high del minuto y posibles cobros en entradas/salidas coincidentes. No son cotizaciones ni cobros exactos. Se mantienen etiquetas y cartera sin funding; el ajuste no recalcula su elegibilidad por capital. El año sigue sin funding completo.', '',
              '## Incertidumbre y comparación con 5m', '']
    lines += [f"Bootstrap descriptivo por {summary['test_bootstrap']['weeks']} bloques de semana UTC (extremos parciales), 5.000 remuestreos, semilla 20261017. IC 95 % media neta de eventos test: {summary['test_bootstrap']['intervals']['net_pnl']}; referencia: {summary['test_bootstrap']['intervals']['reference_pnl']}. No se supone independencia entre señales solapadas; pocos bloques y un solo año limitan la inferencia.",
              f"Referencia histórica 5m/1x, mismo horizonte y costes: {summary['comparison_5m']}. Cambian la ventana de niveles de 100 minutos a 20 horas y las oportunidades; esto no aísla solo un cambio de ruido o frecuencia.",
              f"En 1H, test tiene {test.get('executed', 0)} eventos y {test_port.get('executed', 0)} operaciones de cartera. El tramo ya se conocía por investigaciones anteriores y no se considera prueba independiente, aunque se mantengan las fronteras cronológicas.", '',
              '## Cartera por mes UTC', '', '| Mes | Operaciones | PnL USDT | Comisiones USDT |', '|---|---:|---:|---:|']
    for month, p in portfolio['monthly'].items():
        lines.append(f"| {month[:7]} | {p['executed']} | {p['sum_net_pnl']:.4f} | {p['entry_fees'] + p['exit_fees']:.4f} |")
    lines += ['', '## Ejecución, límites y reproducción', '',
              'Se comprueban las 12 velas de 5m por cada hora y su OHLC contra la vela nativa. Todas las salidas por barrera se recorren en 5m, incluyendo gaps adversos en aperturas de 5m. Si ambos niveles coinciden dentro de 5m, se consulta 1m; si sigue sin orden, etiqueta AMBIGUOUS y SL conservador. El timeout cierra al acabar la sexta hora con costes. No se usan subvelas para generar señales ni filtrar entradas.',
              'Capital a cierre de 1H: no mide drawdown intrabar ni liquidación. Metadatos actuales aplicados retrospectivamente, tarifas de cuenta desconocidas, sin modelar profundidad, latencia o ejecución parcial. La muestra es una sola criptomoneda y los resultados son provisionales sin financiación exacta. 1x sigue siendo un futuro perpetuo y conserva funding; no se han usado precios spot.',
              'La configuración está en config.json; summary.json contiene eventos, cartera, costes, meses/semanas y particiones. manifest.json registra código, versiones y hashes de entradas/salidas. command.txt permite repetir con otro directorio de salida. --offline solo usa caché. Los CSV grandes se conservan localmente. No se modifican los experimentos previos ni se entrena IA ni se envían órdenes.',
              f"Resoluciones: {summary['resolution_counts']}. Las ambigüedades de dirección, purga/embargo e incompletos están separadas de las operaciones ejecutables."]
    (output / 'REPORT.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', default='webui/uploads/bitget_baseline_20261017')
    parser.add_argument('--config', default='research/false_breakout/config_hourly.json')
    parser.add_argument('--funding', default='webui/uploads/bitget_hourly_funding_20261017')
    parser.add_argument('--resolution-cache', default='webui/uploads/bitget_hourly_resolution_20261017')
    parser.add_argument('--output', required=True)
    parser.add_argument('--offline', action='store_true')
    args = parser.parse_args()
    cfg = json.loads(Path(args.config).read_text(encoding='utf-8'))
    validate_config(cfg)
    if cfg['entry_interval'] != '1H' or cfg['leverage_scenarios'] != [1] or cfg['max_holding_bars'] != 6 or cfg['embargo_bars'] != 6:
        raise ValueError('Este experimento congela 1H/1x y seis horas de horizonte/embargo.')
    if cfg.get('execution_interval') != '5m' or cfg.get('resolve_all_touches') is not True:
        raise ValueError('La variante 1H requiere ejecución completa en 5m.')
    output, directory = Path(args.output), Path(args.data)
    if output.exists():
        raise FileExistsError('Usa un directorio de informe nuevo.')
    hourly, hourly_meta = load_history(directory, '1H', cfg)
    fine, fine_meta = load_history(directory, '5m', cfg)
    instrument_path = directory / 'instrument.json'
    inst = json.loads(instrument_path.read_text(encoding='utf-8'))
    if inst['symbol'] != cfg['symbol'] or inst['category'] != cfg['category']:
        raise ValueError('Contrato incompatible.')
    quality = validate_execution_data(hourly, fine, float(inst['priceMultiplier']))
    minute = MinuteResolver(Path(args.resolution_cache), cfg, inst, offline=args.offline)
    resolver = HourlyResolver(fine, minute)
    signals = attach_context(detect_signals(hourly, cfg['lookback_bars'], float(inst['priceMultiplier'])), {}, '1H')
    start, end = hourly.timestamp.iloc[0], hourly.timestamp.iloc[-1] + pd.Timedelta(hours=1)
    records = []
    print(f'Evaluando {len(signals)} candidatos 1H/1x con horizonte fijo de seis horas...', flush=True)
    for signal in signals.to_dict('records'):
        record = label_event(signal, hourly, cfg, inst, 1, resolver)
        split = partition(signal['entry_time'], signal['entry_time'] + pd.Timedelta(hours=6), start, end, cfg)
        record['split'] = split
        if split in {'PURGED', 'EMBARGO', 'INCOMPLETE'}:
            record['evaluation_status'] = split
        records.append(record)
    events = pd.DataFrame(records)
    if events.empty:
        raise ValueError('No hay candidatos 1H; no se produce un informe vacío como resultado financiero.')
    eligible = events[(events.evaluation_status == 'EVALUABLE') & events.net_pnl.notna()].copy()
    trades, curve = simulate_portfolio(events, hourly, cfg)
    if len(eligible[eligible.split == 'test']) == 0:
        raise ValueError('No hay eventos finales evaluables.')
    print('Estimando funding público disponible sin modificar las operaciones...', flush=True)
    funding_directory = Path(args.funding)
    funding_meta = download_funding(funding_directory, cfg, eligible, offline=args.offline)
    rates = pd.read_csv(funding_directory / 'rates.csv', parse_dates=['timestamp'])
    marks = pd.read_csv(funding_directory / 'marks.csv', parse_dates=['timestamp'])
    diagnosed, diagnosis = {}, {}
    for book, frame in [('events', eligible), ('portfolio', trades)]:
        diagnosed[book] = overlay_funding(attribute_costs(frame, cfg, float(inst['priceMultiplier'])), rates, marks)
        diagnosis[book] = {}
        for split in ['ALL', 'discovery', 'validation', 'test']:
            segment = diagnosed[book] if split == 'ALL' else diagnosed[book][diagnosed[book].split == split]
            diagnosis[book][split] = {side: stats(segment if side == 'ALL' else segment[segment.side == side]) for side in ['ALL', 'LONG', 'SHORT']}
    event_stats, portfolio_stats = summarize_book(eligible), summarize_book(trades)
    test = diagnosed['events'][diagnosed['events'].split == 'test']
    bootstrap = clustered_ci(test, ['reference_pnl', 'net_pnl'])
    mean = float(test.net_pnl.mean())
    conclusion = ('La variante 1H/1x no muestra ventaja con los costes supuestos en el tramo final exploratorio. No se justifica entrenar IA ni operar esta regla.'
                  if mean <= 0 else 'La variante 1H/1x tiene media positiva en el tramo final exploratorio, pero no demuestra ventaja: necesita datos nuevos sin observar y ejecución/costes validados antes de continuar.')
    previous_path = Path('research/false_breakout/reports/baseline_20261017_v1/summary.json')
    previous = json.loads(previous_path.read_text(encoding='utf-8'))['scenarios']['1']
    summary = {'config': cfg, 'exploratory': True, 'start': str(start), 'end': str(end), 'conclusion': conclusion,
               'signals_by_side': signals.side.value_counts().to_dict(),
               'evaluation_status_counts': events.evaluation_status.value_counts().to_dict(),
               'data_quality': {'1H': hourly_meta['quality'], '5m': fine_meta['quality']},
               'execution_validation': quality, 'all_candidates': metrics(events), 'events': event_stats, 'portfolio': portfolio_stats,
               'test_by_side': {side: metrics(group) for side, group in eligible[eligible.split == 'test'].groupby('side')},
               'capital_return': float(curve.equity_usdt.iloc[-1] / cfg['initial_equity_usdt'] - 1),
               'max_drawdown': float(curve.drawdown.min()), 'diagnosis': diagnosis, 'funding_metadata': funding_meta,
               'test_bootstrap': bootstrap,
               'resolution_counts': events.get('execution_resolution', pd.Series(dtype=str)).value_counts().to_dict(),
               'comparison_5m': {'test_events': previous['events_by_split']['test']['executed'],
                                 'test_mean_net': previous['events_by_split']['test']['mean_net_pnl'],
                                 'test_profit_factor': previous['events_by_split']['test']['profit_factor'],
                                 'capital_return': previous['capital_return'], 'portfolio_trades': previous['portfolio']['executed']}}
    if len(test) < 100:
        summary['sample_warning'] = 'Menos de 100 eventos finales: evidencia escasa.'
    output.mkdir(parents=True)
    events.to_csv(output / 'events_1x.csv', index=False)
    trades.to_csv(output / 'portfolio_1x.csv', index=False)
    curve.to_csv(output / 'equity_1x.csv', index=False)
    for book, frame in diagnosed.items():
        frame.to_csv(output / f'diagnostic_{book}_1x.csv', index=False)
    (output / 'config.json').write_text(json.dumps(cfg, indent=2), encoding='utf-8')
    (output / 'summary.json').write_text(json.dumps(summary, indent=2, ensure_ascii=False, allow_nan=False), encoding='utf-8')
    (output / 'resolution_5m.json').write_text(json.dumps(resolver.notes, indent=2), encoding='utf-8')
    (output / 'resolution_1m.json').write_text(json.dumps(minute.notes, indent=2), encoding='utf-8')
    report(output, summary)
    input_paths = [directory / hourly_meta['csv_file'], directory / fine_meta['csv_file'],
                   directory / (Path(hourly_meta['csv_file']).stem + '.metadata.json'),
                   directory / (Path(fine_meta['csv_file']).stem + '.metadata.json'), instrument_path, Path(args.config), previous_path]
    funding_paths = [funding_directory / name for name in ['rates.csv', 'marks.csv', 'metadata.json']]
    sources = list(Path('research/false_breakout').glob('*.py')) + [Path('tests/test_hourly.py'), Path('webui/bitget_data.py')]
    manifest = {'git_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
                'python': platform.python_version(), 'dependencies': {name: importlib.metadata.version(name) for name in ['numpy', 'pandas', 'requests']},
                'inputs_sha256': {str(path): sha256(path) for path in input_paths},
                'funding_files_sha256': {str(path): sha256(path) for path in funding_paths},
                'source_sha256': {str(path): sha256(path) for path in sources},
                'output_sha256': {path.name: sha256(path) for path in output.iterdir()},
                'minute_cache_sha256': {path.name: sha256(path) for path in (Path(args.resolution_cache) / 'resolution_1m').glob('*.json')}}
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    command = f'python -m research.false_breakout.run_hourly --data {directory.as_posix()} --config {Path(args.config).as_posix()} --funding {funding_directory.as_posix()} --resolution-cache {Path(args.resolution_cache).as_posix()} --output NUEVO_DIRECTORIO --offline'
    (output / 'command.txt').write_text(command + '\n', encoding='utf-8')
    print(conclusion, flush=True)
    print(f'Informe: {output / "REPORT.md"}', flush=True)


if __name__ == '__main__':
    main()
