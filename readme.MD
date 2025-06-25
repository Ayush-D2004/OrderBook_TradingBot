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
`
git clone https://github.com/your-username/OrderBook_TradingBot.git
cd OrderBook_TradingBot
`

### 2. Create Python Environment
`
python -m venv venv
venv\Scripts\activate 
pip install python-binance python-dotenv pandas numpy
`
### 3. Set up Environment Variables
Get Binance API Keys here : `https://www.binance.com/en-IN/my/settings/api-management`
Create a .env file in the project root:
`
BINANCE_API_KEY=your_api_key_here
BINANCE_API_SECRET=your_api_secret_here
`

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
