import os
import pandas as pd
import numpy as np
import json
import plotly.graph_objects as go
import plotly.utils
from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
import sys
import warnings
import datetime
import uuid
import re
from werkzeug.utils import secure_filename
from kraken_data import available_pairs, fetch_candles, KrakenDataError
warnings.filterwarnings('ignore')

# Add project root directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from model import Kronos, KronosTokenizer, KronosPredictor
    MODEL_AVAILABLE = True
except ImportError:
    MODEL_AVAILABLE = False
    print("Warning: Kronos model cannot be imported, will use simulated data for demonstration")

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
CORS(app)

# Global variables to store models
tokenizer = None
model = None
predictor = None

# Available model configurations
AVAILABLE_MODELS = {
    'kronos-mini': {
        'name': 'Kronos-mini',
        'model_id': 'NeoQuasar/Kronos-mini',
        'tokenizer_id': 'NeoQuasar/Kronos-Tokenizer-2k',
        'context_length': 2048,
        'params': '4.1M',
        'description': 'Lightweight model, suitable for fast prediction'
    },
    'kronos-small': {
        'name': 'Kronos-small',
        'model_id': 'NeoQuasar/Kronos-small',
        'tokenizer_id': 'NeoQuasar/Kronos-Tokenizer-base',
        'context_length': 512,
        'params': '24.7M',
        'description': 'Small model, balanced performance and speed'
    },
    'kronos-base': {
        'name': 'Kronos-base',
        'model_id': 'NeoQuasar/Kronos-base',
        'tokenizer_id': 'NeoQuasar/Kronos-Tokenizer-base',
        'context_length': 512,
        'params': '102.3M',
        'description': 'Base model, provides better prediction quality'
    }
}

def load_data_files():
    """Scan data directory and return available data files"""
    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
    data_files = []
    
    for data_dir in [data_dir, app.config['UPLOAD_FOLDER']]:
        if not os.path.isdir(data_dir):
            continue
        for file in sorted(os.listdir(data_dir)):
            if file.lower().endswith(('.csv', '.feather')) and os.path.isfile(os.path.join(data_dir, file)):
                file_path = os.path.join(data_dir, file)
                file_size = os.path.getsize(file_path)
                data_files.append({
                    'name': file,
                    'path': file_path,
                    'size': f"{file_size / 1024:.1f} KB" if file_size < 1024*1024 else f"{file_size / (1024*1024):.1f} MB"
                })
    
    return data_files

def load_data_file(file_path):
    """Load data file"""
    try:
        if file_path.lower().endswith('.csv'):
            df = pd.read_csv(file_path)
        elif file_path.lower().endswith('.feather'):
            df = pd.read_feather(file_path)
        else:
            return None, "Unsupported file format"
        
        # Check required columns
        required_cols = ['open', 'high', 'low', 'close']
        if not all(col in df.columns for col in required_cols):
            return None, f"Missing required columns: {required_cols}"
        
        # Process timestamp column
        if 'timestamps' in df.columns:
            df['timestamps'] = pd.to_datetime(df['timestamps'])
        elif 'timestamp' in df.columns:
            df['timestamps'] = pd.to_datetime(df['timestamp'])
        elif 'date' in df.columns:
            # If column name is 'date', rename it to 'timestamps'
            df['timestamps'] = pd.to_datetime(df['date'])
        else:
            # If no timestamp column exists, create one
            df['timestamps'] = pd.date_range(start='2024-01-01', periods=len(df), freq='1H')
        
        # Ensure numeric columns are numeric type
        for col in ['open', 'high', 'low', 'close']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Process volume column (optional)
        if 'volume' in df.columns:
            df['volume'] = pd.to_numeric(df['volume'], errors='coerce')
        
        # Process amount column (optional, but not used for prediction)
        if 'amount' in df.columns:
            df['amount'] = pd.to_numeric(df['amount'], errors='coerce')
        
        # Remove rows containing NaN values
        df = df.dropna().reset_index(drop=True)
        if df.empty:
            return None, "File contains no valid data rows"
        if not df['timestamps'].is_monotonic_increasing or df['timestamps'].duplicated().any():
            return None, "Las velas deben estar ordenadas por fecha, sin fechas duplicadas."
        
        return df, None
        
    except Exception as e:
        return None, f"Failed to load file: {str(e)}"

