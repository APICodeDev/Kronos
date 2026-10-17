"""Mercado público Bitget v3. Intervalos [inicio, fin), UTC; nunca envía órdenes."""
import hashlib
import json
import math
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests

INTERVAL_MS = {'1m': 60_000, '5m': 300_000, '15m': 900_000, '1H': 3_600_000}
BASE_URL = 'https://api.bitget.com/api/v3/market/'
COLUMNS = ['timestamp', 'open', 'high', 'low', 'close', 'volume', 'turnover']


class BitgetDataError(ValueError):
    pass


def utc_ms(value):
    stamp = pd.Timestamp(value)
    if stamp.tzinfo is None:
        raise ValueError('La fecha debe incluir zona horaria (por ejemplo Z).')
    return stamp.value // 1_000_000


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class PublicClient:
    def __init__(self, cache_dir=None, retries=3, pause=0.12, session=None):
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.retries, self.pause = retries, pause
        self.session = session or requests.Session()
        self.next_request = 0
        self.receipts = []

    def get(self, endpoint, params=None, cache=True):
        if endpoint not in {'instruments', 'history-candles', 'history-fund-rate', 'time'}:
            raise ValueError('Endpoint público no permitido.')
        params = params or {}
        key = hashlib.sha256(json.dumps([endpoint, params], sort_keys=True).encode()).hexdigest()
        path = self.cache_dir / (key + '.json') if self.cache_dir else None
        if cache and path and path.exists():
            payload = json.loads(path.read_text(encoding='utf-8'))
        else:
            for attempt in range(self.retries + 1):
                time.sleep(max(0, self.next_request - time.monotonic()))
                self.next_request = time.monotonic() + self.pause
                try:
                    response = self.session.get(BASE_URL + endpoint, params=params, timeout=25)
                    if response.status_code == 429 or response.status_code >= 500:
                        retry_after = response.headers.get('Retry-After', '0')
                        try:
                            delay = min(60, max(float(retry_after), 2 ** attempt))
                        except ValueError:
                            delay = 2 ** attempt
                        if attempt < self.retries:
                            time.sleep(delay)
                            continue
                    response.raise_for_status()
                    payload = response.json()
                    if isinstance(payload, dict) and payload.get('code') in {'429', '40015'} and attempt < self.retries:
                        time.sleep(2 ** attempt)
                        continue
                    break
                except (requests.RequestException, ValueError) as exc:
                    if attempt == self.retries:
                        raise BitgetDataError(f'{endpoint}: {exc}') from exc
                    time.sleep(2 ** attempt)
            self._check(payload)
            if cache and path:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(payload), encoding='utf-8')
        self._check(payload)
        self.receipts.append({'endpoint': endpoint, 'params': params, 'requestTime': payload.get('requestTime'),
                              'cache_file': str(path) if path and cache else None})
        return payload['data']

    @staticmethod
    def _check(payload):
        if not isinstance(payload, dict) or payload.get('code') != '00000' or 'data' not in payload:
            raise BitgetDataError(f'Respuesta API inválida: {str(payload)[:500]}')


def instrument(client, symbol='XRPUSDT', category='USDT-FUTURES'):
    data = client.get('instruments', {'category': category, 'symbol': symbol})
    matches = [x for x in data if x.get('symbol') == symbol and x.get('category') == category]
    if len(matches) != 1:
        raise BitgetDataError('Instrumento no encontrado de forma inequívoca.')
    item = matches[0]
    for key in ['priceMultiplier', 'quantityMultiplier', 'minOrderQty', 'minOrderAmount']:
        if not math.isfinite(float(item[key])) or float(item[key]) <= 0:
            raise BitgetDataError(f'Metadato inválido: {key}')
    return item


