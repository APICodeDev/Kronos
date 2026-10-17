"""Aplica un playbook publicado a OHLCV existente, sin optimización ni nuevos rangos."""
import argparse
import importlib.metadata
import json
import platform
import subprocess
from pathlib import Path

import pandas as pd

from webui.bitget_data import sha256
from .backtest import simulate_portfolio
from .costs import validate_config
from .economic_diagnosis import attribute_costs, clustered_ci, overlay_funding, stats
from .funding_data import download as download_funding
from .practitioner import detect_setups, eligible_split, execute_setup, validate_volume
from .run_experiment import MinuteResolver, load_history, metrics
from .run_hourly import HourlyResolver, summarize_book, validate_execution_data
from .study_signal import research_window


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False), encoding='utf-8')


def book_summary(frame):
    if frame.empty:
        return {'ALL': metrics(frame), 'by_split': {}, 'by_side': {}, 'monthly': {}, 'weekly': {}}
    return summarize_book(frame)


def subset_summary(data):
    result = {}
    for split in ['ALL', 'discovery', 'validation']:
        segment = data if split == 'ALL' else data[data.split == split]
        result[split] = {side: stats(segment if side == 'ALL' else segment[segment.side == side])
                         for side in ['ALL', 'LONG', 'SHORT']}
    return result


def validate_protocol(cfg, protocol):
    validate_config(cfg)
    if (cfg['symbol'] != 'XRPUSDT' or cfg['category'] != 'USDT-FUTURES'
            or cfg['entry_interval'] != '1H' or cfg['leverage_scenarios'] != [1]
            or cfg['max_holding_bars'] != 24 or cfg['embargo_bars'] != 24
            or cfg['stop_buffer_ticks'] != 1 or cfg['lookback_bars'] != 20
            or cfg.get('execution_interval') != '5m' or cfg.get('resolve_all_touches') is not True):
        raise ValueError('Protocolo registrado: XRPUSDT 1H/1x, 24h y ejecución 5m, buffer 1 tick.')
    expected = {'horizons_hours': [24], 'purge_hours': 24, 'validation_embargo_hours': 24,
                'variants': ['structure', 'price_volume'], 'primary_variant': 'price_volume',
                'lookback_bars': 20, 'minimum_impulse_body_atr': 1., 'minimum_pullback_atr': .25,
                'minimum_wait_bars': 2, 'maximum_wait_bars': 6, 'minimum_impulse_relative_volume': 1.5,
                'minimum_net_reward_risk': 2., 'risk_budget_fraction_of_initial_equity': .0025,
                'splits_used': ['discovery', 'validation']}
    if any(protocol.get(key) != value for key, value in expected.items()):
        raise ValueError('No modificar umbrales del protocolo después de registrar la hipótesis.')


def fmt(number):
    return '—' if number is None else f'{number:.4f}'


