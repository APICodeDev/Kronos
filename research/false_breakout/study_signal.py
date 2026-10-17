"""Estudio direccional con controles: no opera ni optimiza TP/SL ni consulta la red."""
import argparse
import importlib.metadata
import json
import platform
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

from webui.bitget_data import sha256
from .backtest import detect_signals
from .costs import execution, pnl, position
from .run_experiment import load_history


def causal_features(frame, lookback, tick, edges):
    """Todas las características están disponibles al cerrar cada vela."""
    result = frame.copy()
    previous_close = result.close.shift(1)
    true_range = pd.concat([result.high - result.low, (result.high - previous_close).abs(),
                            (result.low - previous_close).abs()], axis=1).max(axis=1)
    result['volatility'] = true_range.rolling(lookback, min_periods=lookback).mean() / result.close
    result['volatility_bin'] = np.searchsorted(edges, result.volatility, side='right')
    result['side'] = 'NONE'
    signals = detect_signals(result, lookback, tick)
    for signal in signals.itertuples():
        result.loc[signal.signal_index, 'side'] = signal.side
    result['entry_time'] = result.timestamp + pd.Timedelta(hours=1)
    result['month'] = result.entry_time.dt.strftime('%Y-%m')
    result['session'] = result.entry_time.dt.hour // 8
    result['stratum'] = result.month + '|' + result.session.astype(str) + '|' + result.volatility_bin.astype(str)
    result['week'] = result.entry_time.dt.tz_localize(None).dt.to_period('W-SUN').astype(str)
    return result


def research_window(raw, protocol):
    start = raw.timestamp.iloc[0]
    end = raw.timestamp.iloc[-1] + pd.Timedelta(hours=1)
    first = start + (end - start) * .6
    last = start + (end - start) * .8
    # Recortar antes de construir indicadores/resultados impide usar el antiguo test.
    frame = raw[raw.timestamp < last].copy().reset_index(drop=True)
    return frame, {'start': start, 'discovery_end': first, 'validation_start': first + pd.Timedelta(hours=protocol['validation_embargo_hours']),
                   'research_end': last, 'excluded_test_rows': int((raw.timestamp >= last).sum())}


def candidate_entries(frame, bounds, protocol):
    maximum = max(protocol['horizons_hours'])
    result = frame.copy()
    result['signal_index'] = result.index
    result['entry_index'] = result.index + 1
    result['window_end'] = result.entry_time + pd.Timedelta(hours=maximum)
    result['split'] = 'EXCLUDED'
    discovery = (result.entry_time < bounds['discovery_end']) & (result.window_end <= bounds['discovery_end'])
    validation = (result.entry_time >= bounds['validation_start']) & (result.window_end <= bounds['research_end'])
    result.loc[discovery, 'split'] = 'discovery'
    result.loc[validation, 'split'] = 'validation'
    return result[(result.split != 'EXCLUDED') & result.volatility.notna() &
                  (result.entry_index + maximum <= len(frame)) & (result.signal_index >= protocol['lookback_bars'])].copy()


