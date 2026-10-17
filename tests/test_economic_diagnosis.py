import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from research.false_breakout.economic_diagnosis import attribute_costs, clustered_ci, overlay_funding, stats
from research.false_breakout.funding_data import fetch_funding, fetch_mark, normalize_funding
from webui.bitget_data import BitgetDataError, PublicClient

CFG = json.loads(Path('research/false_breakout/config.json').read_text())


@pytest.mark.parametrize('side,entry,exit_fill,reference,gross', [
    ('LONG', 100.1, 101.8, 20., 17.), ('SHORT', 99.9, 98.2, 20., 17.)])
def test_cost_attribution_independent_hand_calculation(side, entry, exit_fill, reference, gross):
    exit_reference = 102 if side == 'LONG' else 98
    fee_in, fee_out = 10 * entry * .0006, 10 * exit_fill * .0006
    event = {'side': side, 'quantity': 10., 'entry_reference': 100., 'entry_fill': entry,
             'exit_reference': exit_reference, 'exit_fill': exit_fill, 'label': 'TP_FIRST',
             'entry_fee': fee_in, 'exit_fee': fee_out, 'net_funding_cost': 0., 'other_costs': 0.,
             'net_pnl': gross - fee_in - fee_out, 'gross_pnl': gross,
             'entry_notional': 10 * entry, 'exit_notional': 10 * exit_fill,
             'stop': 99. if side == 'LONG' else 101., 'tp': exit_reference,
             'expected_tp_fill': exit_fill, 'initial_margin_assigned': 10 * entry,
             'entry_time': pd.Timestamp('2026-01-01T01:00:00Z'), 'exit_time': pd.Timestamp('2026-01-01T02:00:00Z')}
    frame = attribute_costs(pd.DataFrame([event]), CFG, .1)
    actual = frame.iloc[0]
    assert actual.reference_pnl == pytest.approx(reference)
    assert actual.entry_execution_cost == pytest.approx(1.)
    assert actual.exit_execution_cost == pytest.approx(2.)
    assert actual.execution_cost == pytest.approx(3.)
    assert actual.reconciliation_error == pytest.approx(0., abs=1e-10)
    assert actual.nominal_slippage_cost + actual.tick_rounding_cost == pytest.approx(3.)
    assert actual.planned_sl_net_loss > 0


def test_mismatched_pnl_is_rejected():
    data = pd.DataFrame([{'side': 'LONG', 'quantity': 1., 'entry_reference': 100., 'entry_fill': 100.1,
                          'exit_reference': 102., 'exit_fill': 101.9, 'entry_fee': .06, 'exit_fee': .06,
                          'net_funding_cost': 0., 'other_costs': 0., 'net_pnl': 99., 'label': 'TP_FIRST'}])
    with pytest.raises(AssertionError, match='concilia'):
        attribute_costs(data, CFG, .1)


def funding_fixture():
    rates = pd.DataFrame({'timestamp': pd.to_datetime(['2026-01-01T00:00Z', '2026-01-01T08:00Z', '2026-01-01T16:00Z']),
                          'rate': [.001, .001, -.001]})
    marks = pd.DataFrame({'timestamp': rates.timestamp, 'mark_proxy': 100., 'mark_low': 99., 'mark_high': 101.})
    return rates, marks


@pytest.mark.parametrize('side,expected', [('LONG', 1.), ('SHORT', -1.)])
def test_funding_sign_and_exact_interior(side, expected):
    rates, marks = funding_fixture()
    e = pd.DataFrame([{'entry_time': pd.Timestamp('2026-01-01T07:00Z'), 'exit_time': pd.Timestamp('2026-01-01T09:00Z'),
                       'side': side, 'quantity': 10., 'net_pnl': -2.}])
    result = overlay_funding(e, rates, marks).iloc[0]
    assert result.funding_covered
    assert result.funding_cost_estimate == pytest.approx(expected)
    assert result.net_with_estimated_funding == pytest.approx(-2 - expected)
    assert result.funding_interior_settlements == 1
    assert result.funding_boundary_settlements == 0
    assert result.net_funding_sensitivity_low <= result.net_with_estimated_funding <= result.net_funding_sensitivity_high


