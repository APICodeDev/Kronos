import json
from unittest.mock import Mock, patch

import pytest
import requests

from webui.bitget_data import BitgetDataError, PublicClient, fetch_history, normalize, save_history

STEP = 300_000


def row(index, **changes):
    values = dict(timestamp=index * STEP, open=10, high=12, low=9, close=11, volume=5, turnover=55)
    values.update(changes)
    return list(values.values())


class FakeClient:
    def __init__(self, rows):
        self.rows, self.queries = rows, []

    def get(self, endpoint, params=None, **kwargs):
        if endpoint == 'time':
            return {'serverTime': 250 * STEP + 100}
        self.queries.append(params)
        return sorted([r for r in self.rows if int(params['startTime']) < r[0] < int(params['endTime'])], reverse=True)[0:100]


def test_pagination_exact_boundaries_and_closed_only():
    client = FakeClient([row(x) for x in range(251)])
    frame, meta = fetch_history(client, 'XRPUSDT', 'USDT-FUTURES', '5m', 0)
    assert len(frame) == 250
    assert frame.timestamp.is_monotonic_increasing
    assert meta['quality']['missing_bars'] == 0
    assert len(client.queries) == 3
    assert all(int(q['endTime']) - int(q['startTime']) <= 100 * STEP + 1 for q in client.queries)


def test_empty_response_reports_missing_without_filling():
    frame, meta = fetch_history(FakeClient([]), 'XRPUSDT', 'USDT-FUTURES', '5m', 0, 3 * STEP)
    assert len(frame) == 0
    assert meta['quality']['missing_bars'] == 3
    assert meta['quality']['gaps'] == [{'start_ms': 0, 'end_ms': 3 * STEP, 'bars': 3}]


def test_sort_identical_duplicates_and_gaps():
    frame, quality = normalize([row(3), row(0), row(0), row(1)], '5m', 0, 4 * STEP)
    assert len(frame) == 3
    assert quality['missing_bars'] == 1
    assert quality['identical_duplicates_removed'] == 1
    assert quality['backward_steps_before_sort'] == 1


@pytest.mark.parametrize('rows', [
    [row(0), row(0, close=10)], [row(0, open=0)], [row(0, high=9)],
    [row(0, low=12)], [row(0, volume=-1)], [row(0, turnover=-1)],
    [row(0, close=float('nan'))], [row(0, high=float('inf'))],
    [row(0, timestamp=1)], [['bad']],
])
def test_invalid_data_rejected(rows):
    with pytest.raises(BitgetDataError):
        normalize(rows, '5m', 0, STEP)


def test_api_ignoring_window_fails():
    client = Mock()
    client.get.return_value = [row(800)]
    with pytest.raises(BitgetDataError, match='ventana'):
        fetch_history(client, 'XRPUSDT', 'USDT-FUTURES', '5m', 0, STEP, now_ms=STEP)


def response(payload=None, status=200, headers=None):
    result = Mock(status_code=status, headers=headers or {})
    result.json.return_value = payload or {'code': '00000', 'data': []}
    if status >= 400:
        result.raise_for_status.side_effect = requests.HTTPError(str(status))
    return result


def test_rate_limit_and_timeout_bounded_retries():
    session = Mock()
    session.get.side_effect = [response(status=429, headers={'Retry-After': '2'}), requests.Timeout(), response()]
    with patch('webui.bitget_data.time.sleep') as sleep:
        assert PublicClient(session=session, pause=0).get('history-candles') == []
        assert session.get.call_count == 3
        assert any(call.args == (2,) for call in sleep.call_args_list)
    session.get.side_effect = requests.Timeout()
    with patch('webui.bitget_data.time.sleep'), pytest.raises(BitgetDataError):
        PublicClient(session=session, retries=1).get('history-candles')
    assert session.get.call_count == 5


@pytest.mark.parametrize('payload', [{'code': '40000', 'msg': 'bad'}, [], {'code': '00000'}])
def test_api_errors(payload):
    session = Mock()
    session.get.return_value = response()
    session.get.return_value.json.return_value = payload
    with pytest.raises(BitgetDataError):
        PublicClient(session=session).get('instruments')


def test_cache_and_save_no_overwrite(tmp_path):
    session = Mock()
    session.get.return_value = response()
    client = PublicClient(tmp_path / 'cache', session=session)
    client.get('history-candles', {'limit': '100'})
    client.get('history-candles', {'limit': '100'})
    assert session.get.call_count == 1
    frame, meta = fetch_history(FakeClient([row(0)]), 'XRPUSDT', 'USDT-FUTURES', '5m', 0, STEP)
    path = save_history(frame, meta, tmp_path)
    assert len(json.loads(path.with_suffix('.metadata.json').read_text())['csv_sha256']) == 64
    with pytest.raises(FileExistsError):
        save_history(frame, meta, tmp_path)


@pytest.mark.parametrize('interval,step', [('15m', 900000), ('1H', 3600000)])
def test_context_granularities(interval, step):
    frame, quality = normalize([row(0), row(1, timestamp=step)], interval, 0, step * 2)
    assert len(frame) == 2
    assert quality['missing_bars'] == 0
