import json
from pathlib import Path

import pandas as pd
import pytest

from research.false_breakout.backtest import attach_context, barrier, detect_signals, label_event, partition, simulate_portfolio
from research.false_breakout.costs import position

CFG = json.loads(Path('research/false_breakout/config.json').read_text())
INST = {'priceMultiplier': '0.01', 'quantityMultiplier': '1', 'minOrderQty': '1', 'minOrderAmount': '5'}


def candles(n=100):
    return pd.DataFrame({'timestamp': pd.date_range('2026-01-01', periods=n, freq='5min', tz='UTC'),
                         'open': 10., 'high': 10.1, 'low': 9.9, 'close': 10., 'volume': 1., 'turnover': 10.})


def signal_frame(side='LONG'):
    df = candles()
    if side == 'LONG':
        df.loc[20, 'low'] = 9.8
    else:
        df.loc[20, 'high'] = 10.2
    signal = detect_signals(df, 20, .01).iloc[0].to_dict()
    signal['entry_time'] = df.timestamp.iloc[21]
    return df, signal


@pytest.mark.parametrize('side', ['LONG', 'SHORT'])
def test_prior_20_excludes_signal_and_future(side):
    df, signal = signal_frame(side)
    assert signal['signal_index'] == 20
    assert signal['side'] == side
    assert signal['previous_high'] == 10.1
    assert signal['previous_low'] == 9.9
    df.loc[21:, ['high', 'low']] = [100, 1]
    assert detect_signals(df, 20, .01).iloc[0].to_dict() == {k: v for k, v in signal.items() if k != 'entry_time'}


def test_exact_tick_strict_close_and_dual_sweep():
    df = candles()
    df.loc[20, 'high'] = 10.11
    df.loc[20, 'close'] = 10.1
    assert detect_signals(df, 20, .01).empty
    df.loc[20, 'close'] = 10
    assert detect_signals(df, 20, .01).iloc[0].side == 'SHORT'
    df.loc[20, 'low'] = 9.8
    signal = detect_signals(df, 20, .01).iloc[0].to_dict()
    assert signal['side'] == 'BOTH'
    assert label_event(signal, df, CFG, INST, 1)['evaluation_status'] == 'DUAL_SIGNAL'


@pytest.mark.parametrize('side', ['LONG', 'SHORT'])
def test_next_open_tp_sl_and_gap(side):
    df, signal = signal_frame(side)
    pos = position(10, side, 1, CFG, INST)
    df.loc[21, 'high' if side == 'LONG' else 'low'] = pos['tp']
    result = label_event(signal, df, CFG, INST, 1)
    assert result['label'] == 'TP_FIRST'
    assert result['entry_index'] == 21
    assert result['net_margin_roi'] >= .01 - 1e-10
    df.loc[21, 'open'] = 9.7 if side == 'LONG' else 10.3
    assert label_event(signal, df, CFG, INST, 1)['label'] == 'GAP_INVALID'


def test_both_touched_conservative_and_gap_stop_real_price():
    df, signal = signal_frame()
    df.loc[21, ['low', 'high']] = [9, 11]
    result = label_event(signal, df, CFG, INST, 1)
    assert result['label'] == 'AMBIGUOUS'
    assert result['net_pnl'] < 0
    df.loc[21, ['low', 'high']] = [9.9, 10.1]
    df.loc[22, ['open', 'low', 'high']] = [9, 8.9, 9.1]
    result = label_event(signal, df, CFG, INST, 1)
    assert result['label'] == 'SL_FIRST'
    assert result['exit_reference'] == 9