def outcomes(frame, entries, side, horizon, cfg, inst):
    """Cierres y extremos futuros son etiquetas; nunca características de entrada."""
    records = []
    tick = float(inst['priceMultiplier'])
    for entry in entries.itertuples():
        index = int(entry.entry_index)
        bars = frame.iloc[index:index + horizon]
        if len(bars) != horizon:
            raise ValueError('Horizonte incompleto en estudio.')
        pos = position(float(bars.open.iloc[0]), side, 1, cfg, inst)
        sign = 1 if side == 'LONG' else -1
        reference_exit = float(bars.close.iloc[-1])
        fill = execution(reference_exit, side, cfg['timeout_slippage_bps'], tick)
        actual = pnl(pos, side, fill, cfg)
        favorable = float(bars.high.max() if side == 'LONG' else bars.low.min())
        adverse = float(bars.low.min() if side == 'LONG' else bars.high.max())
        optimistic_fill = execution(favorable, side, cfg['tp_slippage_bps'], tick)
        adverse_fill = execution(adverse, side, cfg['sl_slippage_bps'], tick)
        optimistic = pnl(pos, side, optimistic_fill, cfg)
        worst = pnl(pos, side, adverse_fill, cfg)
        record = {'signal_index': entry.signal_index, 'entry_index': index, 'entry_time': entry.entry_time,
                  'exit_time': bars.timestamp.iloc[-1] + pd.Timedelta(hours=1), 'split': entry.split,
                  'side': side, 'source_side': entry.side, 'stratum': entry.stratum, 'week': entry.week,
                  'volatility': entry.volatility, 'horizon_hours': horizon,
                  'kind': 'SIGNAL' if entry.side == side else 'CONTROL', **pos, **actual,
                  'exit_reference': reference_exit,
                  'reference_pnl': sign * pos['quantity'] * (reference_exit - pos['entry_reference']),
                  'net_roi_bps': actual['net_margin_roi'] * 10000,
                  'mfe_price_bps': max(0., sign * (favorable - pos['entry_fill']) / pos['entry_fill'] * 10000),
                  'mae_price_bps': max(0., -sign * (adverse - pos['entry_fill']) / pos['entry_fill'] * 10000),
                  'mfe_net_upper_bound': max(0., optimistic['net_pnl']),
                  'mae_net_extreme': max(0., -worst['net_pnl']),
                  'ever_target_no_stop': optimistic['net_margin_roi'] >= cfg['target_net_margin_roi'] - 1e-10}
        records.append(record)
    return pd.DataFrame(records)


def match_controls(frame, minimum):
    controls = frame[frame.kind == 'CONTROL']
    pool = controls.groupby('stratum').agg(control_count=('net_roi_bps', 'size'),
                                          control_mean_bps=('net_roi_bps', 'mean'), control_mean_usdt=('net_pnl', 'mean'))
    signals = frame[frame.kind == 'SIGNAL'].join(pool, on='stratum')
    matched = signals[signals.control_count.ge(minimum)].copy()
    matched['excess_net_roi_bps'] = matched.net_roi_bps - matched.control_mean_bps
    matched['excess_net_pnl'] = matched.net_pnl - matched.control_mean_usdt
    included = controls[controls.stratum.isin(matched.stratum.unique())].copy()
    return matched, included, {'signals_total': len(signals), 'signals_matched': len(matched),
                               'signals_excluded': len(signals) - len(matched),
                               'coverage': len(matched) / len(signals) if len(signals) else None}


def joint_week_bootstrap(signals, controls, repeats, seed, comparisons):
    """Remuestrea las semanas de ambos grupos y vuelve a calcular controles por estrato."""
    if signals.empty:
        return {'weeks': 0, 'valid_draws': 0}
    weeks = sorted(set(signals.week) | set(controls.week))
    strata = sorted(signals.stratum.unique())
    def matrix(frame, value, count=False):
        group = frame.groupby(['week', 'stratum'])['net_roi_bps']
        grouped = group.size() if count else frame.groupby(['week', 'stratum'])[value].sum()
        return grouped.unstack(fill_value=0).reindex(index=weeks, columns=strata, fill_value=0).to_numpy(dtype=float)
    event_count = matrix(signals, 'net_roi_bps', count=True)
    event_sum = matrix(signals, 'net_roi_bps')
    control_count = matrix(controls, 'net_roi_bps', count=True)
    control_sum = matrix(controls, 'net_roi_bps')
    rng = np.random.default_rng(seed)
    weights = rng.multinomial(len(weeks), np.full(len(weeks), 1 / len(weeks)), size=repeats)
    en, es, cn, cs = [weights @ item for item in [event_count, event_sum, control_count, control_sum]]
    available = cn > 0
    counts = np.where(available, en, 0).sum(axis=1)
    means = np.divide(cs, cn, out=np.zeros_like(cs), where=available)
    candidate = np.divide(np.where(available, es, 0).sum(axis=1), counts, out=np.full(repeats, np.nan), where=counts > 0)
    excess = np.divide(np.where(available, es - en * means, 0).sum(axis=1), counts,
                       out=np.full(repeats, np.nan), where=counts > 0)
    valid = np.isfinite(candidate) & np.isfinite(excess)
    tail = .05 / (2 * comparisons)
    return {'weeks': len(weeks), 'valid_draws': int(valid.sum()),
            'candidate_bps_ci95': np.quantile(candidate[valid], [.025, .975]).tolist(),
            'excess_bps_ci95': np.quantile(excess[valid], [.025, .975]).tolist(),
            'candidate_bps_adjusted_band': np.quantile(candidate[valid], [tail, 1 - tail]).tolist(),
            'excess_bps_adjusted_band': np.quantile(excess[valid], [tail, 1 - tail]).tolist()}


