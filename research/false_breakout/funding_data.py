"""Tasas públicas y velas mark 1m para diagnóstico; no altera el backtest original."""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from webui.bitget_data import BitgetDataError, PublicClient, normalize, sha256


def normalize_funding(rows, symbol, interval_hours):
    if not rows:
        raise BitgetDataError('No hay tasas de funding.')
    frame = pd.DataFrame(rows)
    if not (frame.symbol == symbol).all():
        raise BitgetDataError('Símbolo de funding incorrecto.')
    frame['rate'] = pd.to_numeric(frame.fundingRate, errors='raise')
    frame['time_ms'] = pd.to_numeric(frame.fundingRateTimestamp, errors='raise')
    if not np.isfinite(frame[['rate', 'time_ms']]).all().all() or (frame.rate.abs() >= 1).any():
        raise BitgetDataError('Funding no finito o fuera de escala decimal.')
    step = interval_hours * 3_600_000
    if (frame.time_ms % step != 0).any():
        raise BitgetDataError('Funding fuera de horario supuesto; no se extrapola.')
    duplicated = int(frame.time_ms.duplicated().sum())
    for _, group in frame.groupby('time_ms'):
        if group.rate.nunique() > 1:
            raise BitgetDataError('Tasas de funding contradictorias.')
    frame = frame.drop_duplicates('time_ms').sort_values('time_ms')
    missing = pd.Index(range(int(frame.time_ms.min()), int(frame.time_ms.max()) + step, step)).difference(frame.time_ms)
    if len(missing):
        raise BitgetDataError(f'Huecos de funding: {list(missing)}')
    frame['timestamp'] = pd.to_datetime(frame.time_ms, unit='ms', utc=True)
    return frame[['timestamp', 'rate']].reset_index(drop=True), duplicated


def fetch_funding(client, symbol, category, interval_hours=8):
    rows, queries = [], []
    previous_oldest = None
    for cursor in range(1, 101):
        params = {'category': category, 'symbol': symbol, 'limit': '100', 'cursor': str(cursor)}
        payload = client.get('history-fund-rate', params)
        page = payload.get('resultList') if isinstance(payload, dict) else None
        if not isinstance(page, list):
            raise BitgetDataError('Página de funding inválida.')
        queries.append(params)
        if not page:
            break
        oldest = min(int(item['fundingRateTimestamp']) for item in page)
        if previous_oldest is not None and oldest >= previous_oldest:
            raise BitgetDataError('Paginación de funding sin progreso.')
        previous_oldest = oldest
        rows.extend(page)
    else:
        raise BitgetDataError('Límite de 100 páginas alcanzado sin fin del histórico.')
    frame, duplicates = normalize_funding(rows, symbol, interval_hours)
    return frame, {'provider': 'Bitget', 'symbol': symbol, 'category': category,
                   'endpoint': 'https://api.bitget.com/api/v3/market/history-fund-rate',
                   'downloaded_at': pd.Timestamp.now(tz='UTC').isoformat(), 'queries': queries,
                   'rows': len(frame), 'first': str(frame.timestamp.min()), 'last': str(frame.timestamp.max()),
                   'interval_hours_assumption_verified': interval_hours, 'missing_settlements': 0,
                   'identical_duplicates_removed': duplicates, 'documented_retention_days': 90}


def fetch_mark(client, timestamp, symbol, category):
    start = pd.Timestamp(timestamp).value // 1_000_000
    params = {'category': category, 'symbol': symbol, 'interval': '1m', 'type': 'mark',
              'startTime': str(start - 1), 'endTime': str(start + 60_000), 'limit': '2'}
    rows = client.get('history-candles', params)
    frame, quality = normalize(rows, '1m', start, start + 60_000)
    if quality['missing_bars'] or len(frame) != 1:
        raise BitgetDataError('Falta la vela mark 1m de liquidación de funding.')
    bar = frame.iloc[0]
    return {'timestamp': bar.timestamp, 'mark_proxy': bar.open, 'mark_low': bar.low, 'mark_high': bar.high}


def download(directory, cfg, events, offline=False):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    meta_path = directory / 'metadata.json'
    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding='utf-8'))
        if meta['symbol'] != cfg['symbol'] or meta['category'] != cfg['category']:
            raise ValueError('Los datos de funding pertenecen a otro contrato.')
        for name, digest in meta['sha256'].items():
            if sha256(directory / name) != digest:
                raise ValueError(f'Hash de funding incorrecto: {name}')
        return meta
    client = PublicClient(directory / 'raw')
    if offline:
        def no_network(*args, **kwargs):
            raise BitgetDataError('Respuesta ausente en caché offline.')
        client.session.get = no_network
    frame, meta = fetch_funding(client, cfg['symbol'], cfg['category'])
    used = set()
    for event in events.itertuples():
        if event.entry_time >= frame.timestamp.min() and event.exit_time <= frame.timestamp.max():
            used.update(frame.loc[(frame.timestamp >= event.entry_time) & (frame.timestamp <= event.exit_time), 'timestamp'])
    marks = []
    for index, timestamp in enumerate(sorted(used)):
        marks.append(fetch_mark(client, timestamp, cfg['symbol'], cfg['category']))
        if (index + 1) % 25 == 0:
            print(f'Funding: {index + 1}/{len(used)} velas mark 1m', flush=True)
    paths = [directory / 'rates.csv', directory / 'marks.csv']
    if any(path.exists() for path in paths):
        raise FileExistsError('Existen CSV de funding sin metadatos; usa otro directorio.')
    frame.to_csv(paths[0], index=False)
    pd.DataFrame(marks, columns=['timestamp', 'mark_proxy', 'mark_low', 'mark_high']).to_csv(paths[1], index=False)
    meta.update(mark_rows=len(marks), mark_price_method='Apertura de vela nativa mark 1m: aproximación, no precio de liquidación exacto.',
                sha256={path.name: sha256(path) for path in paths})
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding='utf-8')
    return meta


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--baseline', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--offline', action='store_true')
    args = parser.parse_args()
    baseline = Path(args.baseline)
    cfg = json.loads((baseline / 'summary.json').read_text(encoding='utf-8'))['config']
    frames = []
    for path in sorted(baseline.glob('events_*x.csv')):
        data = pd.read_csv(path, parse_dates=['entry_time', 'exit_time'])
        frames.append(data[(data.evaluation_status == 'EVALUABLE') & data.net_pnl.notna()])
    print(json.dumps(download(args.output, cfg, pd.concat(frames), args.offline), indent=2))
