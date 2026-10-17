"""Segunda interpretación publicada: ejecutar planes congelados como swing >=2R."""
import argparse
import importlib.metadata
import json
import platform
import subprocess
from pathlib import Path

import pandas as pd

from webui.bitget_data import sha256
from .backtest import barrier, simulate_portfolio
from .costs import execution, pnl
from .economic_diagnosis import attribute_costs, clustered_ci, overlay_funding
from .funding_data import download as download_funding
from .run_experiment import MinuteResolver, load_history
from .run_hourly import HourlyResolver, validate_execution_data
from .run_practitioner import book_summary, fmt, subset_summary, write_json


def execute_frozen(plan, frame, cfg, inst, resolver=None):
    """Mismo plan financiero; solo se permite que el precio supere el extremo previo."""
    record = dict(plan)
    if record['label'] in {'GAP_INVALID', 'MIN_SIZE', 'INCOMPLETE'}:
        return record
    entry = int(record['entry_index'])
    horizon = cfg['max_holding_bars']
    if entry + horizon > len(frame):
        raise ValueError('Un plan congelado no tiene horizonte completo.')
    side, tick = record['side'], float(inst['priceMultiplier'])
    if abs(record['entry_reference'] - frame.open.iloc[entry]) > tick * 1e-6:
        raise ValueError('Apertura del plan no coincide con el histórico.')
    record.update(evaluation_status='EVALUABLE', label='PENDING', both_touched_1H=False, both_touched_5m=False,
                  target_requires_prior_extreme_break=bool((1 if side == 'LONG' else -1) * (record['tp'] - record['prior_extreme']) > 0))
    for j in range(entry, entry + horizon):
        bar = frame.iloc[j]
        touch = barrier(bar, side, record['stop'], record['tp'])
        if touch:
            label, reference, at_open = touch
            record['both_touched_1H'] = label == 'AMBIGUOUS'
            exit_time = bar.timestamp if at_open else bar.timestamp + pd.Timedelta(hours=1)
            if resolver:
                resolved = resolver(bar, side, record['stop'], record['tp'])
                if resolved:
                    label, reference, exit_time = resolved
                    record.update(execution_resolution=resolver.last_resolution, both_touched_5m=resolver.last_both_touched_5m)
            slip = cfg['tp_slippage_bps'] if label == 'TP_FIRST' else cfg['sl_slippage_bps']
            break
    else:
        j = entry + horizon - 1
        label, reference, slip = 'TIMEOUT', frame.close.iloc[j], cfg['timeout_slippage_bps']
        exit_time = frame.timestamp.iloc[j] + pd.Timedelta(hours=1)
    actual = pnl(record, side, execution(reference, side, slip, tick), cfg)
    record.update(actual, label=label, exit_reference=float(reference), exit_index=j, exit_time=exit_time,
                  holding_minutes=(exit_time - record['entry_time']).total_seconds() / 60)
    if label == 'TP_FIRST' and actual['net_margin_roi'] < record['required_net_roi'] - 1e-10:
        raise AssertionError('El TP no satisface el plan neto congelado.')
    return record


