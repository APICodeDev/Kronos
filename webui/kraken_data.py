"""Read-only Kraken public market data. No credentials are required."""
import json
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import numpy as np
import pandas as pd

INTERVALS = {1, 5, 15, 30, 60, 240, 1440, 10080, 21600}
_pairs_cache = None
_pairs_expiry = 0
_pairs_lock = threading.Lock()


class KrakenDataError(Exception):
    pass


def public_request(endpoint, params=None):
    url = 'https://api.kraken.com/0/public/' + endpoint
    if params:
        url += '?' + urlencode(params)
    try:
        req = Request(url, headers={'User-Agent': 'Kronos-WebUI/1.0', 'Accept': 'application/json'})
        with urlopen(req, timeout=20) as response:
            payload = json.load(response)
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise KrakenDataError('No se pudo conectar con Kraken. Inténtalo de nuevo en unos momentos.') from exc
    except (ValueError, TypeError) as exc:
        raise KrakenDataError('Kraken devolvió una respuesta no válida.') from exc
    if not isinstance(payload, dict) or not isinstance(payload.get('result'), dict):
        errors = payload.get('error', []) if isinstance(payload, dict) else []
        raise KrakenDataError('Kraken: ' + ', '.join(map(str, errors)) if errors else 'Kraken devolvió una respuesta no válida.')
    if payload.get('error'):
        raise KrakenDataError('Kraken: ' + ', '.join(map(str, payload['error'])))
    return payload['result']


def available_pairs():
    global _pairs_cache, _pairs_expiry
    with _pairs_lock:
        if _pairs_cache is not None and time.monotonic() < _pairs_expiry:
            return _pairs_cache
        result = public_request('AssetPairs', {'aclass_base': 'currency'})
        pairs = []
        for key, item in result.items():
            if not isinstance(item, dict) or item.get('status') != 'online' or not item.get('wsname'):
                continue
            if key.endswith('.d') or item.get('aclass_base', 'currency') != 'currency':
                continue
            code = item.get('altname', key)
            display = '/'.join('BTC' if part == 'XBT' else part for part in item['wsname'].split('/'))
            pairs.append({'code': code, 'name': display})
        if not pairs:
            raise KrakenDataError('Kraken no devolvió pares disponibles.')
        _pairs_cache = sorted(pairs, key=lambda pair: pair['name'])
        _pairs_expiry = time.monotonic() + 900
        return _pairs_cache


def fetch_candles(pair, interval):
    if not isinstance(pair, str) or pair not in {p['code'] for p in available_pairs()}:
        raise ValueError('Selecciona un par disponible de Kraken.')
    if type(interval) is not int or interval not in INTERVALS:
        raise ValueError('Selecciona un intervalo válido de Kraken.')
    result = public_request('OHLC', {'pair': pair, 'interval': interval})
    series = [value for key, value in result.items() if key != 'last' and isinstance(value, list)]
    if len(series) != 1 or not series[0]:
        raise KrakenDataError('Kraken no devolvió velas para este par.')
    # Kraken always includes the unfinished candle as the final entry.
    completed = series[0][:-1]
    if len(completed) < 80:
        raise ValueError(f'Kraken solo ofrece {len(completed)} velas cerradas para este par e intervalo. La predicción futura necesita 80; elige otro par o intervalo.')
    try:
        df = pd.DataFrame(completed, columns=['time', 'open', 'high', 'low', 'close', 'vwap', 'volume', 'count'])
        numeric = ['time', 'open', 'high', 'low', 'close', 'volume']
        df[numeric] = df[numeric].apply(pd.to_numeric, errors='raise')
        if not np.isfinite(df[numeric].to_numpy()).all() or (df['volume'] < 0).any():
            raise ValueError('Invalid numbers')
        prices = df[['open', 'high', 'low', 'close']]
        if (prices <= 0).any().any() or (df['high'] < prices.max(axis=1)).any() or (df['low'] > prices.min(axis=1)).any():
            raise ValueError('Invalid OHLC')
        if not (df['time'].diff().dropna() == interval * 60).all():
            raise ValueError('Missing, duplicated or unordered candles')
        df['timestamps'] = pd.to_datetime(df['time'], unit='s', utc=True).dt.strftime('%Y-%m-%dT%H:%M:%S')
    except (ValueError, TypeError, OverflowError) as exc:
        raise KrakenDataError('Las velas de Kraken contienen datos inválidos o huecos temporales; no se han rellenado ni guardado.') from exc
    return df[['timestamps', 'open', 'high', 'low', 'close', 'volume']]
