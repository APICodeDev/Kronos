"""Detector causal y simulación OHLC conservadora; contexto descriptivo sin filtro."""
import numpy as np
import pandas as pd

from .costs import execution, pnl, position


def detect_signals(df, lookback, tick):
    high = df.high.shift(1).rolling(lookback).max()
    low = df.low.shift(1).rolling(lookback).min()
    # Comparar en unidades enteras de tick evita perder un barrido exacto por float.
    short = (np.rint(df.high / tick) >= np.rint(high / tick) + 1) & (df.close < high)
    long = (np.rint(df.low / tick) <= np.rint(low / tick) - 1) & (df.close > low)
    signals = []
    for index in np.flatnonzero((short | long).to_numpy()):
        signals.append({'signal_index': int(index), 'signal_time': df.timestamp.iloc[index],
                        'side': 'BOTH' if short.iloc[index] and long.iloc[index] else ('SHORT' if short.iloc[index] else 'LONG'),
                        'previous_high': high.iloc[index], 'previous_low': low.iloc[index]})
    return pd.DataFrame(signals, columns=['signal_index', 'signal_time', 'side', 'previous_high', 'previous_low'])


def attach_context(signals, contexts):
    result = signals.copy()
    result['signal_time'] = pd.to_datetime(result.signal_time, utc=True)
    result['entry_time'] = result.signal_time + pd.Timedelta(minutes=5)
    for interval, frame in contexts.items():
        duration = pd.Timedelta(minutes=15) if interval == '15m' else pd.Timedelta(hours=1)
        right = frame.copy()
        right['available_at'] = right.timestamp + duration
        right = right.rename(columns={x: f'{interval}_{x}' for x in frame.columns})
        result = pd.merge_asof(result.sort_values('entry_time'), right.sort_values('available_at'),
                               left_on='entry_time', right_on='available_at', direction='backward')
        result = result.rename(columns={'available_at': f'{interval}_available_at'})
    return result


def partition(entry, final_close, start, end, cfg):
    span = end - start
    first = start + span * cfg['split_fractions'][0]
    second = first + span * cfg['split_fractions'][1]
    embargo = pd.Timedelta(minutes=5 * cfg['embargo_bars'])
    if entry < first:
        return 'discovery' if final_close <= first else 'PURGED'
    if entry < first + embargo:
        return 'EMBARGO'
    if entry < second:
        return 'validation' if final_close <= second else 'PURGED'
    if entry < second + embargo:
        return 'EMBARGO'
    return 'test' if final_close <= end else 'INCOMPLETE'


def barrier(bar, side, stop, target):
    """Una apertura observable resuelve gaps antes de examinar high/low."""
    is_long = side == 'LONG'
    if (bar.open <= stop if is_long else bar.open >= stop):
        return 'SL_FIRST', bar.open, True
    if (bar.open >= target if is_long else bar.open <= target):
        return 'TP_FIRST', target, True  # No regalar mejora de precio en TP.
    sl = bar.low <= stop if is_long else bar.high >= stop
    tp = bar.high >= target if is_long else bar.low <= target
    if sl and tp:
        return 'AMBIGUOUS', stop, False
    if sl:
        return 'SL_FIRST', stop, False
    if tp:
        return 'TP_FIRST', target, False
    return None


