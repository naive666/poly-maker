from graphs.base_strategy import BaseStrategy
from poly_data.orderbook import OrderBook 
import time 
from datetime import datetime 
import asyncio
from typing import Dict
from decimal import Decimal


class strategy_202511(BaseStrategy):
    def __init__(self, token_id:str, order_size:Decimal, bbo_size_thred:Decimal, bbo_gap_thred:int, update_period:int, max_level_thred:int):
        super().__init__()
        self.orderbook:OrderBook = OrderBook(token_id)
        self.token_id:str = token_id
        self.order_size:Decimal = order_size
        self.bbo_size_thred:Decimal = bbo_size_thred
        self.bbo_gap_thred:int = bbo_gap_thred
        self.update_period:int = update_period # evaluate every N seconds 
        self.last_eval_time:Decimal = None 
        self.max_level_thred:int = max_level_thred

    def on_snapshot(self, orderbook:OrderBook):
        self.bid_signal, self.ask_signal, self.best_bid_price, self.best_ask_price = self.compute_signal(orderbook) 
        self.bid_size_signal, self.ask_size_signal = self.order_size, self.order_size
 


    def get_effective_bbo(self, orderbook:OrderBook):
        # bid_cum_size = 0
        # ask_cum_size = 0
        eff_best_bid_price = 0
        eff_best_ask_price = 0
        best_bid_price = orderbook.get_price_at_i(0, 0)
        best_ask_price = orderbook.get_price_at_i(0, 1)

        for i in range(self.max_level_thred):
            bid_price_i = orderbook.get_price_at_i(i, 0)
            bid_size_i = orderbook.get_size_at_i(i, 0)
            # bid_cum_size += bid_size_i
            if bid_size_i >= self.bbo_size_thred:
                eff_best_bid_price = bid_price_i
                break 
        
        for i in range(self.max_level_thred):
            ask_price_i = orderbook.get_price_at_i(i, 1)
            ask_size_i = orderbook.get_size_at_i(i, 1)
            # ask_cum_size += ask_size_i
            if ask_size_i >= self.bbo_size_thred:
                eff_best_ask_price = ask_price_i
                break
            
        return eff_best_bid_price, eff_best_ask_price, best_bid_price, best_ask_price

    def compute_signal(self, orderbook:OrderBook):
        # get the effective best bid and best ask
        eff_best_bid_price, eff_best_ask_price, best_bid_price, best_ask_price = self.get_effective_bbo(orderbook)
        # if eff_best_bid and effect_best_ask has gap larger than 3
        if (eff_best_ask_price - eff_best_bid_price) <= self.bbo_gap_thred: # should be larger than 3, for debug purpose here
            bid_signal = eff_best_bid_price
            ask_signal = eff_best_ask_price
        else:
            bid_signal = 0
            ask_signal = 0
        return bid_signal, ask_signal, best_bid_price, best_ask_price