import gc                      # Garbage collection
import time                    # Time functions
import asyncio                 # Asynchronous I/O
import traceback               # Exception handling
import threading               # Thread management
from decimal import Decimal
from poly_data.polymarket_client import PolymarketClient
from poly_data.data_utils import update_markets, update_positions, update_orders
from poly_data.websocket_handlers_hz import connect_market_websocket_hz, connect_user_websocket_hz
from poly_data.orderbook import OrderBook
from placements.order_manager import OrderManager
from placements.base_placements import BasePlacement
from placements.placement01 import Placement01
from placements.placement_one_side import PlacementOneSide
from placements.order_dispatcher import OrderDispatcher
from graphs.strategy_v20251101 import strategy_202511
import poly_data.global_state as global_state
from poly_data.data_processing import remove_from_performing
from dotenv import load_dotenv
import pandas as pd 
from datetime import datetime, timezone, timedelta
from logging_setup import setup_logger
from telegram_bot.telegram_alerts import send_telegram


load_dotenv()

def check_valid_market(row, volume_thred=100000, min_hour=2, max_hour=24):
    if row['volume'] == '':
        return False
    if Decimal(row['volume']) < volume_thred:
        return False 
    # check start time
    gameStartTime = pd.to_datetime(row["gameStartTime"], utc=True)
    now_utc = datetime.now(timezone.utc)
    if timedelta(hours=min_hour) <= (gameStartTime - now_utc) <= timedelta(hours=max_hour):
        return True 


def update_once(all='Full Sports Markets', sel='Selected Sports Markets', graph_update_period=10, max_level_thred=20):
    """
    Initialize the application state by fetching market data, positions, and orders.
    """
    print(f"start update market")
    update_markets(all=all, sel=sel)    # Get market information from Google Sheets
    print(f"finish update market")
    update_positions()  # Get current positions from Polymarket
    print(f"finish update positions")
    update_orders()     # Get current orders from Polymarket
    print(f"finish update orders")
    valid_mkt_cnt = 0

    for idx, row in global_state.df.iterrows():
        # check if the market is valid
        min_hour, max_hour = 1, 48
        is_market_valid = check_valid_market(row, volume_thred=20000, min_hour=min_hour, max_hour=max_hour)
        if not is_market_valid:
            continue 
        try:
            token_id = str(row['token1'])
            token2_id = str(row['token2'])
            best_bid = Decimal(row['best_bid'])
            best_ask = Decimal(row['best_ask'])
            # only trade small winrate one
            if best_bid > 0.5:
                token_id, token2_id = token2_id, token_id
            conditional_id = row['condition_id']
            order_size = Decimal("8") # Decimal(row['trade_size'])
            bbo_size_thred = Decimal(row['bbo_size_thred'])
            bbo_gap_thred = int(row['bbo_gap_thred'])
            quote_NLevel = int(row['quote_NLevel'])
            max_pos = Decimal("8") # Decimal(row['max_pos'])
            single_pos_percent = Decimal(row['single_pos_percent'])
            maxloss = Decimal("8") # Decimal(row['maxloss'])
            question = row['question']
            position_update_time_thred = 5
            global_state.lock[conditional_id] = asyncio.Lock()
            order_manager = OrderManager(conditional_id)
            update_period = int(graph_update_period)
            max_level_thred = int(max_level_thred)
            game_start_time = row['gameStartTime']
            global_state.market_token_info[conditional_id] = [token_id, token2_id, question]
            exe_config = {'quote_NLevel': quote_NLevel, 'max_pos':max_pos, 'single_pos_percent':single_pos_percent, 'maxloss': maxloss}
            strategy = strategy_202511(token_id, order_size, bbo_size_thred, bbo_gap_thred, update_period, max_level_thred)
            placement = PlacementOneSide( token_id, token2_id, conditional_id, strategy, exe_config, position_update_time_thred, order_manager, min_valid_hour=min_hour, max_valid_hour=max_hour, game_start_time=game_start_time)
            global_state.strategy_dict[conditional_id] = [placement]
            global_state.strategy_list_all += global_state.strategy_dict[conditional_id]
            valid_mkt_cnt += 1
            if token_id not in global_state.all_tokens:
                global_state.all_tokens.append(token_id)
        except:
            continue
    log_str = f'total valid market: {valid_mkt_cnt}'
    print(log_str)
    logger.info(log_str)

def update_periodically(all='Full Sports Markets', sel='Selected Sports Markets'):
    """
    Background thread function that periodically updates market data, positions and orders.
    - Positions and orders are updated every 5 seconds
    - Market data is updated every 30 seconds (every 6 cycles)
    - Stale pending trades are removed each cycle
    """
    i = 1
    while True:
        time.sleep(5)  # Update every 5 seconds
        
        try:
            # Clean up stale trades
            
            # Update positions and orders every cycle
            update_positions(avgOnly=True)  # Only update average price, not position size
            update_orders()

            # Update market data every 6th cycle (30 seconds)
            if i % 6 == 0:
                update_markets(all, sel)
                i = 1
                    
            gc.collect()  # Force garbage collection to free memory
            i += 1
        except:
            print("Error in update_periodically")
            print(traceback.format_exc())


async def strategy_loop(placement:BasePlacement, interval: float = 1):
    while True:
        try:
            async with placement.lock:
                await placement.run_strategy()
        except Exception as e:
            # prevent one strategy from killing everything
            print(f"Error in strategy {getattr(placement, 'name', placement)}: {e}")
            send_telegram(f"❌ Strategy crashed: {type(e).__name__}: {e!r}")
        await asyncio.sleep(interval)



def set_game_start_alert():
    # global_state
    pass




async def main():
    """
    Main application entry point. Initializes client, data, and manages websocket connections.
    """
    # Initialize client
    global_state.client = PolymarketClient()
    global_state.order_dispatcher = OrderDispatcher(global_state.client)
    print('initialize client')
    
    # Initialize state and fetch initial data
    global_state.all_tokens = []
    all_ = 'Full Sports Markets'
    sel_ = 'Selected Sports Markets'
    update_once(all_, sel_)

    print("After initial updates: ", global_state.orders, global_state.positions)

    print("\n")
    print(f'There are {len(global_state.df)} market, {len(global_state.positions)} positions and {len(global_state.orders)} orders. Starting positions: {global_state.positions}')
    
    # set alert for game start
    
    
    # Main loop - maintain websocket connections
    while True:
        asyncio.create_task(global_state.order_dispatcher.send_loop())
        await asyncio.gather(
                connect_market_websocket_hz(global_state.all_tokens),
                connect_user_websocket_hz(),
                *(strategy_loop(s,1) for s in global_state.strategy_list_all),
            )
        # placement.run_strategy()
            
        await asyncio.sleep(1)  
        gc.collect()  # Clean up memory

if __name__ == "__main__":
    try:
        send_telegram("Strategy starting up")
        logger = setup_logger()
        asyncio.run(main())
    except Exception as e:
        # Unexpected crash
        send_telegram(f"❌ Strategy crashed: {type(e).__name__}: {e!r}")
        raise            # re-raise so you still see stack trace / logs
    finally:
        # Called on both normal exit and crash
        send_telegram("⚠️ Strategy stopped (process exiting).")