def label_event(signal, df, cfg, inst, leverage, resolver=None):
    result = dict(signal)
    index = int(signal['signal_index'])
    tick = float(inst['priceMultiplier'])
    entry_index = index + 1
    result.update(leverage=leverage, entry_index=entry_index, label='AMBIGUOUS', evaluation_status='EVALUABLE')
    if signal['side'] == 'BOTH':
        result.update(evaluation_status='DUAL_SIGNAL', ambiguity_reason='Barrido de ambos extremos')
        return result
    if entry_index + cfg['max_holding_bars'] > len(df):
        result.update(evaluation_status='INCOMPLETE', ambiguity_reason='Horizonte final incompleto')
        return result
    side = signal['side']
    stop = (df.low.iloc[index] - cfg['stop_buffer_ticks'] * tick if side == 'LONG'
            else df.high.iloc[index] + cfg['stop_buffer_ticks'] * tick)
    stop = round(stop / tick) * tick
    opening = df.open.iloc[entry_index]
    result['stop'] = stop
    if (opening <= stop if side == 'LONG' else opening >= stop):
        result.update(label='GAP_INVALID', evaluation_status='NO_ENTRY')
        return result
    pos = position(opening, side, leverage, cfg, inst)
    result.update(pos)
    if (pos['entry_fill'] <= stop if side == 'LONG' else pos['entry_fill'] >= stop):
        result.update(label='GAP_INVALID', evaluation_status='NO_ENTRY')
        return result
    for j in range(entry_index, entry_index + cfg['max_holding_bars']):
        bar = df.iloc[j]
        touch = barrier(bar, side, stop, pos['tp'])
        if touch:
            label, reference, at_open = touch
            result['both_touched_5m'] = label == 'AMBIGUOUS'
            exit_time = bar.timestamp if at_open else bar.timestamp + pd.Timedelta(minutes=5)
            if label == 'AMBIGUOUS' and resolver:
                resolved = resolver(bar, side, stop, pos['tp'])
                if resolved:
                    label, reference, exit_time = resolved
                    result['resolved_1m'] = label != 'AMBIGUOUS'
            slip = cfg['tp_slippage_bps'] if label == 'TP_FIRST' else cfg['sl_slippage_bps']
            break
    else:
        j = entry_index + cfg['max_holding_bars'] - 1
        label, reference, slip = 'TIMEOUT', df.close.iloc[j], cfg['timeout_slippage_bps']
        exit_time = df.timestamp.iloc[j] + pd.Timedelta(minutes=5)
    fill = execution(reference, side, slip, tick)
    result.update(pnl(pos, side, fill, cfg))
    result.update(label=label, exit_reference=reference, exit_index=j, exit_time=exit_time,
                  holding_minutes=(exit_time - signal['entry_time']).total_seconds() / 60)
    if label == 'TP_FIRST' and result['net_margin_roi'] < cfg['target_net_margin_roi'] - 1e-10:
        raise AssertionError('TP no satisface rentabilidad neta objetivo.')
    return result


def simulate_portfolio(events, df, cfg):
    """Una posición por símbolo. Margen fijo, sin capitalización ni entradas sin capital."""
    trades = []
    available_at = df.timestamp.iloc[0]
    cash = cfg['initial_equity_usdt']
    for record in events.to_dict('records'):
        if record['evaluation_status'] != 'EVALUABLE' or pd.isna(record.get('net_pnl')):
            continue
        if record['entry_time'] < available_at:
            continue
        if cash < record['initial_margin_assigned'] + record['entry_fee']:
            continue
        cash += record['net_pnl']
        available_at = record['exit_time']
        record['closed_equity'] = cash
        trades.append(record)
    curve = np.full(len(df), cfg['initial_equity_usdt'], dtype=float)
    realized = 0.0
    for trade in trades:
        # Eventos sin entrada/salida convierten la columna de índices a float en pandas.
        a, b = int(trade['entry_index']), int(trade['exit_index'])
        sign = 1 if trade['side'] == 'LONG' else -1
        curve[a:b] = cfg['initial_equity_usdt'] + realized + (
            sign * trade['quantity'] * (df.close.iloc[a:b].to_numpy() - trade['entry_fill']) - trade['entry_fee'])
        realized += trade['net_pnl']
        curve[b:] = cfg['initial_equity_usdt'] + realized
    equity = pd.DataFrame({'timestamp': df.timestamp + pd.Timedelta(minutes=5), 'equity_usdt': curve})
    equity['drawdown'] = equity.equity_usdt / equity.equity_usdt.cummax().clip(lower=cfg['initial_equity_usdt']) - 1
    return pd.DataFrame(trades), equity
