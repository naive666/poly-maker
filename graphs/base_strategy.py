from decimal import Decimal
from poly_data.orderbook import OrderBook
from poly_data.trade_summary import TradeSummary


class BaseStrategy:
    def __init__(self):
        self.token_id = None 
        self.bid_signal = None 
        self.ask_signal = None 
        self.bid_size_signal = None
        self.ask_size_signal = None 
        self.best_bid_price = None 
        self.best_ask_price = None 
    
    def on_snapshot(self, orderbook:OrderBook):
        pass 
    
    def on_book_change(self, price:Decimal, size:Decimal, side:str):
        pass 

    def on_trade(self, trade:TradeSummary):
        pass 

