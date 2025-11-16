
class BaseStrategy:
    def __init__(self):
        self.token_id = None 
        self.bid_signal = None 
        self.ask_signal = None 
        self.bid_size_signal = None
        self.ask_size_signal = None 

    def evaluate(self):
        pass 