@pytest.mark.parametrize('side,low,high', [('LONG', 0., 1.01), ('SHORT', -1.01, 0.)])
def test_funding_entry_exit_boundary_uncertain(side, low, high):
    rates, marks = funding_fixture()
    frame = pd.DataFrame([{'entry_time': pd.Timestamp('2026-01-01T08:00Z'), 'exit_time': pd.Timestamp('2026-01-01T09:00Z'),
                           'side': side, 'quantity': 10., 'net_pnl': 5.}])
    result = overlay_funding(frame, rates, marks).iloc[0]
    assert result.funding_cost_estimate == 0
    assert result.funding_boundary_settlements == 1
    assert result.funding_cost_min_sensitivity == pytest.approx(low)
    assert result.funding_cost_max_sensitivity == pytest.approx(high)
    frame.entry_time = pd.Timestamp('2026-01-01T07:00Z')
    frame.exit_time = pd.Timestamp('2026-01-01T08:00Z')
    assert overlay_funding(frame, rates, marks).iloc[0].funding_boundary_settlements == 1


def test_funding_missing_coverage_never_becomes_zero_cost():
    rates, marks = funding_fixture()
    frame = pd.DataFrame([{'entry_time': pd.Timestamp('2025-12-31T23:00Z'), 'exit_time': pd.Timestamp('2026-01-01T01:00Z'),
                           'side': 'LONG', 'quantity': 10., 'net_pnl': 5.}])
    result = overlay_funding(frame, rates, marks).iloc[0]
    assert not result.funding_covered
    assert pd.isna(result.net_with_estimated_funding)
    frame.entry_time = pd.Timestamp('2026-01-01T07:00Z')
    frame.exit_time = pd.Timestamp('2026-01-01T09:00Z')
    with pytest.raises(ValueError, match='Falta mark'):
        overlay_funding(frame, rates, marks.iloc[:1])


def test_bootstrap_clusters_complete_weeks_and_reproducible():
    frame = pd.DataFrame({'entry_time': pd.date_range('2026-01-05', periods=21, freq='D', tz='UTC'),
                           'net_pnl': np.full(21, -3.), 'reference_pnl': np.full(21, .5)})
    first = clustered_ci(frame, ['net_pnl', 'reference_pnl'], repeats=200)
    assert first == clustered_ci(frame, ['net_pnl', 'reference_pnl'], repeats=200)
    assert first['weeks'] == 3
    assert first['intervals']['net_pnl'] == [-3., -3.]
    assert first['intervals']['reference_pnl'] == [.5, .5]


def funding_rows():
    return [{'symbol': 'XRPUSDT', 'fundingRate': rate, 'fundingRateTimestamp': str(time)}
            for time, rate in [(0, '.0001'), (28800000, '-.0002'), (57600000, '.0001')]]


def test_funding_normalize_duplicates_and_gaps():
    rows = funding_rows()
    frame, count = normalize_funding([rows[2], rows[0], rows[1], rows[1]], 'XRPUSDT', 8)
    assert frame.timestamp.is_monotonic_increasing
    assert len(frame) == 3 and count == 1
    with pytest.raises(BitgetDataError, match='Huecos'):
        normalize_funding([rows[0], rows[2]], 'XRPUSDT', 8)
    with pytest.raises(BitgetDataError, match='contradictorias'):
        normalize_funding(rows + [dict(rows[0], fundingRate='.001')], 'XRPUSDT', 8)


