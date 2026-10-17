import copy
import json
from pathlib import Path

import pandas as pd
import pytest

from research.false_breakout.backtest import label_event
from research.false_breakout.study_momentum import (continuation_decision, momentum_features,
                                                    validate_protocol)
from research.false_breakout.study_signal import candidate_entries, research_window

CFG = json.loads(Path('research/false_breakout/config_hourly.json').read_text())
PROTOCOL = json.loads(Path('research/false_breakout/momentum_protocol.json').read_text(encoding='utf-8'))
INST = {'priceMultiplier': '.01', 'quantityMultiplier': '1', 'minOrderQty': '1', 'minOrderAmount': '5'}


def candles(n=1000):
    return pd.DataFrame({'timestamp': pd.date_range('2026-01-01', periods=n, freq='h', tz='UTC'),
                         'open': 100., 'high': 101., 'low': 99., 'close': 100., 'volume': 1., 'turnover': 100.})


def features(frame):
    return momentum_features(frame, 20, .01, PROTOCOL['volatility_bin_edges'])


@pytest.mark.parametrize('side,close,high,low', [('LONG', 101.01, 103., 99.), ('SHORT', 98.99, 101., 97.)])
def test_exact_tick_close_and_exclusion_of_current_candle(side, close, high, low):
    frame = candles(40)
    frame.loc[20, ['close', 'high', 'low']] = [close, high, low]
    result = features(frame)
    assert result.side.iloc[20] == side
    assert result.previous_high.iloc[20] == 101
    assert result.previous_low.iloc[20] == 99
    assert (result.side.iloc[:20] == 'NONE').all()


def test_touch_without_confirmed_close_is_not_momentum():
    frame = candles(40)
    frame.loc[20, ['high', 'low']] = [103., 97.]
    assert features(frame).side.iloc[20] == 'NONE'
    frame.loc[20, 'close'] = 101.
    assert features(frame).side.iloc[20] == 'NONE'


def test_consecutive_breakouts_are_events_without_hidden_first_cross_filter():
    frame = candles(40)
    frame.loc[20, ['high', 'close']] = [101.01, 101.01]
    frame.loc[21, ['high', 'close']] = [101.02, 101.02]
    assert list(features(frame).side.iloc[20:22]) == ['LONG', 'LONG']


def test_future_candles_and_excluded_test_cannot_change_features():
    original = candles()
    changed = original.copy()
    changed.loc[51:, ['open', 'high', 'low', 'close']] *= 10
    pd.testing.assert_frame_equal(features(original).iloc[:51], features(changed).iloc[:51])
    excluded = original.copy()
    excluded.loc[800:, ['open', 'high', 'low', 'close']] *= 100
    a, bounds = research_window(original, PROTOCOL)
    b, other = research_window(excluded, PROTOCOL)
    pd.testing.assert_frame_equal(features(a), features(b))
    assert bounds == other and bounds['excluded_test_rows'] == 200


def test_same_24h_purge_and_embargo_apply_to_momentum_portfolio():
    frame, bounds = research_window(candles(), PROTOCOL)
    entries = candidate_entries(features(frame), bounds, PROTOCOL)
    for row in entries.itertuples():
        end = bounds['discovery_end'] if row.split == 'discovery' else bounds['research_end']
        assert row.entry_time + pd.Timedelta(hours=24) <= end
        if row.split == 'validation':
            assert row.entry_time >= bounds['discovery_end'] + pd.Timedelta(hours=24)


@pytest.mark.parametrize('side', ['LONG', 'SHORT'])
def test_momentum_entry_stop_and_net_tp_use_actual_margin(side):
    frame = candles(40)
    if side == 'LONG':
        frame.loc[20, ['high', 'close']] = [101.01, 101.01]
        frame.loc[21:26, ['open', 'low', 'high', 'close']] = [101.02, 101., 104., 103.]
    else:
        frame.loc[20, ['low', 'close']] = [98.99, 98.99]
        frame.loc[21:26, ['open', 'low', 'high', 'close']] = [98.98, 96., 99., 97.]
    signal = features(frame).iloc[20].to_dict()
    signal.update(signal_index=20, signal_time=frame.timestamp.iloc[20])
    event = label_event(signal, frame, CFG, INST, 1)
    assert event['entry_index'] == 21 and event['entry_reference'] == frame.open.iloc[21]
    assert event['stop'] == pytest.approx(98.99 if side == 'LONG' else 101.01)
    assert event['label'] == 'TP_FIRST'
    assert event['net_margin_roi'] >= .01
    assert event['initial_margin_assigned'] <= CFG['margin_usdt']


def test_gap_through_momentum_stop_is_not_an_executable_entry():
    frame = candles(40)
    frame.loc[20, ['high', 'close']] = [101.01, 101.01]
    frame.loc[21, ['open', 'low']] = [98., 97.]
    signal = features(frame).iloc[20].to_dict()
    signal.update(signal_index=20, signal_time=frame.timestamp.iloc[20])
    event = label_event(signal, frame, CFG, INST, 1)
    assert event['label'] == 'GAP_INVALID' and 'net_pnl' not in event


def test_do_not_promote_secondary_horizon_or_only_one_profitable_direction():
    profiles = [{'split': 'validation', 'side': side, 'horizon_hours': h, 'signals_matched': 100,
                 'mean_net_usdt': 2., 'excess_usdt': 1.,
                 'bootstrap': {'candidate_bps_adjusted_band': [1., 3.], 'excess_bps_adjusted_band': [1., 2.]}}
                for side in ['LONG', 'SHORT'] for h in [1, 6, 24]]
    portfolio = {'by_split': {'validation': {'sum_net_pnl': 10.}}}
    assert continuation_decision(profiles, portfolio)['meets_exploratory_gate']
    profiles[1]['mean_net_usdt'] = -1.
    assert not continuation_decision(profiles, portfolio)['meets_exploratory_gate']
    profiles[1]['mean_net_usdt'] = 2.
    profiles[4]['bootstrap']['excess_bps_adjusted_band'][0] = -1.
    assert not continuation_decision(profiles, portfolio)['meets_exploratory_gate']


def test_registered_protocol_rejects_different_horizons_or_leverage():
    validate_protocol(CFG, PROTOCOL)
    other = copy.deepcopy(CFG)
    other['leverage_scenarios'] = [3]
    with pytest.raises(ValueError, match='1H/1x'):
        validate_protocol(other, PROTOCOL)
    other_protocol = copy.deepcopy(PROTOCOL)
    other_protocol['horizons_hours'] = [1, 6, 48]
    with pytest.raises(ValueError, match='horizontes'):
        validate_protocol(CFG, other_protocol)