def report(output, s):
    lines = ['# Aplicación swing de la misma estructura y volumen', '',
             '**Mismo rango, 1H/1x. Segunda interpretación declarada; exploratoria y sin funding completo.**', '',
             s['conclusion'], '',
             '## Qué se aplica y por qué', '',
             '[Brooks](https://www.brookstradingcourse.com/futures-market/trade-trend-channels/) describe swings a favor de tendencia, stops estructurales, objetivos de al menos 2R y gestión después de nuevos extremos. Por tanto, el high/low de una sola vela anterior no es un techo universal para un objetivo de continuación.',
             'La primera adaptación rechazó 86 de 87 planes por imponer ese techo, con cero operaciones en validación. Se conserva íntegra. Tras revisar esa ausencia de actividad se registró esta interpretación antes de calcular las salidas de los planes rechazados. Es una decisión posterior al primer ensayo y se muestra como tal; no se presenta como confirmación independiente.',
             'Se ejecutan exactamente las señales y planes financieros guardados: aperturas, volumen, cantidades, stop, TP >=1% neto sobre margen y >=2R netos, riesgo previsto máximo 25 USDT y horizonte 24h. Solo cambia el veto NO_SPACE por superar el extremo inicial. El extremo queda como referencia a romper; no se garantiza esa ruptura ni se mueve el TP. No se usa información futura para habilitar entradas.',
             'structure incluye todos los planes estructurales; price_volume añade las tres condiciones de volumen previamente fijadas. Se muestran ambos libros, sin elegir el de mejor resultado. La señal se detecta en 1H; la ejecución usa 5m y 1m para duales, con SL conservador si no se resuelven. Comisiones supuestas 0,06% por lado, slippage adverso y ticks/lotes reales. Una posición, sin reinversión, 1x.', '',
             f"Ventanas heredadas: {s['bounds']}. Antiguo test excluido; purga y embargo de 24h. Segmentos conocidos por otros ensayos, no nueva evidencia independiente. Calidad 1H/5m: {s['execution_validation']}.", '',
             '## Resultados', '',
             '| Libro | Tramo | Eventos | Media neta evento USDT | Etiquetas | Operaciones cartera | PnL cartera USDT | PF cartera |',
             '|---|---|---:|---:|---|---:|---:|---:|']
    for name, b in s['variants'].items():
        for split in ['discovery', 'validation']:
            e, p = b['events']['by_split'].get(split, {}), b['portfolio']['by_split'].get(split, {})
            lines.append(f"| {name} | {split} | {e.get('executed', 0)} | {fmt(e.get('mean_net_pnl'))} | {e.get('labels', {})} | {p.get('executed', 0)} | {fmt(p.get('sum_net_pnl'))} | {fmt(p.get('profit_factor'))} |")
        lines += ['', f"{name}: retorno conjunto sobre 10000 USDT {b['capital_return']:.3%}; drawdown a cierre 1H {b['max_drawdown']:.3%}; intervalo semanal de validación {b['validation_bootstrap']}; decisión {b['decision']}.", '',
                  f"Direcciones de validación: {b['validation_by_side']}. La muestra por sentido es pequeña; no se elige una dirección por su resultado.", '']
        d = b['diagnosis']['events']['validation']['ALL']
        if d.get('n', 0):
            lines += [f"Validación {name}: referencia {d['mean_reference_pnl']:.6f} − ejecución {d['mean_execution_cost']:.6f} − comisiones {d['mean_fees']:.6f} = neto {d['mean_net']:.6f} USDT/evento. Ganador medio {d['mean_winner']}; perdedor medio absoluto {d['mean_loser_abs']}. Funding: {d['funding']}.", '']
    lines += ['## Límites y reproducción', '',
              'Con menos de 100 eventos de validación, declarar evidencia escasa incluso ante resultado positivo. La elección tras revisar otro ensayo y el historial completo de investigación impiden tratar un perfil favorable como prueba de ventaja. No se garantiza que esta discretización reproduzca el juicio humano ni se ha acreditado rentabilidad de los autores con sus páginas educativas.',
              'El funding solo se estima con cobertura completa, mark aproximado de 1m y sensibilidad de fronteras/extremos. No se extrapola al resto ni se recalcula elegibilidad por capital; los objetivos originales podrían quedar por debajo de 1% o 2R después de financiación. El drawdown de cierres no mide riesgo intrabar y un gap puede superar el riesgo previsto. No se modela profundidad, noticias ni ejecución parcial.',
              'summary.json conserva todos los resultados por segmento/dirección/mes/semana. Los CSV recogen planes y resultados. command.txt reproduce sin red; manifest.json registra hashes de planes anteriores, datos, código, protocolo, caché y financiación. verify_practitioner_swing verifica identidad de planes, cuentas Decimal y cartera. Sin nuevos rangos, IA, órdenes, commits ni push.']
    (output / 'REPORT.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--baseline', default='research/false_breakout/reports/practitioner_20261017')
    parser.add_argument('--data', default='webui/uploads/bitget_baseline_20261017')
    parser.add_argument('--protocol', default='research/false_breakout/practitioner_swing_protocol.json')
    parser.add_argument('--funding', default='webui/uploads/bitget_practitioner_swing_funding_20261017')
    parser.add_argument('--resolution-cache', default='webui/uploads/bitget_practitioner_swing_resolution_20261017')
    parser.add_argument('--output', required=True)
    parser.add_argument('--offline', action='store_true')
    args = parser.parse_args()
    baseline, output, directory = Path(args.baseline), Path(args.output), Path(args.data)
    if output.exists():
        raise FileExistsError('No sobrescribir informes.')
    original = json.loads((baseline / 'summary.json').read_text(encoding='utf-8'))
    old_manifest = json.loads((baseline / 'manifest.json').read_text(encoding='utf-8'))
    plans_path = baseline / 'structure/events_1x.csv'
    if sha256(plans_path) != old_manifest['output_sha256']['structure/events_1x.csv']:
        raise ValueError('Los planes originales fueron modificados.')
    protocol = json.loads(Path(args.protocol).read_text(encoding='utf-8'))
    if protocol['variants'] != ['structure', 'price_volume'] or protocol['horizon_hours'] != 24:
        raise ValueError('Protocolo swing incompatible.')
    cfg = original['config']
    raw, meta = load_history(directory, '1H', cfg)
    fine, fine_meta = load_history(directory, '5m', cfg)
    end = pd.Timestamp(original['bounds']['research_end'])
    frame, fine = raw[raw.timestamp < end].copy(), fine[fine.timestamp < end].copy()
    inst_path = directory / 'instrument.json'
    inst = json.loads(inst_path.read_text(encoding='utf-8'))
    quality = validate_execution_data(frame, fine, float(inst['priceMultiplier']))
    plans = pd.read_csv(plans_path, parse_dates=['entry_time', 'signal_time', 'impulse_time'])
    minute = MinuteResolver(Path(args.resolution_cache), cfg, inst, offline=args.offline)
    resolver = HourlyResolver(fine, minute)
    print(f'Ejecutando {len(plans)} planes congelados con interpretación swing...', flush=True)
    events = pd.DataFrame([execute_frozen(row, frame, cfg, inst, resolver) for row in plans.to_dict('records')])
    eligible = events[(events.evaluation_status == 'EVALUABLE') & events.net_pnl.notna()].copy()
    funding_dir = Path(args.funding)
    funding_meta = download_funding(funding_dir, cfg, eligible, offline=args.offline)
    rates = pd.read_csv(funding_dir / 'rates.csv', parse_dates=['timestamp'])
    marks = pd.read_csv(funding_dir / 'marks.csv', parse_dates=['timestamp'])
    books, frames, curves, diagnosed = {}, {}, {}, {}
    for name in protocol['variants']:
        selected = events if name == 'structure' else events[events.volume_ok]
        evaluated = selected[(selected.evaluation_status == 'EVALUABLE') & selected.net_pnl.notna()].copy()
        trades, curve = simulate_portfolio(selected, frame, cfg)
        diagnosis, diagnosed[name] = {}, {}
        for book, data in [('events', evaluated), ('portfolio', trades)]:
            if len(data):
                diagnostic = overlay_funding(attribute_costs(data, cfg, float(inst['priceMultiplier'])), rates, marks)
                diagnosed[name][book], diagnosis[book] = diagnostic, subset_summary(diagnostic)
        validation = evaluated[evaluated.split == 'validation']
        ci = clustered_ci(validation, ['net_pnl']) if len(validation) else {'weeks': 0, 'intervals': {'net_pnl': None}}
        es, ps = book_summary(evaluated), book_summary(trades)
        lower = ci['intervals']['net_pnl']
        positive = bool(len(validation) and validation.net_pnl.mean() > 0)
        profitable = ps['by_split'].get('validation', {}).get('sum_net_pnl', 0) > 0
        enough = len(validation) >= 100
        books[name] = {'events': es, 'portfolio': ps, 'diagnosis': diagnosis, 'validation_bootstrap': ci,
                       'validation_by_side': {side: book_summary(validation[validation.side == side])['ALL'] for side in ['LONG', 'SHORT']},
                       'capital_return': float(curve.equity_usdt.iloc[-1] / cfg['initial_equity_usdt'] - 1),
                       'max_drawdown': float(curve.drawdown.min()),
                       'decision': {'validation_events': len(validation), 'enough_events': enough, 'positive_event': positive,
                                    'positive_portfolio': profitable, 'meets_gate': enough and positive and profitable and lower is not None and lower[0] > 0}}
        frames[name], curves[name] = (selected, trades), curve
    primary = books['price_volume']
    conclusion = ('La aplicación swing principal supera el criterio exploratorio; no constituye confirmación independiente.' if primary['decision']['meets_gate'] else
                  'La aplicación swing principal no supera el criterio exploratorio; no se ha demostrado una ventaja rentable.')
    if not primary['decision']['enough_events']:
        conclusion += f" Evidencia escasa: {primary['decision']['validation_events']} eventos de validación; no atribuir una conclusión fuerte al método humano."
    summary = {'config': cfg, 'protocol': protocol, 'bounds': original['bounds'], 'variants': books,
               'funding_metadata': funding_meta, 'execution_validation': quality, 'conclusion': conclusion,
               'previous_interpretation': {name: b['events']['ALL'] for name, b in original['variants'].items()}}
    output.mkdir(parents=True)
    write_json(output / 'summary.json', summary)
    write_json(output / 'protocol.json', protocol)
    write_json(output / 'config.json', cfg)
    write_json(output / 'resolution_5m.json', resolver.notes)
    write_json(output / 'resolution_1m.json', minute.notes)
    for name, (selected, trades) in frames.items():
        target = output / name
        target.mkdir()
        selected.to_csv(target / 'events_1x.csv', index=False)
        trades.to_csv(target / 'portfolio_1x.csv', index=False)
        curves[name].to_csv(target / 'equity_1x.csv', index=False)
        write_json(target / 'summary.json', {'config': cfg, **books[name]})
        for book, data in diagnosed[name].items():
            data.to_csv(target / f'diagnostic_{book}_1x.csv', index=False)
    report(output, summary)
    command = (f'python -m research.false_breakout.practitioner_swing --baseline {baseline.as_posix()} --data {directory.as_posix()} '
               f'--protocol {Path(args.protocol).as_posix()} --funding {funding_dir.as_posix()} '
               f'--resolution-cache {Path(args.resolution_cache).as_posix()} --output NUEVO_DIRECTORIO --offline')
    (output / 'command.txt').write_text(command + '\n', encoding='utf-8')
    sources = [Path('research/false_breakout') / n for n in ['practitioner_swing.py', 'verify_practitioner_swing.py', 'practitioner.py',
               'run_practitioner.py', 'backtest.py', 'run_hourly.py', 'run_experiment.py', 'costs.py', 'funding_data.py', 'economic_diagnosis.py']]
    sources += [Path('tests/test_practitioner_swing.py'), Path('webui/bitget_data.py')]
    inputs = [plans_path, baseline / 'summary.json', baseline / 'manifest.json', directory / meta['csv_file'],
              directory / fine_meta['csv_file'], inst_path, Path(args.protocol)]
    manifest = {'git_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(), 'python': platform.python_version(),
                'dependencies': {n: importlib.metadata.version(n) for n in ['numpy', 'pandas', 'requests']},
                'inputs_sha256': {str(p): sha256(p) for p in inputs}, 'source_sha256': {str(p): sha256(p) for p in sources},
                'funding_files_sha256': {str(funding_dir / n): sha256(funding_dir / n) for n in ['rates.csv', 'marks.csv', 'metadata.json']},
                'minute_cache_sha256': {str(p): sha256(p) for p in (Path(args.resolution_cache) / 'resolution_1m').glob('*.json')}}
    for name in protocol['variants']:
        target = output / name
        write_json(target / 'manifest.json', {**manifest, 'output_sha256': {p.name: sha256(p) for p in target.iterdir() if p.is_file()}})
    manifest['output_sha256'] = {p.relative_to(output).as_posix(): sha256(p) for p in output.rglob('*') if p.is_file()}
    write_json(output / 'manifest.json', manifest)
    print(conclusion, flush=True)
    print(f'Informe: {output / "REPORT.md"}', flush=True)


if __name__ == '__main__':
    main()
