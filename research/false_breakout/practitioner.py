"""Playbook causal: impulso, retroceso, confirmación y selección por riesgo/volumen."""
from decimal import Decimal

import numpy as np
import pandas as pd

from .backtest import barrier
from .costs import execution, grid, pnl, position


def detect_setups(frame, protocol, tick):
    n = protocol['lookback_bars']
    previous = frame.close.shift(1)
    tr = pd.concat([frame.high - frame.low, (frame.high - previous).abs(),
                    (frame.low - previous).abs()], axis=1).max(axis=1)
    atr = tr.shift(1).rolling(n).mean()
    volume = frame.volume.shift(1).rolling(n).median()
    highs, lows = frame.high.shift(1).rolling(n).max(), frame.low.shift(1).rolling(n).min()
    records, impulses = [], []
    for a in range(n, len(frame)):
        bar = frame.iloc[a]
        if abs(bar.close - bar.open) < protocol['minimum_impulse_body_atr'] * atr.iloc[a]:
            continue
        side = ('LONG' if bar.close > bar.open and np.rint(bar.close / tick) >= np.rint(highs.iloc[a] / tick) + 1
                else 'SHORT' if bar.close < bar.open and np.rint(bar.close / tick) <= np.rint(lows.iloc[a] / tick) - 1 else None)
        if side is None:
            continue
        impulses.append({'impulse_index': a, 'side': side, 'timestamp': bar.timestamp})
        sign = 1 if side == 'LONG' else -1
        level = highs.iloc[a] if side == 'LONG' else lows.iloc[a]
        origin = bar.low if side == 'LONG' else bar.high
        extreme = bar.high if side == 'LONG' else bar.low
        for i in range(a + protocol['minimum_wait_bars'], min(a + protocol['maximum_wait_bars'] + 1, len(frame))):
            pullback = frame.iloc[a + 1:i]
            current, last = frame.iloc[i], frame.iloc[i - 1]
            sequence = frame.iloc[a + 1:i + 1]
            invalid_level = (sign * (sequence.close - level) < 0).any()
            stop_extreme = sequence.low.min() if side == 'LONG' else sequence.high.max()
            if invalid_level or sign * (stop_extreme - origin) <= 0:
                break
            pb_extreme = pullback.low.min() if side == 'LONG' else pullback.high.max()
            depth = sign * (bar.close - pb_extreme)
            retreat = (sign * (frame.close.diff().iloc[a + 1:i]) < 0).any()
            beyond = (np.rint(current.close / tick) >= np.rint(last.high / tick) + 1 if side == 'LONG'
                      else np.rint(current.close / tick) <= np.rint(last.low / tick) - 1)
            if not (retreat and depth >= protocol['minimum_pullback_atr'] * atr.iloc[a]
                    and sign * (current.close - current.open) > 0 and beyond):
                continue
            rvol = float(bar.volume / volume.iloc[a])
            impulse_volume_ok = rvol >= protocol['minimum_impulse_relative_volume']
            pullback_volume_ok = pullback.volume.mean() < bar.volume
            confirmation_volume_ok = current.volume > last.volume
            stop = grid(Decimal(str(stop_extreme)) - sign * Decimal(str(tick)), tick, up=side == 'SHORT')
            records.append({'signal_index': i, 'signal_time': current.timestamp,
                            'entry_time': current.timestamp + pd.Timedelta(hours=1), 'side': side,
                            'impulse_index': a, 'impulse_time': bar.timestamp, 'impulse_atr': float(atr.iloc[a]),
                            'impulse_body_atr': float(abs(bar.close - bar.open) / atr.iloc[a]),
                            'level': float(level), 'origin': float(origin), 'prior_extreme': float(extreme),
                            'pullback_hours': len(pullback), 'pullback_depth_atr': float(depth / atr.iloc[a]),
                            'stop': stop, 'impulse_volume': float(bar.volume), 'impulse_relative_volume': rvol,
                            'pullback_mean_volume': float(pullback.volume.mean()),
                            'previous_volume': float(last.volume), 'confirmation_volume': float(current.volume),
                            'impulse_volume_ok': bool(impulse_volume_ok), 'pullback_volume_ok': bool(pullback_volume_ok),
                            'confirmation_volume_ok': bool(confirmation_volume_ok),
                            'volume_ok': bool(impulse_volume_ok and pullback_volume_ok and confirmation_volume_ok)})
            # La primera confirmación se fija sin mirar resultado o futuras confirmaciones.
            break
    columns = ['signal_index', 'signal_time', 'entry_time', 'side', 'volume_ok']
    setups = pd.DataFrame(records) if records else pd.DataFrame(columns=columns)
    if len(setups):
        setups = (setups.sort_values(['signal_index', 'impulse_index'])
                  .drop_duplicates(['signal_index', 'side'], keep='last').reset_index(drop=True))
    return setups, pd.DataFrame(impulses)


def eligible_split(entry, bounds, horizon):
    final = entry + pd.Timedelta(hours=horizon)
    if entry < bounds['discovery_end'] and final <= bounds['discovery_end']:
        return 'discovery'
    if entry >= bounds['validation_start'] and final <= bounds['research_end']:
        return 'validation'
    return 'EXCLUDED_WINDOW'


