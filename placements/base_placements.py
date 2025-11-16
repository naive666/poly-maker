from graphs.base_strategy import BaseStrategy
import poly_data.global_state as global_state
from placements.order_manager import Order, OrderManager
import time 
from datetime import datetime
from py_clob_client.clob_types import TradeParams

class BasePlacement:
    def __init__(self, token0_id, token1_id, conditional_id, strategy, exe_config, position_update_time_thred, order_manager:OrderManager):
        self.tick_size = global_state.df[global_state.df['condition_id'] == conditional_id]['tick_size'].iloc[0]
        self.token0_id = token0_id
        self.token1_id = token1_id 
        self.conditional_id = conditional_id
        self.config = exe_config
        self.strategy = strategy
        self.om = order_manager
        self.is_game_status = False 
        self.is_max_loss = False
        self.is_pnl = False  
        self.position_update_time_thred = position_update_time_thred 
        self.bid_submit_price, self.ask_submit_price = 0, 0
        self.bid_leave_price, self.ask_leave_price = 0, 0
        self.bid_size, self.ask_size = 0, 0
        self.ok_process_bid = False 
        self.ok_process_ask = False 
        self.asset_pos_dict = {}
    
    def run_strategy(self):
        self.update_pending_orders()
        self.evaluate_strategy()
        self.check_game_status()
        ok_bid_maxpos, ok_ask_maxpos = self.check_max_position()
        ok_bid_pnl, ok_ask_pnl = self.check_pnl()
        bid_submit_price_tick, ask_submit_price_tick = int(self.bid_submit_price / self.tick_size), int(self.ask_submit_price / self.tick_size)
        bid_leave_price_tick, ask_leave_price_tick = int(self.bid_leave_price / self.tick_size), int(self.ask_leave_price / self.tick_size)
        for i in range(bid_submit_price_tick, bid_leave_price_tick, -1):
            ok_bid_fund = self.check_available_fund(self.tick_size*i, self.bid_size)
            ok_bid_pending, _ = self.check_pending_order(i, 0)
            if ok_bid_fund and ok_bid_maxpos and ok_bid_pnl and ok_bid_pending: 
                token0_buy_order = Order(token_id=self.token0_id, price=i, tick_size=self.tick_size, size=self.bid_size, side=0, create_time=datetime.now())
                self.send_buy_order(token0_buy_order)
        for i in range(ask_submit_price_tick, ask_leave_price_tick, 1):
            ok_ask_fund = self.check_available_fund(self.tick_size*i, self.ask_size)
            _, ok_ask_pending = self.check_pending_order(i, 1)
            if ok_ask_fund and ok_ask_maxpos and ok_ask_pnl and ok_ask_pending: 
                token1_buy_order = Order(token_id=self.token1_id, price=i, tick_size=self.tick_size, size=self.ask_size, side=1, create_time=datetime.now())
                self.send_sell_order(token1_buy_order)
        
        self.merge()
    
    def evaluate_strategy(self):
        pass 

    def check_pnl(self):
        pass 

    def check_max_position(self):
        pass 

    def check_pending_order(self, price, side):
        price = int(price)
        ok_pending_order_bid, ok_pending_order_ask = True, True
        if side == 0:
            if price in self.om.token0_order_dict:
                if len(self.om.token0_order_dict[price]) >= 1:
                    ok_pending_order_bid = False
                    print(f"Pending Order Check fail for Side 0 at {price}")
        elif side == 1:
            if price in self.om.token1_order_dict:
                if len(self.om.token1_order_dict[price]) >= 1:
                    ok_pending_order_ask = False
                    print(f"Pending Order Check fail for Side 1 at {price}")
        return ok_pending_order_bid, ok_pending_order_ask

    def check_game_status(self):
        pass 

    def check_available_fund(self, price, size):
        pass 
        
    def update_pending_orders(self):
        order_df = global_state.client.get_market_orders(self.conditional_id)
        # update pending orders
        for idx, row in order_df.iterrows():
            if row['market'] == self.token0_id:
                price = int(row['price'] / self.tick_size)
                if price in self.om.token0_order_dict:
                    print('update pending order for bid side')
                    order_list = self.om.token0_order_dict[price]
                    for o in order_list:
                        if o.order_id == row['order_id']:
                            o.fill_size = row['size_matched']
                            o.pending_size = row['original_size'] - o.fill_size 
                else:
                    print('reconnect, update pending order for bid side')
                    # in case we have to reconnect and lose all local info
                    order = Order(token_id=self.token0_id, price=price, tick_size=self.tick_size, size=self.bid_size, side=0, create_time=row['created_at'])
                    order.order_id = row['order_id']
                    self.om.add_order(order)

            if row['market'] == self.token1_id:
                price = int(row['price'] / self.tick_size)
                if price in self.om.token1_order_dict:
                    print('update pending order for bid side')
                    order_list = self.om.token1_order_dict[price]
                    for o in order_list:
                        if o.order_id == row['order_id']:
                            o.fill_size = row['size_matched']
                            o.pending_size = row['original_size'] - o.fill_size  
                else:
                    print('reconnect, update pending order for ask side')
                    # in case we have to reconnect and lose all local info
                    order = Order(token_id=self.token0_id, price=price, tick_size=self.tick_size, size=self.bid_size, side=1, create_time=row['created_at'])
                    order.order_id = row['order_id']
                    self.om.add_order(order)
        return order_df


    def get_position(self, token_id):
        if global_state.position_update_time is None:
            global_state.position_update_time = datetime.now()
            global_state.positions = global_state.client.get_all_positions()
        else:
            if (datetime.now() - global_state.position_update_time).total_seconds() > self.position_update_time_thred:
                global_state.position_update_time = datetime.now()
                global_state.positions = global_state.client.get_all_positions() 
        pos_df = global_state.positions[global_state.positions['asset'] == token_id]
        if len(pos_df) > 0:
            size = pos_df['size']
            avg_price = pos_df['avgPrice']
            cashPnl = pos_df['cashPnl']
            initial_value = pos_df['initialValue']
            current_value = pos_df['currentValue']
            pos_dict = {'size': size, 'avg_price': avg_price, 'cashPnl': cashPnl, 'initial_value': initial_value, 'current_value': current_value}
            self.asset_pos_dict[token_id] = pos_dict 
    


    def send_buy_order(self, order:Order):
        """
        Create a BUY order for a specific token.
        """
        client = global_state.client
        # iterate over all orders to decide place new order or not
        if self.is_game_status == False:
            return 
        for prc, order_list in self.om.token0_order_dict.items():
            if prc == order.price:
                # Only cancel existing orders if we need to make significant changes
                existing_buy_size = sum([ o.pending_size for o in order_list])  
                existing_buy_price = order.price 
        
                # Cancel orders if price changed significantly or size needs major adjustment
                price_diff = abs(existing_buy_price - order.price) if existing_buy_price > 0 else float('inf')
                size_diff = abs(existing_buy_size - order.pending_size) if existing_buy_size > 0 else float('inf')
        
                should_cancel = (
                    price_diff == 1 or  # Cancel if price diff == 0 tick
                    size_diff > order.pending_size * 0.1 or  # Cancel if size diff > 10%
                    existing_buy_size == 0  # Cancel if no existing buy order
                )
        
            if should_cancel and existing_buy_size > 0:
                print(f"Cancelling buy orders - price diff: {price_diff:.4f}, size diff: {size_diff:.1f}")
                for o in order_list:
                    client.cancel_order(o.order_id)
                    self.om.delete_order(order_id=o.order_id, order_price=o.price, side=0)
            elif not should_cancel:
                print(f"Keeping existing buy orders - minor changes: price diff: {price_diff:.4f}, size diff: {size_diff:.1f}")
                return  # Don't place new order if existing one is fine

        
        # Only place orders with prices between 0.1 and 0.9 to avoid extreme positions
        print(f'Creating new buy order for {order.pending_size} at {order.price}')
        order_id = client.create_order(
            order.token_id, 
            'BUY', 
            order.price * order.tick_size, 
            order.pending_size
        )
        order.order_id = order_id
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
        for prc, order_list in self.om.token1_order_dict.items():
            if prc == order.price:
                # Only cancel existing orders if we need to make significant changes
                existing_ask_size = sum([ o.pending_size for o in order_list])  
                existing_ask_price = order.price 
        
                # Cancel orders if price changed significantly or size needs major adjustment
                price_diff = abs(existing_ask_price - order.price) if existing_ask_price > 0 else float('inf')
                size_diff = abs(existing_ask_size - order.pending_size) if existing_ask_size > 0 else float('inf')
        
                should_cancel = (
                    price_diff > 0.005 or  # Cancel if price diff > 0.5 cents
                    size_diff > order.pending_size * 0.1 or  # Cancel if size diff > 10%
                    existing_ask_size == 0  # Cancel if no existing buy order
                )
        
            if should_cancel and existing_ask_size > 0:
                print(f"Cancelling buy orders - price diff: {price_diff:.4f}, size diff: {size_diff:.1f}")
                for o in order_list:
                    client.cancel_order(o.order_id)
                    self.om.delete_order(order_id=o.order_id, order_price=o.price, side=1)
            elif not should_cancel:
                print(f"Keeping existing buy orders - minor changes: price diff: {price_diff:.4f}, size diff: {size_diff:.1f}")
                return  # Don't place new order if existing one is fine

        
        # Only place orders with prices between 0.1 and 0.9 to avoid extreme positions
        print(f'Creating new buy order for {order.pending_size} at {order.price}')
        order_id = client.create_order(
            order.token_id, 
            'BUY', 
            order.price * order.tick_size, 
            order.pending_size
        )
        order.order_id = order_id
        self.om.add_order(order)
        
        return order_id

    def cancel_order_id(self, order_id):
        global_state.client.cancel_order(order_id)

    def cancel_order(self, side):
        if side == 0:
            for prc, order_list in self.om.token0_order_dict.items():
                if prc < self.bid_leave_price:
                    for o in order_list:
                        print(f"Cancel Order {o.order_id}")
                        global_state.client.cancel_order(o.order_id)
                        self.om.token0_order_dict.delete_order(o.id, prc, side)
                        
        elif side == 1:
            for prc, order_list in self.om.token1_order_dict.items():
                if prc < self.ask_leave_price:
                    for o in order_list:
                        print(f"Cancel Order {o.order_id}")
                        global_state.client.cancel_order(o.order_id)
                        self.om.token1_order_dict.delete_order(o.id, prc, side)


    def merge(self):
        if self.token0_id in self.asset_pos_dict and self.token1_id in self.asset_pos_dict:
            pos0 = self.asset_pos_dict[self.token0_id]['size']
            pos1 = self.asset_pos_dict[self.token1_id]['size']
            if pos0 < pos1:
                global_state.client.merge_positions(pos0, self.condition_id, False)
                del self.asset_pos_dict[self.token0_id]
                print(f"Merge {pos0}, {self.token0_id} has pos 0, {self.token1_id} has pos {pos1 - pos0}")
            elif pos0 > pos1:
                global_state.client.merge_positions(pos1, self.condition_id, False)
                del self.asset_pos_dict[self.token1_id]
                print(f"Merge {pos1}, {self.token1_id} has pos 0, {self.token0_id} has pos {pos0 - pos1}")
            else:
                global_state.client.merge_positions(pos0, self.condition_id, False)
                del self.asset_pos_dict[self.token0_id]
                del self.asset_pos_dict[self.token1_id]
                print(f"Merge {pos1}, {self.token1_id} has pos 0, {self.token0_id} has pos {pos0 - pos1}")