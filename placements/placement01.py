from graphs.base_strategy import BaseStrategy
import poly_data.global_state as global_state
from placements.order_manager import Order, OrderManager
import time 
from datetime import datetime
from py_clob_client.clob_types import TradeParams
from zoneinfo import ZoneInfo
from placements.base_placements import BasePlacement


class Placement01(BasePlacement):
    def __init__(self, token0_id, token1_id, conditional_id, strategy, exe_config, position_update_time_thred, order_manager):
        super.__init__(self, token0_id, token1_id, conditional_id,  strategy, exe_config, position_update_time_thred, order_manager)
        self.tick_size = global_state.df[global_state.df['condition_id'] == conditional_id]['tick_size']
        
    def evaluate_strategy(self):
        self.strategy.evaluate()
        self.bid_submit_price, self.ask_submit_price = self.strategy.bid_signal, self.strategy.ask_signal
        self.bid_leave_price = self.bid_submit_price - self.config['quote_NLevel'] * self.tick_size
        self.ask_leave_price = self.ask_submit_price + self.config['quote_NLevel'] * self.tick_size
        self.bid_size, self.ask_size = self.strategy.bid_size_signal, self.strategy.ask_size_signal

    def check_game_status(self):
        game_start_time = global_state.df[global_state.df['condition_id'] == self.conditional_id]['gameStartTime']
        local_tz = ZoneInfo("America/New_York")   # your local timezone
        utc_tz   = ZoneInfo("UTC")
        local_now = datetime.now(local_tz)
        utc_now = local_now.astimezone(utc_tz)
        time_diff = game_start_time - utc_now
        if (time_diff.total_seconds() > 60 and time_diff <= 48 * 3600):
            self.is_game_status = True 
        else:
            self.is_game_status = False 

    def check_max_position(self):
        ok_process_bid, ok_process_ask = False, False
        pos0 = self.asset_pos_dict[self.token0_id]['size']
        pos1 = self.asset_pos_dict[self.token1_id]['size']
        if pos0 + self.bid_size <= self.config['max_pos']:
            ok_process_bid = True
        elif pos0 < self.config['max_pos']:
            ok_process_bid = True 
            self.bid_size = self.config['max_pos'] - pos0 
        else:
            ok_process_bid = False

        if pos1 + self.ask_size <= self.config['max_pos']:
            ok_process_ask = True
        elif pos1 < self.config['max_pos']:
            ok_process_ask = True 
            self.ask_size = self.config['max_pos'] - pos1 
        else:
            ok_process_ask = False
        return ok_process_bid, ok_process_ask
    
    def check_available_fund(self, bid_price, bid_size, ask_price, ask_size):
        ok_process_bid, ok_process_ask = False
        # get current available margin
        cash_balance = global_state.client.get_usdc_balance()
        quote_bid_cash = bid_price * bid_size
        quote_ask_cash = ask_price * ask_size 
        if quote_bid_cash + quote_ask_cash < cash_balance:
            ok_process_ask = True 
            ok_process_bid = True 
        else:
            ok_process_ask = False
            ok_process_bid = False
        return ok_process_bid, ok_process_ask
    
    def check_pnl(self):
        ok_process_ask, ok_process_bid = False, False
        if self.token0_id in self.asset_pos_dict and self.token1_id not in self.asset_pos_dict:
            pos_dict = self.asset_pos_dict[self.token0_id]
            initial_value = pos_dict['initialValue']
            current_value = pos_dict['currentValue']
            if (current_value - initial_value) / self.tick_size < -self.config['maxloss']:
                ok_process_ask, ok_process_bid = False, False
                self.is_game_status = False
            else:
                ok_process_ask, ok_process_bid = True, True

        if self.token1_id in self.asset_pos_dict and self.token0_id not in self.asset_pos_dict:
            pos_dict = self.asset_pos_dict[self.token1_id]
            initial_value = pos_dict['initialValue']
            current_value = pos_dict['currentValue']
            if (current_value - initial_value) / self.tick_size < -self.config['maxloss']:
                ok_process_ask, ok_process_bid = False, False
                self.is_game_status = False  
            else:
                ok_process_ask, ok_process_bid = True, True
        return ok_process_bid, ok_process_ask
    
    def check_pending_order(self):
        pass 
        
        