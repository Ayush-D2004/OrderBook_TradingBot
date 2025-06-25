import sys
import asyncio
if sys.platform.startswith('win'):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import os
import time
import logging
from datetime import datetime, timezone
from threading import Thread

import pandas as pd
from dotenv import load_dotenv
from binance.client import Client
from binance.enums import (
    SIDE_BUY, SIDE_SELL, ORDER_TYPE_MARKET, ORDER_TYPE_STOP_LOSS
)
from data_stream import get_snapshot, start_streams, fetch_initial_data, command_queue
from signal import generate_signal

# --- Configuration ---
load_dotenv()
logging.basicConfig(
    filename="trade_log.txt",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

SYMBOL = "LTCUSDT"
LEVERAGE = 20
RISK_PER_TRADE = 0.9
INITIAL_SL = 0.02
DYNAMIC_SL = 0.02
SIGNAL_INTERVAL = 0.1
DRY_RUN = False 

API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")
client = Client(API_KEY, API_SECRET)

# --- Position State ---
position = {
    "state": "none",
    "entry_order_id": None,
    "stop_order_id": None,
    "entry": None,
    "qty": 0.0,
    "max_pnl": 0.0,
    "stop_price": None
}

# --- Helpers ---

def fetch_balance():
    try:
        info = client.futures_account()
        usdt = next(asset for asset in info["assets"] if asset["asset"] == "USDT")
        return float(usdt["availableBalance"])
    except Exception as e:
        logging.error("Futures balance fetch error: %s", e)
        return 0.0

def calc_qty(balance, price):
    risk_amount = balance * RISK_PER_TRADE
    qty = (risk_amount * LEVERAGE) / price 
    return round(qty, 3)

def set_margin_and_leverage():
    try:
        client.futures_change_margin_type(symbol=SYMBOL, marginType="ISOLATED")
        logging.info("Margin type set to ISOLATED")
    except Exception as e:
        logging.warning("Failed to set margin type: %s", e)
    try:
        client.futures_change_leverage(symbol=SYMBOL, leverage=LEVERAGE)
        logging.info("Leverage set to %dx", LEVERAGE)
    except Exception as e:
        logging.warning("Failed to set leverage: %s", e)
    # Verify current settings
    try:
        account_info = client.futures_account()
        for pos in account_info["positions"]:
            if pos["symbol"] == SYMBOL:
                logging.info("Current leverage: %s", pos["leverage"])    
                break
    except Exception as e:
        logging.error("Failed to fetch account info: %s", e)

def place_market_order(side, qty):
    if DRY_RUN:
        logging.info("[DRY RUN] Market %s %.4f %s", side, qty, SYMBOL)
        return {"status": "FILLED", "orderId": None}
    try:
        order = client.futures_create_order(
            symbol=SYMBOL,
            side=side,
            type=ORDER_TYPE_MARKET,
            quantity=qty
        )
        logging.info("Placed market order %s %.4f %s, orderId: %s", side, qty, SYMBOL, order["orderId"])
        return order
    except Exception as e:
        logging.error("Market order failed: %s", e)
        return {"status": "FAILED", "orderId": None}

def place_stop_order(side, qty, stop_price):
    if DRY_RUN:
        logging.info("[DRY RUN] Stop %s %.4f %s @ %.2f", side, qty, SYMBOL, stop_price)
        return {"orderId": 999999}
    try:
        order = client.futures_create_order(
            symbol=SYMBOL,
            side=side,
            type=ORDER_TYPE_STOP_MARKET,
            stopPrice=str(round(stop_price, 2)),
            quantity=qty,
            reduceOnly=True
        )
        logging.info("Placed stop order %s %.4f %s @ %.2f, orderId: %s", side, qty, SYMBOL, stop_price, order["orderId"])
        return order
    except Exception as e:
        logging.error("Stop order failed: %s", e)
        return {"orderId": None}

def cancel_stop_order(order_id):
    if DRY_RUN or not order_id:
        return
    try:
        client.futures_cancel_order(symbol=SYMBOL, orderId=order_id)
        logging.info("Cancelled stop-order %s", order_id)
    except Exception as e:
        logging.error("Failed to cancel stop-order %s: %s", order_id, e)

def update_trailing_stop(current_price):
    if position["state"] == "none":
        return

    entry = position["entry"]
    qty = position["qty"]
    pnl = (current_price - entry) * qty * LEVERAGE if position["state"] == "long" else (entry - current_price) * qty * LEVERAGE

    if pnl > position["max_pnl"]:
        position["max_pnl"] = pnl
        trail_pnl = pnl * (1 - DYNAMIC_SL)
        price_diff = trail_pnl / (qty * LEVERAGE)
        new_stop = entry + price_diff if position["state"] == "long" else entry - price_diff

        if new_stop != position["stop_price"]:
            cancel_stop_order(position["stop_order_id"])
            stop_side = SIDE_SELL if position["state"] == "long" else SIDE_BUY
            stop_res = place_stop_order(stop_side, qty, new_stop)
            position.update(stop_price=new_stop, stop_order_id=stop_res.get("orderId"))

def enter_position(signal, snapshot):
    price = float(client.futures_symbol_ticker(symbol=SYMBOL)["price"])
    balance = fetch_balance()
    qty = calc_qty(balance, price)

    if qty * price < 20:
        logging.error("Order notional below min threshold: %.2f", qty * price)
        return

    side = SIDE_BUY if signal == "BUY" else SIDE_SELL
    res = place_market_order(side, qty)
    if res.get("status") == "FAILED":
        logging.error("Entry order failed: %s", res)
        return

    # Store the entry order ID; position state updated via user data stream
    position["entry_order_id"] = res.get("orderId")
    logging.info("Initiated %s position, waiting for order fill confirmation", signal.lower())

def close_position(current_price):
    if position["state"] == "none":
        return
    side = SIDE_SELL if position["state"] == "long" else SIDE_BUY
    qty = position["qty"]
    res = place_market_order(side, qty)
    if res.get("status") == "FAILED":
        logging.error("Close order failed: %s", res)
        return
    cancel_stop_order(position["stop_order_id"])
    # Assume market order fills immediately for simplicity; user data stream will confirm
    logging.info("Closed %s @ %.2f qty=%.4f", position["state"], current_price, qty)
    position.update(state="none", entry=None, qty=0.0, max_pnl=0.0, stop_price=None, stop_order_id=None, entry_order_id=None)

# --- Trading Loop ---

def run_trading():
    set_margin_and_leverage()

    while True:
        # Process commands from user data stream
        while not command_queue.empty():
            command = command_queue.get()
            if command[0] == 'place_stop_order':
                _, side, qty, stop_price = command
                stop_res = place_stop_order(side, qty, stop_price)
                position["stop_price"] = stop_price
                position["stop_order_id"] = stop_res.get("orderId")

        snapshot = get_snapshot()
        order_book = snapshot.get("order_book", {}).get("depth", {})
        trades = snapshot.get("trades", [])
        volumes = snapshot.get("volume_history", [])
        ticker = {"ticker_pct": snapshot.get("ticker_pct", 0)}

        if "bids" not in order_book or "asks" not in order_book:
            logging.warning("Order book missing bids/asks. Skipping tick.")
            time.sleep(SIGNAL_INTERVAL)
            continue

        bids = list(order_book["bids"].items())
        asks = list(order_book["asks"].items())

        # Ensure same length by truncating to the shorter one
        min_len = min(len(bids), len(asks))
        bids = bids[:min_len]
        asks = asks[:min_len]


        df = pd.DataFrame({
            "price": [b[0] for b in bids],
            "bid_qty": [b[1] for b in bids],
            "ask_price": [a[0] for a in asks],
            "ask_qty": [a[1] for a in asks]
        })

        trades_df = pd.DataFrame(trades)
        volume_df = pd.DataFrame(volumes)

        signal = generate_signal(df, trades_df, volume_df, ticker)
        price = float(client.futures_symbol_ticker(symbol=SYMBOL)["price"])
        logging.info("Signal %s | Price %.2f | Position %s", signal, price, position["state"])

        if position["state"] != "none":
            update_trailing_stop(price)
            if (position["state"] == "long" and price <= position["stop_price"]) or \
               (position["state"] == "short" and price >= position["stop_price"]):
                close_position(price)

        if signal in ("BUY", "SELL") and position["state"] != signal.lower():
            close_position(price)
            enter_position(signal, snapshot)

        time.sleep(SIGNAL_INTERVAL)

# --- Entry Point ---
if __name__ == "__main__":
    fetch_initial_data()
    start_streams()
    Thread(target=run_trading, daemon=True).start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        last_price = float(client.futures_symbol_ticker(symbol=SYMBOL)["price"])
        close_position(last_price)
        logging.info("Bot shutdown at %s", datetime.now(timezone.utc))