def normalize(rows, interval, start_ms, end_ms):
    step = INTERVAL_MS[interval]
    try:
        df = pd.DataFrame(rows, columns=COLUMNS).apply(pd.to_numeric, errors='raise').astype(float)
        if not np.isfinite(df.to_numpy()).all():
            raise ValueError('Valores no finitos')
        if ((df.timestamp % step) != 0).any():
            raise ValueError('Timestamp no alineado')
        prices = df[['open', 'high', 'low', 'close']]
        if (prices <= 0).any().any() or (df[['volume', 'turnover']] < 0).any().any():
            raise ValueError('Precio/volumen inválido')
        if (df.high < prices.max(axis=1)).any() or (df.low > prices.min(axis=1)).any():
            raise ValueError('OHLC incoherente')
        duplicate_count = int(df.timestamp.duplicated().sum())
        for _, group in df[df.timestamp.duplicated(keep=False)].groupby('timestamp'):
            if len(group.drop_duplicates()) > 1:
                raise ValueError('Duplicados contradictorios')
        unordered = int((df.timestamp.diff() < 0).sum())
        # Solo duplicados idénticos: conservar la primera observación.
        df = df.drop_duplicates('timestamp', keep='first').sort_values('timestamp')
        excluded = int(((df.timestamp < start_ms) | (df.timestamp >= end_ms)).sum())
        df = df[(df.timestamp >= start_ms) & (df.timestamp < end_ms)].reset_index(drop=True)
        expected = pd.Index(range(start_ms, end_ms, step))
        missing = expected.difference(df.timestamp)
        gaps = []
        for value in missing:
            value = int(value)
            if gaps and value == gaps[-1]['end_ms']:
                gaps[-1]['end_ms'] += step
                gaps[-1]['bars'] += 1
            else:
                gaps.append({'start_ms': value, 'end_ms': value + step, 'bars': 1})
        df['timestamp'] = pd.to_datetime(df.timestamp, unit='ms', utc=True)
    except (ValueError, TypeError, OverflowError) as exc:
        raise BitgetDataError(f'Datos inválidos: {exc}') from exc
    quality = {'rows': len(df), 'expected_rows': len(expected), 'missing_bars': len(missing), 'gaps': gaps,
               'identical_duplicates_removed': duplicate_count, 'backward_steps_before_sort': unordered,
               'out_of_range_removed': excluded, 'first': str(df.timestamp.min()), 'last': str(df.timestamp.max())}
    return df, quality


def fetch_history(client, symbol, category, interval, start_ms, end_ms=None, now_ms=None):
    step = INTERVAL_MS[interval]
    if now_ms is None:
        now_ms = int(client.get('time', cache=False)['serverTime'])
    end_ms = min(end_ms if end_ms is not None else now_ms, now_ms) // step * step
    start_ms = ((start_ms + step - 1) // step) * step
    if start_ms >= end_ms:
        raise ValueError('Intervalo sin velas cerradas.')
    rows, queries = [], []
    cursor = end_ms
    while cursor > start_ms:
        # Un tick temporal de solape en startTime evita depender de su inclusividad.
        lower = max(start_ms, cursor - 100 * step)
        params = {'category': category, 'symbol': symbol, 'interval': interval,
                  'startTime': str(lower - 1), 'endTime': str(cursor), 'limit': '100', 'type': 'market'}
        page = client.get('history-candles', params)
        queries.append(params)
        if not isinstance(page, list):
            raise BitgetDataError('Página no es una lista.')
        if not page:
            break  # Cobertura faltante queda en el informe; nunca se rellena.
        try:
            stamps = [int(x[0]) for x in page]
        except (ValueError, TypeError, IndexError) as exc:
            raise BitgetDataError('Timestamp de página inválido.') from exc
        if any(stamp % step for stamp in stamps):
            raise BitgetDataError('Timestamp de página no alineado.')
        # La API puede incluir una vela adicional anterior por redondeo.
        if min(stamps) < lower - step or max(stamps) > cursor:
            raise BitgetDataError('API ignoró la ventana temporal solicitada.')
        accepted = [x for x, stamp in zip(page, stamps) if stamp < cursor]
        if not accepted:
            raise BitgetDataError('Paginación sin progreso.')
        rows.extend(accepted)
        cursor = min(int(x[0]) for x in accepted)
    df, quality = normalize(rows, interval, start_ms, end_ms)
    meta = {'provider': 'Bitget', 'symbol': symbol, 'category': category, 'interval': interval,
            'downloaded_at': pd.Timestamp.now(tz='UTC').isoformat(), 'requested_start_ms': start_ms,
            'requested_end_ms': end_ms, 'closed_cutoff_ms': now_ms // step * step,
            'endpoint': BASE_URL + 'history-candles', 'queries': queries, 'quality': quality,
            'deduplication': 'Solo filas idénticas; duplicados contradictorios detienen la descarga.'}
    return df, meta


def save_history(df, meta, directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    name = f"{meta['symbol']}_{meta['interval']}_{meta['requested_start_ms']}_{meta['requested_end_ms']}"
    csv_path = directory / (name + '.csv')
    if any(path.exists() for path in [csv_path, csv_path.with_suffix('.parquet'), csv_path.with_suffix('.metadata.json')]):
        raise FileExistsError(f'No se sobrescribe {csv_path}; elige otro directorio.')
    df.to_csv(csv_path, index=False, float_format='%.12g')
    meta['csv_file'], meta['csv_sha256'] = csv_path.name, sha256(csv_path)
    try:
        import pyarrow  # noqa: F401
    except ImportError:
        pass
    else:
        parquet_path = csv_path.with_suffix('.parquet')
        df.to_parquet(parquet_path, index=False)
        meta['parquet_file'], meta['parquet_sha256'] = parquet_path.name, sha256(parquet_path)
    csv_path.with_suffix('.metadata.json').write_text(json.dumps(meta, indent=2), encoding='utf-8')
    return csv_path
