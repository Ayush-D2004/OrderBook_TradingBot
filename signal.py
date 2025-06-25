import pandas as pd
import numpy as np

# --- Indicators ---
def calculate_ema(series, span):
    return series.ewm(span=span, adjust=False).mean()

def calculate_rsi(prices, period=14):
    delta = prices.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def calculate_vwap(df):
    if df.empty:
        return None
    vwap = (df["price"] * df["qty"]).sum() / df["qty"].sum()
    return vwap

def calculate_atr(prices, period=14):
    if len(prices) < period + 1:
        return None
    highs = prices.rolling(window=2).max()
    lows = prices.rolling(window=2).min()
    close = prices
    tr = pd.concat([
        highs - lows,
        (highs - close.shift()).abs(),
        (lows - close.shift()).abs()
    ], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    return atr.iloc[-1]

# --- Metrics ---
def order_book_pressure(df):
    bid_volume = df["bid_qty"].astype(float).sum()
    ask_volume = df["ask_qty"].astype(float).sum()
    if ask_volume == 0:
        return 1
    return bid_volume / ask_volume

def trade_dominance(trades_df):
    if trades_df.empty:
        return 1
    buys = trades_df[trades_df["side"] == "BUY"]["qty"].sum()
    sells = trades_df[trades_df["side"] == "SELL"]["qty"].sum()
    if sells == 0:
        return 1
    return buys / sells

def volume_trend(volume_df):
    if volume_df.empty or "volume" not in volume_df.columns:
        return 0
    volumes = volume_df["volume"].astype(float)
    if volumes.std(ddof=0) == 0:
        return 0
    return (volumes.iloc[-1] - volumes.mean()) / volumes.std(ddof=0)

# --- Signal Logic ---
def generate_signal(df, trades_df, volume_df, ticker_data):
    if df.empty or trades_df.empty:
        return "HOLD"

    # --- Ratios ---
    ob_ratio = order_book_pressure(df)
    trade_ratio = trade_dominance(trades_df)
    volumes = volume_df["volume"].astype(float)
    ticker_pct = ticker_data.get("ticker_pct", 0)

    # --- Technical Indicators ---
    prices = trades_df["price"].astype(float).tail(100)
    ema_fast = calculate_ema(prices, 12)
    ema_slow = calculate_ema(prices, 26)
    rsi = calculate_rsi(prices, 14)
    vwap = calculate_vwap(trades_df)
    atr = calculate_atr(prices)

    latest_price = prices.iloc[-1] if not prices.empty else 0
    last_fast, last_slow = ema_fast.iloc[-1], ema_slow.iloc[-1]
    vol_score = volume_trend(volume_df)

    # --- Decision Logic --- Main parameters for real trading 

    if (
        ob_ratio > 1.3 and
        trade_ratio > 1.2 and
        vol_score > 0.5 and
        last_fast > last_slow and
        rsi.iloc[-1] < 70 and
        latest_price > vwap
    ):
        return "BUY"

    elif (
        ob_ratio < 0.7 and
        trade_ratio < 0.8 and
        vol_score < -0.5 and
        last_fast < last_slow and
        rsi.iloc[-1] > 30 and
        latest_price < vwap
    ):
        return "SELL"

    ## dummy parameters for testing if orders are being placed 
    # if (ob_ratio > 1.1 and trade_ratio > 1.05 and vol_score > 0.2 and last_fast > last_slow and rsi.iloc[-1] < 75 and latest_price > vwap ):
    #     return "BUY"
    # elif (ob_ratio < 0.9 and trade_ratio < 0.95 and vol_score < -0.2 and last_fast < last_slow and rsi.iloc[-1] > 25 and latest_price < vwap ):
    #     return "SELL"

    return "HOLD"
