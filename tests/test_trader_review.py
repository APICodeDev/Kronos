import pandas as pd

from research.trader_dossier.build_review_pack import FEATURE_COLUMNS, case_view, closed_context


def candles():
    frame = pd.DataFrame({'timestamp': pd.date_range('2026-01-01', periods=300, freq='h', tz='UTC'),
                          'open': 100., 'high': 101., 'low': 99., 'close': 100., 'volume': 10., 'turnover': 1000.})
    frame.loc[90, ['open', 'close']] = [99., 100.]
    return frame


def feature(frame):
    return {'signal_index': 100, 'signal_time': str(frame.timestamp.iloc[100]), 'side': 'LONG', 'impulse_index': 90,
            'impulse_time': str(frame.timestamp.iloc[90]), 'impulse_body_atr': 1., 'impulse_relative_volume': 2.,
            'level': 100., 'origin': 99., 'prior_extreme': 101., 'pullback_hours': 9,
            'pullback_depth_atr': .5, 'stop': 98.99, 'volume_ok': True, 'split': 'discovery'}


def test_all_future_ohlcv_changes_leave_entire_review_pack_identical():
    original = candles()
    changed = original.copy()
    changed.loc[101:, ['open', 'high', 'low', 'close', 'volume', 'turnover']] *= 100
    first, views = case_view(original, feature(original))
    second, changed_views = case_view(changed, feature(original))
    assert first == second
    for interval in views:
        pd.testing.assert_frame_equal(views[interval], changed_views[interval])


def test_higher_context_excludes_current_partial_day_and_partial_two_hour_bar():
    frame = candles().iloc[:101]
    asof = frame.timestamp.iloc[-1] + pd.Timedelta(hours=1)
    for hours in [2, 24]:
        context = closed_context(frame, hours, asof)
        assert (context.available_at <= asof).all()
        assert (context.timestamp + pd.Timedelta(hours=hours) == context.available_at).all()
    assert len(closed_context(frame, 24, asof)) == 4
    assert len(closed_context(frame, 2, asof)) == 50


def test_plan_read_allowlist_cannot_import_trade_outcomes_or_next_open():
    excluded = {'net_pnl', 'label', 'exit_time', 'exit_fill', 'entry_fill', 'entry_reference', 'tp', 'closed_equity'}
    assert not (set(FEATURE_COLUMNS) & excluded)
