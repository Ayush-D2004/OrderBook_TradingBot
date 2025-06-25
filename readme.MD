# 🔥 Binance Futures Order Book Based Trading Bot

A real-time cryptocurrency trading bot built for Binance Futures using Python.  
The bot leverages order book depth, trade flow, technical indicators, and volume patterns to make automated trading decisions for assets like `LTCUSDT`.

---

## 📌 Features

- **Live Data Streaming** via Binance WebSockets (depth, trades, tickers, user data)
- **Custom Signal Engine** using:
  - Order Book Pressure
  - Trade Dominance Ratio
  - Volume Trend Z-Score
  - Exponential Moving Averages (EMA-12, EMA-26)
  - Relative Strength Index (RSI)
  - VWAP comparison
- **Real-time Execution** of Market and Stop-Market Orders
- **Risk Management**:
  - Configurable leverage
  - Dynamic trailing stop-loss
  - Dry-run mode for safe testing
- **State Tracking**:
  - Trade logs
  - Position tracking
  - Volume history and price signal evaluation

---

## 📊 Metrics & Signals Used

| Metric | Description |
|--------|-------------|
| **Order Book Pressure** | Bid volume / Ask volume; gauges buying interest |
| **Trade Dominance** | Ratio of aggressive buy volume to sell volume |
| **Volume Z-Score** | Measures whether volume is significantly above average |
| **EMA Crossover** | Fast EMA > Slow EMA indicates bullish momentum |
| **RSI** | Determines overbought/oversold conditions |
| **VWAP Comparison** | Helps confirm price position relative to weighted average |

---

## 🚀 Setup & Installation

### 1. Clone the Repo

```bash
git clone https://github.com/your-username/binance-orderbook-bot.git
cd binance-orderbook-bot

2. Create Python Environment
bash
Copy
Edit
python -m venv venv
source venv/bin/activate   # or venv\Scripts\activate on Windows
pip install -r requirements.txt
3. Set up Environment Variables
Create a .env file in the project root:

env
Copy
Edit
BINANCE_API_KEY=your_api_key_here
BINANCE_API_SECRET=your_api_secret_here
4. Get Binance API Keys
Go to Binance API Management

Create a new API key

Enable Futures permissions

Copy the key & secret into your .env

⚙️ Configuration Options
Inside main.py:

Variable	Description
SYMBOL	The trading pair (e.g., LTCUSDT)
LEVERAGE	Futures leverage used (default 15x)
DRY_RUN	Set to True for simulation mode
INITIAL_SL	Initial stop loss %
DYNAMIC_SL	Trailing stop loss trigger
RISK_PER_TRADE	Risk per trade (optional if using full balance)

🧠 How It Works
Streams live order book, trade and ticker data via Binance WebSocket

Processes incoming data in real-time threads

Calculates metrics and indicators

Generates BUY, SELL, or HOLD signal

If signal is triggered, places a market order and dynamically manages stop-loss

Logs everything in trade_log.txt

✅ Example Log Entry
pgsql
Copy
Edit
2025-06-23 15:02:01 - INFO - Signal BUY | Price 82.40 | Position none
2025-06-23 15:02:01 - INFO - [DRY RUN] Market BUY 0.220 LTCUSDT
2025-06-23 15:02:03 - INFO - [DRY RUN] Stop SELL 0.220 LTCUSDT @ 80.12
🛡 Safety Notes
Use DRY_RUN mode for initial testing.

Ensure your account has sufficient balance and margin enabled.

Run the bot on low leverage or testnet first to verify logic.

📈 Coming Enhancements (Suggestions)
Backtesting engine integration

Web dashboard with signal visualization

Multi-symbol support and strategy switching

Logging to database or cloud dashboard

👨‍💻 Author
Ayush
Student & Developer
Open to internships, freelance, or collaboration in Algo/Quant/Crypto systems
Feel free to fork or reach out!

📜 License
MIT License – use freely, but at your own risk.

yaml
Copy
Edit

---

## 🧩 Notes

- Add a `requirements.txt` with:
python-binance
python-dotenv
pandas
numpy