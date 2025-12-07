from graphs.base_strategy import BaseStrategy
import poly_data.global_state as global_state
from placements.order_manager import Order, OrderManager
import time 
import pandas as pd 
from decimal import Decimal
from dateutil.parser import isoparse
from datetime import datetime, timedelta, timezone
from py_clob_client.clob_types import TradeParams
from zoneinfo import ZoneInfo
from threading import Timer
from telegram_bot.game_start_alerts import send_position_check
from placements.base_placements import BasePlacement
import logging
logger = logging.getLogger("polymarket_bot")


class PlacementOneSide(BasePlacement):
    def __init__(self, token0_id, token1_id, conditional_id, strategy, exe_config, position_update_time_thred, order_manager, min_valid_hour, max_valid_hour, game_start_time):
        super().__init__(token0_id, token1_id, conditional_id, strategy, exe_config, position_update_time_thred, order_manager, min_valid_hour, max_valid_hour, game_start_time)
        
        
    def evaluate_strategy(self):
        if self.strategy.bid_signal is None or self.strategy.ask_signal is None:
            return
        self.bid_submit_price, self.ask_submit_price = self.strategy.bid_signal, self.strategy.ask_signal
        self.bid_leave_price = self.bid_submit_price - self.config['quote_NLevel'] * self.tick_size
        self.ask_leave_price = self.ask_submit_price + self.config['quote_NLevel'] * self.tick_size
        self.bid_size, self.ask_size = self.strategy.bid_size_signal, self.strategy.ask_size_signal
        self.best_bid_price, self.best_ask_price = self.strategy.best_bid_price, self.strategy.best_ask_price

    def check_game_status(self):
        game_start_time = global_state.df[global_state.df['condition_id'] == self.conditional_id]['gameStartTime'].iloc[0]
        local_tz = ZoneInfo("America/New_York")   # your local timezone
        utc_tz   = ZoneInfo("UTC")
        local_now = datetime.now(local_tz)
        utc_now = local_now.astimezone(utc_tz)
        time_diff = isoparse(game_start_time) - utc_now
        if (time_diff > timedelta(hours=self.min_valid_hour) and time_diff <= timedelta(hours=self.max_valid_hour)):
            self.is_game_status = True 
            log_str = f"Check game {self.market} status success"
            print(log_str)
            logger.info(log_str)
        else:
            self.is_game_status = False 
            log_str = f"Check game {self.market} status success"
            print(log_str)
            logger.info(log_str)

    def check_max_position(self):
        ok_process_bid, ok_process_ask = False, False
        if not self.token0_id in self.asset_pos_dict:
            ok_process_bid = True
            ok_process_ask = False
        else:
            pos0 = Decimal(self.asset_pos_dict[self.token0_id]['size'])
            if pos0 + self.bid_size <= self.config['max_pos']:
                ok_process_bid = True
                ok_process_ask = True
                log_str = f"Check {self.market} max position: pos 0: {pos0}, max pos: {self.config['max_pos']}, place full order"
                print(log_str)
                logger.info(log_str)
            elif pos0 < self.config['max_pos']:
                ok_process_bid = True 
                ok_process_ask = True
                self.bid_size = self.config['max_pos'] - pos0 
                log_str = f"Check {self.market} max position: pos 0: {pos0}, max pos: {self.config['max_pos']}, place partial order"
                print(log_str)
                logger.info(log_str)
            else:
                ok_process_bid = False
                ok_process_ask = True
                log_str = f"Check {self.market} max position: pos 0: {pos0}, max pos: {self.config['max_pos']}, place no order"
                print(log_str)
                logger.info(log_str)
        
        return ok_process_bid, ok_process_ask
    
    def check_available_fund(self, price:Decimal, size:Decimal):
        ok_process = False
        # get current available margin
        cash_balance = Decimal(global_state.client.get_usdc_balance())
        total_balance = Decimal(global_state.client.get_total_balance())
        quote_cash = price * size
        if quote_cash < total_balance * self.config['single_pos_percent'] and quote_cash < cash_balance:
            log_str = f"Check {self.market} availabel fund: cash balance: {cash_balance}, total_balance: {total_balance}, fund sufficient"
            print(log_str)
            logger.info(log_str)
            ok_process = True 
        else:
            log_str = f"Check {self.market} availabel fund: cash balance: {cash_balance}, total_balance: {total_balance}, fund insufficient"
            print(log_str)
            logger.info(log_str)
            ok_process = False 
        return ok_process
    
    def check_pnl(self):
        ok_process_ask, ok_process_bid = True, True
        if self.token0_id in self.asset_pos_dict:
            pos_dict = self.asset_pos_dict[self.token0_id]
            initial_value = pos_dict['initialValue']
            current_value = pos_dict['currentValue']
            if (current_value - initial_value) < -self.config['maxloss']:
                ok_process_ask, ok_process_bid = True, False
                # liqudate ASAP
                self.ask_submit_price = self.bid_submit_price - 10 
                self.is_game_status = False
                log_str = f"Check {self.market} pnl success: intial_value: {initial_value}, current_value: {current_value}, pnl: {current_value - initial_value}, maxloss: {self.config['maxloss']}"
                print(log_str)
                logger.info(log_str)
            else:
                ok_process_ask, ok_process_bid = True, True
                log_str = f"Check {self.market} pnl fail: intial_value: {initial_value}, current_value: {current_value}, pnl: {current_value - initial_value}, maxloss: {self.config['maxloss']}"
                print(log_str)
                logger.info(log_str)
        
        return ok_process_bid, ok_process_ask
    

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
        elif side == 1: # store sell order for token1
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
                if row['side'] == "BUY":
                    self.update_single_pending_order(row, self.om.token0_order_dict)
                if row['side'] == "SELL":
                    self.update_single_pending_order(row, self.om.token1_order_dict)
        else:
            for idx, row in order_df.iterrows():
                if row['side'] == "BUY":
                    self.update_single_pending_order(row, self.om.token0_order_dict)
                    self.om.token1_order_dict = {}
                    self.om.token1_order_cnt = 0
                if row['side'] == "SELL":
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
            if len(pos_df) == 0:
                return
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

            # send alert if there are position 30 minute before game start 
            alert_time = self.game_start_time - timedelta(minutes=30)
            now = datetime.now(timezone.utc)
            delay = max((alert_time - now).total_seconds(), 0)
            if 0 < delay < 120:
                Timer(delay, send_position_check(self.market, 30, token_id, size, self.game_start_time)).start()


    async def run_strategy(self):
        self.eval_cnt += 1
        if self.eval_cnt % 200 == 1:
            self.update_pending_orders()
            self.get_position(self.token0_id) # only trade the first token
            # self.get_position(self.token1_id)
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
            # check is price valid
            ok_bid_price, ok_ask_price = self.check_valid_price(bid_submit_price_tick), self.check_valid_price(ask_submit_price_tick)
            # cancel orders inner than submit price
            self.cancel_order_between_price(bid_submit_price_tick+1, best_bid_price_tick, 0)
            self.cancel_order_between_price(best_ask_price_tick, ask_submit_price_tick-1, 1)
            for i in range(bid_submit_price_tick, bid_leave_price_tick, -1):
                ok_bid_fund = self.check_available_fund(self.tick_size*i, self.bid_size)
                ok_bid_pending, _ = self.check_pending_order(i, 0)
                if not self.is_game_status:
                    # cancel all pending orders
                    if self.om.token0_order_cnt > 0: # cancel all orders for both side
                        self.cance_all_asset(self.token0_id)
                if self.is_game_status and ok_bid_fund and ok_bid_maxpos and ok_bid_pnl and ok_bid_pending and ok_bid_price: 
                    token0_buy_order = Order(token_id=self.token0_id, price=i, tick_size=self.tick_size, size=self.bid_size, 
                                            side=0, create_time=datetime.now(), market=self.market)
                    # if signal changes, we need to change the order
                    self.cancel_invalid_order(0)
                    # self.send_buy_order(token0_buy_order)
                    await global_state.order_dispatcher.submit(token0_buy_order, self.om)
            for i in range(ask_submit_price_tick, ask_leave_price_tick, 1):
                ok_ask_fund = True
                _, ok_ask_pending = self.check_pending_order(i, 1)
                if self.is_game_status and ok_ask_fund and ok_ask_maxpos and ok_ask_pnl and ok_ask_pending and ok_ask_price: 
                    token0_sell_order = Order(token_id=self.token0_id, price=i, tick_size=self.tick_size, size=self.ask_size, 
                                            side=1, create_time=datetime.now(), market=self.market)
                    self.cancel_invalid_order(1)
                    await global_state.order_dispatcher.submit(token0_sell_order, self.om)
                    # self.send_sell_order(token0_sell_order)
    