def describe(signals, controls, coverage, protocol):
    result = dict(coverage)
    if signals.empty:
        return result
    result.update(mean_net_usdt=float(signals.net_pnl.mean()), median_net_usdt=float(signals.net_pnl.median()),
                  mean_reference_usdt=float(signals.reference_pnl.mean()),
                  matched_control_mean_usdt=float(signals.control_mean_usdt.mean()),
                  excess_usdt=float(signals.excess_net_pnl.mean()),
                  mean_net_roi_bps=float(signals.net_roi_bps.mean()),
                  matched_control_mean_bps=float(signals.control_mean_bps.mean()),
                  excess_bps=float(signals.excess_net_roi_bps.mean()),
                  positive_pnl_rate=float((signals.net_pnl > 0).mean()),
                  ever_target_no_stop_rate=float(signals.ever_target_no_stop.mean()),
                  median_mfe_price_bps=float(signals.mfe_price_bps.median()),
                  median_mae_price_bps=float(signals.mae_price_bps.median()),
                  control_count_min=int(signals.control_count.min()),
                  bootstrap=joint_week_bootstrap(signals, controls, **{
                      'repeats': protocol['bootstrap']['repeats'], 'seed': protocol['bootstrap']['seed'],
                      'comparisons': protocol['bootstrap']['validation_comparisons']}))
    return result


