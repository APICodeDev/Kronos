"""Hipótesis registrada de continuación 1H/1x; reutiliza costes y ejecución auditados."""
import argparse
import importlib.metadata
import json
import platform
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

from webui.bitget_data import sha256
from .backtest import label_event, simulate_portfolio
from .costs import validate_config
from .economic_diagnosis import attribute_costs, clustered_ci, overlay_funding, stats
from .funding_data import download as download_funding
from .run_experiment import MinuteResolver, load_history
from .run_hourly import HourlyResolver, summarize_book, validate_execution_data
from .study_signal import (candidate_entries, causal_features, describe, match_controls,
                           outcomes, research_window)


def momentum_features(frame, lookback, tick, edges):
    # Reutilizar solo covariables y emparejamiento; sustituir todas las señales anteriores.
    result = causal_features(frame, lookback, tick, edges)
    high = frame.high.shift(1).rolling(lookback).max()
    low = frame.low.shift(1).rolling(lookback).min()
    long = np.rint(frame.close / tick) >= np.rint(high / tick) + 1
    short = np.rint(frame.close / tick) <= np.rint(low / tick) - 1
    if (long & short).any():
        raise AssertionError('Canal incoherente: ruptura en ambas direcciones.')
    result['side'] = np.select([long, short], ['LONG', 'SHORT'], default='NONE')
    result['previous_high'], result['previous_low'] = high, low
    return result


def validate_protocol(cfg, protocol):
    validate_config(cfg)
    if (cfg['entry_interval'] != '1H' or cfg['leverage_scenarios'] != [1]
            or cfg['max_holding_bars'] != 6 or cfg['lookback_bars'] != protocol['lookback_bars']):
        raise ValueError('La hipótesis registrada exige 1H/1x, horizonte de cartera 6h y lookback común.')
    if (protocol['horizons_hours'] != [1, 6, 24] or protocol['primary_horizon_hours'] != 6
            or protocol['purge_hours'] != 24 or protocol['validation_embargo_hours'] != 24
            or protocol['splits_used'] != ['discovery', 'validation']):
        raise ValueError('No alterar horizontes, purga, embargo o segmentos del protocolo registrado.')
    if cfg.get('execution_interval') != '5m' or cfg.get('resolve_all_touches') is not True:
        raise ValueError('Todas las barreras deben recorrerse en 5m.')


def continuation_decision(profiles, portfolio):
    primary = [p for p in profiles if p['split'] == 'validation' and p['horizon_hours'] == 6]
    enough = len(primary) == 2 and sum(p['signals_matched'] for p in primary) >= 100
    positive = len(primary) == 2 and all(p.get('mean_net_usdt', -1) > 0 and p.get('excess_usdt', -1) > 0
                                        for p in primary)
    bands = len(primary) == 2 and all(p.get('bootstrap', {}).get('candidate_bps_adjusted_band', [-1])[0] > 0
                                     and p.get('bootstrap', {}).get('excess_bps_adjusted_band', [-1])[0] > 0
                                     for p in primary)
    profitable = portfolio['by_split'].get('validation', {}).get('sum_net_pnl', 0) > 0
    return {'enough_validation_events': enough, 'both_directions_positive_at_6h': positive,
            'both_adjusted_bands_positive_at_6h': bands, 'validation_portfolio_positive': profitable,
            'meets_exploratory_gate': enough and positive and bands and profitable}


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False), encoding='utf-8')


