class Order:
    def __init__(self, token_id, price, size, side, create_time):
        self.token_id = token_id
        self.price = round(price, 5) 
        self.pending_size = size
        self.fill_size = 0 
        self.side = side 
        self.status = 'new' 
        self.order_id = None 
        self.create_time = create_time



class OrderManager:
    token0_order_dict = {} # {order_id: Order}
    token1_order_dict = {}
    token0_order_cnt = 0
    token1_order_cnt = 0

    def add_order(self, order:Order):
        if order.side == 0:
            self.add_order_basic(order, self.token0_order_dict)
            self.token0_order_cnt += 1
            print(f"add bid order {order.order_id}")
        elif order.side == 1:
            self.add_order_basic(order, self.token1_order_dict)
            self.token1_order_cnt += 1
            print(f"add ask order {order.order_id}")

    def add_order_basic(self, order, order_dict):
        if round(order.price, 5) not in order_dict:
            order_dict[order.price] = [order]
        else:
            order_dict[order.price].append(order)
    
    def delete_order(self, order_id, order_price, side):
        if side == 0:
            self.delete_order_basic(order_id, order_price, self.token0_order_dict) 
            print(f"cancel order {order_id}")
            self.token0_order_cnt -= 1
        elif side == 1:
            self.delete_order_basic(order_id, order_price, self.token1_order_dict) 
            print(f"cancel order {order_id}")
            self.token1_order_cnt -= 1

    def delete_order_basic(self, order_id, order_price, order_dict):
        order_price = round(order_price,5)
        if order_price in order_dict:
            order_dict[order_price][:] = [o for o in order_dict[order_price] if o.order_id != order_id ]
        else:
            print(f"{order_id} does not exist")
    
    def modify_order(self, order_id, order_price, fill_size, side):
        order_price = round(order_price,5)
        if side == 0:
            self.modify_order_basic(order_id, order_price, fill_size, side, self.token0_order_dict)
            print(f"fill on {order_id}")
        elif side == 1:
            self.modify_order_basic(order_id, order_price, fill_size, side, self.token1_order_dict)
            print(f"fill on {order_id}")

    def modify_order_basic(self, order_id, order_price, fill_size, side, order_dict):
        order_price = round(order_price,5)
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
        
        


        