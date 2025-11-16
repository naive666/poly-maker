from graphs.base_strategy import BaseStrategy
import poly_data.global_state as global_state
from placements.order_manager import Order, OrderManager
import time 
from dateutil.parser import isoparse
from datetime import datetime
from py_clob_client.clob_types import TradeParams
from zoneinfo import ZoneInfo
from placements.base_placements import BasePlacement


class Placement01(BasePlacement):
    def __init__(self, token0_id, token1_id, conditional_id, strategy, exe_config, position_update_time_thred, order_manager):
        super().__init__(token0_id, token1_id, conditional_id,  strategy, exe_config, position_update_time_thred, order_manager)
        
        
    def evaluate_strategy(self):
        self.strategy.evaluate()
        self.bid_submit_price, self.ask_submit_price = self.strategy.bid_signal, self.strategy.ask_signal
        self.bid_leave_price = self.bid_submit_price - self.config['quote_NLevel'] * self.tick_size
        self.ask_leave_price = self.ask_submit_price + self.config['quote_NLevel'] * self.tick_size
        self.bid_size, self.ask_size = self.strategy.bid_size_signal, self.strategy.ask_size_signal

    def check_game_status(self):
        game_start_time = global_state.df[global_state.df['condition_id'] == self.conditional_id]['gameStartTime'].iloc[0]
        local_tz = ZoneInfo("America/New_York")   # your local timezone
        utc_tz   = ZoneInfo("UTC")
        local_now = datetime.now(local_tz)
        utc_now = local_now.astimezone(utc_tz)
        time_diff = isoparse(game_start_time) - utc_now
        if (time_diff.total_seconds() > 60 and time_diff.total_seconds() <= 48 * 3600):
            self.is_game_status = True 
            print(f"Check game status success")
        else:
            self.is_game_status = False 
            print(f"Check game status fail")

    def check_max_position(self):
        ok_process_bid, ok_process_ask = False, False
        if not self.token0_id in self.asset_pos_dict:
            ok_process_bid = True
        else:
            pos0 = self.asset_pos_dict[self.token0_id]['size']
            if pos0 + self.bid_size <= self.config['max_pos']:
                ok_process_bid = True
                print(f"check {self.token0_id} max pos success")
            elif pos0 < self.config['max_pos']:
                ok_process_bid = True 
                self.bid_size = self.config['max_pos'] - pos0 
                print(f"check {self.token0_id} max pos success")
            else:
                ok_process_bid = False
                print(f"check {self.token0_id} max pos fail")
        if not self.token1_id in self.asset_pos_dict:
            ok_process_ask = True 
        else:
            pos1 = self.asset_pos_dict[self.token1_id]['size']
            if pos1 + self.ask_size <= self.config['max_pos']:
                ok_process_ask = True
                print(f"check {self.token0_id} max pos success")
            elif pos1 < self.config['max_pos']:
                ok_process_ask = True 
                self.ask_size = self.config['max_pos'] - pos1 
                print(f"check {self.token0_id} max pos success")
            else:
                ok_process_ask = False
                print(f"check {self.token0_id} max pos fail")
        return ok_process_bid, ok_process_ask
    
    def check_available_fund(self, price, size):
        ok_process = False
        # get current available margin
        cash_balance = global_state.client.get_usdc_balance()
        total_balance = global_state.client.get_total_balance()
        quote_cash = price * size
        if quote_cash < total_balance * self.config['single_pos_percent'] and quote_cash < cash_balance:
            print("Check available fund success")
            ok_process = True 
        else:
            print("Check available fund fail")
            ok_process = False 
        return ok_process
    
    def check_pnl(self):
        ok_process_ask, ok_process_bid = True, True
        if self.token0_id in self.asset_pos_dict and self.token1_id not in self.asset_pos_dict:
            pos_dict = self.asset_pos_dict[self.token0_id]
            initial_value = pos_dict['initialValue']
            current_value = pos_dict['currentValue']
            if (current_value - initial_value) < -self.config['maxloss']:
                ok_process_ask, ok_process_bid = False, False
                self.is_game_status = False
                print(f"{self.token0_id} has reached maxloss")
            else:
                ok_process_ask, ok_process_bid = True, True
                print(f"{self.token0_id} has not reached maxloss")

        if self.token1_id in self.asset_pos_dict and self.token0_id not in self.asset_pos_dict:
            pos_dict = self.asset_pos_dict[self.token1_id]
            initial_value = pos_dict['initialValue']
            current_value = pos_dict['currentValue']
            if (current_value - initial_value) < -self.config['maxloss']:
                ok_process_ask, ok_process_bid = False, False
                self.is_game_status = False  
                print(f"{self.token1_id} has reached maxloss")
            else:
                ok_process_ask, ok_process_bid = True, True
                print(f"{self.token1_id} has not reached maxloss")
        
        return ok_process_bid, ok_process_ask
    



        
        