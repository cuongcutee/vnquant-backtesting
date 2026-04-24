from abc import ABC, abstractmethod
import queue
from core.event import OrderEvent

class Strategy(ABC):

    def __init__(self,symbols, sizer = None):
        self.symbols = symbols
        self.sizer  =    sizer

    @abstractmethod
    def on_bar(self,event,portfolio,events = queue.Queue()):
        pass

    def _send_order(self, symbol, direction, quantity, events,
                order_type="MARKET", limit_price=None, date=None):
        if quantity > 0:
            events.put(OrderEvent(
                symbol      = symbol,
                direction   = direction,
                quantity    = quantity,
                order_type  = order_type,
                limit_price = limit_price,
                date        = date,
            ))
        
    def rebalance_to(self,symbol, target_qty, portfolio, events, order_type = "MARKET",limit_price = None,date = None):
        current_qty = portfolio.positions.get(symbol,0)
        diff = target_qty - current_qty
        if diff > 0:
            self._send_order(symbol, "BUY",diff, events, order_type, limit_price, date)
        if diff < 0:
            self._send_order(symbol,"SELL",abs(diff),events,order_type,limit_price, date )

        

    

class BuyAndHold(Strategy):
    #Mua đủ số cổ tối đa ngày đầu xong giữ mãi
    def __init__(self, symbols,  sizer = None):
        super().__init__(symbols,sizer)
        self._initialized = False
    def on_bar(self, event, portfolio, events):
        if self._initialized:
            return

        price = self.handler.get_latest_bar_value(event.symbol, "close")
        budget   = portfolio.cash * 0.95
        raw_qty  = int(budget / price)
        quantity = (raw_qty // 100) * 100

        self.rebalance_to(event.symbol, quantity, portfolio, events)
        self._initialized = True
