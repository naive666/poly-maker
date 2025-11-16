import gc                      # Garbage collection
import time                    # Time functions
import asyncio                 # Asynchronous I/O
import traceback               # Exception handling
import threading               # Thread management

from poly_data.polymarket_client import PolymarketClient
from poly_data.data_utils import update_markets, update_positions, update_orders
from poly_data.websocket_handlers import connect_market_websocket, connect_user_websocket
from poly_data.orderbook import OrderBook
from placements.order_manager import OrderManager
from placements.base_placements import BasePlacement
from placements.placement01 import Placement01
from graphs.strategy_v20251101 import strategy_202511
import poly_data.global_state as global_state
from poly_data.data_processing import remove_from_performing
from dotenv import load_dotenv


load_dotenv()

def update_once(all='Full Sports Markets', sel='Selected Sports Markets'):
    """
    Initialize the application state by fetching market data, positions, and orders.
    """
    update_markets(all=all, sel=sel)    # Get market information from Google Sheets
    update_positions()  # Get current positions from Polymarket
    update_orders()     # Get current orders from Polymarket


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
            
async def main():
    """
    Main application entry point. Initializes client, data, and manages websocket connections.
    """
    # Initialize client
    global_state.client = PolymarketClient()
    
    # Initialize state and fetch initial data
    global_state.all_tokens = []
    all_ = 'Full Sports Markets'
    sel_ = 'Selected Sports Markets'
    update_once(all_, sel_)

    print("After initial updates: ", global_state.orders, global_state.positions)

    print("\n")
    print(f'There are {len(global_state.df)} market, {len(global_state.positions)} positions and {len(global_state.orders)} orders. Starting positions: {global_state.positions}')
    

    token_id = global_state.df['token1'].iloc[0]
    token2_id = global_state.df['token2'].iloc[0]
    conditional_id = global_state.df['condition_id'].iloc[0]
    order_size = global_state.df['trade_size'].iloc[0]
    bbo_size_thred = global_state.df['bbo_size_thred'].iloc[0]
    bbo_gap_thred = global_state.df['bbo_gap_thred'].iloc[0]
    quote_NLevel = global_state.df['quote_NLevel'].iloc[0]
    max_pos = global_state.df['max_pos'].iloc[0]
    single_pos_percent = global_state.df['single_pos_percent'].iloc[0]
    maxloss = global_state.df['maxloss'].iloc[0]
    position_update_time_thred = 5
    order_manager = OrderManager()
    update_period = 10
    max_level_thred = 10
    exe_config = {'quote_NLevel': quote_NLevel, 'max_pos':max_pos, 'single_pos_percent':single_pos_percent, 'maxloss': maxloss}
    strategy = strategy_202511(token_id, order_size, bbo_size_thred, bbo_gap_thred, update_period, max_level_thred)
    placement = Placement01( token_id, token2_id, conditional_id, strategy, exe_config, position_update_time_thred, order_manager)
    
    # order_manager = OrderManager()
    # bp = BasePlacement('strategy', 'exe_config', 100 ,order_manager)
    # bp.get_pending_orders('0x610880fb46dd51ddd7be1e25a6feb09faf4f3cfd6a6c7c7647c0222dbcf2045a')

    # Start background update thread
    update_thread = threading.Thread(target=update_periodically, daemon=True) # update_periodically will cancel the order the exist too long, but our local code will not
    update_thread.start()
    
    # Main loop - maintain websocket connections
    while True:
        placement.run_strategy()
            
        time.sleep(5)
        gc.collect()  # Clean up memory

if __name__ == "__main__":
    asyncio.run(main())