# data_stream.py

import threading
import queue
import time
import logging
from collections import deque, defaultdict
from binance.client import Client
from binance.enums import *
from binance import ThreadedWebsocketManager
from dotenv import load_dotenv
import os

SYMBOL = 'LTCUSDT'
position = {
    "state": "none",
    "entry_order_id": None,
    "stop_order_id": None,
    "entry": None,
    "qty": 0.0,
    "max_pnl": 0.0,
    "stop_price": None
}

# --- Configuration ---
load_dotenv()
API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")
DEPTH_QPS = 100  # ms
MAX_QUEUE = 1000

client = Client(API_KEY, API_SECRET)
twm = ThreadedWebsocketManager(api_key=API_KEY, api_secret=API_SECRET)
twm.start()

# --- Shared State ---
state = {
    "order_book": {
        "depth": {
            "bids": defaultdict(float),
            "asks": defaultdict(float)
        },
        "last_update_id": 0
    },
    "trades": deque(maxlen=100),
    "volume_history": deque(maxlen=20),
    "ticker_pct": 0.0
}
lock = threading.Lock()

# --- Queues ---
depth_queue = queue.Queue(MAX_QUEUE)
trade_queue = queue.Queue(MAX_QUEUE)
aggtrade_queue = queue.Queue(MAX_QUEUE)
ticker_queue = queue.Queue(MAX_QUEUE)
command_queue = queue.Queue()  # Queue for commands to main thread

# --- WebSocket Handlers ---

def depth_handler(msg):
    if msg['e'] != 'depthUpdate':
        return
    try:
        depth_queue.put_nowait(msg)
    except queue.Full:
        logging.warning("Depth queue full, message dropped.")

def trade_handler(msg):
    try:
        trade_queue.put_nowait(msg)
    except queue.Full:
        logging.warning("Trade queue full, message dropped.")

def aggtrade_handler(msg):
    try:
        aggtrade_queue.put_nowait(msg)
    except queue.Full:
        logging.warning("AggTrade queue full, message dropped.")

def ticker_handler(msg):
    try:
        ticker_queue.put_nowait(msg)
    except queue.Full:
        logging.warning("Ticker queue full, message dropped.")

def user_handler(msg):
    with lock:
        if msg['e'] == 'ORDER_TRADE_UPDATE':
            order = msg['o']
            order_id = order['i']
            status = order['X']
            if status == 'FILLED':
                if order_id == position["entry_order_id"]:
                    side = order['S']
                    qty = float(order['z'])  # Cumulative filled quantity
                    entry_price = float(order['ap'])  # Average fill price
                    position["state"] = "long" if side == 'BUY' else "short"
                    position["entry"] = entry_price
                    position["qty"] = qty
                    position["max_pnl"] = 0.0
                    stop_price = entry_price * (1 - 0.02 if side == 'BUY' else 1 + 0.02)
                    stop_side = 'SELL' if side == 'BUY' else 'BUY'
                    command_queue.put(('place_stop_order', stop_side, qty, stop_price))
                    logging.info("Entry order %s filled: %s @ %.2f, qty=%.4f", order_id, position["state"], entry_price, qty)
                elif order_id == position["stop_order_id"]:
                    position["state"] = "none"
                    position["entry"] = None
                    position["qty"] = 0.0
                    position["max_pnl"] = 0.0
                    position["stop_price"] = None
                    position["stop_order_id"] = None
                    position["entry_order_id"] = None
                    logging.info("Stop order %s filled, position closed", order_id)

# --- Data Processors ---

def _process_depth():
    while True:
        msg = depth_queue.get()
        with lock:
            for price, qty in msg["b"]:
                state["order_book"]["depth"]["bids"][float(price)] = float(qty)
            for price, qty in msg["a"]:
                state["order_book"]["depth"]["asks"][float(price)] = float(qty)
            state["order_book"]["last_update_id"] = msg["u"]

def _process_aggtrades():
    while True:
        msg = aggtrade_queue.get()
        trade = {
            "price": float(msg["p"]),
            "qty": float(msg["q"]),
            "is_buyer_maker": msg["m"],
            "time": msg["T"],
            "side": "SELL" if msg["m"] else "BUY"
        }
        with lock:
            state["trades"].append(trade)
            _update_volumes_locked()

def _process_trades():
    while True:
        msg = trade_queue.get()
        trade = {
            "price": float(msg["p"]),
            "qty": float(msg["q"]),
            "is_buyer_maker": msg["m"],
            "time": msg["T"],
            "side": "SELL" if msg["m"] else "BUY"
        }
        with lock:
            state["trades"].append(trade)
            _update_volumes_locked()

def _update_volumes_locked():
    current_time = int(time.time() // 60) * 60
    current_volume = sum(trade["qty"] for trade in state["trades"] if trade["time"] // 1000 >= current_time)
    if state["volume_history"] and state["volume_history"][-1]["time"] == current_time:
        state["volume_history"][-1]["volume"] = current_volume
    else:
        state["volume_history"].append({"time": current_time, "volume": current_volume})

def _process_ticker():
    while True:
        msg = ticker_queue.get()
        with lock:
            state["ticker_pct"] = float(msg.get("P", 0))

# --- Initial Data Fetch ---

def fetch_initial_data():
    try:
        depth = client.get_order_book(symbol=SYMBOL, limit=100)
        trades = client.get_recent_trades(symbol=SYMBOL, limit=100)
        ticker = client.futures_ticker(symbol=SYMBOL)

        with lock:
            for bid in depth["bids"]:
                state["order_book"]["depth"]["bids"][float(bid[0])] = float(bid[1])
            for ask in depth["asks"]:
                state["order_book"]["depth"]["asks"][float(ask[0])] = float(ask[1])
            state["order_book"]["last_update_id"] = depth["lastUpdateId"]

            for t in trades:
                state["trades"].append({
                    "price": float(t["price"]),
                    "qty": float(t["qty"]),
                    "is_buyer_maker": t["isBuyerMaker"],
                    "time": t["time"],
                    "side": "SELL" if t["isBuyerMaker"] else "BUY"
                })

            _update_volumes_locked()
            state["ticker_pct"] = float(ticker.get("priceChangePercent", 0))

        logging.info("Initial data fetched.")
    except Exception as e:
        logging.error("Failed to fetch initial data: %s", e)

# --- Access Snapshot ---

def get_snapshot():
    with lock:
        return {
            "order_book": {
                "depth": {
                    "bids": dict(state["order_book"]["depth"]["bids"]),
                    "asks": dict(state["order_book"]["depth"]["asks"])
                }
            },
            "trades": list(state["trades"]),
            "volume_history": list(state["volume_history"]),
            "ticker_pct": state["ticker_pct"]
        }

# --- Start Streams ---

def start_streams():
    logging.info("Starting WebSocket streams…")
    twm.start_depth_socket(callback=depth_handler, symbol=SYMBOL, interval=DEPTH_QPS)
    twm.start_trade_socket(callback=trade_handler, symbol=SYMBOL)
    twm.start_aggtrade_socket(callback=aggtrade_handler, symbol=SYMBOL)
    twm.start_symbol_ticker_socket(callback=ticker_handler, symbol=SYMBOL)
    twm.start_futures_user_socket(callback=user_handler)

    threading.Thread(target=_process_depth, daemon=True).start()
    threading.Thread(target=_process_aggtrades, daemon=True).start()
    threading.Thread(target=_process_trades, daemon=True).start()  
    threading.Thread(target=_process_ticker, daemon=True).start()
