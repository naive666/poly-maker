from decimal import Decimal
from typing import Dict
class Order:
    def __init__(self, token_id:str, price:int, tick_size:Decimal, size:Decimal, side:int, create_time:int, market:str=None,):
        self.token_id:str = token_id
        self.market:str = market
        self.price:int = int(price) # price in tick space
        self.tick_size:Decimal = tick_size
        self.pending_size:Decimal = size
        self.fill_size:Decimal = 0 
        self.side:int = side 
        self.status:str = 'new' 
        self.order_id:str = None 
        self.create_time:int = create_time



class OrderManager:
    def __init__(self, conditonal_id:str):
        self.token0_order_dict:Dict[int, Order]  = {} # {order_price tick space: Order}
        self.token1_order_dict:Dict[int, Order] = {}
        self.token0_order_cnt:int = 0
        self.token1_order_cnt:int = 0
        self.om_condition_id:str = conditonal_id

    def add_order(self, order:Order):
        if order.side == 0:
            self.add_order_basic(order, self.token0_order_dict)
            self.token0_order_cnt += 1
            print(f"add bid order {order.order_id}")
        elif order.side == 1:
            self.add_order_basic(order, self.token1_order_dict)
            self.token1_order_cnt += 1
            print(f"add ask order {order.order_id}")

    def add_order_basic(self, order:Order, order_dict:Dict[int, Order]):
        if int(order.price) not in order_dict:
            order_dict[order.price] = [order]
        else:
            order_dict[order.price].append(order)
    
    def delete_order(self, order_id:str, order_price:int, side:int):
        if side == 0:
            self.delete_order_basic(order_id, order_price, self.token0_order_dict) 
            print(f"cancel order {order_id}")
            self.token0_order_cnt -= 1
        elif side == 1:
            self.delete_order_basic(order_id, order_price, self.token1_order_dict) 
            print(f"cancel order {order_id}")
            self.token1_order_cnt -= 1

    def delete_order_basic(self, order_id:str, order_price:int, order_dict:Dict[int, Order]):
        order_price = int(order_price)
        if order_price in order_dict:
            order_dict[order_price][:] = [o for o in order_dict[order_price] if o.order_id != order_id ]
        else:
            print(f"{order_id} does not exist")
    
    def modify_order(self, order_id:str, order_price:int, fill_size:Decimal, side:int):
        order_price = int(order_price)
        if side == 0:
            self.modify_order_basic(order_id, order_price, fill_size, side, self.token0_order_dict)
            print(f"fill on {order_id}")
        elif side == 1:
            self.modify_order_basic(order_id, order_price, fill_size, side, self.token1_order_dict)
            print(f"fill on {order_id}")

    def modify_order_basic(self, order_id:str, order_price:int, fill_size:Decimal, side:int, order_dict:Dict[int, Order]):
        order_price = int(order_price)
        # partial fill
        if order_price in order_dict:
            for order in order_dict[order_price]:
                if order.order_id == order_id:
                    order.pending_size -= fill_size 
                    order.fill_size += fill_size
                if order.pending_size == 0:
                    self.delete_order_basic(order_id, order_price, order_dict)
                    if side == 0:
                        self.token0_order_cnt -= 1
                    elif side == 1:
                        self.token1_order_cnt -= 1
        
        


        