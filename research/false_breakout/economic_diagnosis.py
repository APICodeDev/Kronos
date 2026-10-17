"""Atribución sobre trayectorias congeladas. No optimiza ni recalcula señales/TP."""
import argparse
import importlib.metadata
import json
import platform
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

from webui.bitget_data import sha256
from .costs import execution

SEED = 20261017
BOOTSTRAP_REPEATS = 5000
SOURCES = {
    'funding_api': 'https://www.bitget.com/docs/catalog/market/derivatives',
    'funding_calculation': 'https://www.bitget.com/en-CA/support/articles/12560603817108',
    'funding_timing': 'https://www.bitget.com/support/articles/12560603808908',
    'published_fees': 'https://www.bitget.com/support/articles/12560603892733',
}


def attribute_costs(events, cfg, tick):
    data = events.copy()
    sign = data.side.map({'LONG': 1, 'SHORT': -1})
    if sign.isna().any() or data.net_pnl.isna().any():
        raise ValueError('Solo se atribuyen operaciones ejecutadas LONG/SHORT.')
    q = data.quantity
    data['reference_pnl'] = sign * q * (data.exit_reference - data.entry_reference)
    data['entry_execution_cost'] = sign * q * (data.entry_fill - data.entry_reference)
    data['exit_execution_cost'] = sign * q * (data.exit_reference - data.exit_fill)
    exit_bps = np.select([data.label == 'TP_FIRST', data.label == 'TIMEOUT'],
                         [cfg['tp_slippage_bps'], cfg['timeout_slippage_bps']], default=cfg['sl_slippage_bps'])
    data['nominal_slippage_cost'] = q * (data.entry_reference * cfg['entry_slippage_bps'] + data.exit_reference * exit_bps) / 10000
    data['execution_cost'] = data.entry_execution_cost + data.exit_execution_cost
    data['tick_rounding_cost'] = data.execution_cost - data.nominal_slippage_cost
    data['fees'] = data.entry_fee + data.exit_fee
    reconstructed = data.reference_pnl - data.execution_cost - data.fees - data.net_funding_cost - data.other_costs
    if not np.allclose(reconstructed, data.net_pnl, rtol=0, atol=1e-7):
        raise AssertionError('La atribución no concilia con el PnL original.')
    if (data.tick_rounding_cost < -1e-7).any() or (data.execution_cost < -1e-7).any():
        raise AssertionError('Costes de ejecución adversa negativos.')
    data['reconciliation_error'] = reconstructed - data.net_pnl
    data['target_net_margin_roi'] = cfg['target_net_margin_roi']
    stop_fills = np.array([execution(row.stop, row.side, cfg['sl_slippage_bps'], tick) for row in data.itertuples()])
    data['planned_sl_net_loss'] = -(sign * q * (stop_fills - data.entry_fill) - data.entry_fee - q * stop_fills * cfg['exit_fee_rate'] - data.other_costs)
    data['planned_tp_net_gain'] = sign * q * (data.expected_tp_fill - data.entry_fill) - data.entry_fee - q * data.expected_tp_fill * cfg['exit_fee_rate'] - data.other_costs
    if (data.planned_sl_net_loss <= 0).any() or (data.planned_tp_net_gain <= 0).any():
        raise AssertionError('Gestión inicial con riesgo/recompensa inválidos.')
    data['stop_distance_bps'] = sign * (data.entry_fill - data.stop) / data.entry_fill * 10000
    data['tp_distance_bps'] = sign * (data.tp - data.entry_fill) / data.entry_fill * 10000
    data['planned_reward_risk'] = data.planned_tp_net_gain / data.planned_sl_net_loss
    data['planned_break_even_win_rate'] = data.planned_sl_net_loss / (data.planned_sl_net_loss + data.planned_tp_net_gain)
    data['optimistic_ambiguous_pnl'] = np.where(data.label == 'AMBIGUOUS', data.planned_tp_net_gain, data.net_pnl)
    return data


