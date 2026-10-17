"""python -m research.false_breakout.download_history --help"""
import argparse
import json
from pathlib import Path

from webui.bitget_data import INTERVAL_MS, PublicClient, fetch_history, instrument, save_history, sha256, utc_ms


def main():
    parser = argparse.ArgumentParser(description='Descarga pública Bitget, sin claves; fechas UTC [inicio, fin).')
    parser.add_argument('--start', required=True)
    parser.add_argument('--end', help='Por defecto última vela cerrada según reloj de Bitget.')
    parser.add_argument('--config', default='research/false_breakout/config.json')
    parser.add_argument('--output', required=True, help='Directorio nuevo dentro de webui/uploads recomendado.')
    args = parser.parse_args()
    cfg = json.loads(Path(args.config).read_text(encoding='utf-8'))
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    client = PublicClient(output / 'raw')
    inst_path = output / 'instrument.json'
    if not inst_path.exists():
        inst_path.write_text(json.dumps(instrument(client, cfg['symbol'], cfg['category']), indent=2), encoding='utf-8')
    for interval in [cfg['entry_interval'], *cfg['context_intervals']]:
        existing = list(output.glob(f"{cfg['symbol']}_{interval}_*.metadata.json"))
        if existing:
            if len(existing) != 1:
                raise ValueError('Varios históricos para el mismo intervalo; usa un directorio nuevo.')
            meta = json.loads(existing[0].read_text(encoding='utf-8'))
            step = INTERVAL_MS[interval]
            wanted_start = (utc_ms(args.start) + step - 1) // step * step
            if meta['requested_start_ms'] != wanted_start or (args.end and meta['requested_end_ms'] != utc_ms(args.end) // step * step):
                raise ValueError('El rango existente es distinto; usa un directorio nuevo.')
            if sha256(output / meta['csv_file']) != meta['csv_sha256']:
                raise ValueError('El hash existente ha cambiado; no se sobrescribe.')
            print(f'{interval}: ya guardado; se conserva {existing[0]}', flush=True)
            continue
        print(f'Descargando {interval} desde {args.start} hasta {args.end or "última cerrada"}...', flush=True)
        df, meta = fetch_history(client, cfg['symbol'], cfg['category'], interval, utc_ms(args.start),
                                 utc_ms(args.end) if args.end else None)
        path = save_history(df, meta, output)
        print(json.dumps({'file': str(path), 'interval': interval, 'symbol': cfg['symbol'], **meta['quality']}), flush=True)
    (output / 'receipts.json').write_text(json.dumps(client.receipts, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