def save_prediction_results(file_path, prediction_type, prediction_results, actual_data, input_data, prediction_params):
    """Save prediction results to file"""
    try:
        # Create prediction results directory
        results_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'prediction_results')
        os.makedirs(results_dir, exist_ok=True)
        
        # Generate filename
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'prediction_{timestamp}.json'
        filepath = os.path.join(results_dir, filename)
        
        # Prepare data for saving
        save_data = {
            'timestamp': datetime.datetime.now().isoformat(),
            'file_path': file_path,
            'prediction_type': prediction_type,
            'prediction_params': prediction_params,
            'input_data_summary': {
                'rows': len(input_data),
                'columns': list(input_data.columns),
                'price_range': {
                    'open': {'min': float(input_data['open'].min()), 'max': float(input_data['open'].max())},
                    'high': {'min': float(input_data['high'].min()), 'max': float(input_data['high'].max())},
                    'low': {'min': float(input_data['low'].min()), 'max': float(input_data['low'].max())},
                    'close': {'min': float(input_data['close'].min()), 'max': float(input_data['close'].max())}
                },
                'last_values': {
                    'open': float(input_data['open'].iloc[-1]),
                    'high': float(input_data['high'].iloc[-1]),
                    'low': float(input_data['low'].iloc[-1]),
                    'close': float(input_data['close'].iloc[-1])
                }
            },
            'prediction_results': prediction_results,
            'actual_data': actual_data,
            'analysis': {}
        }
        
        # If actual data exists, perform comparison analysis
        if actual_data and len(actual_data) > 0:
            # Calculate continuity analysis
            if len(prediction_results) > 0 and len(actual_data) > 0:
                last_pred = prediction_results[0]  # First prediction point
            first_actual = actual_data[0]      # First actual point
                
            save_data['analysis']['continuity'] = {
                    'last_prediction': {
                        'open': last_pred['open'],
                        'high': last_pred['high'],
                        'low': last_pred['low'],
                        'close': last_pred['close']
                    },
                    'first_actual': {
                        'open': first_actual['open'],
                        'high': first_actual['high'],
                        'low': first_actual['low'],
                        'close': first_actual['close']
                    },
                    'gaps': {
                        'open_gap': abs(last_pred['open'] - first_actual['open']),
                        'high_gap': abs(last_pred['high'] - first_actual['high']),
                        'low_gap': abs(last_pred['low'] - first_actual['low']),
                        'close_gap': abs(last_pred['close'] - first_actual['close'])
                    },
                    'gap_percentages': {
                        'open_gap_pct': (abs(last_pred['open'] - first_actual['open']) / first_actual['open']) * 100,
                        'high_gap_pct': (abs(last_pred['high'] - first_actual['high']) / first_actual['high']) * 100,
                        'low_gap_pct': (abs(last_pred['low'] - first_actual['low']) / first_actual['low']) * 100,
                        'close_gap_pct': (abs(last_pred['close'] - first_actual['close']) / first_actual['close']) * 100
                    }
                }
        
        # Save to file
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, indent=2, ensure_ascii=False)
        
        print(f"Prediction results saved to: {filepath}")
        return filepath
        
    except Exception as e:
        print(f"Failed to save prediction results: {e}")
        return None

