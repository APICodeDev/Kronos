"""Reconstruye independientemente selección OHLCV, riesgo, costes y cartera."""
import argparse
import csv
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
import json
from pathlib import Path

import pandas as pd

from webui.bitget_data import sha256
from .verify_diagnosis import verify as verify_diagnosis
from .verify_results import verify as verify_financial


def rebuild_setups(raw, protocol, tick):
    """Bucles sobre barras originales; no importa el detector ni sus indicadores."""
    records, impulses = {}, 0
    n = protocol['lookback_bars']
    bars = raw.to_dict('records')
    def units(value):
        return (Decimal(str(value)) / tick).to_integral_value()
    for a in range(n, len(bars)):
        bar, history = bars[a], bars[a - n:a]
        ranges = []
        for j in range(a - n, a):
            previous = bars[j - 1]['close'] if j else bars[j]['close']
            ranges.append(max(bars[j]['high'] - bars[j]['low'], abs(bars[j]['high'] - previous), abs(bars[j]['low'] - previous)))
        atr = sum(ranges) / n
        high, low = max(b['high'] for b in history), min(b['low'] for b in history)
        if abs(bar['close'] - bar['open']) < protocol['minimum_impulse_body_atr'] * atr:
            continue
        side = ('LONG' if bar['close'] > bar['open'] and units(bar['close']) >= units(high) + 1 else
                'SHORT' if bar['close'] < bar['open'] and units(bar['close']) <= units(low) - 1 else None)
        if side is None:
            continue
        impulses += 1
        sign = 1 if side == 'LONG' else -1
        level, origin = (high, bar['low']) if side == 'LONG' else (low, bar['high'])
        for i in range(a + protocol['minimum_wait_bars'], min(a + protocol['maximum_wait_bars'] + 1, len(bars))):
            sequence, pullback, current = bars[a + 1:i + 1], bars[a + 1:i], bars[i]
            extreme = min(b['low'] for b in sequence) if side == 'LONG' else max(b['high'] for b in sequence)
            if any(sign * (b['close'] - level) < 0 for b in sequence) or sign * (extreme - origin) <= 0:
                break
            pb_extreme = min(b['low'] for b in pullback) if side == 'LONG' else max(b['high'] for b in pullback)
            retreat = any(sign * (bars[j]['close'] - bars[j - 1]['close']) < 0 for j in range(a + 1, i))
            beyond = (units(current['close']) >= units(bars[i - 1]['high']) + 1 if side == 'LONG'
                      else units(current['close']) <= units(bars[i - 1]['low']) - 1)
            if not (retreat and sign * (bar['close'] - pb_extreme) >= protocol['minimum_pullback_atr'] * atr
                    and sign * (current['close'] - current['open']) > 0 and beyond):
                continue
            volumes = sorted(b['volume'] for b in history)
            median_volume = (volumes[n // 2 - 1] + volumes[n // 2]) / 2
            volume_ok = (bar['volume'] / median_volume >= protocol['minimum_impulse_relative_volume']
                         and sum(b['volume'] for b in pullback) / len(pullback) < bar['volume']
                         and current['volume'] > bars[i - 1]['volume'])
            records[(i, side)] = {'impulse_index': a, 'stop': Decimal(str(extreme)) - sign * tick,
                                  'level': level, 'volume_ok': volume_ok}
            break
    return records, impulses


def verify(report):
    report = Path(report)
    s = json.loads((report / 'summary.json').read_text(encoding='utf-8'))
    manifest = json.loads((report / 'manifest.json').read_text(encoding='utf-8'))
    for key in ['inputs_sha256', 'source_sha256', 'funding_files_sha256', 'minute_cache_sha256']:
        for path, digest in manifest[key].items():
            assert sha256(path) == digest, f'Fuente modificada: {path}'
    for path, digest in manifest['output_sha256'].items():
        assert sha256(report / path) == digest, f'Salida modificada: {path}'
    source = next(n for n in manifest['inputs_sha256'] if 'XRPUSDT_1H_' in n and n.endswith('.csv'))
    inst = next(n for n in manifest['inputs_sha256'] if n.endswith('instrument.json'))
    instrument = json.loads(Path(inst).read_text())
    tick = Decimal(instrument['priceMultiplier'])
    cfg, protocol, bounds = s['config'], s['protocol'], s['bounds']
    raw = pd.read_csv(source, parse_dates=['timestamp'])
    raw = raw[raw.timestamp < pd.Timestamp(bounds['research_end'])].copy()
    rebuilt, impulses = rebuild_setups(raw, protocol, tick)
    assert impulses == s['impulses']
    setups = pd.read_csv(report / 'diagnostic_setups.csv')
    assert len(setups) == len(rebuilt)
    for row in setups.itertuples():
        expected = rebuilt[(row.signal_index, row.side)]
        assert row.impulse_index == expected['impulse_index'] and row.volume_ok == expected['volume_ok']
        assert abs(Decimal(str(row.stop)) - expected['stop']) < Decimal('0.000001')
        assert row.level == expected['level']
    funding_dir = Path(next(n for n in manifest['funding_files_sha256'] if n.endswith('rates.csv'))).parent
    results, tolerance = {}, Decimal('0.000001')
    def d(value):
        return Decimal(str(value))
    def fill(price, side, bps, entry=False):
        adverse = (1 if side == 'LONG' else -1) * (1 if entry else -1)
        value = d(price) * (1 + adverse * d(bps) / 10000)
        return (value / tick).to_integral_value(rounding=ROUND_CEILING if adverse > 0 else ROUND_FLOOR) * tick
    expected_eligible = {}
    for (i, side), record in rebuilt.items():
        entry = raw.timestamp.iloc[i] + pd.Timedelta(hours=1)
        end = entry + pd.Timedelta(hours=24)
        split = ('discovery' if entry < pd.Timestamp(bounds['discovery_end']) and end <= pd.Timestamp(bounds['discovery_end']) else
                 'validation' if entry >= pd.Timestamp(bounds['validation_start']) and end <= pd.Timestamp(bounds['research_end']) else None)
        if split:
            expected_eligible[(i, side)] = (record, split)
    for name in protocol['variants']:
        directory = report / name
        with (directory / 'events_1x.csv').open(encoding='utf-8', newline='') as handle:
            events = list(csv.DictReader(handle))
        expected_keys = {key for key, (r, _) in expected_eligible.items() if name == 'structure' or r['volume_ok']}
        assert {(int(r['signal_index']), r['side']) for r in events} == expected_keys
        executed = 0
        for row in events:
            i, side = int(row['signal_index']), row['side']
            expected, split = expected_eligible[(i, side)]
            assert row['split'] == split
            assert pd.Timestamp(row['entry_time']) == raw.timestamp.iloc[i + 1]
            stop, opening = expected['stop'], d(raw.open.iloc[i + 1])
            sign = 1 if side == 'LONG' else -1
            entry_fill = fill(opening, side, cfg['entry_slippage_bps'], entry=True)
            if row['label'] == 'GAP_INVALID':
                assert sign * (opening - stop) <= 0 or sign * (entry_fill - stop) <= 0
                continue
            if row['label'] == 'MIN_SIZE':
                continue
            assert abs(entry_fill - d(row['entry_fill'])) < tolerance
            assert d(row['leverage']) == 1
            q, margin, target = d(row['quantity']), d(row['initial_margin_assigned']), d(row['tp'])
            assert q % d(instrument['quantityMultiplier']) == 0 and q >= d(instrument['minOrderQty'])
            assert margin <= d(cfg['margin_usdt']) + tolerance and abs(margin - q * entry_fill) < tolerance
            stop_fill = fill(stop, side, cfg['sl_slippage_bps'])
            risk = -sign * q * (stop_fill - entry_fill) + q * entry_fill * d(cfg['entry_fee_rate']) + q * stop_fill * d(cfg['exit_fee_rate']) + d(cfg['other_costs_usdt'])
            target_fill = fill(target, side, cfg['tp_slippage_bps'])
            reward = sign * q * (target_fill - entry_fill) - q * entry_fill * d(cfg['entry_fee_rate']) - q * target_fill * d(cfg['exit_fee_rate']) - d(cfg['other_costs_usdt'])
            assert abs(risk - d(row['planned_stop_net_loss'])) < tolerance
            assert abs(reward - d(row['planned_target_net_pnl'])) < tolerance
            assert risk <= d(cfg['initial_equity_usdt']) * d(protocol['risk_budget_fraction_of_initial_equity']) + tolerance
            assert reward >= d(protocol['minimum_net_reward_risk']) * risk - tolerance
            assert reward / margin >= d(cfg['target_net_margin_roi']) - tolerance
            extreme = d(row['prior_extreme'])
            if row['label'] == 'NO_SPACE':
                assert sign * (extreme - target) < 0 and row['evaluation_status'] == 'NO_ENTRY'
                assert not row.get('net_pnl')
                continue
            assert sign * (extreme - target) >= 0
            exit_time = pd.Timestamp(row['exit_time'])
            assert pd.Timestamp(row['entry_time']) <= exit_time <= pd.Timestamp(row['entry_time']) + pd.Timedelta(hours=24)
            if row['label'] == 'TP_FIRST':
                assert d(row['net_pnl']) >= max(d(cfg['target_net_margin_roi']) * margin, d(protocol['minimum_net_reward_risk']) * risk) - tolerance
            executed += 1
        if executed:
            financial = verify_financial(directory)
            write = directory / 'tp_financial_verification.json'
            write.write_text(json.dumps(financial, indent=2), encoding='utf-8')
            attribution = verify_diagnosis(directory, funding_dir)
        else:
            financial, attribution = {'checked_events': 0}, {'checked_rows': 0}
        trades = pd.read_csv(directory / 'portfolio_1x.csv', dtype=str).to_dict('records')
        cash, available = d(cfg['initial_equity_usdt']), None
        executed_rows = {int(r['signal_index']): r for r in events if r['evaluation_status'] == 'EVALUABLE'}
        for trade in trades:
            entry, exit_time = pd.Timestamp(trade['entry_time']), pd.Timestamp(trade['exit_time'])
            assert available is None or entry >= available
            assert cash >= d(trade['initial_margin_assigned']) + d(trade['entry_fee'])
            original = executed_rows[int(trade['signal_index'])]
            for field in ['entry_fill', 'exit_fill', 'net_pnl', 'quantity', 'label']:
                assert original[field] == trade[field]
            cash += d(trade['net_pnl'])
            assert abs(cash - d(trade['closed_equity'])) < tolerance
            available = exit_time
        curve = pd.read_csv(directory / 'equity_1x.csv', parse_dates=['timestamp'])
        assert curve.timestamp.max() <= pd.Timestamp(bounds['research_end'])
        assert abs(cash - d(curve.equity_usdt.iloc[-1])) < tolerance
        results[name] = {'decisions_checked': len(events), 'financial': financial,
                         'attribution': attribution, 'sequential_portfolio_trades_checked': len(trades)}
    result = {'independent_impulses': impulses, 'independent_setups': len(rebuilt), 'variants': results,
              'all_registered_decisions_present': True, 'old_test_rows_excluded': manifest['old_test_rows_excluded'],
              'verifier_sha256': sha256(__file__)}
    (report / 'verification.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--report', required=True)
    print(json.dumps(verify(parser.parse_args().report), indent=2))