def test_timeout_incomplete_and_1m_resolver():
    df, signal = signal_frame()
    result = label_event(signal, df, CFG, INST, 1)
    assert result['label'] == 'TIMEOUT'
    assert result['holding_minutes'] == 360
    assert result['net_pnl'] < 0
    assert label_event(signal, df.iloc[:50], CFG, INST, 1)['evaluation_status'] == 'INCOMPLETE'
    df.loc[21, ['low', 'high']] = [9, 11]
    result = label_event(signal, df, CFG, INST, 1,
                         lambda bar, side, stop, tp: ('TP_FIRST', tp, bar.timestamp + pd.Timedelta(minutes=1)))
    assert result['resolved_1m']
    assert result['label'] == 'TP_FIRST'


def test_context_asof_uses_closed_candle_only():
    df, signal = signal_frame()
    context = candles(3).iloc[:2].copy()
    context.timestamp = pd.to_datetime(['2026-01-01T00:00:00Z', '2026-01-01T01:00:00Z'])
    signal['signal_time'] = pd.Timestamp('2026-01-01T01:30:00Z')
    joined = attach_context(pd.DataFrame([signal]), {'1H': context})
    assert joined.iloc[0]['1H_timestamp'] == context.timestamp.iloc[0]
    assert joined.iloc[0]['1H_available_at'] <= joined.iloc[0].entry_time


def test_partition_purges_full_horizon_and_embargo():
    start, end = pd.Timestamp('2026-01-01', tz='UTC'), pd.Timestamp('2026-01-11', tz='UTC')
    cut = start + (end - start) * .6
    assert partition(cut - pd.Timedelta(hours=1), cut + pd.Timedelta(hours=5), start, end, CFG) == 'PURGED'
    assert partition(cut, cut + pd.Timedelta(hours=6), start, end, CFG) == 'EMBARGO'
    assert partition(cut + pd.Timedelta(hours=6), cut + pd.Timedelta(hours=12), start, end, CFG) == 'validation'


@pytest.mark.parametrize('intraminute_ambiguous', [False, True])
def test_minute_resolution_order_and_intraminute_conservative(tmp_path, monkeypatch, intraminute_ambiguous):
    from research.false_breakout.run_experiment import MinuteResolver
    import research.false_breakout.run_experiment as runner
    start = pd.Timestamp('2026-01-01T01:00:00Z')
    minutes = pd.DataFrame({'timestamp': pd.date_range(start, periods=5, freq='min'),
                            'open': 10., 'high': [11, 10.1, 10.1, 10.1, 10.1],
                            'low': [9 if intraminute_ambiguous else 9.9, 9, 9.9, 9.9, 9.9], 'close': 10.})
    monkeypatch.setattr(runner, 'fetch_history', lambda *args, **kwargs: (minutes, {'quality': {'missing_bars': 0}}))
    bar = pd.Series({'timestamp': start, 'open': 10., 'high': 11., 'low': 9., 'close': 10.})
    resolver = MinuteResolver(tmp_path, CFG, INST)
    label, reference, time = resolver(bar, 'LONG', 9.5, 10.5)
    assert label == ('AMBIGUOUS' if intraminute_ambiguous else 'TP_FIRST')
    assert reference == (9.5 if intraminute_ambiguous else 10.5)
    assert time == start + pd.Timedelta(minutes=1)


def test_minute_resolution_inconsistent_cannot_grant_win(tmp_path, monkeypatch):
    from research.false_breakout.run_experiment import MinuteResolver
    import research.false_breakout.run_experiment as runner
    minutes = candles(5)
    monkeypatch.setattr(runner, 'fetch_history', lambda *args, **kwargs: (minutes, {'quality': {'missing_bars': 0}}))
    bar = pd.Series({'timestamp': minutes.timestamp.iloc[0], 'open': 10., 'high': 11., 'low': 9., 'close': 10.})
    resolver = MinuteResolver(tmp_path, CFG, INST)
    assert resolver(bar, 'LONG', 9.5, 10.5) is None
    assert 'no coincide' in next(iter(resolver.notes.values()))


