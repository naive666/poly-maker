import threading
import pandas as pd
from typing import Dict
from poly_data.orderbook import OrderBook
from graphs.base_strategy import BaseStrategy
from placements.base_placements import BasePlacement

# ============ Market Data ============

# List of all tokens being tracked
all_tokens = []

# Mapping between tokens in the same market (YES->NO, NO->YES)
REVERSE_TOKENS = {}  

# Order book data for all markets
orderbook_data: Dict[str, OrderBook] = {}  # token_id: orderbook

# Market configuration data from Google Sheets
df = None  

# ============ Client & Parameters ============

# Polymarket client instance
client = None

# Trading parameters from Google Sheets
params = {}

# Lock for thread-safe trading operations, {conditiion_id: lock}
lock = {}

# ============ Trading State ============

# Tracks trades that have been matched but not yet mined
# Format: {"token_side": {trade_id1, trade_id2, ...}}
performing = {}

# Timestamps for when trades were added to performing
# Used to clear stale trades
performing_timestamps = {}

# Timestamps for when positions were last updated
last_trade_update = {}

# Current open orders for each token
# Format: {token_id: {'buy': {price, size}, 'sell': {price, size}}}
orders = {}

# Current positions for each token
# Format: {token_id: {'size': float, 'avgPrice': float, 'market': str}}
positions = {}
position_update_time = None 

# strategy dict, key is conditional_id, value is a list consisting of all strategy
strategy_dict: Dict[str, list[BasePlacement]] = {}
strategy_list_all: list[BasePlacement] = []

# market token map
market_token_info: Dict[str, list[str]] = {}  # {conditional_id: [token_id1, token_id2]}
