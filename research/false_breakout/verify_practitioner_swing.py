"""Comprueba identidad de planes, contabilidad y cartera de interpretación swing."""
import argparse
from decimal import Decimal
import json
from pathlib import Path

import pandas as pd

from webui.bitget_data import sha256
from .verify_diagnosis import verify as verify_diagnosis
from .verify_results import verify as verify_financial


def verify(report):
    report = Path(report)
    m = json.loads((report / 'manifest.json').read_text(encoding='utf-8'))
    s = json.loads((report / 'summary.json').read_text(encoding='utf-8'))
    for key in ['inputs_sha256', 'source_sha256', 'funding_files_sha256', 'minute_cache_sha256']:
        for name, digest in m[key].items():
            assert sha256(name) == digest, f'Entrada modificada: {name}'
    for name, digest in m['output_sha256'].items():
        assert sha256(report / name) == digest, f'Salida modificada: {name}'
    source = next(n for n in m['inputs_sha256'] if n.replace('\\', '/').endswith('structure/events_1x.csv'))
    plans = pd.read_csv(source, dtype=str)
    original = {int(r['signal_index']): r for r in plans.to_dict('records')}
    funding_dir = Path(next(n for n in m['funding_files_sha256'] if n.endswith('rates.csv'))).parent
    tolerance = Decimal('0.000001')
    results = {}
    fields = ['side', 'split', 'signal_time', 'entry_time', 'impulse_index', 'volume_ok',
              'quantity', 'entry_reference', 'entry_fill', 'stop', 'tp', 'prior_extreme',
              'initial_margin_assigned', 'planned_stop_net_loss', 'planned_target_net_pnl', 'required_net_roi']
    numeric = set(fields[7:]) - {'volume_ok'}
    for name in s['protocol']['variants']:
        directory = report / name
        rows = pd.read_csv(directory / 'events_1x.csv', dtype=str).to_dict('records')
        wanted = {i for i, r in original.items() if name == 'structure' or r['volume_ok'] == 'True'}
        assert {int(r['signal_index']) for r in rows} == wanted
        for row in rows:
            plan = original[int(row['signal_index'])]
            for field in fields:
                if field in numeric:
                    assert abs(Decimal(row[field]) - Decimal(plan[field])) < tolerance, field
                else:
                    assert row[field] == plan[field], field
            assert row['evaluation_status'] == 'EVALUABLE'
            opened, closed = pd.Timestamp(row['entry_time']), pd.Timestamp(row['exit_time'])
            assert opened <= closed <= opened + pd.Timedelta(hours=24)
            end = s['bounds']['discovery_end'] if row['split'] == 'discovery' else s['bounds']['research_end']
            assert opened + pd.Timedelta(hours=24) <= pd.Timestamp(end)
            if row['split'] == 'validation':
                assert opened >= pd.Timestamp(s['bounds']['validation_start'])
            risk, reward = Decimal(row['planned_stop_net_loss']), Decimal(row['planned_target_net_pnl'])
            assert risk <= Decimal('25') + tolerance and reward >= 2 * risk - tolerance
            if row['label'] == 'TP_FIRST':
                assert Decimal(row['net_pnl']) >= max(2 * risk, Decimal('.01') * Decimal(row['initial_margin_assigned'])) - tolerance
        financial = verify_financial(directory)
        (directory / 'tp_financial_verification.json').write_text(json.dumps(financial, indent=2), encoding='utf-8')
        funding = verify_diagnosis(directory, funding_dir)
        trades = pd.read_csv(directory / 'portfolio_1x.csv', dtype=str).to_dict('records')
        cash, available = Decimal(str(s['config']['initial_equity_usdt'])), None
        event_map = {int(r['signal_index']): r for r in rows}
        for trade in trades:
            opened, closed = pd.Timestamp(trade['entry_time']), pd.Timestamp(trade['exit_time'])
            assert available is None or opened >= available
            assert cash >= Decimal(trade['initial_margin_assigned']) + Decimal(trade['entry_fee'])
            event = event_map[int(trade['signal_index'])]
            for field in ['net_pnl', 'entry_fill', 'exit_fill', 'quantity', 'label']:
                assert event[field] == trade[field]
            cash += Decimal(trade['net_pnl'])
            assert abs(cash - Decimal(trade['closed_equity'])) < tolerance
            available = closed
        curve = pd.read_csv(directory / 'equity_1x.csv', parse_dates=['timestamp'])
        assert abs(cash - Decimal(str(curve.equity_usdt.iloc[-1]))) < tolerance
        assert curve.timestamp.max() <= pd.Timestamp(s['bounds']['research_end'])
        results[name] = {'identical_frozen_plans_checked': len(rows), 'financial': financial,
                         'funding': funding, 'portfolio_trades_checked': len(trades)}
    result = {'variants': results, 'no_entries_stops_sizes_or_targets_changed': True,
              'only_prior_extreme_veto_removed': True, 'verifier_sha256': sha256(__file__)}
    (report / 'verification.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--report', required=True)
    print(json.dumps(verify(parser.parse_args().report), indent=2))