def data_source_info(file_path):
    """Identify imported Kraken files independently of the current UI filters."""
    filename = os.path.basename(file_path)
    match = re.fullmatch(r'kraken_([A-Z0-9]+)_(\d+)m_\d{8}_\d{6}_[a-f0-9]{8}\.csv', filename)
    if not match:
        return {'pair': None, 'pair_name': None, 'source': 'Archivo', 'filename': filename}
    code, interval = match.groups()
    try:
        name = next((pair['name'] for pair in available_pairs() if pair['code'] == code), code)
    except KrakenDataError:
        name = code
    return {'pair': code, 'pair_name': name, 'source': 'Kraken',
            'interval_minutes': int(interval), 'filename': filename}


def prediction_interval(df):
    interval = df['timestamps'].diff().dropna().median()
    return interval if pd.notna(interval) and interval > pd.Timedelta(0) else pd.Timedelta(hours=1)


def create_prediction_chart(df, pred_df, lookback, pred_len, actual_df=None, historical_start_idx=0,
                            prediction_timestamps=None):
    """Create prediction chart"""
    historical_df = df.iloc[historical_start_idx:historical_start_idx + lookback]
    
    # Create chart
    fig = go.Figure()
    
    # Add historical data (candlestick chart)
    fig.add_trace(go.Candlestick(
        x=historical_df['timestamps'] if 'timestamps' in historical_df.columns else historical_df.index,
        open=historical_df['open'],
        high=historical_df['high'],
        low=historical_df['low'],
        close=historical_df['close'],
        name=(f'Últimas {lookback} velas reales' if actual_df is None else f'Contexto histórico ({lookback} velas)'),
        increasing_line_color='#26A69A',
        decreasing_line_color='#EF5350'
    ))
    
    # Add prediction data (candlestick chart)
    if pred_df is not None and len(pred_df) > 0:
        if prediction_timestamps is not None:
            pred_timestamps = prediction_timestamps
        elif 'timestamps' in df.columns and len(historical_df) > 0:
            time_diff = df['timestamps'].diff().dropna().median()
            if pd.isna(time_diff) or time_diff <= pd.Timedelta(0):
                time_diff = pd.Timedelta(hours=1)
            pred_timestamps = pd.date_range(
                start=historical_df['timestamps'].iloc[-1] + time_diff,
                periods=len(pred_df),
                freq=time_diff
            )
        else:
            # If no timestamps, use index
            pred_timestamps = range(len(historical_df), len(historical_df) + len(pred_df))
        
        fig.add_trace(go.Candlestick(
            x=pred_timestamps,
            open=pred_df['open'],
            high=pred_df['high'],
            low=pred_df['low'],
            close=pred_df['close'],
        name=(f'Predicción futura ({pred_len} velas)' if actual_df is None else f'Predicción histórica ({pred_len} velas)'),
            increasing_line_color='#66BB6A',
            decreasing_line_color='#FF7043'
        ))
    
    # Add actual data for comparison (if exists)
    if actual_df is not None and len(actual_df) > 0:
        # Actual data should be in the same time period as prediction data
        if 'timestamps' in df.columns:
            if 'timestamps' in actual_df.columns:
                actual_timestamps = actual_df['timestamps']
            elif 'pred_timestamps' in locals():
                actual_timestamps = pred_timestamps
        else:
            actual_timestamps = range(len(historical_df), len(historical_df) + len(actual_df))
        
        fig.add_trace(go.Candlestick(
            x=actual_timestamps,
            open=actual_df['open'],
            high=actual_df['high'],
            low=actual_df['low'],
            close=actual_df['close'],
            name='Actual Data (120 data points)',
            increasing_line_color='#FF9800',
            decreasing_line_color='#F44336'
        ))
    
    # Update layout
    fig.update_layout(
        title=(f'Comparación histórica · {lookback} velas de contexto + {pred_len} de prueba'
               if actual_df is not None and len(actual_df) else
               f'Predicción futura · {lookback} velas de contexto + {pred_len} futuras'),
        xaxis_title='Fecha y hora del archivo (Kraken: UTC)',
        yaxis_title='Precio',
        yaxis={'side': 'right'},
        margin={'l': 30, 'r': 90, 't': 80, 'b': 60},
        template='plotly_white',
        height=600,
        showlegend=True
    )
    
    # Ensure x-axis time continuity
    if 'timestamps' in historical_df.columns:
        # Get all timestamps and sort them
        all_timestamps = []
        if len(historical_df) > 0:
            all_timestamps.extend(historical_df['timestamps'])
        if 'pred_timestamps' in locals():
            all_timestamps.extend(pred_timestamps)
        if 'actual_timestamps' in locals():
            all_timestamps.extend(actual_timestamps)
        
        if all_timestamps:
            all_timestamps = sorted(all_timestamps)
            visible_start = all_timestamps[0]
            fig.update_xaxes(
                range=[visible_start, all_timestamps[-1]],
                rangeslider_visible=False,
                type='date'
            )
    if prediction_timestamps is not None and len(prediction_timestamps):
        boundary = prediction_timestamps.iloc[0].isoformat()
        fig.add_shape(type='line', x0=boundary, x1=boundary, y0=0, y1=1,
                      yref='paper', line={'color': '#667eea', 'dash': 'dash'})
        fig.add_annotation(x=boundary, y=1, yref='paper', text='Inicio de predicción',
                           showarrow=False, xanchor='left')
    
    return json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)

