"""Contabilidad de un contrato lineal. Slippage incorporado una sola vez al fill."""
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
import math


def grid(value, step, up=False):
    number, quantum = Decimal(str(value)), Decimal(str(step))
    return float((number / quantum).to_integral_value(rounding=ROUND_CEILING if up else ROUND_FLOOR) * quantum)


def execution(price, side, bps, tick, entry=False):
    sign = 1 if side == 'LONG' else -1
    adverse = sign if entry else -sign
    return grid(price * (1 + adverse * bps / 10000), tick, up=adverse > 0)


def position(open_price, side, leverage, cfg, inst):
    tick = float(inst['priceMultiplier'])
    entry = execution(open_price, side, cfg['entry_slippage_bps'], tick, entry=True)
    qty = grid(cfg['margin_usdt'] * leverage / entry, inst['quantityMultiplier'])
    notional = qty * entry
    if qty < float(inst['minOrderQty']) or notional < float(inst['minOrderAmount']):
        raise ValueError('Cantidad inferior al mínimo del contrato.')
    maximum = float(inst.get('maxMarketOrderQty', inst.get('maxOrderQty', 0)))
    if maximum and qty > maximum:
        raise ValueError('Cantidad superior al máximo del contrato.')
    if not float(inst.get('minLeverage', 1)) <= leverage <= float(inst.get('maxLeverage', leverage)):
        raise ValueError('Apalancamiento fuera de límites del contrato.')
    margin = notional / leverage
    target_per_coin = (cfg['target_net_margin_roi'] * margin + cfg['other_costs_usdt']) / qty
    f_in, f_out = cfg['entry_fee_rate'], cfg['exit_fee_rate']
    if side == 'LONG':
        desired_exit = (entry * (1 + f_in) + target_per_coin) / (1 - f_out)
        trigger = grid(desired_exit / (1 - cfg['tp_slippage_bps'] / 10000), tick, up=True)
    else:
        desired_exit = (entry * (1 - f_in) - target_per_coin) / (1 + f_out)
        trigger = grid(desired_exit / (1 + cfg['tp_slippage_bps'] / 10000), tick)
    if trigger <= 0:
        raise ValueError('Objetivo TP no ejecutable.')
    result = {'quantity': qty, 'entry_reference': open_price, 'entry_fill': entry,
              'entry_notional': notional, 'initial_margin_assigned': margin,
              'leverage': leverage, 'tp': trigger}
    # El redondeo adverso del fill también debe permitir el objetivo.
    for _ in range(4):
        fill = execution(trigger, side, cfg['tp_slippage_bps'], tick)
        if pnl(result, side, fill, cfg)['net_margin_roi'] >= cfg['target_net_margin_roi'] - 1e-12:
            result['tp'], result['expected_tp_fill'] = trigger, fill
            return result
        trigger = grid(trigger + (tick if side == 'LONG' else -tick), tick, up=side == 'LONG')
    raise ValueError('No se pudo redondear el TP al objetivo neto.')


def pnl(pos, side, exit_fill, cfg, funding_cost=0):
    quantity, entry = pos['quantity'], pos['entry_fill']
    gross = quantity * (exit_fill - entry) * (1 if side == 'LONG' else -1)
    entry_fee, exit_fee = quantity * entry * cfg['entry_fee_rate'], quantity * exit_fill * cfg['exit_fee_rate']
    net = gross - entry_fee - exit_fee - funding_cost - cfg['other_costs_usdt']
    return {'exit_fill': exit_fill, 'exit_notional': quantity * exit_fill, 'gross_pnl': gross,
            'entry_fee': entry_fee, 'exit_fee': exit_fee, 'slippage_cost': 0,
            'slippage_in_execution_prices': True, 'net_funding_cost': funding_cost,
            'funding_included': False, 'other_costs': cfg['other_costs_usdt'],
            'net_pnl': net, 'net_margin_roi': net / pos['initial_margin_assigned']}


def validate_config(cfg):
    for key in ['margin_usdt', 'initial_equity_usdt', 'target_net_margin_roi']:
        if not math.isfinite(cfg[key]) or cfg[key] <= 0:
            raise ValueError(f'Configuración inválida: {key}')
    for key in ['entry_fee_rate', 'exit_fee_rate']:
        if not math.isfinite(cfg[key]) or not 0 <= cfg[key] < 1:
            raise ValueError(f'Tasa decimal inválida: {key}')
    for key in ['entry_slippage_bps', 'tp_slippage_bps', 'sl_slippage_bps', 'timeout_slippage_bps']:
        if not math.isfinite(cfg[key]) or not 0 <= cfg[key] < 10000:
            raise ValueError(f'Deslizamiento inválido: {key}')
    for key in ['lookback_bars', 'max_holding_bars', 'embargo_bars', 'stop_buffer_ticks']:
        if type(cfg[key]) is not int or cfg[key] < (0 if key == 'embargo_bars' else 1):
            raise ValueError(f'Entero inválido: {key}')
    if cfg['funding'] != 'excluded_provisional' or cfg['timezone'] != 'UTC':
        raise ValueError('Esta versión solo admite UTC y resultados provisionales sin funding.')
    valid_intervals = {'5m': ['15m', '1H'], '1H': []}
    if cfg['entry_interval'] not in valid_intervals or cfg['context_intervals'] != valid_intervals[cfg['entry_interval']]:
        raise ValueError('Usa 5m con contexto 15m/1H, o el experimento 1H sin filtros de contexto.')
    if cfg['other_costs_usdt'] < 0 or not math.isfinite(cfg['other_costs_usdt']):
        raise ValueError('Otros costes inválidos.')
    if len(cfg['split_fractions']) != 3 or any(x <= 0 for x in cfg['split_fractions']) or not math.isclose(sum(cfg['split_fractions']), 1):
        raise ValueError('Particiones inválidas.')
    if not cfg['leverage_scenarios'] or any(not math.isfinite(x) or x < 1 for x in cfg['leverage_scenarios']):
        raise ValueError('Apalancamientos inválidos.')
