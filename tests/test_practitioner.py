import copy
import json
from pathlib import Path

import pandas as pd
import pytest

from research.false_breakout.practitioner import (detect_setups, eligible_split, execute_setup,
                                                plan_entry, validate_volume)
from research.false_breakout.run_practitioner import book_summary, validate_protocol
from research.false_breakout.study_signal import research_window

P = json.loads(Path('research/false_breakout/practitioner_protocol.json').read_text(encoding='utf-8'))
C = json.loads(Path('research/false_breakout/config_practitioner.json').read_text())
INST = {'priceMultiplier': '.01', 'quantityMultiplier': '1', 'minOrderQty': '1', 'minOrderAmount': '5'}


def candles(n=100):
    return pd.DataFrame({'timestamp': pd.date_range('2026-01-01', periods=n, freq='h', tz='UTC'),
                         'open': 100., 'high': 100.2, 'low': 99.8, 'close': 100., 'volume': 100., 'turnover': 10000.})


def scenario():
    f = candles()
    f.loc[20, ['open', 'high', 'low', 'close', 'volume']] = [100., 104., 99.9, 103.8, 300.]
    f.loc[21, ['open', 'high', 'low', 'close', 'volume']] = [103.8, 103.85, 101.85, 102., 80.]
    f.loc[22, ['open', 'high', 'low', 'close', 'volume']] = [102., 102.1, 101.8, 101.9, 70.]
    f.loc[23, ['open', 'high', 'low', 'close', 'volume']] = [101.9, 102.2, 101.85, 102.11, 150.]
    f.loc[24:47, ['open', 'high', 'low', 'close']] = [102.12, 104., 102., 103.]
    return f


def test_setup_waits_for_pullback_and_first_confirmed_resumption():
    f = scenario()
    setups, _ = detect_setups(f, P, .01)
    row = setups[setups.impulse_index == 20].iloc[0]
    assert row.signal_index == 23 and row.side == 'LONG'
    assert row.entry_time == f.timestamp.iloc[24]
    assert row.level == 100.2 and row.stop == pytest.approx(101.79)
    assert row.volume_ok and row.impulse_relative_volume == 3


def test_future_price_or_volume_cannot_change_an_earlier_setup():
    f = scenario()
    changed = f.copy()
    changed.loc[24:, ['open', 'high', 'low', 'close', 'volume']] *= 10
    a, _ = detect_setups(f, P, .01)
    b, _ = detect_setups(changed, P, .01)
    pd.testing.assert_frame_equal(a[a.signal_index <= 23].reset_index(drop=True), b[b.signal_index <= 23].reset_index(drop=True))


def test_short_structure_mirrors_long_without_reversing_volume_rule():
    f = scenario()
    f[['open', 'close']] = 200 - f[['open', 'close']]
    high, low = 200 - f.low, 200 - f.high
    f['high'], f['low'] = high, low
    row = detect_setups(f, P, .01)[0].iloc[0]
    assert row.side == 'SHORT' and row.signal_index == 23
    assert row.stop == pytest.approx(98.21) and row.volume_ok


def test_volume_filters_do_not_rewrite_structural_setup_or_wait_for_better_outcome():
    f = scenario()
    original, _ = detect_setups(f, P, .01)
    f.loc[20, 'volume'] = 100.
    changed, _ = detect_setups(f, P, .01)
    a, b = original.iloc[0], changed.iloc[0]
    assert a.signal_index == b.signal_index == 23 and a.stop == b.stop
    assert a.volume_ok and not b.volume_ok


def test_losing_broken_level_permanently_invalidates_impulse():
    f = scenario()
    f.loc[21, ['low', 'close']] = [100., 100.1]
    setups, _ = detect_setups(f, P, .01)
    assert setups.empty or not (setups.impulse_index == 20).any()


def test_touch_without_closed_confirmation_is_not_entry():
    f = scenario()
    f.loc[23, ['high', 'close']] = [103., 102.1]
    setups, _ = detect_setups(f.iloc[:24], P, .01)
    assert setups.empty


@pytest.mark.parametrize('side,stop,extreme', [('LONG', 95., 120.), ('SHORT', 105., 80.)])
def test_sizing_caps_net_risk_and_target_covers_two_r_after_costs(side, stop, extreme):
    signal = {'signal_index': 20, 'side': side, 'stop': stop, 'prior_extreme': extreme}
    r = plan_entry(signal, 100., C, P, INST)
    assert r['evaluation_status'] == 'EVALUABLE'
    assert r['planned_stop_net_loss'] <= 25.
    assert r['initial_margin_assigned'] <= 1000.
    assert r['quantity'] == 4.
    assert r['planned_target_net_pnl'] >= 2 * r['planned_stop_net_loss']
    assert r['required_net_roi'] >= .01


def test_insufficient_room_rejects_before_outcomes_are_read():
    signal = {'signal_index': 20, 'side': 'LONG', 'stop': 99., 'prior_extreme': 100.1}
    r = plan_entry(signal, 100., C, P, INST)
    assert r['evaluation_status'] == 'NO_ENTRY' and r['label'] == 'NO_SPACE'
    assert 'net_pnl' not in r


def test_gap_does_not_create_fictitious_entry():
    signal = {'signal_index': 20, 'side': 'LONG', 'stop': 99., 'prior_extreme': 110.}
    assert plan_entry(signal, 98., C, P, INST)['label'] == 'GAP_INVALID'


def test_executed_setup_preserves_net_target_and_structural_stop():
    f = scenario()
    signal = detect_setups(f, P, .01)[0].iloc[0].to_dict()
    signal['split'] = 'discovery'
    r = execute_setup(signal, f, C, P, INST)
    assert r['entry_reference'] == 102.12 and r['entry_index'] == 24
    assert r['label'] == 'TP_FIRST' and r['net_margin_roi'] >= r['required_net_roi']
    assert r['stop'] == pytest.approx(101.79)


def test_purge_embargo_and_old_test_remain_excluded():
    raw = candles(1000)
    f, bounds = research_window(raw, P)
    assert len(f) == 800
    assert eligible_split(raw.timestamp.iloc[575], bounds, 24) == 'discovery'
    assert eligible_split(raw.timestamp.iloc[577], bounds, 24) == 'EXCLUDED_WINDOW'
    assert eligible_split(raw.timestamp.iloc[610], bounds, 24) == 'EXCLUDED_WINDOW'
    assert eligible_split(raw.timestamp.iloc[624], bounds, 24) == 'validation'
    assert eligible_split(raw.timestamp.iloc[777], bounds, 24) == 'EXCLUDED_WINDOW'


def test_volume_integrity_detects_mismatched_parent():
    fine = candles(12)
    fine['timestamp'] = pd.date_range('2026-01-01', periods=12, freq='5min', tz='UTC')
    hourly = candles(1)
    hourly[['volume', 'turnover']] *= 12
    assert validate_volume(hourly, fine)['max_abs_volume_difference'] == 0
    fine.loc[0, 'volume'] += 1
    with pytest.raises(ValueError, match='concuerdan'):
        validate_volume(hourly, fine)


def test_empty_book_is_reported_without_inventing_trades():
    assert book_summary(pd.DataFrame())['ALL']['executed'] == 0
    assert book_summary(pd.DataFrame())['ALL']['mean_net_pnl'] is None


def test_registered_rules_are_not_silently_reoptimized():
    validate_protocol(C, P)
    changed = copy.deepcopy(P)
    changed['minimum_impulse_relative_volume'] = 1.2
    with pytest.raises(ValueError, match='umbrales'):
        validate_protocol(C, changed)