def overlay_funding(events, rates, marks):
    """Estimación de coste: LONG positivo paga; solo instantes interiores en punto central."""
    if rates.timestamp.duplicated().any() or marks.timestamp.duplicated().any():
        raise ValueError('Funding/mark duplicados.')
    if rates.empty:
        raise ValueError('No hay cobertura de funding.')
    rates = rates.sort_values('timestamp')
    joined = rates.merge(marks, on='timestamp', how='left', validate='one_to_one')
    if ((marks.mark_low > marks.mark_proxy) | (marks.mark_proxy > marks.mark_high) | (marks.mark_low <= 0)).any():
        raise ValueError('Precios mark incoherentes.')
    records = []
    for event in events.itertuples():
        covered = event.entry_time >= rates.timestamp.min() and event.exit_time <= rates.timestamp.max()
        result = {'funding_covered': covered, 'funding_cost_estimate': np.nan,
                  'funding_cost_min_sensitivity': np.nan, 'funding_cost_max_sensitivity': np.nan,
                  'funding_interior_settlements': 0, 'funding_boundary_settlements': 0}
        if covered:
            applicable = joined[(joined.timestamp >= event.entry_time) & (joined.timestamp <= event.exit_time)]
            if applicable[['mark_proxy', 'mark_low', 'mark_high']].isna().any().any():
                raise ValueError('Falta mark para una operación marcada con cobertura.')
            sign = 1 if event.side == 'LONG' else -1
            factor = sign * event.quantity * applicable.rate
            low = np.minimum(factor * applicable.mark_low, factor * applicable.mark_high)
            high = np.maximum(factor * applicable.mark_low, factor * applicable.mark_high)
            interior = (applicable.timestamp > event.entry_time) & (applicable.timestamp < event.exit_time)
            boundary = ~interior
            result.update(funding_cost_estimate=float((factor * applicable.mark_proxy)[interior].sum()),
                          funding_cost_min_sensitivity=float(low[interior].sum() + np.minimum(low[boundary], 0).sum()),
                          funding_cost_max_sensitivity=float(high[interior].sum() + np.maximum(high[boundary], 0).sum()),
                          funding_interior_settlements=int(interior.sum()), funding_boundary_settlements=int(boundary.sum()))
        records.append(result)
    result = events.copy()
    for key in records[0] if records else []:
        result[key] = [row[key] for row in records]
    if not records:
        return result
    result['net_with_estimated_funding'] = result.net_pnl - result.funding_cost_estimate
    result['net_funding_sensitivity_low'] = result.net_pnl - result.funding_cost_max_sensitivity
    result['net_funding_sensitivity_high'] = result.net_pnl - result.funding_cost_min_sensitivity
    return result


def clustered_ci(frame, columns, repeats=BOOTSTRAP_REPEATS, seed=SEED):
    # Semanas UTC lunes-domingo. Se remuestrea la semana entera, no eventos solapados.
    week = frame.entry_time.dt.tz_localize(None).dt.to_period('W-SUN').astype(str)
    work = frame[columns].copy()
    work['week'] = week
    totals = work.groupby('week')[columns].sum()
    sizes = work.groupby('week').size().reindex(totals.index).to_numpy()
    if len(totals) < 2:
        return {'weeks': len(totals), 'intervals': {column: None for column in columns}}
    rng = np.random.default_rng(seed)
    indices = rng.integers(0, len(totals), size=(repeats, len(totals)))
    draws = totals.to_numpy()[indices].sum(axis=1) / sizes[indices].sum(axis=1)[:, None]
    return {'weeks': len(totals), 'intervals': {column: [float(x) for x in np.quantile(draws[:, i], [.025, .975])]
                                              for i, column in enumerate(columns)}}


def distribution(series):
    return {str(q): float(x) for q, x in series.quantile([0, .1, .5, .9, 1]).items()}


