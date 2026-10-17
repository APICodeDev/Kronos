import json
from pathlib import Path

import pytest

from research.false_breakout.costs import execution, pnl, position, validate_config

CFG = json.loads(Path('research/false_breakout/config.json').read_text())
INST = {'priceMultiplier': '0.0001', 'quantityMultiplier': '1', 'minOrderQty': '1', 'minOrderAmount': '5'}


@pytest.mark.parametrize('side', ['LONG', 'SHORT'])
@pytest.mark.parametrize('leverage', [1, 3, 5, 10])
def test_tp_exact_net_margin_after_costs(side, leverage):
    pos = position(2.1234, side, leverage, CFG, INST)
    actual = pnl(pos, side, pos['expected_tp_fill'], CFG)
    assert actual['net_margin_roi'] >= .01 - 1e-12
    assert actual['net_margin_roi'] < .01 + .002
    assert pos['quantity'] == int(pos['quantity'])
    assert pos['initial_margin_assigned'] == pytest.approx(pos['entry_notional'] / leverage)
    assert pos['initial_margin_assigned'] <= CFG['margin_usdt']
    assert actual['entry_fee'] == pytest.approx(pos['entry_notional'] * CFG['entry_fee_rate'])
    assert actual['exit_fee'] == pytest.approx(actual['exit_notional'] * CFG['exit_fee_rate'])
    assert actual['net_pnl'] == pytest.approx(actual['gross_pnl'] - actual['entry_fee'] - actual['exit_fee'])


@pytest.mark.parametrize('side,exit_price,gross', [('LONG', 102, 20), ('SHORT', 98, 20)])
def test_independent_hand_calculation(side, exit_price, gross):
    cfg = dict(CFG, entry_fee_rate=.001, exit_fee_rate=.002, other_costs_usdt=.5)
    actual = pnl({'quantity': 10, 'entry_fill': 100, 'initial_margin_assigned': 200}, side, exit_price, cfg, funding_cost=.3)
    expected = gross - 1 - 10 * exit_price * .002 - .3 - .5
    assert actual['net_pnl'] == pytest.approx(expected)
    assert actual['net_margin_roi'] == pytest.approx(expected / 200)


def test_slippage_adverse_and_margin_editable():
    assert execution(100, 'LONG', 10, .01, entry=True) >= 100.1
    assert execution(100, 'LONG', 10, .01) <= 99.9
    assert execution(100, 'SHORT', 10, .01, entry=True) <= 99.9
    assert execution(100, 'SHORT', 10, .01) >= 100.1
    pos = position(2, 'LONG', 3, dict(CFG, margin_usdt=300), INST)
    assert 299 < pos['initial_margin_assigned'] <= 300


def test_reject_impossible_quantity_and_config():
    with pytest.raises(ValueError):
        position(100000, 'LONG', 1, CFG, INST)
    with pytest.raises(ValueError):
        validate_config(dict(CFG, entry_fee_rate=2))
    with pytest.raises(ValueError):
        validate_config(dict(CFG, max_holding_bars=0))
