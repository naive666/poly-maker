from graphs.base_strategy import BaseStrategy
import poly_data.global_state as global_state
from placements.order_manager import Order, OrderManager
from poly_data.utils import parse_polymarket_time
import time, asyncio
import pandas as pd 
from typing import Dict
from datetime import datetime
from decimal import Decimal
from py_clob_client.clob_types import TradeParams
import logging
logger = logging.getLogger("polymarket_bot")

class BasePlacement:
    def __init__(self, token0_id:str, token1_id:str, conditional_id:str, strategy:BaseStrategy, exe_config:Dict, position_update_time_thred:Decimal, 
                 order_manager:OrderManager, min_valid_hour:int=3, max_valid_hour:int=48, game_start_time:str=None):
        self.tick_size:Decimal = Decimal(global_state.df[global_state.df['condition_id'] == conditional_id]['tick_size'].iloc[0])
        self.token0_id:str = token0_id
        self.token1_id:str = token1_id 
        self.conditional_id:str = conditional_id
        self.config:Dict = exe_config
        self.strategy:BaseStrategy = strategy
        self.om:OrderManager = order_manager
        self.is_game_status:bool = False 
        self.is_max_loss:bool = False
        self.is_pnl:bool = False  
        self.position_update_time_thred:Decimal = position_update_time_thred 
        self.bid_submit_price: Decimal = None  
        self.ask_submit_price:Decimal =  None
        self.bid_leave_price:Decimal = None  
        self.ask_leave_price:Decimal = None
        self.best_bid_price:Decimal = None 
        self.best_ask_price:Decimal = None 
        self.bid_size:Decimal = 0 
        self.ask_size:Decimal = 0
        self.ok_process_bid:bool = False 
        self.ok_process_ask:bool = False 
        self.asset_pos_dict:Dict[str, Dict[str, Decimal]] = {}
        self.lock:asyncio.Lock = global_state.lock[self.conditional_id]
        self.eval_cnt:int = 0
        self.market = global_state.market_token_info[self.conditional_id][2]
        self.min_valid_hour = min_valid_hour
        self.max_valid_hour = max_valid_hour
        self.game_start_time = game_start_time 
        if self.game_start_time is not None:
            self.game_start_time = parse_polymarket_time(self.game_start_time)
        # self.last_update_time = 0
    
    def check_valid_price(self, price:int):
        ok_to_process = True 
        if price < 5 or price > 95:
            ok_to_process = False 
        return ok_to_process

    def check_pending_order(self, price:int, side:int):
        price = round(price)  # price is in tick space
        ok_pending_order_bid, ok_pending_order_ask = True, True
        if side == 0:
            if price in self.om.token0_order_dict:
                if len(self.om.token0_order_dict[price]) >= 1:
                    ok_pending_order_bid = False
                    log_str = f"Check Pending Order for: {self.market} token 0 at price: {price}, pending order: {len(self.om.token0_order_dict[price])}"
                    print(log_str)
                    logger.info(log_str)
        elif side == 1:
            if price in self.om.token1_order_dict:
                if len(self.om.token1_order_dict[price]) >= 1:
                    ok_pending_order_ask = False
                    log_str = f"Check Pending Order for: {self.market} token 1 at price: {price}, pending order: {len(self.om.token1_order_dict[price])}"
                    print(log_str)
                    logger.info(log_str)
        return ok_pending_order_bid, ok_pending_order_ask
    
    def update_single_pending_order(self, row, order_dict):
        price = round(Decimal(row['price']) / self.tick_size)
        if price in order_dict:
            log_str = f"Update pending order for {self.market} token 0"
            print(log_str)
            logger.info(log_str)
            order_list = order_dict[price]
            for o in order_list:
                if o.order_id == row['id']:
                    o.fill_size = row['size_matched']
                    o.pending_size = row['original_size'] - o.fill_size 
        else:
            # in case we have to reconnect and lose all local info
            order = Order(token_id=self.token0_id, price=price, tick_size=self.tick_size, size=self.bid_size, 
                        side=0, create_time=row['created_at'], market=self.market)
            order.order_id = row['id']
            self.om.add_order(order)
            log_str = f"Reconnect, update pending order for {self.market} token 0"
            print(log_str)
            logger.info(log_str)

    def update_pending_orders(self):
        order_df = global_state.client.get_market_orders(self.conditional_id)
        # update pending orders
        # if both have pending orders
        if len(order_df) > 1:
            for idx, row in order_df.iterrows():
                if row['asset_id'] == self.token0_id:
                    self.update_single_pending_order(row, self.om.token0_order_dict)
                if row['asset_id'] == self.token1_id:
                    self.update_single_pending_order(row, self.om.token1_order_dict)
        else:
            for idx, row in order_df.iterrows():
                if row['asset_id'] == self.token0_id:
                    self.update_single_pending_order(row, self.om.token0_order_dict)
                    self.om.token1_order_dict = {}
                    self.om.token1_order_cnt = 0
                if row['asset_id'] == self.token1_id:
                    self.update_single_pending_order(row, self.om.token1_order_dict)
                    self.om.token0_order_dict = {}
                    self.om.token0_order_cnt = 0
        return order_df
    
    def get_position(self, token_id:str):
        pos_df = pd.DataFrame()                 
        global_state.position_update_time = datetime.now()
        pos_all = global_state.client.get_all_positions()         
        if len(pos_all) > 0:
            pos_df = pos_all[pos_all['asset'] == token_id]
            size = Decimal(str(pos_df['size'].values[0]))
            avg_price = Decimal(str(pos_df['avgPrice'].values[0]))
            cashPnl = Decimal(str(pos_df['cashPnl'].values[0]))
            initial_value = Decimal(str(pos_df['initialValue'].values[0]))
            current_value = Decimal(str(pos_df['currentValue'].values[0]))
            if token_id == self.token0_id:
                log_str = f"Get Position for {self.market} token 0, size: {size}, avg_price: {avg_price}"
                print(log_str)
                logger.info(log_str)
            elif token_id == self.token1_id:
                log_str = f"Get Position for {self.market} token 1, size: {size}, avg_price: {avg_price}"
                print(log_str)
                logger.info(log_str)

            pos_dict = {'size': size, 'avg_price': avg_price, 'cashPnl': cashPnl, 'initialValue': initial_value, 'currentValue': current_value}
            self.asset_pos_dict[token_id] = pos_dict 


    async def run_strategy(self):
        self.eval_cnt += 1
        if self.eval_cnt % 100 == 1:
            self.update_pending_orders()
            self.get_position(self.token0_id)
            self.get_position(self.token1_id)
            self.check_game_status()
            self.evaluate_strategy()
            # self.merge()
            if self.bid_submit_price is None or self.ask_submit_price is None:
                return 
            ok_bid_maxpos, ok_ask_maxpos = self.check_max_position()
            ok_bid_pnl, ok_ask_pnl = self.check_pnl()
            bid_submit_price_tick, ask_submit_price_tick = round(self.bid_submit_price / self.tick_size), round(self.ask_submit_price / self.tick_size)
            bid_leave_price_tick, ask_leave_price_tick = round(self.bid_leave_price / self.tick_size), round(self.ask_leave_price / self.tick_size)
            best_bid_price_tick, best_ask_price_tick = round(self.best_bid_price / self.tick_size), round(self.best_ask_price / self.tick_size )
            # cancel orders inner than submit price
            self.cancel_order_between_price(bid_submit_price_tick+1, best_bid_price_tick, 0)
            self.cancel_order_between_price(best_ask_price_tick, ask_submit_price_tick-1, 1)
            for i in range(bid_submit_price_tick, bid_leave_price_tick, -1):
                ok_bid_fund = self.check_available_fund(self.tick_size*i, self.bid_size)
                ok_bid_pending, _ = self.check_pending_order(i, 0)
                if ok_bid_fund and ok_bid_maxpos and ok_bid_pnl and ok_bid_pending: 
                    token0_buy_order = Order(token_id=self.token0_id, price=i, tick_size=self.tick_size, size=self.bid_size, 
                                            side=0, create_time=datetime.now(), market=self.market)
                    # if signal changes, we need to change the order
                    self.cancel_invalid_order(0)
                    self.send_buy_order(token0_buy_order)
            for i in range(ask_submit_price_tick, ask_leave_price_tick, 1):
                ok_ask_fund = self.check_available_fund(self.tick_size*i, self.ask_size)
                _, ok_ask_pending = self.check_pending_order(i, 1)
                if ok_ask_fund and ok_ask_maxpos and ok_ask_pnl and ok_ask_pending: 
                    token1_buy_order = Order(token_id=self.token1_id, price=i, tick_size=self.tick_size, size=self.ask_size, 
                                            side=1, create_time=datetime.now(), market=self.market)
                    self.cancel_invalid_order(1)
                    self.send_buy_order(token1_buy_order)

    
    def evaluate_strategy(self):
        pass 

    def check_pnl(self):
        pass 

    def check_max_position(self):
        pass 

    def check_game_status(self):
        pass 

    def check_available_fund(self, price:Decimal, size:Decimal):
        pass 

    def send_buy_order(self, order:Order):
        """
        Create a BUY order for a specific token.
        """
        client = global_state.client
        # iterate over all orders to decide place new order or not
        if self.is_game_status == False:
            return 
        
        # Only place orders with prices between 0.1 and 0.9 to avoid extreme positions
        log_str = f"Create Buy Order for {order.market}, size: {order.pending_size}, price: {order.price}"
        print(log_str)
        logger.info(log_str)
        order_id = client.create_order(
            order.token_id, 
            'BUY', 
            float(order.price * order.tick_size), 
            float(order.pending_size)
        )
        if len(order_id) > 0:
            order.order_id = order_id['orderID']
            self.om.add_order(order)

        return order_id


    def send_sell_order(self, order:Order):
        """
        Create a sell order for a specific token.
        sell order equals to buy token1
        """
        client = global_state.client
        # iterate over all orders to decide place new order or not
        if self.is_game_status == False:
            return
        
        # Only place orders with prices between 0.1 and 0.9 to avoid extreme positions
        log_str = f"Create Sell Order for {order.market}, size: {order.pending_size}, price: {order.price}"
        print(log_str)
        logger.info(log_str)
        order_id = client.create_order(
            order.token_id, 
            'SELL', 
            float(order.price * order.tick_size), 
            float(order.pending_size)
        )
        if len(order_id) > 0:
            order.order_id = order_id['orderID']
            self.om.add_order(order)
        
        return order_id
    
    def cancel_all_asset(self, asset:str):
        # cancel all pending orders
        global_state.client.cancel_all_asset(asset)

    def cancel_all_market(self, market:str):
        global_state.client.cancel_all_market(market)
    

    def cancel_order_between_price(self, price_lower:int, price_higher:int, side:int):
        for p in range(price_lower, price_higher+1):
            self.cancel_order_by_price(p, side)

            

    def cancel_order_by_price(self, price: int, side: int):
        if side == 0:
            if price in self.om.token0_order_dict:
                order_list = self.om.token0_order_dict[price]
                for o in order_list:
                    log_str = f"Cancel Order for {self.market}, price: {o.price}"
                    print(log_str)
                    logger.info(log_str)
                    global_state.client.cancel_order(o.order_id)
                    self.om.delete_order(o.order_id, price, side)
        elif side == 1:
            if price in self.om.token1_order_dict:
                order_list = self.om.token1_order_dict[price]
                for o in order_list:
                    log_str = f"Cancel Order for {self.market}, price: {o.price}"
                    print(log_str)
                    logger.info(log_str)
                    global_state.client.cancel_order(o.order_id)
                    self.om.delete_order(o.order_id, price, side)


    def cancel_invalid_order(self, side:int):
        if side == 0:
            for prc, order_list in self.om.token0_order_dict.items():
                if prc < round(self.bid_leave_price / self.tick_size) or prc > round(self.bid_submit_price / self.tick_size):
                    for o in order_list:
                        log_str = f"Cancel Order for {self.market}, price: {o.price}"
                        print(log_str)
                        logger.info(log_str)
                        global_state.client.cancel_order(o.order_id)
                        self.om.delete_order(o.order_id, prc, side)
                        
        elif side == 1:
            for prc, order_list in self.om.token1_order_dict.items():
                if prc > round(self.ask_leave_price / self.tick_size) or prc < round(self.ask_submit_price / self.tick_size):
                    for o in order_list:
                        log_str = f"Cancel Order for {self.market}, price: {o.price}"
                        print(log_str)
                        logger.info(log_str)
                        global_state.client.cancel_order(o.order_id)
                        self.om.delete_order(o.order_id, prc, side)


    def merge(self):
        if self.token0_id in self.asset_pos_dict and self.token1_id in self.asset_pos_dict:
            pos0 = self.asset_pos_dict[self.token0_id]['size']
            pos1 = self.asset_pos_dict[self.token1_id]['size']
            if pos0 < pos1:
                global_state.client.merge_positions(pos0, self.conditional_id, False)
                del self.asset_pos_dict[self.token0_id]
                print(f"Merge {pos0}, {self.token0_id} has pos 0, {self.token1_id} has pos {pos1 - pos0}")
            elif pos0 > pos1:
                global_state.client.merge_positions(pos1, self.conditional_id, False)
                del self.asset_pos_dict[self.token1_id]
                print(f"Merge {pos1}, {self.token1_id} has pos 0, {self.token0_id} has pos {pos0 - pos1}")
            else:
                global_state.client.merge_positions(pos0, self.conditional_id, False)
                del self.asset_pos_dict[self.token0_id]
                del self.asset_pos_dict[self.token1_id]
                print(f"Merge {pos1}, {self.token1_id} has pos 0, {self.token0_id} has pos {pos0 - pos1}")