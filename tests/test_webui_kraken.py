"""Run with python -m unittest discover -s tests -p test_webui_kraken.py."""
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'webui'))
import kraken_data
import app as webui


def candles(count=521):
    return [[1700000000 + i * 3600, '10', '12', '9', '11', '10.5', '3.2', 5] for i in range(count)]


class KrakenTests(unittest.TestCase):
    def setUp(self):
        kraken_data._candles_cache.clear()
        kraken_data._next_request = 0
        kraken_data._cooldown_until = 0
        self.pairs = patch.object(kraken_data, 'available_pairs', return_value=[{'code': 'XBTEUR', 'name': 'BTC/EUR'}])
        self.pairs.start()
        self.addCleanup(self.pairs.stop)

    def fetch(self, values):
        with patch.object(kraken_data, 'public_request', return_value={'XXBTZEUR': values, 'last': 1700000000}):
            return kraken_data.fetch_candles('XBTEUR', 60)

    def test_discards_unfinished_candle_and_preserves_ohlcv(self):
        values = candles()
        values[-1][1] = '999999'  # Current candle must never enter the CSV.
        df = self.fetch(values)
        self.assertEqual(len(df), 520)
        self.assertEqual(list(df.columns), ['timestamps', 'open', 'high', 'low', 'close', 'volume'])
        self.assertEqual(df.iloc[0].to_dict(), {'timestamps': '2023-11-14T22:13:20', 'open': 10,
                                               'high': 12, 'low': 9, 'close': 11, 'volume': 3.2})
        self.assertEqual(df.iloc[-1]['open'], 10)

    def test_rejects_insufficient_history(self):
        with self.assertRaisesRegex(ValueError, '79.*80'):
            self.fetch(candles(80))

    def test_caps_history_to_documented_window_and_discards_current(self):
        values = candles(721)
        values[-1][1] = '999999'
        df = self.fetch(values)
        self.assertEqual(len(df), 719)
        self.assertEqual(df.iloc[-1]['open'], 10)

    def test_rejects_gaps_and_bad_prices(self):
        for mutation in [lambda v: v[12].__setitem__(0, v[11][0]),
                         lambda v: v[12].__setitem__(2, '8'),
                         lambda v: v[12].__setitem__(1, 'NaN'),
                         lambda v: v[12].__setitem__(6, '-1')]:
            with self.subTest(mutation=mutation):
                values = candles(); mutation(values)
                with self.assertRaises(kraken_data.KrakenDataError):
                    self.fetch(values)

    def test_rejects_invalid_parameters_before_ohlc_request(self):
        with patch.object(kraken_data, 'public_request') as request:
            for pair, interval in [('wrong', 60), ('XBTEUR', 2), ('XBTEUR', '60'), ('XBTEUR', True)]:
                with self.assertRaises(ValueError):
                    kraken_data.fetch_candles(pair, interval)
            request.assert_not_called()

    def test_handles_network_and_api_errors(self):
        with patch.object(kraken_data, 'urlopen', side_effect=URLError('unavailable')):
            with self.assertRaises(kraken_data.KrakenDataError):
                kraken_data.public_request('OHLC')
        for payload in [{'error': ['EGeneral:Too many requests']}, [], {'result': []}]:
            with patch.object(kraken_data, 'urlopen', return_value=io.BytesIO(json.dumps(payload).encode())):
                with self.assertRaises(kraken_data.KrakenDataError):
                    kraken_data.public_request('OHLC')

    def test_paces_public_requests(self):
        with patch.object(kraken_data, '_public_request', return_value={}), \
             patch.object(kraken_data.time, 'monotonic', return_value=100), \
             patch.object(kraken_data.time, 'sleep') as sleep:
            kraken_data.public_request('OHLC')
            kraken_data.public_request('AssetPairs')
            sleep.assert_called_once()
            self.assertAlmostEqual(sleep.call_args.args[0], 1.05)

    def test_rate_limit_cooldown_prevents_more_requests(self):
        error = HTTPError('url', 429, 'rate limited', {'Retry-After': '120'}, None)
        with patch.object(kraken_data.time, 'monotonic', return_value=100), \
             patch.object(kraken_data, 'urlopen', side_effect=error) as request:
            with self.assertRaises(kraken_data.KrakenDataError):
                kraken_data.public_request('OHLC')
            self.assertEqual(kraken_data._cooldown_until, 220)
            with self.assertRaises(kraken_data.KrakenDataError):
                kraken_data.public_request('OHLC')
            request.assert_called_once()

    def test_cache_reuses_validated_closed_candles_without_sharing_mutations(self):
        with patch.object(kraken_data, 'public_request', return_value={'XXBTZEUR': candles(), 'last': 0}) as request:
            first = kraken_data.fetch_candles('XBTEUR', 60)
            first.loc[0, 'close'] = 999
            second = kraken_data.fetch_candles('XBTEUR', 60)
            self.assertEqual(second.loc[0, 'close'], 11)
            request.assert_called_once()

    def test_import_save_list_load_download_and_failure_cleanup(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.dict(webui.app.config, {'UPLOAD_FOLDER': folder}):
                client = webui.app.test_client()
                with patch.object(kraken_data, 'public_request', return_value={'XXBTZEUR': candles(), 'last': 0}):
                    imported = client.post('/api/import-kraken', json={'pair': 'XBTEUR', 'interval': 60})
                self.assertEqual(imported.status_code, 200, imported.data)
                path = imported.json['file_path']
                self.assertEqual(imported.json['rows'], 520)
                self.assertTrue(Path(path).is_file())
                self.assertIn(path, [item['path'] for item in client.get('/api/data-files').json])
                loaded = client.post('/api/load-data', json={'file_path': path})
                self.assertEqual(loaded.json['data_info']['rows'], 520)
                download = client.get('/api/data-download', query_string={'file_path': path})
                self.assertEqual(download.status_code, 200)
                self.assertIn('attachment', download.headers['Content-Disposition'])
                download.close()
                self.assertEqual(client.get('/api/data-download', query_string={'file_path': __file__}).status_code, 404)
                with patch.object(webui, 'fetch_candles', side_effect=kraken_data.KrakenDataError('Unavailable')):
                    self.assertEqual(client.post('/api/import-kraken', json={'pair': 'XBTEUR', 'interval': 60}).status_code, 502)
                self.assertEqual(len(list(Path(folder).iterdir())), 1)
                self.assertEqual(client.post('/api/import-kraken', json=[]).status_code, 400)


if __name__ == '__main__':
    unittest.main()