def write_report(output, s):
    lines = ['# Continuación tras ruptura confirmada — XRPUSDT, 1H, 1x', '',
             '**Investigación exploratoria. Datos ya observados; antiguo test excluido. Neto provisional sin funding completo.**', '',
             s['conclusion'], '',
             '## Regla y contraste registrados antes del cálculo', '',
             'LONG si el cierre supera en al menos un tick el máximo de las 20 horas completas anteriores; SHORT si cierra al menos un tick por debajo del mínimo. Entrada siguiente. Cada cierre válido cuenta como evento; no se impone un filtro de primera ruptura ni indicadores adicionales. Se reutiliza la infraestructura, no la señal de falso rompimiento.',
             'Hipótesis: persistencia tras confirmarse una ruptura. [Liu y Tsyvinski, Risks and Returns of Cryptocurrency](https://www.nber.org/papers/w24877) documentan momentum histórico en criptomonedas. La referencia motiva la familia; no demuestra esta regla en 1H ni su rentabilidad actual.',
             'Contraste principal: cierre fijo a 6h, LONG y SHORT por separado, con costes idénticos al control. Cierres a 1h y 24h son diagnósticos secundarios registrados; no se elige el mejor. Controles: horas sin esta nueva señal, mismo segmento/mes UTC/sesión de 8h/banda de volatilidad causal; mínimo diez por estrato. Se informa lo excluido por falta de soporte.',
             'Cartera independiente del diagnóstico de cierre fijo: TP de +1% sobre margen efectivo tras comisiones y ejecución previstas, SL extremo de la vela de señal más un tick, timeout 6h. Máximo una posición simultánea; margen fijo máximo 1000 USDT sobre capital inicial 10000 USDT, sin reinversión, 1x. Una entrada que ya cruza el stop es inválida. No se cambia de futures a spot.',
             'Costes supuestos: 0,06% por lado, slippage 1 bp en entrada/TP/timeout y 2 bp en SL; tick y lotes reales, redondeo adverso. Las tarifas de cuenta pueden diferir. Los fills contienen el slippage: no se resta dos veces.', '',
             f"Ventanas UTC: {s['bounds']}. Se excluyen {s['bounds']['excluded_test_rows']} horas del antiguo test antes de construir indicadores/etiquetas. Purga de 24h y embargo de 24h para todos los horizontes y la cartera. La validación utilizada ya fue examinada en estudios previos; no es nueva evidencia independiente.",
             f"Calidad de ejecución: {s['execution_validation']}. Se comprueban las 12 subvelas de 5m contra cada hora elegible. Fuente anual comprobada por hash; los resultados solo abarcan hasta {s['bounds']['research_end']} (fin excluido).", '',
             '## Señal frente a horas comparables: todos los perfiles', '',
             '| Tramo | Dirección | Horas | Emparejadas / señales | Neto medio señal USDT | Neto medio control USDT | Diferencia USDT |',
             '|---|---|---:|---:|---:|---:|---:|']
    for p in s['profiles']:
        if p['signals_matched']:
            lines.append(f"| {p['split']} | {p['side']} | {p['horizon_hours']} | {p['signals_matched']} / {p['signals_total']} | {p['mean_net_usdt']:.4f} | {p['matched_control_mean_usdt']:.4f} | {p['excess_usdt']:.4f} |")
    lines += ['', 'Medias por evento; no son rentabilidad de cartera. El control se pondera por los estratos de las señales, no por todas las horas. Los eventos pueden solaparse. MFE/MAE y alcanzar el objetivo alguna vez sin stop son diagnósticos futuros, nunca precios de salida ni filtros.', '',
              '## Incertidumbre de validación', '',
              '| Dirección | Horas | Banda ajustada neto, bp margen | Banda ajustada diferencia, bp margen |',
              '|---|---:|---|---|']
    for p in s['profiles']:
        if p['split'] == 'validation' and p['signals_matched']:
            lines.append(f"| {p['side']} | {p['horizon_hours']} | {p['bootstrap']['candidate_bps_adjusted_band']} | {p['bootstrap']['excess_bps_adjusted_band']} |")
    lines += ['', '5.000 remuestreos conjuntos de semanas UTC, semilla 20261017, recalculando controles. Bandas percentiles con cuantiles Bonferroni para seis perfiles por segmento; summary.json incluye IC descriptivos del 95%. No corrigen el historial completo de investigación. Son aproximaciones con pocas semanas de validación, extremos parciales y ventanas que cruzan bloques; no certifican una ventaja.', '',
              '## Ejecución con TP/SL y cartera secuencial', '',
              '| Tramo | Eventos ejecutables | Media evento USDT | TP / SL / timeout / ambiguos | Operaciones cartera | PnL cartera USDT | PF cartera |',
              '|---|---:|---:|---|---:|---:|---:|']
    for split in ['discovery', 'validation']:
        e, p = s['events']['by_split'][split], s['portfolio']['by_split'][split]
        lines.append(f"| {split} | {e['executed']} | {e['mean_net_pnl']:.4f} | {e['labels']} | {p['executed']} | {p['sum_net_pnl']:.4f} | {p['profit_factor']:.4f} |")
    lines += ['', f"Estados de candidatos elegibles temporalmente: {s['evaluation_status_counts']}. Se conservan inválidos en events_1x.csv. Resoluciones: {s['resolution_counts']}. Ambiguos finales se contabilizan y reciben SL conservador, sin regalar el TP.",
              f"Cartera conjunta de investigación y validación: {s['portfolio']['ALL']['sum_net_pnl']:.4f} USDT; retorno sobre 10000 USDT {s['capital_return']:.3%}; drawdown a cierre de 1H {s['max_drawdown']:.3%}. Se conserva el efectivo entre segmentos, sin posiciones que crucen fronteras. No mide drawdown intrabar ni garantiza pérdidas máximas ante gaps.", '',
              '## Costes, pagos y financiación: validación por evento', '']
    d = s['diagnosis']['events']['validation']['ALL']
    lines += [f"Referencia {d['mean_reference_pnl']:.6f} − ejecución {d['mean_execution_cost']:.6f} − comisiones {d['mean_fees']:.6f} = neto {d['mean_net']:.6f} USDT/evento. Ejecución se descompone en slippage nominal {d['mean_nominal_slippage']:.6f} y redondeo {d['mean_tick_rounding']:.6f} USDT. Son atribuciones contables sobre salidas congeladas, no reoptimizaciones de TP.",
              f"Ganador medio {d['mean_winner']:.4f} USDT; perdedor medio −{d['mean_loser_abs']:.4f}; proporción positiva {d['positive_rate_nonzero']:.2%}; equilibrio con pagos observados {d['break_even_positive_rate_nonzero']:.2%}. Incluye timeouts; no equivale a tasa de TP. Pérdida neta SL planificada (cuantiles): {d['planned_sl_net_loss']}. El margen fijo no supone riesgo fijo por operación.",
              f"Tasas públicas disponibles: {s['funding_metadata']['first']} a {s['funding_metadata']['last']}. Cobertura validación: {d['funding']}. La cobertura restante no se trata como coste cero ni se extrapola. Apertura de mark 1m como aproximación; sensibilidad low/high y cobros coincidentes con entrada/salida en JSON. Los TP se calculan sin funding completo y algunos podrían bajar de +1% después de financiarse. No se ha recalculado la cartera tras ese overlay.", '',
              '## Cartera por mes UTC', '', '| Mes | Operaciones | PnL USDT | Comisiones USDT |', '|---|---:|---:|---:|']
    for month, p in s['portfolio']['monthly'].items():
        lines.append(f"| {month[:7]} | {p['executed']} | {p['sum_net_pnl']:.4f} | {p['entry_fees'] + p['exit_fees']:.4f} |")
    lines += ['', '## Decisión y límites', '',
              f"Criterio registrado: {s['decision']}. Solo permitiría pasar a observación prospectiva, nunca operar automáticamente o dar la rentabilidad por demostrada. No se entrenó IA ni se seleccionaron dirección, lookback o salida según el resultado.",
              'XRPUSDT y un solo año; tramos ya explorados y pocos regímenes. No representa todos los mercados ni invalida la rentabilidad de otros operadores. El control es observacional y no aísla todas las condiciones del mercado. Hay dependencia entre eventos y posible sesgo de selección entre investigaciones. Metadatos actuales aplicados retrospectivamente; no hay profundidad histórica, latencia, ejecuciones parciales ni funding anual completo.',
              'Si la regla no supera el criterio, no se añaden filtros para rescatar este resultado. El siguiente avance útil requeriría una hipótesis económica diferente, registrada, o datos adicionales con un tramo realmente reservado. Si lo supera, congelar reglas y costes y observar datos posteriores no examinados antes de considerar modelos.', '',
              '## Reproducción y verificación', '',
              'protocol.json y config.json conservan decisiones; summary.json incluye todos los perfiles y estadísticas de cartera por dirección/segmento/mes/semana. execution/ guarda eventos, operaciones, capital y atribución de costes/funding. manifest.json incluye hashes de datos, scripts, pruebas, caché 1m, funding y salidas. command.txt repite en un directorio nuevo con --offline. Los CSV grandes permanecen locales e ignorados por Git.',
              'python -m research.false_breakout.verify_momentum --report RUTA verifica con Decimal los cálculos, el emparejamiento, señales contra OHLC originales, ventanas temporales y cartera sin solapamientos. No se modifican informes anteriores, funciones de Kraken ni el modelo; no se envían órdenes, commits ni push.']
    (output / 'REPORT.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', default='webui/uploads/bitget_baseline_20261017')
    parser.add_argument('--config', default='research/false_breakout/config_hourly.json')
    parser.add_argument('--protocol', default='research/false_breakout/momentum_protocol.json')
    parser.add_argument('--funding', default='webui/uploads/bitget_momentum_funding_20261017')
    parser.add_argument('--resolution-cache', default='webui/uploads/bitget_momentum_resolution_20261017')
    parser.add_argument('--output', required=True)
    parser.add_argument('--offline', action='store_true')
    args = parser.parse_args()
    directory, output = Path(args.data), Path(args.output)
    if output.exists():
        raise FileExistsError('Usa un directorio nuevo; no se sobrescriben resultados.')
    cfg = json.loads(Path(args.config).read_text(encoding='utf-8'))
    protocol = json.loads(Path(args.protocol).read_text(encoding='utf-8'))
    validate_protocol(cfg, protocol)
    raw, meta = load_history(directory, '1H', cfg)
    fine, fine_meta = load_history(directory, '5m', cfg)
    inst_path = directory / 'instrument.json'
    inst = json.loads(inst_path.read_text(encoding='utf-8'))
    if inst['symbol'] != cfg['symbol'] or inst['category'] != cfg['category']:
        raise ValueError('Instrumento incompatible.')
    frame, bounds = research_window(raw, protocol)
    fine = fine[fine.timestamp < bounds['research_end']].copy().reset_index(drop=True)
    quality = validate_execution_data(frame, fine, float(inst['priceMultiplier']))
    features = momentum_features(frame, protocol['lookback_bars'], float(inst['priceMultiplier']), protocol['volatility_bin_edges'])
    entries = candidate_entries(features, bounds, protocol)
    rows, matches, profiles = [], [], []
    for split in protocol['splits_used']:
        segment = entries[entries.split == split]
        for side in ['LONG', 'SHORT']:
            for horizon in protocol['horizons_hours']:
                print(f'Continuación {split} {side} {horizon}h...', flush=True)
                data = outcomes(frame, segment[segment.side.isin([side, 'NONE'])], side, horizon, cfg, inst)
                matched, controls, coverage = match_controls(data, protocol['minimum_controls_per_stratum'])
                profiles.append({'split': split, 'side': side, 'horizon_hours': horizon,
                                 **describe(matched, controls, coverage, protocol)})
                rows.append(data)
                matches.append(matched)
    minute = MinuteResolver(Path(args.resolution_cache), cfg, inst, offline=args.offline)
    resolver = HourlyResolver(fine, minute)
    records = []
    signals = entries[entries.side.isin(['LONG', 'SHORT'])]
    print(f'Ejecutando {len(signals)} eventos elegibles con TP/SL...', flush=True)
    for signal in signals.to_dict('records'):
        signal['signal_time'] = signal['timestamp']
        records.append(label_event(signal, frame, cfg, inst, 1, resolver))
    events = pd.DataFrame(records)
    if events.empty or 'net_pnl' not in events:
        raise ValueError('Sin eventos ejecutables; no fabricar resultado financiero.')
    eligible = events[(events.evaluation_status == 'EVALUABLE') & events.net_pnl.notna()].copy()
    trades, curve = simulate_portfolio(events, frame, cfg)
    funding_dir = Path(args.funding)
    print('Comprobando financiación pública disponible...', flush=True)
    funding_meta = download_funding(funding_dir, cfg, eligible, offline=args.offline)
    rates = pd.read_csv(funding_dir / 'rates.csv', parse_dates=['timestamp'])
    marks = pd.read_csv(funding_dir / 'marks.csv', parse_dates=['timestamp'])
    diagnosed, diagnosis = {}, {}
    for book, data in [('events', eligible), ('portfolio', trades)]:
        diagnosed[book] = overlay_funding(attribute_costs(data, cfg, float(inst['priceMultiplier'])), rates, marks)
        diagnosis[book] = {}
        for split in ['ALL', 'discovery', 'validation']:
            subset = diagnosed[book] if split == 'ALL' else diagnosed[book][diagnosed[book].split == split]
            diagnosis[book][split] = {side: stats(subset if side == 'ALL' else subset[subset.side == side])
                                    for side in ['ALL', 'LONG', 'SHORT']}
    portfolio_stats = summarize_book(trades)
    decision = continuation_decision(profiles, portfolio_stats)
    conclusion = ('Supera el criterio exploratorio registrado, pero requiere datos prospectivos y costes completos antes de considerarse una ventaja.'
                  if decision['meets_exploratory_gate'] else
                  'La continuación registrada no supera el criterio exploratorio. No se justifica operar esta regla, entrenar IA ni añadir filtros para rescatarla; conservar la infraestructura y revisar la hipótesis con datos adicionales.')
    summary = {'protocol': protocol, 'config': cfg, 'bounds': {k: str(v) if isinstance(v, pd.Timestamp) else v for k, v in bounds.items()},
               'profiles': profiles, 'conclusion': conclusion, 'decision': decision,
               'execution_validation': quality, 'data_quality': {'1H': meta['quality'], '5m': fine_meta['quality']},
               'signals_by_side': signals.side.value_counts().to_dict(),
               'evaluation_status_counts': events.evaluation_status.value_counts().to_dict(),
               'events': summarize_book(eligible), 'portfolio': portfolio_stats, 'diagnosis': diagnosis,
               'capital_return': float(curve.equity_usdt.iloc[-1] / cfg['initial_equity_usdt'] - 1),
               'max_drawdown': float(curve.drawdown.min()), 'funding_metadata': funding_meta,
               'validation_event_bootstrap': clustered_ci(eligible[eligible.split == 'validation'], ['net_pnl']),
               'resolution_counts': events.get('execution_resolution', pd.Series(dtype=str)).value_counts().to_dict()}
    execution_dir = output / 'execution'
    execution_dir.mkdir(parents=True)
    pd.concat(rows, ignore_index=True).to_csv(output / 'diagnostic_signal_controls.csv', index=False)
    pd.concat(matches, ignore_index=True).to_csv(output / 'diagnostic_matched_signals.csv', index=False)
    events.to_csv(execution_dir / 'events_1x.csv', index=False)
    trades.to_csv(execution_dir / 'portfolio_1x.csv', index=False)
    curve.to_csv(execution_dir / 'equity_1x.csv', index=False)
    for book, data in diagnosed.items():
        data.to_csv(execution_dir / f'diagnostic_{book}_1x.csv', index=False)
    for target in [output, execution_dir]:
        write_json(target / 'summary.json', summary)
    write_json(output / 'config.json', cfg)
    write_json(output / 'protocol.json', protocol)
    write_json(execution_dir / 'resolution_5m.json', resolver.notes)
    write_json(execution_dir / 'resolution_1m.json', minute.notes)
    write_report(output, summary)
    command = (f'python -m research.false_breakout.study_momentum --data {directory.as_posix()} '
               f'--config {Path(args.config).as_posix()} --protocol {Path(args.protocol).as_posix()} '
               f'--funding {funding_dir.as_posix()} --resolution-cache {Path(args.resolution_cache).as_posix()} '
               '--output NUEVO_DIRECTORIO --offline')
    (output / 'command.txt').write_text(command + '\n', encoding='utf-8')
    inputs = [directory / meta['csv_file'], directory / fine_meta['csv_file'], inst_path,
              directory / (Path(meta['csv_file']).stem + '.metadata.json'),
              directory / (Path(fine_meta['csv_file']).stem + '.metadata.json'), Path(args.config), Path(args.protocol)]
    sources = list(Path('research/false_breakout').glob('*.py')) + [Path('webui/bitget_data.py'), Path('tests/test_momentum.py')]
    manifest = {'git_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
                'python': platform.python_version(), 'dependencies': {n: importlib.metadata.version(n) for n in ['numpy', 'pandas', 'requests']},
                'input_sha256': {str(p): sha256(p) for p in inputs},
                'source_sha256': {str(p): sha256(p) for p in sources},
                'funding_files_sha256': {str(funding_dir / n): sha256(funding_dir / n) for n in ['rates.csv', 'marks.csv', 'metadata.json']},
                'old_test_rows_excluded_before_analysis': bounds['excluded_test_rows'],
                'minute_cache_sha256': {str(p): sha256(p) for p in (Path(args.resolution_cache) / 'resolution_1m').glob('*.json')},
                'output_sha256': {p.relative_to(output).as_posix(): sha256(p) for p in output.rglob('*') if p.is_file()}}
    execution_manifest = {**manifest, 'inputs_sha256': manifest['input_sha256'],
                          'output_sha256': {p.name: sha256(p) for p in execution_dir.iterdir() if p.is_file()}}
    write_json(execution_dir / 'manifest.json', execution_manifest)
    manifest['output_sha256']['execution/manifest.json'] = sha256(execution_dir / 'manifest.json')
    write_json(output / 'manifest.json', manifest)
    print(conclusion, flush=True)
    print(f'Informe: {output / "REPORT.md"}', flush=True)


if __name__ == '__main__':
    main()