@app.route('/')
def index():
    """Home page"""
    return render_template('index.html')

@app.route('/api/data-files')
def get_data_files():
    """Get available data file list"""
    data_files = load_data_files()
    return jsonify(data_files)

@app.errorhandler(413)
def upload_too_large(error):
    return jsonify({'error': 'File is too large. Maximum upload size is 50 MB.'}), 413


@app.route('/api/kraken-pairs')
def get_kraken_pairs():
    try:
        return jsonify({'pairs': available_pairs()})
    except KrakenDataError as exc:
        return jsonify({'error': str(exc)}), 502


@app.route('/api/import-kraken', methods=['POST'])
def import_kraken():
    try:
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({'error': 'Indica el par y el intervalo.'}), 400
        pair, interval = data.get('pair'), data.get('interval', 60)
        df = fetch_candles(pair, interval)
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d_%H%M%S')
        filename = f'kraken_{secure_filename(pair)}_{interval}m_{stamp}_{uuid.uuid4().hex[:8]}.csv'
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        # Atomic save keeps partially written files out of the selector.
        temp_path = file_path + '.tmp'
        try:
            df.to_csv(temp_path, index=False)
            os.replace(temp_path, file_path)
        finally:
            if os.path.isfile(temp_path):
                os.remove(temp_path)
        return jsonify({'success': True, 'file_path': file_path, 'rows': len(df),
                        'message': f'{len(df)} velas cerradas descargadas de Kraken. Fechas en UTC; excluida la vela en curso.'})
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    except KrakenDataError as exc:
        return jsonify({'error': str(exc)}), 502
    except OSError:
        app.logger.exception('Could not save Kraken data')
        return jsonify({'error': 'No se pudo guardar el CSV de Kraken.'}), 500


@app.route('/api/data-download')
def download_data():
    file_path = request.args.get('file_path', '')
    allowed = {item['path'] for item in load_data_files()}
    if file_path not in allowed:
        return jsonify({'error': 'Data file not found'}), 404
    return send_file(file_path, as_attachment=True)


@app.route('/api/upload-data', methods=['POST'])
def upload_data():
    uploaded = request.files.get('file')
    if uploaded is None or not uploaded.filename:
        return jsonify({'error': 'Please choose a CSV or Feather file.'}), 400
    filename = secure_filename(uploaded.filename)
    if not filename.lower().endswith(('.csv', '.feather')):
        return jsonify({'error': 'Unsupported file format. Choose CSV or Feather.'}), 400
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], f'{uuid.uuid4().hex}_{filename}')
    try:
        uploaded.save(file_path)
        df, error = load_data_file(file_path)
        if error:
            os.remove(file_path)
            return jsonify({'error': error}), 400
        return jsonify({'success': True, 'file_path': file_path})
    except Exception:
        if os.path.isfile(file_path):
            os.remove(file_path)
        app.logger.exception('Data upload failed')
        return jsonify({'error': 'Could not save the uploaded file.'}), 500


