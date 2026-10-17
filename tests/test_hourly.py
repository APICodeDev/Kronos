import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from research.false_breakout.backtest import attach_context, label_event, partition, simulate_portfolio, detect_signals
from research.false_breakout.costs import validate_config
from research.false_breakout.run_hourly import HourlyResolver, validate_execution_data

CFG = json.loads(Path('research/false_breakout/config_hourly.json').read_text())
INST = {'priceMultiplier': '0.01', 'quantityMultiplier': '1', 'minOrderQty': '1', 'minOrderAmount': '5'}


def frames():
    fine = pd.DataFrame({'timestamp': pd.date_range('2026-01-01', periods=40 * 12, freq='5min', tz='UTC'),
                          'open': 10., 'high': 10.1, 'low': 9.9, 'close': 10., 'volume': 1., 'turnover': 10.})
    fine.loc[20 * 12, 'low'] = 9.8
    return aggregate(fine), fine


def aggregate(fine):
    return fine.set_index('timestamp').resample('1h').agg({'open': 'first', 'high': 'max', 'low': 'min',
                                                         'close': 'last', 'volume': 'sum', 'turnover': 'sum'}).reset_index()


def get_signal(hourly):
    return attach_context(detect_signals(hourly, 20, .01), {}, '1H').iloc[0].to_dict()


def no_ambiguity(*args):
    pytest.fail('No debería consultarse 1m si el orden se resuelve en 5m')


def test_hourly_configuration_and_one_hour_confirmation():
    validate_config(CFG)
    h, f = frames()
    signal = get_signal(h)
    assert signal['signal_index'] == 20
    assert signal['entry_time'] == h.timestamp.iloc[21]
    assert signal['previous_low'] == 9.9
    assert signal['previous_high'] == 10.1
    assert validate_execution_data(h, f, .01)['inconsistent_hours'] == 0


def test_hourly_timeout_is_six_hours_and_curve_is_hourly():
    h, f = frames()
    signal = get_signal(h)
    event = label_event(signal, h, CFG, INST, 1, HourlyResolver(f, no_ambiguity))
    assert event['label'] == 'TIMEOUT'
    assert event['entry_index'] == 21
    assert event['exit_index'] == 26
    assert event['holding_minutes'] == 360
    assert event['exit_time'] == h.timestamp.iloc[27]
    trades, curve = simulate_portfolio(pd.DataFrame([event]), h, CFG)
    assert len(trades) == 1
    assert curve.timestamp.iloc[0] == h.timestamp.iloc[0] + pd.Timedelta(hours=1)
    assert curve.equity_usdt.iloc[-1] == pytest.approx(CFG['initial_equity_usdt'] + event['net_pnl'])


@pytest.mark.parametrize('first', ['TP_FIRST', 'SL_FIRST'])
def test_hourly_both_touches_resolved_with_five_minute_order(first):
    _, f = frames()
    a = 21 * 12 + 1
    f.loc[a, 'high' if first == 'TP_FIRST' else 'low'] = 10.5 if first == 'TP_FIRST' else 9.5
    f.loc[a + 1, 'low' if first == 'TP_FIRST' else 'high'] = 9.5 if first == 'TP_FIRST' else 10.5
    h = aggregate(f)
    validate_execution_data(h, f, .01)
    event = label_event(get_signal(h), h, CFG, INST, 1, HourlyResolver(f, no_ambiguity))
    assert event['label'] == first
    assert event['both_touched_1H']
    assert not event['both_touched_5m']
    assert event['execution_resolution'] == '5m'
    assert event['holding_minutes'] == 10
    if first == 'TP_FIRST':
        assert event['net_margin_roi'] >= .01
    else:
        assert event['net_pnl'] < 0


def test_hourly_stop_gap_inside_hour_fills_at_gap_open():
    _, f = frames()
    f.loc[21 * 12 + 2, ['open', 'high', 'low', 'close']] = [9., 9.1, 8.9, 9.]
    h = aggregate(f)
    event = label_event(get_signal(h), h, CFG, INST, 1, HourlyResolver(f, no_ambiguity))
    assert event['label'] == 'SL_FIRST'
    assert event['exit_reference'] == 9.
    assert event['holding_minutes'] == 10


def test_nested_minute_resolution_and_unresolved_conservative():
    _, f = frames()
    f.loc[21 * 12 + 1, ['high', 'low']] = [10.5, 9.5]
    h = aggregate(f)
    def minute(bar, side, stop, target):
        return 'TP_FIRST', target, bar.timestamp + pd.Timedelta(minutes=2)
    event = label_event(get_signal(h), h, CFG, INST, 1, HourlyResolver(f, minute))
    assert event['label'] == 'TP_FIRST'
    assert event['execution_resolution'] == '1m'
    assert event['holding_minutes'] == 7
    def unavailable(*args):
        return None
    conservative = label_event(get_signal(h), h, CFG, INST, 1, HourlyResolver(f, unavailable))
    assert conservative['label'] == 'AMBIGUOUS'
    assert conservative['net_pnl'] < 0
    assert conservative['execution_resolution'] == '5m_AMBIGUOUS'


def test_hourly_data_mismatch_and_missing_children_fail():
    h, f = frames()
    bad = h.copy()
    bad.loc[2, 'high'] += .1
    with pytest.raises(ValueError, match='Inconsistencia'):
        validate_execution_data(bad, f, .01)
    with pytest.raises(ValueError, match='cubren'):
        validate_execution_data(h, f.iloc[1:], .01)


def test_hourly_embargo_is_six_hours_not_thirty_minutes():
    start, end = pd.Timestamp('2026-01-01', tz='UTC'), pd.Timestamp('2026-01-11', tz='UTC')
    cut = start + (end - start) * .6
    assert partition(cut + pd.Timedelta(hours=1), cut + pd.Timedelta(hours=7), start, end, CFG) == 'EMBARGO'
    assert partition(cut + pd.Timedelta(hours=6), cut + pd.Timedelta(hours=12), start, end, CFG) == 'validation'
    assert partition(cut - pd.Timedelta(hours=1), cut + pd.Timedelta(hours=5), start, end, CFG) == 'PURGED'


def test_five_minute_default_entry_timing_is_unchanged():
    h, _ = frames()
    signals = detect_signals(h, 20, .01)
    attached = attach_context(signals, {})
    assert np.all((attached.entry_time - attached.signal_time) == pd.Timedelta(minutes=5))
