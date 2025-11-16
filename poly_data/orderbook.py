import poly_data.global_state as global_state
import time 
from datetime import datetime 

class OrderBook:
    def __init__(self, token_id):
        self.token_id = token_id
        self.bid_levels = None 
        self.ask_levels = None  
        self.update_ts = None 
    
    def update_orderbook(self):
        ob = global_state.client.get_order_book(self.token_id)
        self.bid_levels = ob[0].sort_values('price', ascending=False).reset_index(drop=True)
        self.ask_levels = ob[1].sort_values('price', ascending=True).reset_index(drop=True)
        self.update_ts = time.time()
    
    def get_price_at_i(self, i, side):
        # side: 0 is bid, 1 is ask
        if side == 0:
            if len(self.bid_levels) > i:
                return self.bid_levels['price'].iloc[i]
            else:
                # if the book is empty
                return 0
        elif side == 1:
            if len(self.ask_levels) > i:
                return self.ask_levels['price'].iloc[i] 
            else:
                return 0 
    
    def get_size_at_i(self, i, side):
        # side: 0 is bid, 1 is ask
        if side == 0:
            if len(self.bid_levels) > i:
                return self.bid_levels['size'].iloc[i]
            else:
                # if the book is empty
                return 0
        elif side == 1:
            if len(self.ask_levels) > i:
                return self.ask_levels['size'].iloc[i] 
            else:
                return 0 
