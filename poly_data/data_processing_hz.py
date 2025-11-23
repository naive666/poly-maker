import json
from sortedcontainers import SortedDict
import poly_data.global_state as global_state
import poly_data.CONSTANTS as CONSTANTS
import pandas as pd 
from trading import perform_trade
import time 
from datetime import datetime
import asyncio
from decimal import Decimal
from poly_data.trade_summary import TradeSummary
from poly_data.orderbook import OrderBook
from poly_data.data_utils import set_position, set_order, update_positions
from placements.base_placements import BasePlacement



def process_book_data_hz(json_data):
    if json_data['asset_id'] not in global_state.orderbook_data:
        bid_df = pd.DataFrame(json_data['bids']).sort_values(by='price', ascending=False)
        bid_df['price'] = bid_df['price'].apply(Decimal)
        bid_df = bid_df.set_index('price')
        bid_df['size'] = bid_df['size'].apply(Decimal)
        ask_df = pd.DataFrame(json_data['asks']).sort_values(by='price', ascending=True)
        ask_df['price'] = ask_df['price'].apply(Decimal)
        ask_df = ask_df.set_index('price')
        ask_df['size'] = ask_df['size'].apply(Decimal)
        orderbook = OrderBook(json_data['asset_id'])
        orderbook.bid_levels = bid_df
        orderbook.ask_levels = ask_df
        orderbook.update_ts = datetime.now()
        global_state.orderbook_data[json_data['asset_id']] = orderbook
    else:
        # update bid
        for bid_snapshot in json_data['bids']:
            p, s = Decimal(bid_snapshot['price']), Decimal(bid_snapshot['size'])
            bid_df = global_state.orderbook_data[json_data['asset_id']].bid_levels.at[p,'size'] = s
        # update ask 
        for ask_snapshot in json_data['asks']:
            p, s = Decimal(ask_snapshot['price']), Decimal(ask_snapshot['size'])
            ask_df = global_state.orderbook_data[json_data['asset_id']].ask_levels.at[p,'size'] = s


def process_price_change_hz(asset_id, side, price_level, new_size):
    if asset_id not in global_state.orderbook_data:
        return  # skip updates for the No token to prevent duplicated updates
    if side == 'bids':
        book = global_state.orderbook_data[asset_id].bid_levels
        if new_size == 0:
            if price_level in book.index:
                book.drop(price_level, inplace=True)
        else:
            book[price_level] = new_size
        global_state.orderbook_data[asset_id].bid_levels = book
    else:
        book = global_state.orderbook_data[asset_id].ask_levels
        if new_size == 0:
            if price_level in book.index:
                book.drop(price_level, inplace=True)
        else:
            book[price_level] = new_size
        global_state.orderbook_data[asset_id].ask_levels = book


async def process_indiv_market_data(json_data):
    event_type = json_data['event_type']
    market = json_data['market']
    asset_strat_list = global_state.strategy_dict[json_data['market']]
    lock = global_state.lock[json_data['market']]
    async with lock:
        if event_type == 'book':
            process_book_data_hz(json_data)
            # on_book_change
            for placement in asset_strat_list:
                placement.eval_cnt += 1
                placement.strategy.on_snapshot(global_state.orderbook_data[json_data['asset_id']] )
                
        elif event_type == 'price_change':
            for data in json_data['price_changes']:
                side = 'bids' if data['side'] == 'BUY' else 'asks'
                asset_id = data['asset_id']
                price_level = Decimal(data['price'])
                new_size = Decimal(data['size'])
                process_price_change_hz(asset_id, side, price_level, new_size)
                for placement in asset_strat_list:
                    placement.eval_cnt += 1
                    placement.strategy.on_book_change( price_level, new_size, side )
            
        elif event_type == 'last_trade_price':
            trade_info = TradeSummary(json_data['asset_id'], json_data['event_type'], json_data['fee_rate_bps'], json_data['market'], 
                                    Decimal(json_data['price']), json_data['side'], Decimal(json_data['size']), int(json_data['timestamp']))
            for placement in asset_strat_list:
                placement.eval_cnt += 1
                placement.strategy.on_trade(trade_info)


async def process_market_data(json_datas):
    tasks = []
    if isinstance(json_datas, list):
        for json_data in json_datas:
            tasks.append(process_indiv_market_data(json_data))
    else:
        tasks.append(process_indiv_market_data(json_datas))
    await asyncio.gather(*tasks)

# async def process_market_data(json_datas):
#     for json_data in json_datas:
#         asyncio.create_task(process_indiv_market_data(json_data))
        

async def process_indiv_user_data(json_data):
    conditional_id = json_data['market']
    side = json_data['side'].lower()
    asset_id = json_data['asset_id']
    event_type = json_data['event_type']
    asset_strat_list = global_state.strategy_dict[json_data['market']]
    lock = global_state.lock[json_data['market']]
    async with lock:
        if conditional_id in global_state.market_token_info:
            market_info = global_state.market_token_info[conditional_id] 
        else:
            print("Market is not register")
            return 
        if event_type == 'trade':
            for placement in asset_strat_list:
                placement.eval_cnt += 1
                order_manager = placement.om
                tick_size = placement.tick_size
                if asset_id == market_info[0]:
                    if json_data['status'] == 'CONFIRMED':
                        for maker_order in json_data['maker_orders']:
                            fill_price = int(float(maker_order['price']) / tick_size)
                            fill_size = maker_order['size']
                            print(f"token 1 is filled at price {fill_price}, size {fill_size}")
                            order_id = maker_order['order_id']
                            order_manager.modify_order(order_id, fill_price, fill_size, 0)
                elif asset_id == market_info[1]:
                    if json_data['status'] == 'CONFIRMED':
                        for maker_order in json_data['maker_orders']:
                            fill_price = int(float(maker_order['price']) / tick_size)
                            fill_size = maker_order['size']
                            print(f"token 2 is filled at price {fill_price}, size {fill_size}")
                            order_id = maker_order['order_id']
                            order_manager.modify_order(order_id, fill_price, fill_size, 1)
        elif event_type == 'order':
            # useful to record transact time
            pass 

# async def process_user_data(json_datas):
#     for json_data in json_datas:
#         asyncio.create_task(process_indiv_user_data(json_data))
        
async def process_user_data(json_datas):
    tasks = []
    if isinstance(json_datas, list):
        for json_data in json_datas:
            tasks.append(process_indiv_user_data(json_data))
    else:
        tasks.append(process_indiv_user_data(json_datas))
    await asyncio.gather(*tasks)



