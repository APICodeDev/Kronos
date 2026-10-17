"""Verificación independiente de costes, ventanas temporales y emparejamiento."""
import argparse
import csv
from decimal import Decimal
import json
from pathlib import Path

import pandas as pd

from webui.bitget_data import sha256


def verify(report):
    report = Path(report)
    manifest = json.loads((report / 'manifest.json').read_text())
    summary = json.loads((report / 'summary.json').read_text(encoding='utf-8'))
    for name, digest in manifest['input_sha256'].items():
        if sha256(name) != digest:
            raise AssertionError(f'Entrada modificada: {name}')
    source_path = next(Path(name) for name in manifest['input_sha256'] if 'XRPUSDT_1H_' in name and name.endswith('.csv'))
    raw = pd.read_csv(source_path, parse_dates=['timestamp'])
    bounds = summary['bounds']
    research_end = pd.Timestamp(bounds['research_end'])
    raw = raw[raw.timestamp < research_end].copy()
    maximum_error, checked = Decimal(0), 0
    pools = {}

    def compare(expected, actual):
        nonlocal maximum_error
        error = abs(expected - Decimal(str(actual)))
        maximum_error = max(maximum_error, error)
        if error > Decimal('0.000001'):
            raise AssertionError(f'Error financiero o de control: {error}')

    with (report / 'diagnostic_signal_controls.csv').open(encoding='utf-8', newline='') as handle:
        for row in csv.DictReader(handle):
            entry, horizon = int(row['entry_index']), int(row['horizon_hours'])
            assert entry + horizon <= len(raw)
            entry_time, exit_time = pd.Timestamp(row['entry_time']), pd.Timestamp(row['exit_time'])
            assert exit_time == entry_time + pd.Timedelta(hours=horizon)
            assert exit_time <= research_end
            if row['split'] == 'discovery':
                assert entry_time + pd.Timedelta(hours=24) <= pd.Timestamp(bounds['discovery_end'])
            else:
                assert row['split'] == 'validation'
                assert entry_time >= pd.Timestamp(bounds['validation_start'])
                assert entry_time + pd.Timedelta(hours=24) <= research_end
            compare(Decimal(str(raw.open.iloc[entry])), row['entry_reference'])
            compare(Decimal(str(raw.close.iloc[entry + horizon - 1])), row['exit_reference'])
            q = Decimal(row['quantity'])
            sign = 1 if row['side'] == 'LONG' else -1
            e, x = Decimal(row['entry_fill']), Decimal(row['exit_fill'])
            gross = sign * q * (x - e)
            fee_in = q * e * Decimal(str(summary['config']['entry_fee_rate']))
            fee_out = q * x * Decimal(str(summary['config']['exit_fee_rate']))
            net = gross - fee_in - fee_out - Decimal(row['other_costs']) - Decimal(row['net_funding_cost'])
            compare(gross, row['gross_pnl'])
            compare(fee_in, row['entry_fee'])
            compare(fee_out, row['exit_fee'])
            compare(net, row['net_pnl'])
            compare(net / Decimal(row['initial_margin_assigned']) * 10000, row['net_roi_bps'])
            assert row['source_side'] == ('NONE' if row['kind'] == 'CONTROL' else row['side'])
            if row['kind'] == 'CONTROL':
                key = (row['split'], row['side'], row['horizon_hours'], row['stratum'])
                count, bps, usdt = pools.get(key, (0, Decimal(0), Decimal(0)))
                pools[key] = count + 1, bps + Decimal(row['net_roi_bps']), usdt + Decimal(row['net_pnl'])
            checked += 1
    matched = 0
    with (report / 'diagnostic_matched_signals.csv').open(encoding='utf-8', newline='') as handle:
        for row in csv.DictReader(handle):
            key = (row['split'], row['side'], row['horizon_hours'], row['stratum'])
            count, bps, usdt = pools[key]
            assert count >= summary['protocol']['minimum_controls_per_stratum']
            assert count == int(float(row['control_count']))
            compare(bps / count, row['control_mean_bps'])
            compare(usdt / count, row['control_mean_usdt'])
            compare(Decimal(row['net_roi_bps']) - bps / count, row['excess_net_roi_bps'])
            matched += 1
    result = {'financial_rows_checked': checked, 'matched_rows_checked': matched,
              'max_absolute_error': str(maximum_error), 'tolerance': '0.000001',
              'old_test_rows_excluded': manifest['old_test_rows_excluded_before_analysis'],
              'all_exit_windows_before_old_test': True, 'verifier_sha256': sha256(__file__)}
    (report / 'verification.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--report', required=True)
    print(json.dumps(verify(parser.parse_args().report), indent=2))
