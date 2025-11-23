class TradeSummary:
    asset_id = None
    event_type = "last_trade_price"
    fee_rate_bps = 0
    market = None
    price = 0
    side = None
    size = 0
    timestamp = 0

    def __init__(self, asset_id, event_type, fee_rate_bps, market, price, side, size, timestamp):
        self.asset_id = asset_id
        self.event_type = "last_trade_price"
        self.fee_rate_bps = fee_rate_bps
        self.market = market
        self.price = price
        self.side = side
        self.size = size
        self.timestamp = timestamp