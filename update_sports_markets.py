import time
import pandas as pd
from data_updater.trading_utils import get_clob_client
from data_updater.google_utils import get_spreadsheet
from data_updater.find_markets import get_sel_df, get_all_markets, get_all_results, get_markets, add_volatility_to_df
from gspread_dataframe import set_with_dataframe
import traceback, logging
import requests, itertools, os, re 
from datetime import datetime, timezone, date
from concurrent.futures import ThreadPoolExecutor, as_completed

# Initialize global variables
spreadsheet = get_spreadsheet()
client = get_clob_client()



def get_markets_by_tag_id(tag_id, closed=False, limit=250, max_pages=20):
    all_markets = []
    for page in range(max_pages):
        offset = page * limit
        params = {"tag_id": tag_id, "closed": str(closed).lower(), "limit": limit, "offset": offset}
        r = requests.get(f"{BASE}/markets", params=params, timeout=30)
        r.raise_for_status()
        chunk = r.json()
        markets = chunk if isinstance(chunk, list) else chunk.get("markets", chunk)
        # docs show /markets returns a list; some SDKs wrap it. Handle both.
        if not markets:
            break
        all_markets.extend(markets)
        if len(markets) < limit:
            break
    return all_markets



def get_alive_market(all_mkt):
    alive = [m for m in all_mkt if m.get('active') is True and m.get("acceptingOrders") is True]
    want_types = {"moneyline", "spread", "total"}  # example
    typed = [m for m in alive if str(m.get("sportsMarketType","")).lower() in want_types]
    print("Alive (selected types):", len(typed))
    return typed



def list_series(limit=100, offset=0, closed=None, order=None, ascending=None):
    params = {"limit": limit, "offset": offset}
    if closed is not None:
        params["closed"] = str(closed).lower()
    if order:
        params["order"] = order
    if ascending is not None:
        params["ascending"] = str(ascending).lower()
    r = requests.get(f"{BASE}/series", params=params, timeout=30)
    r.raise_for_status()
    return r.json()  # top-level LIST


# Flatten the nested markets (events → markets), if present
def iter_markets_from_series(series_obj):
    for ev in series_obj.get("events", []) or []:
        for m in ev.get("markets", []) or []:
            yield m


def process_single_sport(sport_type):
    spprt_tag = requests.get(f"{BASE}/tags/slug/{sport_type}", timeout=20).json()
    sport_tag_id = int(spprt_tag["id"])    
    all_mkt = get_markets_by_tag_id(sport_tag_id, closed=False, limit=250)
    alive_mkt = get_alive_market(all_mkt)
    cache = []
    for js in alive_mkt:
        s = sport_json_to_df(js, sport_type)
        cache.append(s)
    alive_mkt_df = pd.DataFrame(cache)
    return sport_type, alive_mkt_df, None 


def sport_json_to_df(mkt_info_dict, sport_type):
    question = mkt_info_dict.get('question')
    conditionId = mkt_info_dict.get('conditionId')
    slug = mkt_info_dict.get('slug')
    endDate = mkt_info_dict.get('endDate')
    liquidity = mkt_info_dict.get('liquidity')
    volume = mkt_info_dict.get('volume')
    tick_size = mkt_info_dict.get('orderPriceMinTickSize')
    orderMinSize = mkt_info_dict.get('orderMinSize')
    volumeNum = mkt_info_dict.get('volumeNum')
    liquidityNum = mkt_info_dict.get('liquidityNum')
    volume1wk = mkt_info_dict.get('volume1wk')
    volume1mo = mkt_info_dict.get('volume1mo')
    volume1yr = mkt_info_dict.get('volume1yr')
    volumeClob = mkt_info_dict.get('510.615132')
    volume1wkClob = mkt_info_dict.get('volume1wkClob')
    volume1moClob = mkt_info_dict.get('volume1moClob')
    volume1yrClob = mkt_info_dict.get('volume1yrClob')
    best_bid = mkt_info_dict.get('bestBid')
    best_ask = mkt_info_dict.get('bestAsk')
    token1 = mkt_info_dict.get('clobTokenIds')[0]
    token2 = mkt_info_dict.get('clobTokenIds')[1]
    umaReward = mkt_info_dict.get('umaReward')
    negRisk = mkt_info_dict.get('negRisk')
    rewardsMinSize = mkt_info_dict.get('rewardsMinSize')
    rewardsMaxSpread = mkt_info_dict.get('rewardsMaxSpread')
    spread = mkt_info_dict.get('spread')
    lastTradePrice = mkt_info_dict.get('lastTradePrice')
    sportsMarketType = mkt_info_dict.get('sportsMarketType')
    holdingRewardsEnabled = mkt_info_dict.get('holdingRewardsEnabled')
    info_series = pd.Series(
        {
            'sport_type': sport_type,
            'question': question,
            'conditionId': conditionId,
            'slug': slug,
            'best_bid': best_bid,
            'best_ask': best_ask,
            'endDate': endDate,
            'liquidity': liquidity,
            'volume': volume,
            'spread': spread,
            'lastTradePrice': lastTradePrice,
            'sportsMarketType': sportsMarketType,
            'tick_size': tick_size,
            'orderMinSize': orderMinSize,
            'volumeNum': volumeNum,
            'liquidityNum': liquidityNum,
            'volume1wk': volume1wk,
            'volume1mo': volume1mo,
            'volume1yr': volume1yr,
            'volumeClob': volumeClob,
            'volume1wkClob': volume1wkClob,
            'volume1moClob': volume1moClob,
            'volume1yrClob': volume1yrClob,
            'token1': token1,
            'token2': token2,
            'umaReward': umaReward,
            'negRisk': negRisk,
            'rewardsMinSize': rewardsMinSize,
            'rewardsMaxSpread': rewardsMaxSpread,
            'holdingRewardsEnabled': holdingRewardsEnabled
        }
    )
    return info_series


