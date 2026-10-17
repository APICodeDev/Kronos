"""Recalcula los CSV con Decimal, sin reutilizar las fórmulas de costs.py."""
import argparse
from decimal import Decimal
import json
from pathlib import Path

import pandas as pd


def verify(directory):
    directory = Path(directory)
    cfg = json.loads((directory / 'summary.json').read_text(encoding='utf-8'))['config']
    def d(value):
        return Decimal(str(value))
    tolerance = Decimal('0.000001')  # CSV guarda floats; tolerancia absoluta en USDT.
    checked, worst_error, tp_count = 0, Decimal(0), 0
    for path in sorted(directory.glob('events_*x.csv')):
        frame = pd.read_csv(path, dtype=str)
        if 'net_pnl' not in frame:
            continue
        for record in frame.dropna(subset=['net_pnl']).to_dict('records'):
            qty, entry, exit_price = d(record['quantity']), d(record['entry_fill']), d(record['exit_fill'])
            leverage = d(record['leverage'])
            margin = qty * entry / leverage
            gross = qty * (exit_price - entry) * (1 if record['side'] == 'LONG' else -1)
            fee_in, fee_out = qty * entry * d(cfg['entry_fee_rate']), qty * exit_price * d(cfg['exit_fee_rate'])
            net = gross - fee_in - fee_out - d(record['net_funding_cost']) - d(cfg['other_costs_usdt'])
            for name, actual in [('initial_margin_assigned', margin), ('gross_pnl', gross), ('entry_fee', fee_in),
                                 ('exit_fee', fee_out), ('net_pnl', net), ('net_margin_roi', net / margin)]:
                error = abs(actual - d(record[name]))
                worst_error = max(worst_error, error)
                if error > tolerance:
                    raise AssertionError(f'{path.name}: {name} difiere {error}')
            if record['label'] == 'TP_FIRST':
                tp_count += 1
                if net / margin < d(cfg['target_net_margin_roi']) - Decimal('1e-10'):
                    raise AssertionError('TP por debajo del objetivo neto')
            checked += 1
    if not checked:
        raise AssertionError('No hay operaciones para verificar')
    result = {'checked_events': checked, 'checked_tp': tp_count, 'max_absolute_error': str(worst_error),
              'tolerance': str(tolerance), 'method': 'Recomputación Decimal independiente sobre CSV; sin funding.'}
    (directory / 'financial_verification.json').write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--report', required=True)
    print(json.dumps(verify(parser.parse_args().report), indent=2))
