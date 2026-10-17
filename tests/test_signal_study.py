import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from research.false_breakout.study_signal import (candidate_entries, causal_features, joint_week_bootstrap,
                                                match_controls, outcomes, research_window)

PROTOCOL = json.loads(Path('research/false_breakout/signal_study_protocol.json').read_text(encoding='utf-8'))
CFG = json.loads(Path('research/false_breakout/config_hourly.json').read_text())
INST = {'priceMultiplier': '0.01', 'quantityMultiplier': '1', 'minOrderQty': '1', 'minOrderAmount': '5'}


def candles(n=1000):
    return pd.DataFrame({'timestamp': pd.date_range('2026-01-01', periods=n, freq='h', tz='UTC'),
                         'open': 100., 'high': 101., 'low': 99., 'close': 100., 'volume': 1., 'turnover': 100.})


def test_future_prices_cannot_change_causal_features():
    first = candles()
    second = first.copy()
    second.loc[51:, ['open', 'high', 'low', 'close']] *= 10
    a = causal_features(first, 20, .01, PROTOCOL['volatility_bin_edges'])
    b = causal_features(second, 20, .01, PROTOCOL['volatility_bin_edges'])
    pd.testing.assert_frame_equal(a.iloc[:51], b.iloc[:51])


def test_old_test_is_removed_before_building_labels_and_features():
    original = candles()
    changed = original.copy()
    changed.loc[800:, ['open', 'high', 'low', 'close']] *= 100
    a, bounds = research_window(original, PROTOCOL)
    b, other_bounds = research_window(changed, PROTOCOL)
    pd.testing.assert_frame_equal(a, b)
    assert bounds == other_bounds
    assert len(a) == 800
    assert bounds['excluded_test_rows'] == 200


def test_complete_max_horizon_purge_and_embargo_for_both_segments():
    raw, bounds = research_window(candles(), PROTOCOL)
    features = causal_features(raw, 20, .01, PROTOCOL['volatility_bin_edges'])
    entries = candidate_entries(features, bounds, PROTOCOL)
    discovery = entries[entries.split == 'discovery']
    validation = entries[entries.split == 'validation']
    assert (discovery.window_end <= bounds['discovery_end']).all()
    assert (validation.entry_time >= bounds['discovery_end'] + pd.Timedelta(hours=24)).all()
    assert (validation.window_end <= bounds['research_end']).all()
    assert entries.entry_index.max() + 24 <= len(raw)


@pytest.mark.parametrize('side', ['LONG', 'SHORT'])
def test_fixed_horizon_is_actual_exit_not_hindsight_mfe(side):
    frame = candles(50)
    # Una excursión favorable intrabar no cambia el cierre de salida.
    frame.loc[21, 'high' if side == 'LONG' else 'low'] = 120 if side == 'LONG' else 80
    features = causal_features(frame, 20, .01, PROTOCOL['volatility_bin_edges'])
    features['signal_index'], features['entry_index'] = features.index, features.index + 1
    features['split'] = 'discovery'
    features.loc[20, 'side'] = side
    result = outcomes(frame, features.loc[[20]], side, 1, CFG, INST).iloc[0]
    assert result.entry_time == frame.timestamp.iloc[21]
    assert result.exit_time == frame.timestamp.iloc[22]
    assert result.net_pnl < 0  # Precio vuelve a la entrada; ejecución y fees cuestan.
    assert result.mfe_net_upper_bound > 100
    assert result.ever_target_no_stop
    assert result.net_pnl != result.mfe_net_upper_bound


def test_matching_uses_signal_stratum_weights_and_reports_missing_controls():
    rows = []
    for stratum, count, value in [('A', 10, 1.), ('B', 30, 10.)]:
        rows.extend({'kind': 'CONTROL', 'stratum': stratum, 'net_pnl': value, 'net_roi_bps': value * 10} for _ in range(count))
    rows += [{'kind': 'SIGNAL', 'stratum': key, 'net_pnl': 5., 'net_roi_bps': 50.} for key in ['A', 'B', 'C']]
    matched, controls, coverage = match_controls(pd.DataFrame(rows), 10)
    assert coverage == {'signals_total': 3, 'signals_matched': 2, 'signals_excluded': 1, 'coverage': 2 / 3}
    assert matched.control_mean_usdt.mean() == 5.5
    assert matched.excess_net_pnl.mean() == -.5
    assert controls.net_pnl.mean() == 7.75  # No es el benchmark ponderado por señales.
    assert set(matched.stratum) == {'A', 'B'}


def test_joint_bootstrap_recomputes_controls_and_is_deterministic():
    events, controls = [], []
    for week in ['2026-01-05/2026-01-11', '2026-01-12/2026-01-18', '2026-01-19/2026-01-25']:
        events.append({'stratum': 'A', 'week': week, 'net_roi_bps': 5.})
        controls.extend({'stratum': 'A', 'week': week, 'net_roi_bps': 2.} for _ in range(10))
    a = joint_week_bootstrap(pd.DataFrame(events), pd.DataFrame(controls), 200, 123, 6)
    b = joint_week_bootstrap(pd.DataFrame(events), pd.DataFrame(controls), 200, 123, 6)
    assert a == b
    assert a['candidate_bps_ci95'] == [5., 5.]
    assert a['excess_bps_ci95'] == [3., 3.]
    assert a['valid_draws'] == 200


def test_unsupported_signals_do_not_get_a_silent_fallback():
    frame = pd.DataFrame([{'kind': 'SIGNAL', 'stratum': 'A', 'net_pnl': 2., 'net_roi_bps': 20.},
                           {'kind': 'CONTROL', 'stratum': 'B', 'net_pnl': 5., 'net_roi_bps': 50.}])
    matched, controls, coverage = match_controls(frame, 10)
    assert matched.empty and controls.empty
    assert coverage['signals_excluded'] == 1


def test_forward_window_length_is_checked():
    frame = candles(30)
    entries = causal_features(frame, 20, .01, PROTOCOL['volatility_bin_edges'])
    entries['entry_index'], entries['signal_index'], entries['split'] = entries.index + 1, entries.index, 'discovery'
    with pytest.raises(ValueError, match='incompleto'):
        outcomes(frame, entries.loc[[25]], 'LONG', 24, CFG, INST)


def test_fixed_volatility_bins_are_not_fitted_to_future_data():
    frame = causal_features(candles(100), 20, .01, [.003, .006, .012])
    # Rango verdadero 2 / cierre 100 = 0,02; pertenece a la banda superior.
    assert np.all(frame.volatility.iloc[19:] == .02)
    assert (frame.volatility_bin.iloc[19:] == 3).all()