def write_report(output, s):
    lines = ['# Aplicación de un playbook de operadores experimentados', '',
             '**1H / 1x, mismo histórico OHLCV; exploratorio, sin funding completo.**', '',
             s['conclusion'], '', '## Publicación y adaptación', '',
             'Se aplican impulso, retroceso y confirmación (Grimes); volumen y localización (SMB y Morpheus); stop estructural y recompensa/riesgo (Brooks); registro/revisión de un playbook (Bellafiore). No se afirma reproducir toda su discreción ni verificar sus beneficios.',
             'Los enlaces y la correspondencia están en protocol.json y PRACTITIONER_RESEARCH.md. Los umbrales son nuestros y se fijaron antes de los resultados. No se asume que volumen alto identifique compradores institucionales: OHLCV no permite saber quién opera ni reconstruir el order book.', '',
             '## Reglas congeladas', '',
             'Impulso: cierre fuera del canal de las 20 horas previas por un tick y cuerpo direccional >= ATR simple previo de 20 horas. Esperar 2..6 horas; al menos una vela de retroceso, un cierre contrario y profundidad >=0,25 ATR. Los cierres mantienen el nivel roto; el extremo no cruza el origen del impulso. Primera confirmación con cuerpo a favor y cierre más allá del extremo de la vela anterior por un tick. Se conserva la confirmación antes de examinar volumen o resultados. Si coinciden impulsos, prevalece el más reciente.',
             'structure incluye todos esos setups. price_volume exige además volumen del impulso >=1,5 veces mediana previa de 20 horas, volumen medio del retroceso menor que el del impulso y volumen de confirmación mayor que el anterior. La estructura, entrada, stop y objetivo no cambian entre libros. Es una comparación observacional del subconjunto retenido, no una prueba causal del volumen.',
             'Entrada siguiente; SL en extremo de todo el retroceso incluida confirmación más un tick. Riesgo modelado máximo 0,25% del capital inicial, margen máximo 1000 USDT sobre 10000 USDT, 1x, sin reinversión. TP: máximo entre +1% neto del margen y 2R netos. Si no cabe antes del extremo previo del impulso, NO_SPACE y no se opera. No hay órdenes límite con fills supuestos ni máximos futuros como salida.',
             'Horizonte fijo 24 horas, medido sobre velas de 1H; no es un cambio de temporalidad. Todas las barreras se recorren en 5m; duales recurren a 1m y, sin orden, SL conservador. Comisiones supuestas 0,06% por lado, slippage entrada/TP/timeout 1 bp y SL 2 bp, ticks/lotes adversos. El slippage se descuenta una sola vez en fills; no son tarifas efectivas de cuenta.', '',
             f"Ventanas y exclusión previa del antiguo test: {s['bounds']}. Purga y embargo de 24h. Los segmentos utilizados ya fueron observados; no son una nueva validación independiente. No se amplió rango ni instrumentos.",
             f"Calidad OHLC: {s['execution_validation']}. Calidad de volumen: {s['volume_validation']}. El turnover de 1H tiene un pequeño redondeo respecto a la suma de 5m y se valida con tolerancia explícita.", '',
             '## Embudo de selección y rechazo', '',
             f"Impulsos de estructura: {s['impulses']}; confirmaciones deduplicadas: {s['setups_total']}; estados temporales: {s['setups_by_window']}. Solo se calculan salidas dentro de las ventanas elegibles.", '',
             '| Libro | Setups elegibles | Retenidos por volumen | Estados / razones de entrada |', '|---|---:|---:|---|']
    for name, b in s['variants'].items():
        lines.append(f"| {name} | {s['eligible_structural_setups']} | {b['candidate_count']} | {b['entry_labels']} |")
    lines += ['', '## Resultados por evento y cartera', '',
              '| Libro | Tramo | Eventos ejecutables | Media neta evento USDT | TP / SL / timeout | Operaciones cartera | PnL cartera USDT |',
              '|---|---|---:|---:|---|---:|---:|']
    for name, b in s['variants'].items():
        for split in ['discovery', 'validation']:
            e, p = b['events']['by_split'].get(split, {}), b['portfolio']['by_split'].get(split, {})
            lines.append(f"| {name} | {split} | {e.get('executed', 0)} | {fmt(e.get('mean_net_pnl'))} | {e.get('labels', {})} | {p.get('executed', 0)} | {fmt(p.get('sum_net_pnl'))} |")
        lines += ['', f"{name}: retorno conjunto sobre capital inicial {b['capital_return']:.3%}; drawdown a cierre de 1H {b['max_drawdown']:.3%}. Intervalo descriptivo semanal de validación: {b['validation_bootstrap']}. No incluye drawdown intrabar ni garantiza riesgo ante gaps.", '']
    lines += ['## Atribución, volumen y financiación', '']
    for name, b in s['variants'].items():
        d = b['diagnosis'].get('events', {}).get('validation', {}).get('ALL', {})
        if d.get('n', 0):
            lines += [f"{name}, validación: referencia {d['mean_reference_pnl']:.6f} − ejecución {d['mean_execution_cost']:.6f} − comisiones {d['mean_fees']:.6f} = neto {d['mean_net']:.6f} USDT/evento. Ganador medio {d['mean_winner']}; perdedor medio absoluto {d['mean_loser_abs']}; factor beneficio {b['events']['by_split']['validation']['profit_factor']}. Funding: {d['funding']}."]
    lines += [f"Resultado del subconjunto estructural que el volumen descarta: {s['discarded_by_volume']}. No se escoge retrospectivamente el libro ganador; price_volume permanece como principal.",
              f"Financiación pública disponible desde {s['funding_metadata']['first']} hasta {s['funding_metadata']['last']}. Solo se ajustan operaciones totalmente cubiertas; el resto es desconocido, no coste cero. Mark aproximado por apertura de 1m y sensibilidad de extremos/fronteras. El objetivo +1% y 2R son previos a financiación completa y pueden incumplirse tras el cobro. La cartera no se recalcula con el overlay.", '',
              '## Decisión y revisión de casos', '', s['conclusion'],
              'Menos de 100 eventos de validación implica evidencia escasa aunque la media sea positiva; no se modifica un umbral para aumentar artificialmente la muestra. El paso útil con este rango es revisar los motivos de aceptación/rechazo y contrastar la fidelidad de la traducción publicada. No se amplían datos por defecto ni se entrena IA.',
              'cases.json muestra las primeras tres oportunidades de cada clase por orden temporal: operación principal, rechazo por espacio y descarte por volumen. Se eligen por fecha, no por beneficio. El diario diagnostic_setups.csv contiene todos los niveles, volúmenes y razones; events_1x.csv añade plan y resultado. Esto permite revisar la operación como una ficha de playbook.',
              'Limitaciones: discretización propia de conceptos cualitativos, una muestra y activo, historia de investigaciones conocida, dependencia de eventos y pocos bloques. No se trasladan noticias, selección entre miles de acciones o lectura de cinta de los autores a XRP. No se demuestra la rentabilidad de un humano ni se explica toda su toma de decisiones.', '',
              '## Reproducción', '',
              'command.txt reproduce sin red en otro directorio con datos/caché/funding conservados. config.json y protocol.json congelan decisiones. manifest.json registra datos, fuentes locales, código, pruebas, funding, caché 1m y salidas; verify_practitioner comprueba decisiones de entrada, contabilidad Decimal, ventanas y cartera sin solapamiento. Los CSV grandes se mantienen locales. Sin entrenamiento, claves privadas, órdenes, commits ni push.']
    (output / 'REPORT.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', default='webui/uploads/bitget_baseline_20261017')
    parser.add_argument('--config', default='research/false_breakout/config_practitioner.json')
    parser.add_argument('--protocol', default='research/false_breakout/practitioner_protocol.json')
    parser.add_argument('--funding', default='webui/uploads/bitget_practitioner_funding_20261017')
    parser.add_argument('--resolution-cache', default='webui/uploads/bitget_practitioner_resolution_20261017')
    parser.add_argument('--output', required=True)
    parser.add_argument('--offline', action='store_true')
    args = parser.parse_args()
    output, directory = Path(args.output), Path(args.data)
    if output.exists():
        raise FileExistsError('No sobrescribir informes: elegir directorio nuevo.')
    cfg = json.loads(Path(args.config).read_text(encoding='utf-8'))
    protocol = json.loads(Path(args.protocol).read_text(encoding='utf-8'))
    validate_protocol(cfg, protocol)
    raw, meta = load_history(directory, '1H', cfg)
    fine, fine_meta = load_history(directory, '5m', cfg)
    inst_path = directory / 'instrument.json'
    inst = json.loads(inst_path.read_text(encoding='utf-8'))
    if inst['symbol'] != cfg['symbol'] or inst['category'] != cfg['category']:
        raise ValueError('Contrato incompatible.')
    frame, bounds = research_window(raw, protocol)
    fine = fine[fine.timestamp < bounds['research_end']].copy()
    quality = validate_execution_data(frame, fine, float(inst['priceMultiplier']))
    volume_quality = validate_volume(frame, fine)
    print('Detectando impulso, retroceso y confirmación sin mirar resultados...', flush=True)
    setups, impulses = detect_setups(frame, protocol, float(inst['priceMultiplier']))
    setups['split'] = [eligible_split(t, bounds, 24) for t in setups.entry_time]
    candidates = setups[setups.split.isin(protocol['splits_used'])].copy()
    minute = MinuteResolver(Path(args.resolution_cache), cfg, inst, offline=args.offline)
    resolver = HourlyResolver(fine, minute)
    rows = [execute_setup(r, frame, cfg, protocol, inst, resolver) for r in candidates.to_dict('records')]
    events = pd.DataFrame(rows) if rows else pd.DataFrame(columns=[*candidates.columns, 'evaluation_status', 'label'])
    for field in ['net_pnl', 'entry_fee', 'exit_fee', 'holding_minutes', 'net_margin_roi']:
        if field not in events:
            events[field] = pd.Series(dtype=float)
    for field in ['both_touched_1H', 'both_touched_5m']:
        if field in events:
            events[field] = events[field].astype('boolean')
    eligible = events[(events.evaluation_status == 'EVALUABLE') & events.net_pnl.notna()].copy()
    funding_dir = Path(args.funding)
    funding_meta = download_funding(funding_dir, cfg, eligible, offline=args.offline)
    rates = pd.read_csv(funding_dir / 'rates.csv', parse_dates=['timestamp'])
    marks = pd.read_csv(funding_dir / 'marks.csv', parse_dates=['timestamp'])
    books, frames, curves, diagnosed = {}, {}, {}, {}
    for name in protocol['variants']:
        candidate = events if name == 'structure' else events[events.volume_ok.astype(bool)]
        evaluated = candidate[(candidate.evaluation_status == 'EVALUABLE') & candidate.net_pnl.notna()].copy()
        trades, curve = simulate_portfolio(candidate, frame, cfg)
        if trades.empty:
            trades = evaluated.iloc[:0].copy()
        diagnosis, diagnosed[name] = {}, {}
        for book, data in [('events', evaluated), ('portfolio', trades)]:
            if len(data):
                diagnostic = overlay_funding(attribute_costs(data, cfg, float(inst['priceMultiplier'])), rates, marks)
                diagnosed[name][book] = diagnostic
                diagnosis[book] = subset_summary(diagnostic)
        validation = evaluated[evaluated.split == 'validation']
        ci = (clustered_ci(validation, ['net_pnl']) if len(validation)
              else {'weeks': 0, 'intervals': {'net_pnl': None}})
        intervals = ci['intervals']['net_pnl']
        enough = len(validation) >= 100
        event_positive = len(validation) > 0 and validation.net_pnl.mean() > 0
        ps = book_summary(trades)
        portfolio_positive = ps['by_split'].get('validation', {}).get('sum_net_pnl', 0) > 0
        gate = enough and event_positive and portfolio_positive and intervals is not None and intervals[0] > 0
        books[name] = {'candidate_count': len(candidate), 'entry_labels': candidate.label.value_counts().to_dict(),
                       'events': book_summary(evaluated), 'portfolio': ps,
                       'capital_return': float(curve.equity_usdt.iloc[-1] / cfg['initial_equity_usdt'] - 1),
                       'max_drawdown': float(curve.drawdown.min()), 'diagnosis': diagnosis,
                       'validation_bootstrap': ci,
                       'decision': {'enough_validation_events': enough, 'validation_event_positive': bool(event_positive),
                                    'validation_portfolio_positive': portfolio_positive, 'meets_gate': bool(gate)}}
        frames[name], curves[name] = (candidate, trades), curve
    primary = books[protocol['primary_variant']]
    conclusion = ('La adaptación principal supera el criterio exploratorio, sin constituir prueba independiente de rentabilidad.' if primary['decision']['meets_gate']
                  else 'La adaptación principal no supera el criterio registrado; no se justifica operar o entrenar IA. Revisar selección, riesgo y fidelidad de la traducción, conservando todos los resultados.')
    validation_n = primary['events']['by_split'].get('validation', {}).get('executed', 0)
    if validation_n < 100:
        conclusion += f' Evidencia escasa: solo {validation_n} eventos ejecutables de validación; no permiten una conclusión fuerte sobre el método humano.'
    discarded = eligible[~eligible.volume_ok.astype(bool)]
    summary = {'config': cfg, 'protocol': protocol, 'bounds': {k: str(v) if isinstance(v, pd.Timestamp) else v for k, v in bounds.items()},
               'conclusion': conclusion, 'execution_validation': quality, 'volume_validation': volume_quality,
               'impulses': len(impulses), 'setups_total': len(setups), 'setups_by_window': setups.split.value_counts().to_dict(),
               'eligible_structural_setups': len(candidates), 'variants': books, 'funding_metadata': funding_meta,
               'discarded_by_volume': book_summary(discarded)}
    output.mkdir(parents=True)
    setups.to_csv(output / 'diagnostic_setups.csv', index=False)
    cases = {}
    for kind, selected in [('primary_trades', eligible[eligible.volume_ok.astype(bool)]),
                           ('no_space', events[events.label == 'NO_SPACE']), ('volume_rejected', events[~events.volume_ok.astype(bool)])]:
        # JSON de pandas convierte Timestamp y NaN correctamente para la ficha.
        cases[kind] = json.loads(selected.head(3).to_json(orient='records', date_format='iso'))
    write_json(output / 'cases.json', cases)
    write_json(output / 'config.json', cfg)
    write_json(output / 'protocol.json', protocol)
    write_json(output / 'summary.json', summary)
    write_json(output / 'resolution_5m.json', resolver.notes)
    write_json(output / 'resolution_1m.json', minute.notes)
    for name, (candidate, trades) in frames.items():
        target = output / name
        target.mkdir()
        candidate.to_csv(target / 'events_1x.csv', index=False)
        trades.to_csv(target / 'portfolio_1x.csv', index=False)
        curves[name].to_csv(target / 'equity_1x.csv', index=False)
        write_json(target / 'summary.json', {'config': cfg, **books[name]})
        for book, data in diagnosed[name].items():
            data.to_csv(target / f'diagnostic_{book}_1x.csv', index=False)
    write_report(output, summary)
    command = (f'python -m research.false_breakout.run_practitioner --data {directory.as_posix()} '
               f'--config {Path(args.config).as_posix()} --protocol {Path(args.protocol).as_posix()} '
               f'--funding {funding_dir.as_posix()} --resolution-cache {Path(args.resolution_cache).as_posix()} '
               '--output NUEVO_DIRECTORIO --offline')
    (output / 'command.txt').write_text(command + '\n', encoding='utf-8')
    sources = list(Path('research/false_breakout').glob('*.py')) + [Path('tests/test_practitioner.py'), Path('webui/bitget_data.py'),
                                                                 Path('research/false_breakout/PRACTITIONER_RESEARCH.md')]
    inputs = [directory / meta['csv_file'], directory / fine_meta['csv_file'], inst_path, Path(args.config), Path(args.protocol),
              directory / (Path(meta['csv_file']).stem + '.metadata.json'), directory / (Path(fine_meta['csv_file']).stem + '.metadata.json')]
    manifest = {'git_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
                'python': platform.python_version(), 'dependencies': {n: importlib.metadata.version(n) for n in ['numpy', 'pandas', 'requests']},
                'inputs_sha256': {str(p): sha256(p) for p in inputs}, 'source_sha256': {str(p): sha256(p) for p in sources},
                'funding_files_sha256': {str(funding_dir / n): sha256(funding_dir / n) for n in ['rates.csv', 'marks.csv', 'metadata.json']},
                'minute_cache_sha256': {str(p): sha256(p) for p in (Path(args.resolution_cache) / 'resolution_1m').glob('*.json')},
                'old_test_rows_excluded': bounds['excluded_test_rows']}
    for name in protocol['variants']:
        target = output / name
        write_json(target / 'manifest.json', {**manifest, 'output_sha256': {p.name: sha256(p) for p in target.iterdir() if p.is_file()}})
    manifest['output_sha256'] = {p.relative_to(output).as_posix(): sha256(p) for p in output.rglob('*') if p.is_file()}
    write_json(output / 'manifest.json', manifest)
    print(conclusion, flush=True)
    print(f'Informe: {output / "REPORT.md"}', flush=True)


if __name__ == '__main__':
    main()