@app.route('/api/load-data', methods=['POST'])
def load_data():
    """Load data file"""
    try:
        data = request.get_json()
        file_path = data.get('file_path')
        
        if not file_path:
            return jsonify({'error': 'File path cannot be empty'}), 400
        
        df, error = load_data_file(file_path)
        if error:
            return jsonify({'error': error}), 400
        
        # Detect data time frequency
        def detect_timeframe(df):
            if len(df) < 2:
                return "Unknown"
            
            time_diffs = []
            for i in range(1, min(10, len(df))):  # Check first 10 time differences
                diff = df['timestamps'].iloc[i] - df['timestamps'].iloc[i-1]
                time_diffs.append(diff)
            
            if not time_diffs:
                return "Unknown"
            
            # Calculate average time difference
            avg_diff = sum(time_diffs, pd.Timedelta(0)) / len(time_diffs)
            
            # Convert to readable format
            if avg_diff < pd.Timedelta(minutes=1):
                return f"{avg_diff.total_seconds():.0f} seconds"
            elif avg_diff < pd.Timedelta(hours=1):
                return f"{avg_diff.total_seconds() / 60:.0f} minutes"
            elif avg_diff < pd.Timedelta(days=1):
                return f"{avg_diff.total_seconds() / 3600:.0f} hours"
            else:
                return f"{avg_diff.days} days"
        
        # Return data information
        data_info = {
            **data_source_info(file_path),
            'rows': len(df),
            'columns': list(df.columns),
            'start_date': df['timestamps'].min().isoformat() if 'timestamps' in df.columns else 'N/A',
            'end_date': df['timestamps'].max().isoformat() if 'timestamps' in df.columns else 'N/A',
            'price_range': {
                'min': float(df[['open', 'high', 'low', 'close']].min().min()),
                'max': float(df[['open', 'high', 'low', 'close']].max().max())
            },
            'prediction_columns': ['open', 'high', 'low', 'close'] + (['volume'] if 'volume' in df.columns else []),
            'timeframe': detect_timeframe(df),
            'forecast_start': (df['timestamps'].iloc[-1] + prediction_interval(df)).isoformat(),
            'forecast_end': (df['timestamps'].iloc[-1] + 120 * prediction_interval(df)).isoformat()
        }
        
        return jsonify({
            'success': True,
            'data_info': data_info,
            'message': f'Successfully loaded data, total {len(df)} rows'
        })
        
    except Exception as e:
        return jsonify({'error': f'Failed to load data: {str(e)}'}), 500

