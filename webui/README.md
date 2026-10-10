# Kronos Web UI

Web user interface for Kronos financial prediction model, providing intuitive graphical operation interface.

## ✨ Features

- **Multi-format data support**: Supports CSV, Feather and other financial data formats
- **Smart time window**: Hourly context: up to 719 closed candles + 120 forecast candles, adapted to available history and model capacity; other intervals: 80 + 120
- **Real model prediction**: Integrated real Kronos model, supports multiple model sizes
- **Prediction quality control**: Adjustable temperature, nucleus sampling, sample count and other parameters
- **CPU inference**: Runs without a GPU in the provided Docker setup
- **Comparison analysis**: Detailed comparison between prediction results and actual data
- **K-line chart display**: Professional financial K-line chart display

## 🚀 Quick Start

### Run with Docker (CPU)

From the project root:

```bash
docker compose up --build -d
```

Open http://localhost:7070. Put CSV or Feather market-data files in the root
`data/` directory or use **Upload Data File** to choose one from your computer
(up to 50 MB). Uploaded files are validated and loaded automatically, and are
kept in the persistent `uploaded-data` Docker volume. The container uses CPU-only
PyTorch; no GPU or external LLM service is required. On first use, load a
Kronos model in the UI; its files are downloaded from Hugging Face and cached
in a persistent Docker volume. Prediction results are written to
`webui/prediction_results/`.

To stop the service, run `docker compose down`. The model cache and saved
prediction results are preserved.

### Method 1: Start with Python script
```bash
cd webui
python run.py
```

### Method 2: Start with Shell script
```bash
cd webui
chmod +x start.sh
./start.sh
```

### Method 3: Start Flask application directly
```bash
cd webui
python app.py
```

After successful startup, visit http://localhost:7070

## 📋 Usage Steps

### Download market data directly from Kraken

Use **Datos de Kraken**, search for a spot pair (for example BTC/EUR), choose a
candle interval, and press **Descargar y cargar datos de Kraken**. This uses
Kraken's free public market-data API and requires no API key or account access.
The app excludes the unfinished candle, checks OHLC values and time continuity,
and requires at least 80 completed candles. Timestamps are in UTC. The CSV is
saved in the same persistent upload directory and can also be downloaded.

Kraken's OHLC endpoint only returns recent candles; it cannot retrieve arbitrary
older dates. New pairs or long intervals may not provide 80 completed candles.
See the [official OHLC documentation](https://docs.kraken.com/api-reference/market-data/get-ohlc-data).

1. **Load data**: Select financial data file from data directory
2. **Load model**: Select Kronos model and computing device
3. **Set parameters**: Adjust prediction quality parameters
4. **Select time window**: Use slider to select 80+120 data point time range
5. **Start prediction**: Click prediction button to generate results
6. **View results**: View prediction results in charts and tables

## 🔧 Prediction Quality Parameters

### Temperature (T)
- **Range**: 0.1 - 2.0
- **Effect**: Controls prediction randomness
- **Recommendation**: 1.2-1.5 for better prediction quality

### Nucleus Sampling (top_p)
- **Range**: 0.1 - 1.0
- **Effect**: Controls prediction diversity
- **Recommendation**: 0.95-1.0 to consider more possibilities

### Sample Count
- **Range**: 1 - 5
- **Effect**: Generate multiple prediction samples
- **Recommendation**: 2-3 samples to improve quality

## 📊 Supported Data Formats

### Required Columns
- `open`: Opening price
- `high`: Highest price
- `low`: Lowest price
- `close`: Closing price

### Optional Columns
- `volume`: Trading volume
- `amount`: Trading amount (not used for prediction)
- `timestamps`/`timestamp`/`date`: Timestamp

## 🤖 Model Support

- **Kronos-mini**: 4.1M parameters, lightweight fast prediction
- **Kronos-small**: 24.7M parameters, balanced performance and speed
- **Kronos-base**: 102.3M parameters, high quality prediction

## 🖥️ Docker runtime

The provided Docker image installs CPU-only PyTorch; GPU passthrough is not
configured. The default mode forecasts the next 120 candles from the last 80
rows in the loaded file. The UI displays the last input timestamp and forecast
dates before running, and labels them again above the result. Kraken timestamps
are UTC. Download fresh data to forecast from the latest available candle.

Choose **Comparación histórica (backtest)** to select a 200-row historical
window: 80 context rows plus 120 held-out rows for comparison. The API requires
`mode: "backtest"` to use a historical window; otherwise it forecasts from the
latest rows, even if an older browser tab sends a slider index.

## ⚠️ Notes

- `amount` column is not used for prediction, only for display
- Future forecasts require 80 historical rows; historical comparisons require 200.
- First model loading may require download, please be patient

## 🔍 Comparison Analysis

The system automatically provides comparison analysis between prediction results and actual data, including:
- Price difference statistics
- Error analysis
- Prediction quality assessment

## 🛠️ Technical Architecture

- **Backend**: Flask + Python
- **Frontend**: HTML + CSS + JavaScript
- **Charts**: Plotly.js
- **Data processing**: Pandas + NumPy
- **Model**: Hugging Face Transformers

## 📝 Troubleshooting

### Common Issues
1. **Port occupied**: Modify port number in app.py
2. **Missing dependencies**: Run `pip install -r requirements.txt`
3. **Model loading failed**: Check network connection and model ID
4. **Data format error**: Ensure data column names and format are correct

### Log Viewing
Detailed runtime information will be displayed in the console at startup, including model status and error messages.

## 📄 License

This project follows the license terms of the original Kronos project.

## 🤝 Contributing

Welcome to submit Issues and Pull Requests to improve this Web UI!

## 📞 Support

If you have questions, please check:
1. Project documentation
2. GitHub Issues
3. Console error messages

## Kraken-compatible hourly sample

Kraken OHLC returns at most 720 entries including the unfinished candle. The app discards that candle and uses up to 719 consecutive closed hourly candles (29 days and 23 hours), with a minimum of 80. It adapts to the available history and model capacity: Mini can use 719; Small and Base use up to 512. Backtests reserve 120 known candles for comparison, so a 719-row file uses 599 context candles. Other intervals retain the 80-candle context. The future forecast remains 120 candles (5 days at 1 hour). The interface displays the actual sample size.

Public requests are serialized at most once every 1.05 seconds within the single-worker service. Closed candles are cached for at most 60 seconds, expiring at the next candle boundary; pairs are cached for 15 minutes. HTTP 429/503 responses and Kraken rate-limit/throttle errors trigger a cooldown, honoring Retry-After or a throttle timestamp when supplied. No automatic retries, pagination for unavailable OHLC history, or filling of missing candles are performed. Other applications sharing the public IP can also consume Kraken's rate allowance.

See [OHLC limits](https://docs.kraken.com/api-reference/market-data/get-ohlc-data) and [public API rate limits](https://support.kraken.com/articles/206548367-what-are-the-api-rate-limits-).