def stats(frame):
    if frame.empty:
        return {'n': 0}
    v = frame.net_pnl
    winners, losers = v[v > 0], v[v < 0]
    gain = float(winners.mean()) if len(winners) else None
    loss = float(-losers.mean()) if len(losers) else None
    tp, sl = frame[frame.label == 'TP_FIRST'], frame[frame.label == 'SL_FIRST']
    result = {'n': len(frame), 'mean_reference_pnl': float(frame.reference_pnl.mean()),
              'mean_nominal_slippage': float(frame.nominal_slippage_cost.mean()),
              'mean_tick_rounding': float(frame.tick_rounding_cost.mean()),
              'mean_execution_cost': float(frame.execution_cost.mean()), 'mean_fees': float(frame.fees.mean()),
              'mean_gross_after_execution': float(frame.gross_pnl.mean()), 'mean_net': float(v.mean()),
              'sum_net': float(v.sum()), 'positive_rate': float((v > 0).mean()),
              'positive_rate_nonzero': len(winners) / (len(winners) + len(losers)) if len(winners) + len(losers) else None,
              'mean_winner': gain, 'mean_loser_abs': loss,
              'break_even_positive_rate_nonzero': loss / (gain + loss) if gain is not None and loss is not None else None,
              'tp_rate_all': float((frame.label == 'TP_FIRST').mean()),
              'tp_rate_resolved_tp_sl': len(tp) / (len(tp) + len(sl)) if len(tp) + len(sl) else None,
              'break_even_tp_rate_resolved': float(-sl.net_pnl.mean() / (tp.net_pnl.mean() - sl.net_pnl.mean())) if len(tp) and len(sl) else None,
              'label_counts': frame.label.value_counts().to_dict(),
              'optimistic_ambiguous_mean_net': float(frame.optimistic_ambiguous_pnl.mean()),
              'planned_sl_net_loss': distribution(frame.planned_sl_net_loss),
              'planned_reward_risk': distribution(frame.planned_reward_risk),
              'planned_break_even_win_rate': distribution(frame.planned_break_even_win_rate),
              'stop_distance_bps': distribution(frame.stop_distance_bps), 'tp_distance_bps': distribution(frame.tp_distance_bps),
              'max_reconciliation_error': float(frame.reconciliation_error.abs().max())}
    total_notional = float((frame.entry_notional + frame.exit_notional).sum())
    result['break_even_equal_fee_bps_current_execution'] = float(frame.gross_pnl.sum()) / total_notional * 10000
    result['break_even_equal_fee_bps_zero_execution_cost'] = float(frame.reference_pnl.sum()) / total_notional * 10000
    result['frozen_path_cost_sensitivities'] = {
        'zero_fees_current_execution': float(frame.gross_pnl.mean()),
        'zero_execution_cost_current_fees': float((frame.reference_pnl - frame.fees).mean()),
        'zero_fees_zero_execution_cost': float(frame.reference_pnl.mean()),
        '2bp_each_current_execution': float((frame.gross_pnl - .0002 * (frame.entry_notional + frame.exit_notional)).mean()),
        'maker_entry_2bp_taker_exit_6bp_current_execution': float((frame.gross_pnl - .0002 * frame.entry_notional - .0006 * frame.exit_notional).mean())}
    funded = frame[frame.funding_covered] if 'funding_covered' in frame else frame.iloc[:0]
    result['funding'] = {'covered': len(funded), 'coverage_fraction': len(funded) / len(frame)}
    if len(funded):
        result['funding'].update(mean_cost_estimate=float(funded.funding_cost_estimate.mean()),
                                 mean_net_same_events_without_funding=float(funded.net_pnl.mean()),
                                 mean_net_with_estimate=float(funded.net_with_estimated_funding.mean()),
                                 mean_net_sensitivity_low=float(funded.net_funding_sensitivity_low.mean()),
                                 mean_net_sensitivity_high=float(funded.net_funding_sensitivity_high.mean()),
                                 interior_settlements=int(funded.funding_interior_settlements.sum()),
                                 boundary_settlements=int(funded.funding_boundary_settlements.sum()),
                                 tp_below_target_after_estimate=int(((funded.label == 'TP_FIRST') &
                                     (funded.net_with_estimated_funding / funded.initial_margin_assigned < funded.target_net_margin_roi - 1e-10)).sum()))
    return result


