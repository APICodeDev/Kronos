"""Comprueba CSV con Decimal y liquidaciones con bisect; independiente del diagnóstico."""
import argparse
from bisect import bisect_left, bisect_right
import csv
from datetime import datetime
from decimal import Decimal
import json
from pathlib import Path

from webui.bitget_data import sha256


def verify(report, funding):
    report, funding = Path(report), Path(funding)
    manifest = json.loads((report / 'manifest.json').read_text(encoding='utf-8'))
    for name, digest in manifest['inputs_sha256'].items():
        if sha256(name) != digest:
            raise AssertionError(f'Entrada original modificada: {name}')
    for name, digest in manifest['output_sha256'].items():
        if sha256(report / name) != digest:
            raise AssertionError(f'Informe modificado: {name}')
    for name, digest in manifest['funding_files_sha256'].items():
        if sha256(name) != digest:
            raise AssertionError(f'Funding modificado: {name}')
    with (funding / 'rates.csv').open(encoding='utf-8', newline='') as handle:
        rates = {datetime.fromisoformat(row['timestamp']): Decimal(row['rate']) for row in csv.DictReader(handle)}
    with (funding / 'marks.csv').open(encoding='utf-8', newline='') as handle:
        marks = {datetime.fromisoformat(row['timestamp']): Decimal(row['mark_proxy']) for row in csv.DictReader(handle)}
    times = sorted(rates)
    tolerance = Decimal('0.000001')
    maximum = Decimal(0)
    checked, funded, not_covered = 0, 0, 0

    def compare(number, actual, label):
        nonlocal maximum
        error = abs(number - Decimal(actual))
        maximum = max(maximum, error)
        if error > tolerance:
            raise AssertionError(f'{label}: error {error}')

    for path in sorted(report.glob('diagnostic_*.csv')):
        with path.open(encoding='utf-8', newline='') as handle:
            for row in csv.DictReader(handle):
                q = Decimal(row['quantity'])
                sign = 1 if row['side'] == 'LONG' else -1
                entry, exit_price = Decimal(row['entry_fill']), Decimal(row['exit_fill'])
                reference = sign * q * (Decimal(row['exit_reference']) - Decimal(row['entry_reference']))
                execution_cost = sign * q * (entry - Decimal(row['entry_reference']) + Decimal(row['exit_reference']) - exit_price)
                fees = Decimal(row['entry_fee']) + Decimal(row['exit_fee'])
                net = sign * q * (exit_price - entry) - fees - Decimal(row['other_costs']) - Decimal(row['net_funding_cost'])
                compare(reference, row['reference_pnl'], 'PnL referencia')
                compare(execution_cost, row['execution_cost'], 'Coste ejecución')
                compare(execution_cost, str(Decimal(row['nominal_slippage_cost']) + Decimal(row['tick_rounding_cost'])), 'Slippage y redondeo')
                compare(fees, row['fees'], 'Comisiones')
                compare(net, row['net_pnl'], 'PnL neto')
                if row['funding_covered'] == 'True':
                    opened, closed = datetime.fromisoformat(row['entry_time']), datetime.fromisoformat(row['exit_time'])
                    applicable = times[bisect_right(times, opened):bisect_left(times, closed)]
                    cost = sum((sign * q * marks[time] * rates[time] for time in applicable), Decimal(0))
                    compare(cost, row['funding_cost_estimate'], 'Funding interior')
                    compare(net - cost, row['net_with_estimated_funding'], 'Neto con funding estimado')
                    funded += 1
                else:
                    if row['net_with_estimated_funding']:
                        raise AssertionError('Falta de cobertura tratada como coste cero')
                    not_covered += 1
                checked += 1
    if not checked:
        raise AssertionError('Sin filas verificables')
    result = {'checked_rows': checked, 'checked_funding_rows': funded, 'rows_without_funding_coverage': not_covered,
              'max_absolute_error': str(maximum), 'tolerance': str(tolerance),
              'method': 'Decimal independiente y búsqueda binaria de timestamps estrictamente interiores; eventos y cartera por separado.',
              'verifier_sha256': sha256(__file__)}
    (report / 'financial_verification.json').write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--report', required=True)
    parser.add_argument('--funding', required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.report, args.funding), indent=2))