def update_sports_sheet(data, worksheet):
    all_values = worksheet.get_all_values()
    existing_num_rows = len(all_values)
    existing_num_cols = len(all_values[0]) if all_values else 0

    num_rows, num_cols = data.shape
    max_rows = max(num_rows, existing_num_rows)
    max_cols = max(num_cols, existing_num_cols)

    # Create a DataFrame with the maximum size and fill it with empty strings
    padded_data = pd.DataFrame('', index=range(max_rows), columns=range(max_cols))

    # Update the padded DataFrame with the original data and its columns
    padded_data.iloc[:num_rows, :num_cols] = data.values
    padded_data.columns = list(data.columns) + [''] * (max_cols - num_cols)

    # Update the sheet with the padded DataFrame, including column headers
    set_with_dataframe(worksheet, padded_data, include_index=False, include_column_header=True, resize=True)



def update_sport_sheet(sport_market_df):
    sport_market_df = sport_market_df.sort_values(by=['sport_type', 'endDate'])
    spreadsheet = get_spreadsheet()
    sport_sheet_all = spreadsheet.worksheet("Full Sports Markets")
    update_sports_sheet(sport_market_df, sport_sheet_all)






if __name__ == '__main__':
    log_folder_path = './log'
    today_str = date.today().strftime("%Y-%m-%d")
    logging.basicConfig(
        filename=os.path.join(log_folder_path, f'{today_str}.log' ),        # file name
        level=logging.INFO,        # log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format='%(asctime)s [%(levelname)s] %(message)s',  # log format
    )

    logging.info("Program started")
    logging.warning("This is a warning")
    logging.error("Something went wrong")

    BASE = "https://gamma-api.polymarket.com"
    # sport_type_list = ['ncaab', 'epl', 'lal', 'cbb', 'ipl', 'wnba', 'bun', 'mlb', 'cfb', 
    #               'nfl', 'fl1', 'sea', 'ucl', 'afc', 'ofc', 'fif', 'ere', 'arg', 
    #               'itc', 'mex', 'lcs', 'lib', 'sud', 'tur', 'con', 'cof', 'uef', 
    #               'caf', 'rus', 'efa', 'efl', 'mls', 'nba', 'nhl', 'uel', 'csgo', 
    #               'dota2', 'lol', 'valorant', 'odi', 't20', 'abb', 'csa', 'atp', 
    #               'wta', 'cwbb', 'mma', 'cdr']
    sport_type_list = ['nba', 'nhl', 'cfb', 'nfl']
    result_list = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        futs = [pool.submit(process_single_sport, s) for s in sport_type_list]
        for fut in as_completed(futs):
            sport_type, alive_mkt_df, err = fut.result()
            if err:
                print(f"{sport_type} has error: {err}")
            else:
                result_list.append(alive_mkt_df)
                print(f"{sport_type} alive market successful")
        sport_market_df = pd.concat(result_list)
    
    update_sport_sheet(sport_market_df)
    print("update google sprot sheet ready")