@app.route('/api/predict', methods=['POST'])
def predict():
    """Perform prediction"""
    try:
        data = request.get_json() or {}
        file_path = data.get('file_path')
        lookback = int(data.get('lookback', 80))
        pred_len = int(data.get('pred_len', 120))
        mode = data.get('mode', 'forecast')
        if mode not in ('forecast', 'backtest'):
            return jsonify({'error': 'Selecciona predicción futura o comparación histórica.'}), 400
        if lookback < 1 or pred_len < 1:
            return jsonify({'error': 'Los tamaños de contexto y predicción deben ser positivos.'}), 400
        
        # Get prediction quality parameters
        temperature = float(data.get('temperature', 1.0))
        top_p = float(data.get('top_p', 0.9))
        sample_count = int(data.get('sample_count', 1))
        
        if not file_path:
            return jsonify({'error': 'File path cannot be empty'}), 400
        
        # Load data
        df, error = load_data_file(file_path)
        if error:
            return jsonify({'error': error}), 400
        
        if not MODEL_AVAILABLE or predictor is None:
            return jsonify({'error': 'Kronos model not loaded, please load model first'}), 400

        # Only an explicit backtest may consume a historical window. Old browser
        # tabs that still send a slider index now also forecast from the latest row.
        start_index = data.get('start_index') if mode == 'backtest' else None
        start_date = data.get('start_date') if mode == 'backtest' else None
        selected_window = mode == 'backtest'
        if selected_window and start_index is None and start_date is None:
            return jsonify({'error': 'Selecciona una ventana para la comparación histórica.'}), 400
        actual_df = None

        if selected_window:
            if start_index is not None:
                start_index = int(start_index)
            else:
                start_dt = pd.to_datetime(start_date)
                matching_positions = np.flatnonzero((df['timestamps'] >= start_dt).to_numpy())
                if len(matching_positions) == 0:
                    return jsonify({'error': 'Selected start time is outside the data range'}), 400
                start_index = int(matching_positions[0])

            if start_index < 0 or start_index + lookback + pred_len > len(df):
                available = max(0, len(df) - start_index)
                return jsonify({
                    'error': f'Insufficient data from selected window, need {lookback + pred_len} rows, currently only {available} available'
                }), 400

            window_df = df.iloc[start_index:start_index + lookback + pred_len]
            context_df = window_df.iloc[:lookback]
            actual_df = window_df.iloc[lookback:]
            x_df = context_df[[
                'open', 'high', 'low', 'close'
            ] + (['volume'] if 'volume' in df.columns else [])]
            x_timestamp = context_df['timestamps']
            y_timestamp = actual_df['timestamps']
            historical_start_idx = start_index
            prediction_type = "Kronos model backtest (selected historical window)"
        else:
            if len(df) < lookback:
                return jsonify({'error': f'Insufficient data length, need at least {lookback} rows'}), 400

            historical_start_idx = len(df) - lookback
            context_df = df.iloc[historical_start_idx:]
            x_df = context_df[[
                'open', 'high', 'low', 'close'
            ] + (['volume'] if 'volume' in df.columns else [])]
            x_timestamp = context_df['timestamps']
            time_diff = prediction_interval(df)
            y_timestamp = pd.Series(
                pd.date_range(
                    start=context_df['timestamps'].iloc[-1] + time_diff,
                    periods=pred_len,
                    freq=time_diff
                ),
                name='timestamps'
            )
            prediction_type = "Kronos model prediction (forecast from latest data)"

        try:
            pred_df = predictor.predict(
                df=x_df,
                x_timestamp=x_timestamp,
                y_timestamp=y_timestamp,
                pred_len=pred_len,
                T=temperature,
                top_p=top_p,
                sample_count=sample_count
            )
        except Exception as e:
            return jsonify({'error': f'Kronos model prediction failed: {str(e)}'}), 500

        actual_data = []
        if actual_df is not None:
            for _, row in actual_df.iterrows():
                actual_data.append({
                    'timestamp': row['timestamps'].isoformat(),
                    'open': float(row['open']),
                    'high': float(row['high']),
                    'low': float(row['low']),
                    'close': float(row['close']),
                    'volume': float(row['volume']) if 'volume' in row else 0,
                    'amount': float(row['amount']) if 'amount' in row else 0
                })

        chart_json = create_prediction_chart(
            df, pred_df, lookback, pred_len, actual_df, historical_start_idx,
            prediction_timestamps=y_timestamp
        )

        prediction_results = []
        for i, (_, row) in enumerate(pred_df.iterrows()):
            prediction_results.append({
                'timestamp': y_timestamp.iloc[i].isoformat() if i < len(y_timestamp) else f"T{i}",
                'open': float(row['open']),
                'high': float(row['high']),
                'low': float(row['low']),
                'close': float(row['close']),
                'volume': float(row['volume']) if 'volume' in row else 0,
                'amount': float(row['amount']) if 'amount' in row else 0
            })
        
        # Save prediction results to file
        try:
            save_prediction_results(
                file_path=file_path,
                prediction_type=prediction_type,
                prediction_results=prediction_results,
                actual_data=actual_data,
                input_data=x_df,
                prediction_params={
                    'lookback': lookback,
                    'pred_len': pred_len,
                    'temperature': temperature,
                    'top_p': top_p,
                    'sample_count': sample_count,
                    'mode': mode,
                    'start_index': start_index if selected_window else 'latest'
                }
            )
        except Exception as e:
            print(f"Failed to save prediction results: {e}")
        
        return jsonify({
            'success': True,
            'prediction_type': prediction_type,
            'mode': mode,
            'market': data_source_info(file_path),
            'context_end': context_df['timestamps'].iloc[-1].isoformat(),
            'prediction_start': y_timestamp.iloc[0].isoformat(),
            'prediction_end': y_timestamp.iloc[-1].isoformat(),
            'chart': chart_json,
            'prediction_results': prediction_results,
            'actual_data': actual_data,
            'has_comparison': len(actual_data) > 0,
            'message': f'Prediction completed, generated {pred_len} prediction points' + (f', including {len(actual_data)} actual data points for comparison' if len(actual_data) > 0 else '')
        })
        
    except Exception as e:
        return jsonify({'error': f'Prediction failed: {str(e)}'}), 500