@pytest.mark.parametrize('key,value', [('symbol', 'BTCUSDT'), ('fundingRate', 'nan'), ('fundingRate', '1'), ('fundingRateTimestamp', '1')])
def test_invalid_funding_rows(key, value):
    rows = funding_rows()
    rows[0][key] = value
    with pytest.raises((BitgetDataError, ValueError)):
        normalize_funding(rows, 'XRPUSDT', 8)


def test_funding_pagination_and_no_progress():
    class Client:
        def __init__(self, repeat=False):
            self.calls, self.repeat = 0, repeat

        def get(self, endpoint, params):
            assert endpoint == 'history-fund-rate'
            self.calls += 1
            return {'resultList': funding_rows() if self.calls == 1 or self.repeat else []}
    client = Client()
    frame, meta = fetch_funding(client, 'XRPUSDT', 'USDT-FUTURES')
    assert len(frame) == 3 and client.calls == 2
    assert len(meta['queries']) == 2
    with pytest.raises(BitgetDataError, match='progreso'):
        fetch_funding(Client(repeat=True), 'XRPUSDT', 'USDT-FUTURES')


def test_native_mark_type_and_minute_boundary():
    class Client:
        def get(self, endpoint, params):
            assert endpoint == 'history-candles'
            assert params['type'] == 'mark'
            assert params['interval'] == '1m'
            return [[0, 100, 101, 99, 100, 0, 0]]
    result = fetch_mark(Client(), pd.Timestamp('1970-01-01', tz='UTC'), 'XRPUSDT', 'USDT-FUTURES')
    assert result['mark_proxy'] == 100


def test_funding_request_remains_public_and_offline_cache(tmp_path, monkeypatch):
    client = PublicClient(tmp_path)
    params = {'symbol': 'XRPUSDT', 'category': 'USDT-FUTURES', 'cursor': '1', 'limit': '100'}
    import hashlib
    key = hashlib.sha256(json.dumps(['history-fund-rate', params], sort_keys=True).encode()).hexdigest()
    (tmp_path / (key + '.json')).write_text(json.dumps({'code': '00000', 'data': {'resultList': funding_rows()}}))
    monkeypatch.setattr(client.session, 'get', lambda *args, **kwargs: pytest.fail('No se permite red en prueba de caché'))
    assert client.get('history-fund-rate', params)['resultList'] == funding_rows()
    with pytest.raises(ValueError, match='permitido'):
        client.get('place-order')


def test_stats_empty_group():
    assert stats(pd.DataFrame()) == {'n': 0}


def test_observed_win_rate_and_break_even_hand_calculation():
    cfg = dict(CFG, entry_fee_rate=0., exit_fee_rate=0., entry_slippage_bps=0., tp_slippage_bps=0., sl_slippage_bps=0.)
    records = []
    for index, exit_price in enumerate([110., 80., 80.]):
        records.append({'side': 'LONG', 'quantity': 1., 'entry_reference': 100., 'entry_fill': 100.,
                        'exit_reference': exit_price, 'exit_fill': exit_price, 'entry_fee': 0., 'exit_fee': 0.,
                        'net_funding_cost': 0., 'other_costs': 0., 'net_pnl': exit_price - 100.,
                        'gross_pnl': exit_price - 100., 'label': 'TP_FIRST' if index == 0 else 'SL_FIRST',
                        'entry_notional': 100., 'exit_notional': exit_price, 'stop': 90., 'tp': 110.,
                        'expected_tp_fill': 110., 'initial_margin_assigned': 100.,
                        'entry_time': pd.Timestamp('2026-01-01', tz='UTC')})
    result = stats(attribute_costs(pd.DataFrame(records), cfg, .01))
    assert result['positive_rate_nonzero'] == pytest.approx(1 / 3)
    assert result['break_even_positive_rate_nonzero'] == pytest.approx(2 / 3)
    assert result['mean_winner'] == 10
    assert result['mean_loser_abs'] == 20
    assert result['mean_net'] == -10
    assert result['frozen_path_cost_sensitivities']['zero_fees_current_execution'] == -10