def test_portfolio_one_position_and_no_overlap_capital_curve():
    df, signal = signal_frame()
    result = label_event(signal, df, CFG, INST, 1)
    second = dict(result, entry_time=result['entry_time'] + pd.Timedelta(minutes=5))
    trades, curve = simulate_portfolio(pd.DataFrame([result, second]), df, CFG)
    assert len(trades) == 1
    assert curve.equity_usdt.iloc[-1] == pytest.approx(CFG['initial_equity_usdt'] + result['net_pnl'])
    assert curve.drawdown.min() < 0


def test_portfolio_mixed_no_entry_events_keep_indices_integer():
    df, signal = signal_frame()
    result = label_event(signal, df, CFG, INST, 1)
    no_entry = {'evaluation_status': 'DUAL_SIGNAL', 'entry_time': result['entry_time'], 'label': 'AMBIGUOUS'}
    trades, curve = simulate_portfolio(pd.DataFrame([result, no_entry]), df, CFG)
    assert len(trades) == 1
    assert curve.equity_usdt.iloc[-1] == pytest.approx(CFG['initial_equity_usdt'] + result['net_pnl'])


def test_barrier_open_order_known():
    bar = pd.Series({'open': 12, 'low': 8, 'high': 13})
    assert barrier(bar, 'LONG', 9, 11) == ('TP_FIRST', 11, True)
    assert barrier(bar, 'SHORT', 11, 9) == ('SL_FIRST', 12, True)


@pytest.mark.parametrize('with_signals', [False, True])
def test_cli_end_to_end_frozen_files_and_no_signal_case(tmp_path, monkeypatch, with_signals):
    import sys
    from webui.bitget_data import normalize, save_history
    from research.false_breakout.run_experiment import main, load_history
    from research.false_breakout.verify_results import verify

    data, output = tmp_path / 'data', tmp_path / 'report'
    data.mkdir()
    frame = candles(600)
    if with_signals:
        for index in [20, 100, 180, 260, 340, 420, 500]:
            frame.loc[index, 'low'] = 9.8
    start_ms = frame.timestamp.iloc[0].value // 1_000_000
    end_ms = start_ms + len(frame) * 300_000
    for interval, rule, step in [('5m', '5min', 300_000), ('15m', '15min', 900_000), ('1H', '1h', 3_600_000)]:
        native = frame.set_index('timestamp').resample(rule).agg(
            {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum', 'turnover': 'sum'}).reset_index()
        native.timestamp = native.timestamp.map(lambda value: value.value // 1_000_000)
        normalized, quality = normalize(native.values.tolist(), interval, start_ms, end_ms // step * step)
        meta = {'provider': 'Bitget', 'symbol': 'XRPUSDT', 'category': 'USDT-FUTURES', 'interval': interval,
                'requested_start_ms': start_ms, 'requested_end_ms': end_ms // step * step,
                'closed_cutoff_ms': end_ms, 'quality': quality}
        save_history(normalized, meta, data)
    (data / 'instrument.json').write_text(json.dumps(dict(INST, symbol='XRPUSDT', category='USDT-FUTURES')))
    cfg_path = tmp_path / 'config.json'
    cfg_path.write_text(json.dumps(dict(CFG, leverage_scenarios=[1])))
    monkeypatch.setattr(sys, 'argv', ['run_experiment', '--data', str(data), '--output', str(output), '--config', str(cfg_path)])
    main()
    assert (output / 'REPORT.md').exists()
    assert (output / 'manifest.json').exists()
    summary = json.loads((output / 'summary.json').read_text(encoding='utf-8'))
    if with_signals:
        assert summary['scenarios']['1']['all_candidates']['executed'] > 0
        assert verify(output)['checked_events'] > 0
    else:
        assert summary['signals_by_side'] == {}
        assert summary['scenarios']['1']['portfolio']['sum_net_pnl'] == 0
    with pytest.raises(FileExistsError):
        main()
    history_path = next(data.glob('*_5m_*.csv'))
    history_path.write_text('tampered')
    with pytest.raises(ValueError, match='Hash'):
        load_history(data, '5m', CFG)