def write_report(output, summary):
    lines = ['# ¿Aporta información la señal, aparte de sus TP/SL?', '',
             '**Estudio exploratorio. No es una estrategia optimizada ni un resultado de cartera. No utiliza el antiguo segmento test.**', '',
             'Se mantienen XRPUSDT perpetuo, 1H, 1x, niveles de 20 velas anteriores, entrada siguiente y costes previos. Se eliminan TP/SL para medir cierres a 1, 6 y 24 horas. Los controles son horas sin señal, del mismo segmento, mes UTC, bloque horario de ocho horas y banda fija de volatilidad causal. Se requieren diez controles por estrato; los casos sin soporte se cuentan y se excluyen, sin ampliar bandas buscando resultados.', '',
             f"Ventanas utilizadas: {summary['bounds']}. El último 20 % se recorta antes de construir indicadores y etiquetas. Purga y embargo de 24 horas: todos los perfiles usan la misma elegibilidad temporal. Los segmentos ya se habían examinado en trabajos previos y no son una validación independiente nueva.", '',
             '## Todos los perfiles registrados', '',
             '| Segmento | Dirección | Horas | Señales emparejadas / totales | Neto señal USDT | Neto control emparejado USDT | Diferencia USDT |',
             '|---|---|---:|---:|---:|---:|---:|']
    for profile in summary['profiles']:
        if not profile['signals_matched']:
            continue
        lines.append(f"| {profile['split']} | {profile['side']} | {profile['horizon_hours']} | {profile['signals_matched']} / {profile['signals_total']} | {profile['mean_net_usdt']:.4f} | {profile['matched_control_mean_usdt']:.4f} | {profile['excess_usdt']:.4f} |")
    lines += ['', 'Importes medios por evento, margen efectivo cercano a 1.000 USDT. Controles ponderados como las señales: cada evento se compara con la media de su propio estrato. La diferencia mide asociación condicional, no causalidad ni beneficio ejecutable de cartera. No se suman eventos solapados como si fueran capital.', '',
              '## Recorrido disponible y riesgo en validación', '',
              '| Dirección | Horas | Fracción que alguna vez alcanzó el objetivo sin SL | MFE mediana, bp precio | MAE mediana, bp precio | Banda ajustada exceso, bp margen |',
              '|---|---:|---:|---:|---:|---|']
    for profile in summary['profiles']:
        if profile['split'] != 'validation' or not profile['signals_matched']:
            continue
        lines.append(f"| {profile['side']} | {profile['horizon_hours']} | {profile['ever_target_no_stop_rate']:.2%} | {profile['median_mfe_price_bps']:.2f} | {profile['median_mae_price_bps']:.2f} | {profile['bootstrap']['excess_bps_adjusted_band']} |")
    lines += ['', 'MFE/MAE son extremos que solo se conocen después. Alcanzar el precio objetivo en algún momento sin stop no significa que se pueda elegir ese máximo para salir, ni que no se haya soportado antes una pérdida grande. Ningún extremo futuro se usa como característica, filtro o precio ejecutable del backtest.', '',
              '## Qué significa el contraste', '',
              'Una media superior al control con una media neta negativa no constituye una oportunidad rentable. Una media positiva aislada tampoco prueba ventaja después de financiación, riesgo, límites de cartera y selección entre alternativas. Se muestran los seis perfiles dirección/horizonte por segmento, sin elegir un ganador.',
              'Se remuestrean conjuntamente semanas UTC de señales y controles y se recalculan las medias de control por estrato. 5.000 remuestreos, semilla fija. Hay intervalos percentiles descriptivos del 95 % y una banda adicional con cuantiles Bonferroni para seis perfiles por segmento. Son aproximaciones: los bloques extremos pueden ser parciales, las ventanas cruzan semanas y el emparejamiento no controla todos los estados de mercado. No son una certificación estadística ni eliminan el sesgo de investigaciones anteriores.', '',
              '## Límites y decisión', '',
              summary['conclusion'],
              'El funding está excluido, especialmente material al extender el horizonte a 24 horas. No se reconstruye una cartera ni el riesgo de mantener posiciones sin SL. El control no es una prueba causal aleatoria: solo ajusta las variables de emparejamiento fijadas. Los eventos sin controles suficientes quedan fuera de las medias y su cobertura se informa. No se ha ajustado ninguna banda, horizonte o salida después de observar los resultados.',
              'El conocimiento y el cómputo permiten contrastar más hipótesis y detectar errores; no garantizan que estos datos contengan una ventaja explotable con estos costes. Si aparece una asociación útil, el paso siguiente sería registrar una hipótesis de ejecución y validarla con datos nuevos, sin convertir retrospectivamente el mejor extremo del precio en una operación.', '',
              '## Reproducibilidad', '',
              'protocol.json copia las decisiones registradas antes del cálculo. summary.json incluye todos los perfiles y sus intervalos; los CSV conservan resultados de señales y controles. manifest.json registra hashes de entradas, scripts, protocolo y salidas. El comando de command.txt reproduce el estudio sin red en un directorio nuevo. Se conservan todos los experimentos anteriores.',
              'Referencia metodológica: [Bailey y colaboradores, The Probability of Backtest Overfitting](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2326253). El trabajo explica por qué seleccionar estrategias a partir de muchos backtests puede sobreajustar; este estudio no implementa su estimador PBO ni pretende haberlo calculado.']
    (output / 'REPORT.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', default='webui/uploads/bitget_baseline_20261017')
    parser.add_argument('--config', default='research/false_breakout/config_hourly.json')
    parser.add_argument('--protocol', default='research/false_breakout/signal_study_protocol.json')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    directory, output = Path(args.data), Path(args.output)
    if output.exists():
        raise FileExistsError('Usa un directorio nuevo para el estudio.')
    cfg = json.loads(Path(args.config).read_text(encoding='utf-8'))
    protocol = json.loads(Path(args.protocol).read_text(encoding='utf-8'))
    if cfg['entry_interval'] != '1H' or cfg['leverage_scenarios'] != [1] or protocol['horizons_hours'] != [1, 6, 24]:
        raise ValueError('Protocolo registrado incompatible: 1H/1x y horizontes 1/6/24.')
    if protocol['purge_hours'] != max(protocol['horizons_hours']):
        raise ValueError('La purga debe cubrir el horizonte máximo.')
    raw, meta = load_history(directory, '1H', cfg)
    inst_path = directory / 'instrument.json'
    inst = json.loads(inst_path.read_text(encoding='utf-8'))
    frame, bounds = research_window(raw, protocol)
    frame = causal_features(frame, protocol['lookback_bars'], float(inst['priceMultiplier']), protocol['volatility_bin_edges'])
    entries = candidate_entries(frame, bounds, protocol)
    rows, matched_rows, profiles = [], [], []
    for split in protocol['splits_used']:
        segment = entries[entries.split == split]
        for side in ['LONG', 'SHORT']:
            selected = segment[segment.side.isin([side, 'NONE'])]
            for horizon in protocol['horizons_hours']:
                print(f'Estudio {split} {side} {horizon}h...', flush=True)
                data = outcomes(frame, selected, side, horizon, cfg, inst)
                matched, controls, coverage = match_controls(data, protocol['minimum_controls_per_stratum'])
                profiles.append({'split': split, 'side': side, 'horizon_hours': horizon,
                                 **describe(matched, controls, coverage, protocol)})
                rows.append(data)
                matched_rows.append(matched)
    summary = {'protocol': protocol, 'config': cfg, 'bounds': {key: str(value) if isinstance(value, pd.Timestamp) else value for key, value in bounds.items()},
               'profiles': profiles, 'conclusion': 'El estudio separa señal y gestión, pero no establece una estrategia rentable. No se selecciona un perfil por su mejor resultado ni se utiliza el antiguo test para volver a ajustar la regla.'}
    output.mkdir(parents=True)
    pd.concat(rows, ignore_index=True).to_csv(output / 'diagnostic_signal_controls.csv', index=False)
    pd.concat(matched_rows, ignore_index=True).to_csv(output / 'diagnostic_matched_signals.csv', index=False)
    (output / 'protocol.json').write_text(json.dumps(protocol, indent=2, ensure_ascii=False), encoding='utf-8')
    (output / 'summary.json').write_text(json.dumps(summary, indent=2, ensure_ascii=False, allow_nan=False), encoding='utf-8')
    write_report(output, summary)
    sources = [Path('research/false_breakout') / name for name in ['study_signal.py', 'costs.py', 'backtest.py', 'run_experiment.py']]
    sources += [Path('webui/bitget_data.py'), Path('tests/test_signal_study.py')]
    inputs = [directory / meta['csv_file'], inst_path, Path(args.config), Path(args.protocol)]
    manifest = {'git_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
                'python': platform.python_version(), 'dependencies': {name: importlib.metadata.version(name) for name in ['numpy', 'pandas']},
                'input_sha256': {str(path): sha256(path) for path in inputs},
                'source_sha256': {str(path): sha256(path) for path in sources},
                'old_test_rows_excluded_before_analysis': bounds['excluded_test_rows'],
                'output_sha256': {path.name: sha256(path) for path in output.iterdir()}}
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    command = f'python -m research.false_breakout.study_signal --data {directory.as_posix()} --config {Path(args.config).as_posix()} --protocol {Path(args.protocol).as_posix()} --output NUEVO_DIRECTORIO'
    (output / 'command.txt').write_text(command + '\n', encoding='utf-8')
    print(f'Informe: {output / "REPORT.md"}', flush=True)


if __name__ == '__main__':
    main()