def plan_entry(signal, opening, cfg, protocol, inst):
    """La selección usa solo barras cerradas y apertura; no examina resultados."""
    result = dict(signal)
    side, stop = signal['side'], signal['stop']
    sign, tick = (1 if side == 'LONG' else -1), float(inst['priceMultiplier'])
    result.update(entry_index=int(signal['signal_index']) + 1, leverage=1,
                  label='GAP_INVALID', evaluation_status='NO_ENTRY')
    fill = execution(opening, side, cfg['entry_slippage_bps'], tick, entry=True)
    if sign * (opening - stop) <= 0 or sign * (fill - stop) <= 0:
        return result
    local = dict(cfg)
    stop_fill = execution(stop, side, cfg['sl_slippage_bps'], tick)
    budget = cfg['initial_equity_usdt'] * protocol['risk_budget_fraction_of_initial_equity']
    per_unit_loss = -sign * (stop_fill - fill) + fill * cfg['entry_fee_rate'] + stop_fill * cfg['exit_fee_rate']
    maximum_qty = grid((budget - cfg['other_costs_usdt']) / per_unit_loss, inst['quantityMultiplier'])
    if maximum_qty < float(inst['minOrderQty']) or maximum_qty * fill < float(inst['minOrderAmount']):
        result.update(label='MIN_SIZE')
        return result
    local['margin_usdt'] = min(cfg['margin_usdt'], maximum_qty * fill)
    pos = position(opening, side, 1, local, inst)
    loss = -pnl(pos, side, stop_fill, local)['net_pnl']
    local['target_net_margin_roi'] = max(cfg['target_net_margin_roi'], protocol['minimum_net_reward_risk'] * loss / pos['initial_margin_assigned'])
    pos = position(opening, side, 1, local, inst)
    loss = -pnl(pos, side, stop_fill, local)['net_pnl']
    planned_tp = pnl(pos, side, pos['expected_tp_fill'], local)['net_pnl']
    if loss > budget + 1e-8 or planned_tp < protocol['minimum_net_reward_risk'] * loss - 1e-8:
        raise AssertionError('Plan incumple presupuesto de riesgo o recompensa neta.')
    result.update(pos, planned_stop_net_loss=loss, planned_target_net_pnl=planned_tp,
                  planned_net_reward_risk=planned_tp / loss, risk_budget_usdt=budget,
                  required_net_roi=local['target_net_margin_roi'])
    # El extremo es anterior a la entrada y no un máximo/mínimo futuro.
    if sign * (signal['prior_extreme'] - pos['tp']) < -tick * 1e-8:
        result.update(label='NO_SPACE')
        return result
    result.update(label='PENDING', evaluation_status='EVALUABLE')
    return result


def execute_setup(signal, frame, cfg, protocol, inst, resolver=None):
    index = int(signal['signal_index']) + 1
    horizon = protocol['horizons_hours'][0]
    if index + horizon > len(frame):
        return {**signal, 'evaluation_status': 'INCOMPLETE', 'label': 'INCOMPLETE'}
    result = plan_entry(signal, float(frame.open.iloc[index]), cfg, protocol, inst)
    if result['evaluation_status'] != 'EVALUABLE':
        return result
    side, tick = signal['side'], float(inst['priceMultiplier'])
    result.update(both_touched_1H=False, both_touched_5m=False)
    for j in range(index, index + horizon):
        bar = frame.iloc[j]
        touch = barrier(bar, side, result['stop'], result['tp'])
        if touch:
            label, reference, at_open = touch
            result['both_touched_1H'] = label == 'AMBIGUOUS'
            exit_time = bar.timestamp if at_open else bar.timestamp + pd.Timedelta(hours=1)
            if resolver:
                resolved = resolver(bar, side, result['stop'], result['tp'])
                if resolved:
                    label, reference, exit_time = resolved
                    result.update(execution_resolution=resolver.last_resolution,
                                  both_touched_5m=resolver.last_both_touched_5m)
            slip = cfg['tp_slippage_bps'] if label == 'TP_FIRST' else cfg['sl_slippage_bps']
            break
    else:
        j = index + horizon - 1
        label, reference, slip = 'TIMEOUT', frame.close.iloc[j], cfg['timeout_slippage_bps']
        exit_time = frame.timestamp.iloc[j] + pd.Timedelta(hours=1)
    actual = pnl(result, side, execution(reference, side, slip, tick), cfg)
    result.update(actual, label=label, exit_reference=float(reference), exit_index=j, exit_time=exit_time,
                  holding_minutes=(exit_time - signal['entry_time']).total_seconds() / 60)
    if label == 'TP_FIRST' and actual['net_margin_roi'] < result['required_net_roi'] - 1e-10:
        raise AssertionError('TP incumple objetivo neto registrado.')
    return result


def validate_volume(hourly, fine):
    fields = ['open', 'high', 'low', 'close', 'volume', 'turnover']
    for name, data in [('1H', hourly), ('5m', fine)]:
        if not set(fields).issubset(data) or not np.isfinite(data[fields]).all().all():
            raise ValueError(f'OHLCV/turnover incompletos: {name}')
        if (data.volume <= 0).any() or (data.turnover <= 0).any():
            raise ValueError(f'Volumen/turnover no positivo: {name}')
    aggregate = fine.set_index('timestamp')[['volume', 'turnover']].resample('1h').sum()
    original = hourly.set_index('timestamp')[['volume', 'turnover']]
    if not aggregate.index.equals(original.index):
        raise ValueError('Ventanas de volumen incompatibles.')
    differences = (original - aggregate).abs()
    if not np.allclose(original, aggregate, rtol=1e-10, atol=1e-6):
        raise ValueError('Volumen/turnover 1H no concuerdan con 5m.')
    return {'hours': len(hourly), 'missing_ohlcv': 0, 'nonpositive_volume': 0,
            'max_abs_volume_difference': float(differences.volume.max()),
            'max_abs_turnover_difference': float(differences.turnover.max()),
            'relative_tolerance': 1e-10, 'absolute_tolerance': 1e-6}
