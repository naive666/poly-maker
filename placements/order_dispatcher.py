import asyncio, time
from collections import deque
from placements.order_manager import Order, OrderManager
import logging
logger = logging.getLogger("polymarket_bot")

MAX_ORDERS_PER_SEC = 5  # conservative
WINDOW = 1.0

class OrderDispatcher:
    def __init__(self, client):
        self.client = client
        self.queue = asyncio.Queue()
        self.timestamps = deque()  # recent send times

    async def send_loop(self):
        while True:
            order, om = await self.queue.get()

            # simple sliding window rate limit
            now = time.time()
            while self.timestamps and (now - self.timestamps[0]) > WINDOW:
                self.timestamps.popleft()

            if len(self.timestamps) >= MAX_ORDERS_PER_SEC:
                sleep_time = WINDOW - (now - self.timestamps[0]) + 0.01
                await asyncio.sleep(sleep_time)

            try:
                if order.side == 0:
                    await self.send_buy_order(order, om)
                elif order.side == 1:
                    await self.send_sell_order(order, om)
            except Exception as e:
                print(f"[DISPATCH] order failed: {e}")
            finally:
                self.timestamps.append(time.time())
                self.queue.task_done()

    async def send_buy_order(self, order:Order, om: OrderManager):
        """
        Create a BUY order for a specific token.
        """
        # Only place orders with prices between 0.1 and 0.9 to avoid extreme positions
        log_str = f"Create Buy Order for {order.market}, size: {order.pending_size}, price: {order.price}"
        print(log_str)
        logger.info(log_str)
        order_id = self.client.create_order(
            order.token_id, 
            'BUY', 
            float(order.price * order.tick_size), 
            float(order.pending_size)
        )
        if len(order_id) > 0:
            order.order_id = order_id['orderID']
            om.add_order(order)

        return order_id
    
    
    async def send_sell_order(self, order:Order, om: OrderManager):
        """
        Create a Sell order for a specific token.
        """
        # iterate over all orders to decide place new order or not 
        # Only place orders with prices between 0.1 and 0.9 to avoid extreme positions
        log_str = f"Create SELL Order for {order.market}, size: {order.pending_size}, price: {order.price}"
        print(log_str)
        logger.info(log_str)
        order_id = self.client.create_order(
            order.token_id, 
            'SELL', 
            float(order.price * order.tick_size), 
            float(order.pending_size)
        )
        if len(order_id) > 0:
            order.order_id = order_id['orderID']
            om.add_order(order)

        return order_id


    async def submit(self, order, om: OrderManager):
        await self.queue.put((order, om))