@app.route('/api/load-model', methods=['POST'])
def load_model():
    """Load Kronos model"""
    global tokenizer, model, predictor
    
    try:
        if not MODEL_AVAILABLE:
            return jsonify({'error': 'Kronos model library not available'}), 400
        
        data = request.get_json()
        model_key = data.get('model_key', 'kronos-small')
        device = data.get('device', 'cpu')
        
        if model_key not in AVAILABLE_MODELS:
            return jsonify({'error': f'Unsupported model: {model_key}'}), 400
        
        model_config = AVAILABLE_MODELS[model_key]
        
        # Load tokenizer and model
        tokenizer = KronosTokenizer.from_pretrained(model_config['tokenizer_id'])
        model = Kronos.from_pretrained(model_config['model_id'])
        
        # Create predictor
        predictor = KronosPredictor(model, tokenizer, device=device, max_context=model_config['context_length'])
        
        return jsonify({
            'success': True,
            'message': f'Model loaded successfully: {model_config["name"]} ({model_config["params"]}) on {device}',
            'model_info': {
                'name': model_config['name'],
                'params': model_config['params'],
                'context_length': model_config['context_length'],
                'description': model_config['description']
            }
        })
        
    except Exception as e:
        return jsonify({'error': f'Model loading failed: {str(e)}'}), 500

@app.route('/api/available-models')
def get_available_models():
    """Get available model list"""
    return jsonify({
        'models': AVAILABLE_MODELS,
        'model_available': MODEL_AVAILABLE
    })

@app.route('/api/model-status')
def get_model_status():
    """Get model status"""
    if MODEL_AVAILABLE:
        if predictor is not None:
            return jsonify({
                'available': True,
                'loaded': True,
                'message': 'Kronos model loaded and available',
                'current_model': {
                    'name': predictor.model.__class__.__name__,
                    'device': str(next(predictor.model.parameters()).device)
                }
            })
        else:
            return jsonify({
                'available': True,
                'loaded': False,
                'message': 'Kronos model available but not loaded'
            })
    else:
        return jsonify({
            'available': False,
            'loaded': False,
            'message': 'Kronos model library not available, please install related dependencies'
        })

if __name__ == '__main__':
    print("Starting Kronos Web UI...")
    print(f"Model availability: {MODEL_AVAILABLE}")
    if MODEL_AVAILABLE:
        print("Tip: You can load Kronos model through /api/load-model endpoint")
    else:
        print("Tip: Will use simulated data for demonstration")
    
    app.run(debug=True, host='0.0.0.0', port=7070)
