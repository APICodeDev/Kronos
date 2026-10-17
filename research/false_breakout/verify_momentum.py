"""Verificación independiente adicional de señales, costes, controles y cartera."""
import argparse
import csv
from decimal import Decimal
import json
from pathlib import Path

import pandas as pd

from webui.bitget_data import sha256
from .verify_diagnosis import verify as verify_diagnosis
from .verify_results import verify as verify_financial
from .verify_signal_study import verify as verify_study


def verify(report):
    report = Path(report)
    manifest = json.loads((report / 'manifest.json').read_text(encoding='utf-8'))
    s = json.loads((report / 'summary.json').read_text(encoding='utf-8'))
    for key in ['input_sha256', 'source_sha256', 'funding_files_sha256', 'minute_cache_sha256']:
        for name, digest in manifest[key].items():
            if sha256(name) != digest:
                raise AssertionError(f'Hash modificado: {name}')
    for name, digest in manifest['output_sha256'].items():
        if sha256(report / name) != digest:
            raise AssertionError(f'Salida modificada: {name}')
    source = next(n for n in manifest['input_sha256'] if 'XRPUSDT_1H_' in n and n.endswith('.csv'))
    instrument = next(n for n in manifest['input_sha256'] if n.endswith('instrument.json'))
    tick = Decimal(json.loads(Path(instrument).read_text())['priceMultiplier'])
    raw = pd.read_csv(source, dtype={'open': str, 'high': str, 'low': str, 'close': str}, parse_dates=['timestamp'])
    raw = raw[raw.timestamp < pd.Timestamp(s['bounds']['research_end'])].copy()
    n, maximum = s['protocol']['lookback_bars'], max(s['protocol']['horizons_hours'])
    sides = {}
    for i in range(n, len(raw)):
        previous = raw.iloc[i - n:i]
        high = max(map(Decimal, previous.high))
        low = min(map(Decimal, previous.low))
        close = Decimal(raw.close.iloc[i])
        # Independiente de numpy/rolling y de momentum_features.
        sides[i] = ('LONG' if (close / tick).to_integral_value() >= (high / tick).to_integral_value() + 1
                    else 'SHORT' if (close / tick).to_integral_value() <= (low / tick).to_integral_value() - 1 else 'NONE')
    expected = {}
    for i, side in sides.items():
        entry = raw.timestamp.iloc[i] + pd.Timedelta(hours=1)
        end = entry + pd.Timedelta(hours=maximum)
        split = ('discovery' if entry < pd.Timestamp(s['bounds']['discovery_end']) and end <= pd.Timestamp(s['bounds']['discovery_end'])
                 else 'validation' if entry >= pd.Timestamp(s['bounds']['validation_start']) and end <= pd.Timestamp(s['bounds']['research_end'])
                 else None)
        if split:
            expected[i] = (side, split)
    actual = set()
    checked = 0
    with (report / 'diagnostic_signal_controls.csv').open(encoding='utf-8', newline='') as handle:
        for row in csv.DictReader(handle):
            i, h = int(row['signal_index']), int(row['horizon_hours'])
            side, split = expected[i]
            assert row['source_side'] == side and row['split'] == split
            assert side == 'NONE' or side == row['side']
            key = (i, row['side'], h)
            assert key not in actual
            actual.add(key)
            checked += 1
    wanted = {(i, direction, h) for i, (side, _) in expected.items()
              for direction in (['LONG', 'SHORT'] if side == 'NONE' else [side]) for h in s['protocol']['horizons_hours']}
    assert actual == wanted, 'Faltan o sobran señales/controles registrados.'
    event_frame = pd.read_csv(report / 'execution/events_1x.csv', parse_dates=['entry_time', 'exit_time'])
    assert set(event_frame.signal_index) == {i for i, (side, _) in expected.items() if side != 'NONE'}
    for row in event_frame.itertuples():
        i = int(row.signal_index)
        assert row.side == sides[i] and row.split == expected[i][1]
        price = Decimal(raw.low.iloc[i] if row.side == 'LONG' else raw.high.iloc[i])
        stop = price + (-1 if row.side == 'LONG' else 1) * tick * s['config']['stop_buffer_ticks']
        assert abs(stop - Decimal(str(row.stop))) < Decimal('0.000001')
        assert row.entry_time == raw.timestamp.iloc[i + 1]
        if row.evaluation_status == 'EVALUABLE':
            assert row.entry_time <= row.exit_time <= row.entry_time + pd.Timedelta(hours=6)
    trades = pd.read_csv(report / 'execution/portfolio_1x.csv', dtype=str)
    events = {int(float(r['signal_index'])): r for r in pd.read_csv(report / 'execution/events_1x.csv', dtype=str).to_dict('records')}
    cash, last_exit = Decimal(str(s['config']['initial_equity_usdt'])), None
    maximum_error = Decimal(0)
    for row in trades.to_dict('records'):
        entry, exit_time = pd.Timestamp(row['entry_time']), pd.Timestamp(row['exit_time'])
        assert last_exit is None or entry >= last_exit
        assert cash >= Decimal(row['initial_margin_assigned']) + Decimal(row['entry_fee'])
        original = events[int(float(row['signal_index']))]
        for field in ['side', 'entry_time', 'exit_time', 'quantity', 'entry_fill', 'exit_fill', 'net_pnl', 'label']:
            assert row[field] == original[field]
        cash += Decimal(row['net_pnl'])
        error = abs(cash - Decimal(row['closed_equity']))
        maximum_error = max(maximum_error, error)
        assert error < Decimal('0.000001')
        last_exit = exit_time
    curve = pd.read_csv(report / 'execution/equity_1x.csv', parse_dates=['timestamp'])
    assert curve.timestamp.max() <= pd.Timestamp(s['bounds']['research_end'])
    assert abs(cash - Decimal(str(curve.equity_usdt.iloc[-1]))) < Decimal('0.000001')
    funding_dir = Path(next(n for n in manifest['funding_files_sha256'] if n.endswith('rates.csv'))).parent
    study_result = verify_study(report)
    tp_result = verify_financial(report / 'execution')
    (report / 'execution/tp_financial_verification.json').write_text(json.dumps(tp_result, indent=2), encoding='utf-8')
    funding_result = verify_diagnosis(report / 'execution', funding_dir)
    result = {'study': study_result, 'tp': tp_result, 'funding_attribution': funding_result,
              'independently_checked_signal_control_rows': checked, 'complete_registered_event_set': True,
              'portfolio_no_overlap': True, 'portfolio_trades_checked': len(trades),
              'max_portfolio_equity_error': str(maximum_error), 'verifier_sha256': sha256(__file__)}
    (report / 'momentum_verification.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--report', required=True)
    print(json.dumps(verify(parser.parse_args().report), indent=2))
