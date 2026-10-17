"""Fichas retrospectivas con el futuro oculto, sin importar resultados de operaciones."""
import argparse
import json
from pathlib import Path

import pandas as pd

from webui.bitget_data import sha256
from research.false_breakout.run_experiment import load_history


FEATURE_COLUMNS = ['signal_index', 'signal_time', 'side', 'impulse_index', 'impulse_time',
                   'impulse_body_atr', 'impulse_relative_volume', 'level', 'origin', 'prior_extreme',
                   'pullback_hours', 'pullback_depth_atr', 'stop', 'volume_ok', 'split']
PRICE_COLUMNS = ['timestamp', 'open', 'high', 'low', 'close', 'volume', 'turnover']


def choose_cases(features):
    ordered = features.sort_values('signal_index')
    ranked = ordered.sort_values(['impulse_relative_volume', 'signal_index'])
    return [('first', ordered.iloc[0]),
            ('largest_prior_rvol', ranked.iloc[-1]),
            ('median_prior_rvol', ranked.iloc[len(ranked) // 2]),
            ('first_validation', ordered[ordered.split == 'validation'].iloc[0])]


def closed_context(prefix, hours, asof):
    rule = f'{hours}h'
    indexed = prefix.set_index('timestamp')
    grouped = indexed.resample(rule, origin='start_day', closed='left', label='left')
    context = grouped.agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last',
                           'volume': 'sum', 'turnover': 'sum'})
    counts = grouped.size()
    context = context[(counts == hours) & (context.index + pd.Timedelta(hours=hours) <= asof)]
    result = context.reset_index()
    result['available_at'] = result.timestamp + pd.Timedelta(hours=hours)
    return result


def case_view(raw, feature):
    i, anchor = int(feature['signal_index']), int(feature['impulse_index'])
    asof = pd.Timestamp(feature['signal_time']) + pd.Timedelta(hours=1)
    if raw.timestamp.iloc[i] != pd.Timestamp(feature['signal_time']):
        raise ValueError('La ficha no coincide con la vela original.')
    # Recortar ANTES de indicadores, contexto o cualquier estadística descriptiva.
    prefix = raw.iloc[:i + 1][PRICE_COLUMNS].copy()
    if not (prefix.timestamp + pd.Timedelta(hours=1) <= asof).all():
        raise AssertionError('Una vela no cerrada aparece en la ficha.')
    hourly = prefix.copy()
    hourly['ema20'] = hourly.close.ewm(span=20, adjust=False, min_periods=20).mean()
    hourly['available_at'] = hourly.timestamp + pd.Timedelta(hours=1)
    hourly = hourly.tail(96)
    two_hour = closed_context(prefix, 2, asof).tail(60)
    daily = closed_context(prefix, 24, asof).tail(30)
    impulse = prefix.iloc[anchor]
    pullback = prefix.iloc[anchor + 1:i]
    sign = 1 if feature['side'] == 'LONG' else -1
    extreme = pullback.low.min() if sign == 1 else pullback.high.max()
    giveback = sign * (impulse.close - extreme) / abs(impulse.close - impulse.open)
    metadata = {key: feature[key] for key in FEATURE_COLUMNS}
    metadata.update(asof=asof, impulse_open=float(impulse.open), impulse_close=float(impulse.close),
                    giveback_fraction_of_impulse_body=float(giveback),
                    previous_closed_daily_high=float(daily.high.iloc[-1]) if len(daily) else None,
                    previous_closed_daily_low=float(daily.low.iloc[-1]) if len(daily) else None,
                    hourly_rows=len(hourly), two_hour_rows=len(two_hour), daily_rows=len(daily),
                    outcome_hidden=True, contains_entry_or_exit_fill=False,
                    assessment='Ficha descriptiva: no emite recomendación de entrada ni etiqueta retrospectiva de ganador/perdedor.')
    # pandas convierte Timestamp/numpy/NaN sin incluir campos de resultados.
    clean = json.loads(pd.DataFrame([metadata]).to_json(orient='records', date_format='iso'))[0]
    return clean, {'1H': hourly, '2H': two_hour, '1D': daily}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', default='webui/uploads/bitget_baseline_20261017')
    parser.add_argument('--plans', default='research/false_breakout/reports/practitioner_20261017/structure/events_1x.csv')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    output, data, plans = Path(args.output), Path(args.data), Path(args.plans)
    if output.exists():
        raise FileExistsError('Las fichas se guardan en un directorio nuevo.')
    cfg_path = Path('research/false_breakout/config_practitioner.json')
    cfg = json.loads(cfg_path.read_text(encoding='utf-8'))
    raw, meta = load_history(data, '1H', cfg)
    # Lista blanca: ni siquiera se cargan PnL, resultados, fills o salidas del CSV.
    features = pd.read_csv(plans, usecols=FEATURE_COLUMNS)
    cases = []
    output.mkdir(parents=True)
    for label, row in choose_cases(features):
        metadata, views = case_view(raw, row)
        metadata['case_id'] = label
        cases.append(metadata)
        for interval, frame in views.items():
            frame.to_csv(output / f'{label}_{interval}.csv', index=False)
    summary = {'purpose': 'Auditar fidelidad al método con futuro oculto; no medir rentabilidad ni seleccionar parámetros.',
               'selection': 'Primer caso, mayor volumen relativo conocido en su impulso, mediana de ese volumen y primer caso de validación. La selección del panel es retrospectiva; no es una señal operativa ni una muestra aleatoria independiente.',
               'loaded_plan_columns': FEATURE_COLUMNS, 'cases': cases,
               'sources': {str(plans): sha256(plans), str(data / meta['csv_file']): sha256(data / meta['csv_file']), str(cfg_path): sha256(cfg_path)},
               'code_sha256': sha256(__file__),
               'outputs_sha256': {p.name: sha256(p) for p in output.glob('*.csv')}}
    (output / 'cases.json').write_text(json.dumps(summary, indent=2, ensure_ascii=False, allow_nan=False), encoding='utf-8')
    print(json.dumps({'cases': len(cases), 'output': str(output), 'contains_trade_results': False}))


if __name__ == '__main__':
    main()
