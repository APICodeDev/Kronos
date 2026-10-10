"""Read-only Kronos feasibility audit. Run in the existing Docker Python runtime.

docker cp research/audit_kronos.py kronos-kronos-1:/tmp/audit_kronos.py
docker exec -w /app kronos-kronos-1 python /tmp/audit_kronos.py --output /tmp/kronos_audit.json
docker cp kronos-kronos-1:/tmp/kronos_audit.json research/kronos_audit.json

No Flask state, uploaded files, or pretrained weights are modified.
"""
import argparse
import hashlib
import json
import platform
import sys
import time
import urllib.request
from pathlib import Path

import huggingface_hub
import numpy as np
import pandas as pd
import torch

sys.path.insert(0, "/app")
from model import Kronos, KronosPredictor, KronosTokenizer


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def describe(model):
    shapes = [(name, list(p.shape), p.numel()) for name, p in model.named_parameters()]
    count = sum(p.numel() for p in model.parameters())
    return {"parameters": count, "fp32_bytes": count * 4,
            "largest_parameter": max(shapes, key=lambda row: row[2]),
            "parameter_tensors_over_pine_collection_limit": sum(n > 100000 for _, _, n in shapes),
            "training": model.training}


def archived_results(root):
    rows = []
    for path in sorted(root.glob("prediction_*.json")):
        j = json.loads(path.read_text())
        pred = pd.DataFrame(j["prediction_results"])
        if pred.empty:
            continue
        ohlc = pred[["open", "high", "low", "close"]]
        invalid = ((pred.high < ohlc.max(axis=1)) | (pred.low > ohlc.min(axis=1))).sum()
        row = {"file": path.name, "params": j["prediction_params"], "rows": len(pred),
               "invalid_ohlc_rows": int(invalid),
               "negative_volume_rows": int((pred.volume < 0).sum()),
               "negative_amount_rows": int((pred.amount < 0).sum())}
        actual = pd.DataFrame(j.get("actual_data", []))
        if not actual.empty and len(actual) == len(pred) and list(pred.timestamp) == list(actual.timestamp):
            last = j["input_data_summary"]["last_values"]["close"]
            row["close_mae"] = float(np.mean(np.abs(pred.close - actual.close)))
            row["persistence_close_mae"] = float(np.mean(np.abs(last - actual.close)))
            row["close_rmse"] = float(np.sqrt(np.mean((pred.close - actual.close)**2)))
        rows.append(row)
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--mode-only", action="store_true", help="Only inspect dropout and cross-attention semantics")
    args = parser.parse_args()
    torch.set_num_threads(4)
    cache = Path("/home/kronos/.cache/huggingface/hub")
    tokenizer_path = cache / "models--NeoQuasar--Kronos-Tokenizer-base/snapshots/0e0117387f39004a9016484a186a908917e22426"
    model_path = cache / "models--NeoQuasar--Kronos-base/snapshots/2b554741eca47781b64468546e77fef3e85130e6"
    tokenizer = KronosTokenizer.from_pretrained(str(tokenizer_path))
    model = Kronos.from_pretrained(str(model_path))
    output = {"scope": "local commit 325d4e0; offline cached base weights; isolated process",
              "versions": {"python": platform.python_version(), "torch": torch.__version__,
                           "huggingface_hub": huggingface_hub.__version__},
              "source_sha256": {p: sha256('/app/' + p) for p in
                                ['model/kronos.py', 'model/module.py', 'webui/app.py']},
              "snapshots": {"tokenizer": tokenizer_path.name, "predictor": model_path.name},
              "tokenizer": describe(tokenizer), "models": {}, "experiments": {}}
    for name in ['mini', 'small', 'base']:
        if name == 'base':
            cfg = json.loads((model_path / 'config.json').read_text())
            desc = describe(model)
        else:
            url = f'https://huggingface.co/NeoQuasar/Kronos-{name}/resolve/main/config.json'
            with urllib.request.urlopen(url, timeout=30) as response:
                cfg = json.load(response)
            with torch.device('meta'):
                candidate = Kronos(**cfg)
            desc = describe(candidate)
            del candidate
        d, f, layers = cfg['d_model'], cfg['ff_dim'], cfg['n_layers']
        desc['config'] = cfg
        desc['trunk_linear_mac_80_to_120_one_path'] = layers * (4*d*d + 3*d*f) * sum(range(80, 200))
        output['models'][name] = desc
    print('MODEL_COUNTS', {k: v['parameters'] for k, v in output['models'].items()}, flush=True)
    # Use precisely the input file of the latest local AVAXUSD result; no new market download.
    saved = json.loads(Path('/app/webui/prediction_results/prediction_20261008_191209.json').read_text())
    df = pd.read_csv(saved['file_path'])
    df['timestamps'] = pd.to_datetime(df['timestamps'])
    context = df.tail(80).reset_index(drop=True)
    output['input'] = {'file': Path(saved['file_path']).name, 'sha256': sha256(saved['file_path']),
                       'rows': len(context), 'start': context.timestamps.iloc[0].isoformat(),
                       'end': context.timestamps.iloc[-1].isoformat()}
    features = context[['open', 'high', 'low', 'close', 'volume']]
    future = pd.Series(pd.date_range(context.timestamps.iloc[-1] + pd.Timedelta(hours=1), periods=120, freq='h'))
    predictor = KronosPredictor(model, tokenizer, device='cpu', max_context=512)

    # Directly measure logits: equal greedy tokens do not imply equal neural computations.
    x = features.copy()
    x['amount'] = x.volume * x[['open', 'high', 'low', 'close']].mean(axis=1)
    x = x.to_numpy(dtype=np.float32)
    x = np.clip((x-x.mean(axis=0))/(x.std(axis=0)+1e-5), -5, 5)
    t = context.timestamps
    stamp = torch.tensor(np.stack([t.dt.minute, t.dt.hour, t.dt.weekday, t.dt.day, t.dt.month], axis=1), dtype=torch.float32)[None]
    tokenizer.eval()
    with torch.no_grad():
        tokens = tokenizer.encode(torch.from_numpy(x)[None], half=True)
        def logits(training, seed):
            model.train(training)
            torch.manual_seed(seed)
            coarse, hidden = model.decode_s1(tokens[0], tokens[1], stamp)
            fine = model.decode_s2(hidden, coarse[:, -1].argmax(-1, keepdim=True))
            return coarse[:, -1], fine[:, -1]
        train_a, train_b = logits(True, 123), logits(True, 124)
        eval_a, eval_b = logits(False, 123), logits(False, 124)
    q = torch.zeros(1, 1, 1, 2)
    k = torch.zeros(1, 1, 4, 2)
    v = torch.arange(4, dtype=torch.float32).view(1, 1, 4, 1).expand(1, 1, 4, 2)
    sdpa = torch.nn.functional.scaled_dot_product_attention
    output['inference_mode'] = {
        'train_different_seed_coarse_logits_max_abs': float((train_a[0]-train_b[0]).abs().max()),
        'train_different_seed_fine_logits_max_abs': float((train_a[1]-train_b[1]).abs().max()),
        'eval_different_seed_coarse_logits_max_abs': float((eval_a[0]-eval_b[0]).abs().max()),
        'train_vs_eval_coarse_logits_max_abs': float((train_a[0]-eval_a[0]).abs().max()),
        'single_query_causal_value': sdpa(q, k, v, is_causal=True).flatten().tolist(),
        'single_query_noncausal_value': sdpa(q, k, v, is_causal=False).flatten().tolist()}
    print('INFERENCE_MODE', output['inference_mode'], flush=True)
    if args.mode_only:
        Path(args.output).write_text(json.dumps(output, indent=2, ensure_ascii=False) + '\n')
        return

    def run(name, seed, *, mode='eval', top_k=0, top_p=0.9, count=1, horizon=8, data=None, stamps=None):
        model.train(mode == 'app')
        tokenizer.train(mode == 'app')
        torch.manual_seed(seed)
        start = time.perf_counter()
        result = predictor.predict(df=features if data is None else data,
                                   x_timestamp=context.timestamps if stamps is None else stamps,
                                   y_timestamp=future.iloc[:horizon] if stamps is None else future.iloc[:horizon] + pd.Timedelta(hours=6),
                                   pred_len=horizon, T=1.0, top_k=top_k, top_p=top_p,
                                   sample_count=count, verbose=False)
        output['experiments'][name] = {'seed': seed, 'mode': mode, 'top_k': top_k, 'top_p': top_p,
                                       'sample_count': count, 'horizon': horizon,
                                       'seconds': round(time.perf_counter()-start, 4),
                                       'values': result.to_numpy().tolist()}
        print('EXPERIMENT', name, output['experiments'][name]['seconds'], 'seconds', flush=True)
        return result.to_numpy()

    a = run('eval_sampling_seed123', 123)
    repeat = run('eval_sampling_seed123_repeat', 123)
    b = run('eval_sampling_seed124', 124)
    app_a = run('app_greedy_seed123', 123, mode='app', top_k=1, top_p=1.0)
    app_b = run('app_greedy_seed124', 124, mode='app', top_k=1, top_p=1.0)
    greedy_a = run('eval_greedy_seed123', 123, top_k=1, top_p=1.0)
    greedy_b = run('eval_greedy_seed124', 124, top_k=1, top_p=1.0)
    no_volume = run('eval_no_volume_seed123', 123, top_k=1, top_p=1.0, data=features.drop(columns='volume'))
    shifted = run('eval_shifted_time_seed123', 123, top_k=1, top_p=1.0, stamps=context.timestamps + pd.Timedelta(hours=6))
    run('eval_full120_two_paths_seed123', 123, horizon=120, count=2, top_p=1.0)
    output['comparisons'] = {
        'same_seed_eval_exact_repeat': bool(np.array_equal(a, repeat)),
        'different_seed_sampling_close_max_abs': float(np.max(np.abs(a[:, 3]-b[:, 3]))),
        'app_greedy_different_seed_close_max_abs': float(np.max(np.abs(app_a[:, 3]-app_b[:, 3]))),
        'eval_greedy_different_seed_close_max_abs': float(np.max(np.abs(greedy_a[:, 3]-greedy_b[:, 3]))),
        'remove_volume_greedy_close_max_abs': float(np.max(np.abs(greedy_a[:, 3]-no_volume[:, 3]))),
        'shift_time_greedy_close_max_abs': float(np.max(np.abs(greedy_a[:, 3]-shifted[:, 3])))}
    output['archived_predictions'] = archived_results(Path('/app/webui/prediction_results'))
    Path(args.output).write_text(json.dumps(output, indent=2, ensure_ascii=False) + '\n')
    print('COMPARISONS', output['comparisons'], flush=True)
    print('OUTPUT', args.output, flush=True)


if __name__ == '__main__':
    main()
