"""Ejecuta una configuración congelada; no optimiza ni entrena modelos."""
import argparse
import importlib.metadata
import json
import platform
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

from webui.bitget_data import BitgetDataError, PublicClient, fetch_history, normalize, sha256, utc_ms
from .backtest import attach_context, barrier, detect_signals, label_event, partition, simulate_portfolio
from .costs import validate_config


def load_history(directory, interval, cfg):
    paths = list(directory.glob(f"{cfg['symbol']}_{interval}_*.metadata.json"))
    if len(paths) != 1:
        raise ValueError(f'Se requiere un único histórico {interval}: {paths}')
    meta = json.loads(paths[0].read_text(encoding='utf-8'))
    if meta['provider'] != 'Bitget' or meta['symbol'] != cfg['symbol'] or meta['category'] != cfg['category']:
        raise ValueError('Procedencia incompatible.')
    path = directory / meta['csv_file']
    if sha256(path) != meta['csv_sha256']:
        raise ValueError(f'Hash incorrecto: {path}')
    df = pd.read_csv(path)
    df.timestamp = pd.to_datetime(df.timestamp, utc=True)
    numeric = df.copy()
    numeric.timestamp = numeric.timestamp.map(lambda x: x.value // 1_000_000)
    df, quality = normalize(numeric.values.tolist(), interval, meta['requested_start_ms'], meta['requested_end_ms'])
    if quality['missing_bars'] or quality['identical_duplicates_removed']:
        raise ValueError(f'Histórico discontinuo/duplicado: {interval}; {quality}')
    if meta['requested_end_ms'] > meta['closed_cutoff_ms']:
        raise ValueError('El archivo incluye velas no cerradas.')
    return df, {key: value for key, value in meta.items() if key != 'queries'}


class MinuteResolver:
    def __init__(self, directory, cfg, inst, offline=False):
        self.client = PublicClient(directory / 'resolution_1m')
        self.cfg, self.inst, self.offline = cfg, inst, offline
        self.frames, self.notes = {}, {}

    def __call__(self, bar, side, stop, target):
        stamp = bar.timestamp.isoformat()
        if stamp not in self.frames:
            try:
                start = utc_ms(bar.timestamp)
                if self.offline:
                    # Impide red accidental durante una repetición sin conexión.
                    def no_network(*args, **kwargs):
                        raise BitgetDataError('Respuesta 1m ausente en caché offline')
                    self.client.session.get = no_network
                frame, meta = fetch_history(self.client, self.cfg['symbol'], self.cfg['category'], '1m',
                                            start, start + 300_000, now_ms=start + 300_000)
                if meta['quality']['missing_bars']:
                    raise BitgetDataError('Cobertura 1m incompleta')
                actual = [frame.open.iloc[0], frame.high.max(), frame.low.min(), frame.close.iloc[-1]]
                if not np.allclose(actual, [bar.open, bar.high, bar.low, bar.close], rtol=0,
                                   atol=float(self.inst['priceMultiplier']) / 2):
                    raise BitgetDataError('OHLC 1m no coincide con vela 5m')
                self.frames[stamp], self.notes[stamp] = frame, '1m completo y coherente; ambigüedad intraminuto sigue siendo conservadora'
            except (BitgetDataError, ValueError) as exc:
                self.frames[stamp], self.notes[stamp] = None, str(exc)
        frame = self.frames[stamp]
        if frame is None:
            return None
        for bar1 in frame.itertuples():
            touch = barrier(bar1, side, stop, target)
            if touch:
                label, reference, at_open = touch
                return label, reference, bar1.timestamp + (pd.Timedelta(0) if at_open else pd.Timedelta(minutes=1))
        return None


def metrics(frame):
    labels = frame['label'].value_counts().to_dict() if 'label' in frame else {}
    actual = frame.dropna(subset=['net_pnl']) if 'net_pnl' in frame else pd.DataFrame()
    count = len(actual)
    values = actual.net_pnl if count else pd.Series(dtype=float)
    gain, loss = values[values > 0].sum(), -values[values < 0].sum()
    evaluated = frame[frame.evaluation_status == 'EVALUABLE'] if 'evaluation_status' in frame else frame
    return {'signals': len(frame), 'executed': count, 'labels': labels,
            'tp_rate_evaluable': float((evaluated.label == 'TP_FIRST').mean()) if len(evaluated) else None,
            'mean_net_pnl': float(values.mean()) if count else None,
            'median_net_pnl': float(values.median()) if count else None,
            'sum_net_pnl': float(values.sum()),
            'mean_margin_roi': float(actual.net_margin_roi.mean()) if count else None,
            'profit_factor': float(gain / loss) if loss else None,
            'winning_net_pnl_sum': float(gain), 'losing_net_pnl_sum_abs': float(loss),
            'mean_winner': float(values[values > 0].mean()) if (values > 0).any() else None,
            'mean_loser': float(values[values < 0].mean()) if (values < 0).any() else None,
            'loss_quantiles': {str(q): float(x) for q, x in values[values < 0].quantile([0, .05, .5, .95, 1]).items()} if loss else {},
            'entry_fees': float(actual.entry_fee.sum()) if count else 0,
            'exit_fees': float(actual.exit_fee.sum()) if count else 0,
            'mean_duration_minutes': float(actual.holding_minutes.mean()) if count else None,
            'both_touched_5m': int(actual.get('both_touched_5m', pd.Series(dtype=bool)).fillna(False).sum()) if count else 0,
            'unresolved_execution': int((actual.label == 'AMBIGUOUS').sum()) if count else 0,
            'incomplete': int((frame.evaluation_status == 'INCOMPLETE').sum()) if len(frame) else 0}


def period_metrics(frame, freq):
    if frame.empty:
        return {}
    return {str(key): metrics(group) for key, group in frame.groupby(pd.Grouper(key='entry_time', freq=freq)) if len(group)}


def write_report(output, summary):
    lines = ['# Primer experimento de falsos rompimientos — Bitget XRPUSDT', '',
             '**Resultados provisionales sin funding. No se ha entrenado IA ni optimizado parámetros.**', '',
             f"Datos: {summary['start']} a {summary['end']} (fin excluido), {summary['rows']} velas de 5m, {summary['days']:.2f} días.",
             f"Señales: {summary['signals_by_side']}. Contexto incompleto: {summary['context_missing_fraction']:.4%}.", '',
             'Configuración congelada antes de observar resultados; 60/20/20 por tiempo, purga del horizonte completo y embargo de 72 barras.',
             'El conjunto final se evalúa en esta ejecución; cualquier cambio posterior exige otro tramo final sin observar.', '',
             '| Escenario | Cartera: operaciones | PnL USDT | ROI capital | DD máx. cierres 5m | PF | Test: operaciones | Test: media USDT |',
             '|---|---:|---:|---:|---:|---:|---:|---:|']
    for leverage, result in summary['scenarios'].items():
        port, test = result['portfolio'], result['portfolio_by_split'].get('test', {})
        lines.append(f"| {leverage}x | {port['executed']} | {port['sum_net_pnl']:.4f} | {result['capital_return']:.3%} | {result['max_drawdown']:.3%} | {port['profit_factor']} | {test.get('executed', 0)} | {test.get('mean_net_pnl')} |")
    lines += ['', '## Etiquetas y rendimiento por evento', '',
              'Las etiquetas de esta tabla corresponden a todas las señales; los PnL de la tabla posterior excluyen purga/embargo e incompletos.', '',
              '| Escenario | TP_FIRST | SL_FIRST | TIMEOUT | AMBIGUOUS | GAP_INVALID | Incompletos |',
              '|---|---:|---:|---:|---:|---:|---:|']
    for leverage, result in summary['scenarios'].items():
        counts = result['all_candidates']['labels']
        lines.append(f"| {leverage}x | " + ' | '.join(str(counts.get(key, 0)) for key in ['TP_FIRST', 'SL_FIRST', 'TIMEOUT', 'AMBIGUOUS', 'GAP_INVALID']) + f" | {result['all_candidates']['incomplete']} |")
    lines += ['', '| Escenario / dirección | Ejecutados | Tasa TP evaluables | Media USDT | Mediana USDT | Ganador medio | Perdedor medio | PF | Duración min |',
              '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for leverage, result in summary['scenarios'].items():
        for side, values in {'TOTAL': result['events'], **result['events_by_side']}.items():
            if not values['executed']:
                continue
            lines.append(f"| {leverage}x / {side} | {values['executed']} | {values['tp_rate_evaluable']} | {values['mean_net_pnl']:.4f} | {values['median_net_pnl']:.4f} | {values['mean_winner']} | {values['mean_loser']} | {values['profit_factor']} | {values['mean_duration_minutes']:.2f} |")
    lines += ['', '## Cartera por período y costes', '',
              '| Escenario / mes UTC | Operaciones | PnL USDT | Media USDT | Comisiones USDT |',
              '|---|---:|---:|---:|---:|']
    for leverage, result in summary['scenarios'].items():
        for month, values in result['portfolio_monthly'].items():
            lines.append(f"| {leverage}x / {month[:7]} | {values['executed']} | {values['sum_net_pnl']:.4f} | {values['mean_net_pnl']:.4f} | {values['entry_fees'] + values['exit_fees']:.4f} |")
    lines += ['', '## Hipótesis de ejecución y contabilidad', '',
              'Entrada en apertura siguiente con slippage adverso y redondeo al tick; cantidad redondeada hacia abajo. Margen = nominal ejecutado / apalancamiento. TP resuelto incluyendo comisión de salida sobre su nominal y slippage previsto, redondeado para alcanzar al menos +1 % del margen efectivo.',
              'SL fijo; gap de salida al peor precio entre apertura y SL. TIMEOUT liquida al cierre de la barra 72 con costes. Un gap que ya cruza TP se ejecuta al TP sin mejora favorable. Si ambos niveles se tocan, se consultan velas 1m cuando se habilita; si persiste incertidumbre, etiqueta AMBIGUOUS y pérdida por SL.',
              'Cartera con una posición por símbolo, margen fijo sin reinversión y capital inicial configurable. Se omiten las entradas sin capital. Curva marcada a cierre 5m, comisión de apertura descontada al entrar y resto de costes al salir; DD intrabar y coste de liquidación inmediata de posiciones abiertas no incluidos.',
              'El análisis por evento admite solapamientos y su suma de PnL no representa una cartera. Las particiones se asignan por entrada con horizonte máximo, sin utilizar la duración realizada para decidir la purga.', '',
              '## Limitaciones y decisión', '',
              *[f'- {item}' for item in summary['limitations']], '',
              summary['conclusion'], '',
              '## Configuración exacta', '', '```json', json.dumps(summary['config'], indent=2, ensure_ascii=False), '```', '',
              '## Reproducibilidad', '',
              'Ver `manifest.json` para hashes de código, configuración, instrumentos, datos y versiones. `summary.json` contiene etiquetas, costes, resultados por dirección, partición, mes y semana. Los CSV conservan cada evento, operación de cartera y curva.', '',
              'Repetir con el comando de `command.txt`; añadir `--offline` utiliza la caché de resolución 1m sin red. Los datos están en el directorio de cargas persistente y no se incluyen en Git.']
    (output / 'REPORT.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--config', default='research/false_breakout/config.json')
    parser.add_argument('--resolve-1m', action='store_true')
    parser.add_argument('--offline', action='store_true')
    args = parser.parse_args()
    cfg = json.loads(Path(args.config).read_text(encoding='utf-8'))
    validate_config(cfg)
    if cfg['entry_interval'] != '5m':
        raise ValueError('Para la variante 1H usa research.false_breakout.run_hourly.')
    directory, output = Path(args.data), Path(args.output)
    if output.exists():
        raise FileExistsError('El informe ya existe; selecciona un directorio nuevo.')
    df, data_meta = load_history(directory, '5m', cfg)
    contexts, context_meta = {}, {}
    for interval in cfg['context_intervals']:
        contexts[interval], context_meta[interval] = load_history(directory, interval, cfg)
        duration = 900_000 if interval == '15m' else 3_600_000
        expected_start = (data_meta['requested_start_ms'] + duration - 1) // duration * duration
        expected_end = data_meta['requested_end_ms'] // duration * duration
        if context_meta[interval]['requested_start_ms'] != expected_start or context_meta[interval]['requested_end_ms'] != expected_end:
            raise ValueError('El contexto nativo no cubre el rango solicitado para 5m.')
    inst_path = directory / 'instrument.json'
    inst = json.loads(inst_path.read_text(encoding='utf-8'))
    if inst['symbol'] != cfg['symbol'] or inst['category'] != cfg['category']:
        raise ValueError('Instrumento incompatible.')
    signals = attach_context(detect_signals(df, cfg['lookback_bars'], float(inst['priceMultiplier'])), contexts)
    start, end = df.timestamp.iloc[0], df.timestamp.iloc[-1] + pd.Timedelta(minutes=5)
    output.mkdir(parents=True)
    resolver = MinuteResolver(directory, cfg, inst, offline=args.offline) if args.resolve_1m else None
    summary = {'config': cfg, 'start': str(start), 'end': str(end), 'rows': len(df),
               'days': (end - start).total_seconds() / 86400,
               'signals_by_side': signals.side.value_counts().to_dict(),
               'context_missing_fraction': float(signals[['15m_available_at', '1H_available_at']].isna().any(axis=1).mean()) if len(signals) else 0,
               'scenarios': {}, 'limitations': []}
    for leverage in cfg['leverage_scenarios']:
        print(f'Evaluando escenario {leverage}x ({len(signals)} señales)...', flush=True)
        records = []
        for signal in signals.to_dict('records'):
            horizon_end = signal['entry_time'] + pd.Timedelta(minutes=5 * cfg['max_holding_bars'])
            split = partition(signal['entry_time'], horizon_end, start, end, cfg)
            record = label_event(signal, df, cfg, inst, leverage, resolver)
            record['split'] = split
            if split in {'PURGED', 'EMBARGO', 'INCOMPLETE'}:
                record['evaluation_status'] = split
            records.append(record)
        events = pd.DataFrame(records) if records else pd.DataFrame(columns=[
            'entry_time', 'side', 'label', 'evaluation_status', 'split', 'net_pnl'])
        events.to_csv(output / f'events_{leverage}x.csv', index=False)
        trades, curve = simulate_portfolio(events, df, cfg)
        trades.to_csv(output / f'portfolio_{leverage}x.csv', index=False)
        curve.to_csv(output / f'equity_{leverage}x.csv', index=False)
        eligible = events[events.split.isin(['discovery', 'validation', 'test'])] if len(events) else events
        result = {'events': metrics(eligible), 'all_candidates': metrics(events), 'portfolio': metrics(trades),
                  'events_by_side': {side: metrics(group) for side, group in eligible.groupby('side')},
                  'events_by_split': {key: metrics(group) for key, group in eligible.groupby('split')},
                  'portfolio_by_split': {key: metrics(group) for key, group in trades.groupby('split')} if len(trades) else {},
                  'events_monthly': period_metrics(eligible, 'MS'), 'portfolio_monthly': period_metrics(trades, 'MS'),
                  'portfolio_weekly': period_metrics(trades, 'W-MON'),
                  'max_drawdown': float(curve.drawdown.min()),
                  'capital_return': float(curve.equity_usdt.iloc[-1] / cfg['initial_equity_usdt'] - 1)}
        summary['scenarios'][str(leverage)] = result
    if resolver:
        (output / 'resolution_1m.json').write_text(json.dumps(resolver.notes, indent=2), encoding='utf-8')
    summary['limitations'] += [
        'Funding excluido: PnL tras comisiones y slippage, no neto completo. Ningún escenario equivale a la tarifa o al apalancamiento real de la cuenta.',
        'Metadatos actuales aplicados retrospectivamente: no hay histórico de cambios de tick, lotes, comisiones o límites del contrato.',
        'OHLC no reconstruye spread, profundidad, latencia, colas, ejecución parcial ni liquidación/mantenimiento del margen. Escenarios de apalancamiento son simulaciones provisionales.',
        'Una única criptomoneda y un período temporal no prueban estabilidad en otros regímenes. Los eventos solapados no son observaciones independientes.',
        'No se ha probado ningún clasificador: la comparación frente a IA queda fuera de este hito.'
    ]
    if summary['days'] < 180:
        summary['limitations'].append('Menos de seis meses: muestra insuficiente para concluir robustez.')
    if any(result['events_by_split'].get('test', {}).get('executed', 0) < 100 for result in summary['scenarios'].values()):
        summary['limitations'].append('Algún escenario tiene menos de 100 eventos ejecutables finales: evidencia escasa.')
    if not args.resolve_1m:
        summary['limitations'].append('No se consultó resolución 1m; todas las dobles barreras se trataron como SL conservador.')
    positive = [key for key, value in summary['scenarios'].items()
                if (value['portfolio_by_split'].get('test', {}).get('mean_net_pnl') or 0) > 0]
    summary['conclusion'] = ('No se encuentra ventaja neta fuera de muestra en ninguno de los escenarios. No procede añadir IA ni filtros para rescatar esta hipótesis.'
                             if not positive else f'Hay medias positivas provisionales en test en {positive}, pero costes omitidos y dependencia temporal impiden declarar ventaja demostrada. No se selecciona un ganador ni se entrena IA.')
    source_paths = sorted(Path('research/false_breakout').glob('*.py')) + [Path('webui/bitget_data.py'), Path(args.config)]
    source_paths += [Path('tests') / name for name in ['test_bitget_data.py', 'test_costs.py', 'test_false_breakout.py']]
    versions = {}
    for name in ['numpy', 'pandas', 'requests', 'pyarrow', 'pytest']:
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    manifest = {'git_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
                'git_status': subprocess.check_output(['git', 'status', '--short'], text=True),
                'python': platform.python_version(), 'dependencies': versions,
                'source_sha256': {str(path): sha256(path) for path in source_paths},
                'instrument_sha256': sha256(inst_path), 'data': data_meta, 'contexts': context_meta,
                'resolution_cache_sha256': {path.name: sha256(path) for path in (directory / 'resolution_1m').glob('*.json')},
                'artifact_sha256': {path.name: sha256(path) for path in output.glob('*.csv')}}
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    (output / 'summary.json').write_text(json.dumps(summary, indent=2, ensure_ascii=False, allow_nan=False), encoding='utf-8')
    command = f'python -m research.false_breakout.run_experiment --data {directory.as_posix()} --output NUEVO_DIRECTORIO --config {Path(args.config).as_posix()}'
    if args.resolve_1m:
        command += ' --resolve-1m'
    (output / 'command.txt').write_text(command + '\n', encoding='utf-8')
    write_report(output, summary)
    print(summary['conclusion'], flush=True)
    print(f'Informe: {output / "REPORT.md"}', flush=True)


if __name__ == '__main__':
    main()