def format_number(number, digits=4):
    return '—' if number is None else f'{number:.{digits}f}'


def write_report(output, summary):
    lines = ['# Diagnóstico económico de la línea base', '',
             '**Conclusión: detener esta regla como candidata operativa. Conservar la infraestructura y estudiar una sola hipótesis nueva si se decide continuar. La evidencia actual no justifica entrenar IA.**', '',
             'Se analizan exactamente las entradas, cantidades, barreras y salidas ya guardadas. No se cambian señales, filtros, parámetros, capital ni particiones. Test ya estaba observado: esto es diagnóstico retrospectivo, sin nueva validación independiente.', '',
             '## Dónde se pierde el dinero: test por evento', '',
             '| Escenario | N | PnL referencia | Slippage nominal | Redondeo tick | Comisiones | PnL neto sin funding |',
             '|---|---:|---:|---:|---:|---:|---:|']
    for lev, scenario in summary['scenarios'].items():
        s = scenario['events']['test']['ALL']
        lines.append(f"| {lev}x | {s['n']} | {s['mean_reference_pnl']:.4f} | {s['mean_nominal_slippage']:.4f} | {s['mean_tick_rounding']:.4f} | {s['mean_fees']:.4f} | {s['mean_net']:.4f} |")
    lines += ['', 'Importes medios en USDT por operación, con margen efectivo cercano a 1.000 USDT. Identidad comprobada por fila: referencia − slippage nominal − redondeo − comisiones − otros costes = PnL original. El slippage no se descuenta dos veces.', '',
              'El PnL de referencia elimina aritméticamente los costes de los fills, manteniendo salidas, cantidad y TP originales. Es una descomposición contable, no el resultado de una estrategia sin costes: recalcular sus TP podría cambiar la trayectoria y las etiquetas.', '',
              '## ¿Bastaría reducir comisiones?', '',
              '| Escenario test | Comisión cero, ejecución actual | Ejecución ideal, comisiones actuales | 2 bp por lado, ejecución actual | Comisión máxima por lado con ejecución actual (bp) |',
              '|---|---:|---:|---:|---:|']
    for lev, scenario in summary['scenarios'].items():
        s = scenario['events']['test']['ALL']
        c = s['frozen_path_cost_sensitivities']
        lines.append(f"| {lev}x | {c['zero_fees_current_execution']:.4f} | {c['zero_execution_cost_current_fees']:.4f} | {c['2bp_each_current_execution']:.4f} | {s['break_even_equal_fee_bps_current_execution']:.4f} |")
    lines += ['', 'Una comisión de equilibrio negativa significa que ni una tarifa cero bastaría: haría falta un rebate para esas ejecuciones. Los escenarios de 2 bp son sensibilidad aritmética; no se supone que órdenes de mercado puedan ejecutarse como maker ni que exista esa tarifa efectiva de cuenta.', '',
              '## Acierto y tamaño de pérdidas', '',
              '| Escenario test | Operaciones positivas | Acierto de equilibrio | Ganador medio USDT | Perdedor medio USDT | SL previsto mediano USDT | Recompensa/riesgo mediana |',
              '|---|---:|---:|---:|---:|---:|---:|']
    for lev, scenario in summary['scenarios'].items():
        s = scenario['events']['test']['ALL']
        lines.append(f"| {lev}x | {s['positive_rate_nonzero']:.2%} | {s['break_even_positive_rate_nonzero']:.2%} | {s['mean_winner']:.4f} | {s['mean_loser_abs']:.4f} | {s['planned_sl_net_loss']['0.5']:.4f} | {s['planned_reward_risk']['0.5']:.4f} |")
    lines += ['', 'Acierto de equilibrio = pérdida media / (ganancia media + pérdida media), condicionado a PnL distinto de cero y manteniendo la distribución de pagos observada. No es una probabilidad aprendida ni un umbral de filtro. Incluye TIMEOUT positivos y negativos; no equivale a tasa TP. El JSON separa además TP/SL resueltos y conserva las contribuciones de timeout/ambiguos.', '',
              'El mayor apalancamiento acerca el TP al precio y aumenta su frecuencia, pero multiplica el nominal, las comisiones y el daño de un SL mientras el beneficio objetivo permanece aproximadamente en 10 USDT. Aumentar el acierto por sí solo no arregla esa relación.', '',
              '## LONG y SHORT en test', '',
              '| Escenario | Dirección | N | Referencia media | Ejecución media | Comisiones medias | Neto medio |',
              '|---|---|---:|---:|---:|---:|---:|']
    for lev, scenario in summary['scenarios'].items():
        for side in ['LONG', 'SHORT']:
            s = scenario['events']['test'][side]
            lines.append(f"| {lev}x | {side} | {s['n']} | {s['mean_reference_pnl']:.4f} | {s['mean_execution_cost']:.4f} | {s['mean_fees']:.4f} | {s['mean_net']:.4f} |")
    lines += ['', '## Incertidumbre y ambigüedades', '',
              'Bootstrap descriptivo por semanas UTC completas agrupadas (lunes-domingo), 5.000 remuestreos, semilla 20261017. Mantiene juntos eventos de una misma semana para evitar tratarlos como observaciones independientes. Los intervalos percentiles no garantizan estacionariedad ni generalización y proceden de pocas semanas de test.', '',
              '| Escenario test | Semanas | IC 95 % media referencia | IC 95 % media neta | Media neta si todos los ambiguos de ejecución fueran TP |',
              '|---|---:|---|---|---:|']
    for lev, scenario in summary['scenarios'].items():
        ci = scenario['test_weekly_bootstrap']
        intervals = ci['intervals']
        def text(column):
            return ' / '.join(format_number(x) for x in intervals[column])
        lines.append(f"| {lev}x | {ci['weeks']} | {text('reference_pnl')} | {text('net_pnl')} | {scenario['events']['test']['ALL']['optimistic_ambiguous_mean_net']:.4f} |")
    lines += ['', 'El último escenario es solo una cota optimista de diagnóstico; las etiquetas y pérdidas conservadoras originales se conservan.', '',
              '## Funding público: cobertura y estimación', '',
              f"Se descargaron {summary['funding_metadata']['rows']} tasas entre {summary['funding_metadata']['first']} y {summary['funding_metadata']['last']}; no hay huecos dentro del horario observado de 8 h. La retención pública documentada es de 90 días. No se extrapola al año anterior.", '',
              '| Escenario test | Cobertura | Coste funding medio estimado | Neto con estimación | Sensibilidad favorable / desfavorable | Casos con entrada/salida en liquidación | TP originales bajo +1 % tras estimación |',
              '|---|---:|---:|---:|---|---:|---:|']
    for lev, scenario in summary['scenarios'].items():
        s = scenario['events']['test']['ALL']['funding']
        lines.append(f"| {lev}x | {s['covered']} | {s.get('mean_cost_estimate', 0):.6f} | {s.get('mean_net_with_estimate', 0):.4f} | {s.get('mean_net_sensitivity_high', 0):.4f} / {s.get('mean_net_sensitivity_low', 0):.4f} | {s.get('boundary_settlements', 0)} | {s.get('tp_below_target_after_estimate', 0)} |")
    lines += ['', 'Coste = signo LONG/SHORT × cantidad × mark aproximado × tasa histórica. El mark usado es la apertura de la vela nativa mark de 1m del instante de liquidación, no una cotización exacta. La sensibilidad usa low/high del minuto y permite cobrar/no cobrar funding si entrada o salida coincide con el instante. Esa banda no es un intervalo de confianza ni una cota garantizada de ejecución real.',
              'El punto central incluye únicamente instantes estrictamente interiores a la posición. Se considera posible incertidumbre al entrar/salir en el segundo de liquidación. El intercambio advierte de retardos al cobrar funding. No se reconstruyen esos retardos ni liquidaciones. El TP original se calculó sin funding: se cuentan los TP que ya no llegarían al objetivo tras este coste, sin reetiquetar el original.',
              'Esto es una revaloración de operaciones congeladas, no una nueva cartera financiada: no cambia el capital disponible ni su secuencia. El resultado anual sigue sin funding completo y la estimación reciente no merece llamarse neto completo.', '',
              '## Decisión y siguientes pasos', '',
              '1. Cerrar esta versión del falso rompimiento como regla operativa. Ambas direcciones y todos los apalancamientos pierden con los supuestos fijados; los costes consumen el pequeño margen de referencia y reducir solo las tarifas no lo recupera.',
              '2. Conservar el descargador, la validación causal y la contabilidad. El proyecto como banco de pruebas sí es reutilizable; este resultado no justifica dedicar recursos a entrenar un modelo ni operar en real.',
              '3. Si se continúa investigando, escribir primero una única hipótesis nueva con fundamento de mercado, entradas/salidas y costes explícitos, y un control sencillo de comparación. Usar el histórico observado solo como exploración y registrar todas las variantes.',
              '4. Recoger datos posteriores al intervalo ya observado y reservar un test cronológico que no se mire durante el diseño, con purga/embargo. Confirmar tarifas efectivas y medir ejecución en simulación antes de interpretar como real un margen pequeño.',
              '5. Exigir expectativa positiva tras costes, suficiente muestra en test (100 eventos es solo un mínimo, no garantía), estabilidad temporal y comparación con el control. Si falla, detener esa hipótesis. Solo una regla que supere esa fase permitiría plantear un clasificador pequeño con otro test intacto.', '',
              '## Reproducibilidad y límites', '',
              'Se preserva el baseline original. `manifest.json` registra hashes de entradas, scripts, dependencias, tasas y mark; los CSV de diagnóstico desglosan cada operación. `summary.json` separa eventos/cartera, dirección, partición y mes. Las sumas por evento no son una curva de capital. La cartera de 3x/5x/10x ya dejó de operar antes de test; no hay operaciones de cartera finales que revalorar allí.',
              'Las tarifas efectivas de cuenta no pueden deducirse de datos públicos. No se ha pedido ni usado una clave privada. Tampoco se han añadido filtros, seleccionado escenarios favorables, entrenado IA, enviado órdenes, hecho commits ni push.', '',
              'Fuentes oficiales consultadas el 17-10-2026: ' + ', '.join(f'[{name}]({url})' for name, url in SOURCES.items()) + '.']
    (output / 'REPORT.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--baseline', required=True)
    parser.add_argument('--funding', required=True)
    parser.add_argument('--instrument', default='webui/uploads/bitget_baseline_20261017/instrument.json')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    baseline, funding_dir, output = Path(args.baseline), Path(args.funding), Path(args.output)
    if output.exists():
        raise FileExistsError('El diagnóstico ya existe; usa otro directorio.')
    baseline_manifest = json.loads((baseline / 'manifest.json').read_text(encoding='utf-8'))
    cfg = json.loads((baseline / 'summary.json').read_text(encoding='utf-8'))['config']
    instrument_path = Path(args.instrument)
    inst = json.loads(instrument_path.read_text(encoding='utf-8'))
    if sha256(instrument_path) != baseline_manifest['instrument_sha256']:
        raise ValueError('Los metadatos del contrato no coinciden con el baseline.')
    funding_meta = json.loads((funding_dir / 'metadata.json').read_text(encoding='utf-8'))
    for name, digest in funding_meta['sha256'].items():
        if sha256(funding_dir / name) != digest:
            raise ValueError('Hash de funding incorrecto.')
    rates = pd.read_csv(funding_dir / 'rates.csv', parse_dates=['timestamp'])
    marks = pd.read_csv(funding_dir / 'marks.csv', parse_dates=['timestamp'])
    output.mkdir(parents=True)
    summary = {'baseline': str(baseline), 'config': cfg, 'funding_metadata': funding_meta,
               'bootstrap': {'seed': SEED, 'repeats': BOOTSTRAP_REPEATS, 'cluster': 'UTC Monday-Sunday'},
               'scenarios': {}, 'sources': SOURCES}
    inputs = {str(baseline / name): sha256(baseline / name) for name in ['manifest.json', 'summary.json']}
    inputs[str(instrument_path)] = sha256(instrument_path)
    monthly_rows = []
    for leverage in cfg['leverage_scenarios']:
        scenario = {'events': {}, 'portfolio': {}}
        for book, prefix in [('events', 'events'), ('portfolio', 'portfolio')]:
            path = baseline / f'{prefix}_{leverage}x.csv'
            if sha256(path) != baseline_manifest['artifact_sha256'][path.name]:
                raise ValueError('El CSV original ha cambiado.')
            inputs[str(path)] = sha256(path)
            frame = pd.read_csv(path, parse_dates=['entry_time', 'exit_time'])
            frame = frame[(frame.evaluation_status == 'EVALUABLE') & frame.net_pnl.notna()].copy()
            frame = attribute_costs(frame, cfg, float(inst['priceMultiplier']))
            frame = overlay_funding(frame, rates, marks)
            frame.to_csv(output / f'diagnostic_{book}_{leverage}x.csv', index=False)
            for split in ['ALL', 'discovery', 'validation', 'test']:
                part = frame if split == 'ALL' else frame[frame.split == split]
                scenario[book][split] = {side: stats(part if side == 'ALL' else part[part.side == side]) for side in ['ALL', 'LONG', 'SHORT']}
            for month, group in frame.groupby(pd.Grouper(key='entry_time', freq='MS')):
                if group.empty:
                    continue
                for side in ['ALL', 'LONG', 'SHORT']:
                    values = stats(group if side == 'ALL' else group[group.side == side])
                    monthly_rows.append({'leverage': leverage, 'book': book, 'month': str(month), 'side': side,
                                         **{key: value for key, value in values.items() if not isinstance(value, (dict, list))}})
            if book == 'events':
                scenario['test_weekly_bootstrap'] = clustered_ci(frame[frame.split == 'test'], ['reference_pnl', 'net_pnl'])
        summary['scenarios'][str(leverage)] = scenario
        print(f'Diagnóstico {leverage}x completado.', flush=True)
    pd.DataFrame(monthly_rows).to_csv(output / 'monthly.csv', index=False)
    (output / 'summary.json').write_text(json.dumps(summary, indent=2, ensure_ascii=False, allow_nan=False), encoding='utf-8')
    write_report(output, summary)
    source_paths = [Path('research/false_breakout') / name for name in ['economic_diagnosis.py', 'funding_data.py', 'costs.py']]
    source_paths += [Path('webui/bitget_data.py'), Path('tests/test_economic_diagnosis.py')]
    manifest = {'git_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
                'python': platform.python_version(),
                'dependencies': {name: importlib.metadata.version(name) for name in ['numpy', 'pandas', 'requests']},
                'inputs_sha256': inputs, 'source_sha256': {str(path): sha256(path) for path in source_paths},
                'funding_files_sha256': {str(funding_dir / name): sha256(funding_dir / name) for name in ['rates.csv', 'marks.csv', 'metadata.json']},
                'raw_funding_sha256': {path.name: sha256(path) for path in sorted((funding_dir / 'raw').glob('*.json'))},
                'output_sha256': {path.name: sha256(path) for path in output.glob('*') if path.is_file()}}
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    command = f'python -m research.false_breakout.economic_diagnosis --baseline {baseline.as_posix()} --funding {funding_dir.as_posix()} --instrument {instrument_path.as_posix()} --output NUEVO_DIRECTORIO'
    (output / 'command.txt').write_text(command + '\n', encoding='utf-8')
    print(f'Informe: {output / "REPORT.md"}', flush=True)


if __name__ == '__main__':
    main()
