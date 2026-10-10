"""Regression checks for future forecasts and the explicitly selected backtest."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'webui'))
import app as webui


class ForecastTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = str(Path(self.folder.name) / 'market.csv')
        self.df = pd.DataFrame({'timestamps': pd.date_range('2026-08-19 17:00', periods=1200, freq='h'),
                                'open': 10., 'high': 12., 'low': 9., 'close': 11., 'volume': 5.})
        self.df.to_csv(self.path, index=False)
        self.predictor = Mock()
        self.predictor.max_context = 2048
        self.predictor.predict.return_value = pd.DataFrame({'open': [10.] * 120, 'high': [12.] * 120,
                                                            'low': [9.] * 120, 'close': [11.] * 120})
        for key, value in [('MODEL_AVAILABLE', True), ('predictor', self.predictor),
                           ('save_prediction_results', Mock())]:
            scope = patch.object(webui, key, value); scope.start(); self.addCleanup(scope.stop)
        self.client = webui.app.test_client()

    def predict(self, **kwargs):
        return self.client.post('/api/predict', json={'file_path': self.path, **kwargs})

    def test_default_and_stale_slider_requests_forecast_from_latest_719(self):
        for params in [{}, {'start_index': 200}, {'mode': 'forecast', 'lookback': 719, 'start_index': 200}]:
            with self.subTest(params=params):
                response = self.predict(**params)
                self.assertEqual(response.status_code, 200, response.data)
                result = response.json
                self.assertEqual(result['mode'], 'forecast')
                self.assertEqual(result['context_end'], '2026-10-08T16:00:00')
                self.assertEqual(result['prediction_start'], '2026-10-08T17:00:00')
                self.assertEqual(result['prediction_end'], '2026-10-13T16:00:00')
                self.assertFalse(result['has_comparison'])
                self.assertEqual(result['actual_data'], [])
                inputs = self.predictor.predict.call_args.kwargs
                self.assertEqual(len(inputs['df']), 719)
                self.assertEqual(inputs['x_timestamp'].iloc[0], self.df.timestamps.iloc[-719])
                self.assertEqual(inputs['x_timestamp'].iloc[-1], self.df.timestamps.iloc[-1])
                self.assertGreater(inputs['y_timestamp'].min(), inputs['x_timestamp'].max())
                chart = json.loads(result['chart'])
                self.assertEqual([len(t['open']) for t in chart['data']], [719, 120])
                self.assertIn('Predicción futura', chart['layout']['title']['text'])
                self.assertEqual(chart['layout']['shapes'][0]['x0'], result['prediction_start'])

    def test_history_requires_explicit_mode(self):
        result = self.predict(mode='backtest', start_index=361).json
        self.assertEqual(result['mode'], 'backtest')
        self.assertEqual(result['prediction_start'], '2026-10-03T17:00:00')
        self.assertTrue(result['has_comparison'])
        self.assertEqual(len(result['actual_data']), 120)
        self.assertEqual(self.predict(mode='backtest').status_code, 400)
        self.assertEqual(self.predict(mode='unknown').status_code, 400)

    def test_short_history_adapts_until_the_minimum(self):
        self.df.tail(80).to_csv(self.path, index=False)
        self.assertEqual(self.predict().status_code, 200)
        self.assertEqual(self.predict(mode='backtest', start_index=0).status_code, 400)
        self.df.tail(79).to_csv(self.path, index=False)
        self.assertEqual(self.predict().status_code, 400)

    def test_rejects_short_sample_and_model_truncation(self):
        self.assertEqual(self.predict(lookback=79).status_code, 400)
        self.predictor.max_context = 512
        result = self.predict(lookback=719)
        self.assertEqual(result.status_code, 400)
        self.assertIn('Kronos-mini', result.json['error'])
        self.predictor.predict.assert_not_called()
        self.assertEqual(self.predict().status_code, 200)
        self.assertEqual(len(self.predictor.predict.call_args.kwargs['df']), 512)

    def test_rejects_gaps_in_hourly_sample(self):
        self.df.drop(index=900).to_csv(self.path, index=False)
        self.assertEqual(self.predict().status_code, 400)
        self.predictor.predict.assert_not_called()

    def test_other_intervals_keep_80_candles(self):
        self.df['timestamps'] = pd.date_range('2026-01-01', periods=1200, freq='4h')
        self.df.to_csv(self.path, index=False)
        self.assertEqual(self.predict().status_code, 200)
        self.assertEqual(len(self.predictor.predict.call_args.kwargs['df']), 80)

    def test_kraken_history_adapts_forecast_and_reserves_backtest_rows(self):
        for rows in [719, 520]:
            self.df.tail(rows).to_csv(self.path, index=False)
            result = self.predict()
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.json['context_rows'], rows)
            result = self.predict(mode='backtest', start_index=0)
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.json['context_rows'], rows - 120)
            self.assertEqual(len(result.json['actual_data']), 120)

    def test_load_metadata_matches_the_forecast_dates(self):
        data = self.client.post('/api/load-data', json={'file_path': self.path}).json['data_info']
        result = self.predict().json
        self.assertEqual(data['forecast_start'], result['prediction_start'])
        self.assertEqual(data['forecast_end'], result['prediction_end'])

    def test_rejects_unordered_or_duplicate_timestamps(self):
        for df in [self.df.iloc[::-1], pd.concat([self.df, self.df.tail(1)])]:
            with self.subTest(rows=len(df)):
                df.to_csv(self.path, index=False)
                self.assertEqual(self.predict().status_code, 400)


if __name__ == '__main__':
    unittest.main()
