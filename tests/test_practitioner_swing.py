import copy
import json
from pathlib import Path

import pandas as pd
import pytest

from research.false_breakout.practitioner import plan_entry
from research.false_breakout.practitioner_swing import execute_frozen

CFG = json.loads(Path('research/false_breakout/config_practitioner.json').read_text())
PROTOCOL = json.loads(Path('research/false_breakout/practitioner_protocol.json').read_text(encoding='utf-8'))
INST = {'priceMultiplier': '.01', 'quantityMultiplier': '1', 'minOrderQty': '1', 'minOrderAmount': '5'}


def candles():
    return pd.DataFrame({'timestamp': pd.date_range('2026-01-01', periods=60, freq='h', tz='UTC'),
                         'open': 100., 'high': 100.2, 'low': 99.8, 'close': 100.})


@pytest.mark.parametrize('side,stop,extreme,high,low', [('LONG', 99., 100.1, 104., 99.5), ('SHORT', 101., 99.9, 100.5, 96.)])
def test_swing_uses_exact_frozen_plan_and_can_reach_target_beyond_old_extreme(side, stop, extreme, high, low):
    f = candles()
    f.loc[21:, ['high', 'low']] = [high, low]
    signal = {'signal_index': 20, 'side': side, 'stop': stop, 'prior_extreme': extreme,
              'entry_time': f.timestamp.iloc[21], 'split': 'discovery'}
    plan = plan_entry(signal, 100., CFG, PROTOCOL, INST)
    saved = copy.deepcopy(plan)
    assert plan['label'] == 'NO_SPACE'
    result = execute_frozen(plan, f, CFG, INST)
    assert plan == saved
    for field in ['entry_reference', 'entry_fill', 'quantity', 'stop', 'tp', 'required_net_roi']:
        assert result[field] == saved[field]
    assert result['label'] == 'TP_FIRST' and result['target_requires_prior_extreme_break']
    assert result['net_pnl'] >= 2 * result['planned_stop_net_loss']


def test_removed_space_veto_does_not_remove_stop_loss_or_simulate_free_exit():
    f = candles()
    f.loc[21:, ['high', 'low']] = [100.5, 98.]
    signal = {'signal_index': 20, 'side': 'LONG', 'stop': 99., 'prior_extreme': 100.1,
              'entry_time': f.timestamp.iloc[21], 'split': 'discovery'}
    plan = plan_entry(signal, 100., CFG, PROTOCOL, INST)
    result = execute_frozen(plan, f, CFG, INST)
    assert result['label'] == 'SL_FIRST'
    assert result['net_pnl'] == pytest.approx(-result['planned_stop_net_loss'])


def test_actual_gap_invalid_entry_stays_invalid_in_swing_interpretation():
    f = candles()
    signal = {'signal_index': 20, 'side': 'LONG', 'stop': 101., 'prior_extreme': 110.,
              'entry_time': f.timestamp.iloc[21], 'split': 'discovery'}
    plan = plan_entry(signal, 100., CFG, PROTOCOL, INST)
    result = execute_frozen(plan, f, CFG, INST)
    assert result['label'] == 'GAP_INVALID' and 'net_pnl' not in result
