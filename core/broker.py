import queue
from core.event import OrderEvent, FillEvent, EventType
from data.calendar import VNTradingCalendar
from datetime import date
class T2Broker:
    def __init__(self,handler,commission,tax = 0.001):
        self.handler = handler
        self.cal        = VNTradingCalendar()
        self.commission = commission
        self.tax = tax
        self._pending = [] #list(những OrderEvent)
        self._rejected = [] #list những Order bị reject

    def execute(self, order:OrderEvent):
        #Nhận Order từ engine. Append pending, fill vào ngày mai
        self._pending.append(order)
    
    def process_pending(self, date: date, fills_queue: queue.Queue):
        #Fill các lệnh pending hôm qua tại giá close hôm nay => 
        #lệnh nào mà symbol k có data thì giữ lại chờ ngày có data
        still_pending = []
        for order in self._pending:
            price = self.handler.get_latest_bar_value(order.symbol, "close")
            if price is None:
                still_pending.append(order)   # chưa có data, chờ thêm
                continue
            self._do_fill(order, price, date, fills_queue)
        self._pending = still_pending  
    
    def _do_fill(self, order: OrderEvent, price: float,
                 fill_date: date, fills_queue: queue.Queue):
        qty = self._round_lot(order.quantity)
        if qty == 0:
            return

        commission = price * qty * self.commission
        tax        = price * qty * self.tax if order.direction == "SELL" else 0.0

        fill = FillEvent(
            symbol          = order.symbol,
            direction       = order.direction,
            quantity        = qty,
            fill_price      = price,
            date            = fill_date,
            commission      = commission,
            tax             = tax,
            settlement_date = self.cal.settlement_date(fill_date),
        )
        fills_queue.put(fill)   # ← nhét vào queue tạm của engine

    def _round_lot(self, qty: int) -> int:
        """HOSE: lô tối thiểu 100 cổ phiếu."""
        return (qty // 100) * 100