import queue
from dataclasses import dataclass, field
from core.event import EventType, OrderEvent, FillEvent

class BacktestEngine:
    def __init__(self, handler, strategy, broker, portfolio):
        self.handler = handler  #Nguồn data
        self.strategy = strategy
        self.broker = broker
        self.portfolio = portfolio
    
    def run(self):
        # heartbeats_by_date() yield (date, [symbols]) — gom tất cả symbols trong 1 ngày
        for date, symbols_today in self.handler.heartbeats_by_date():
             self._run_one_day(date, symbols_today)
 


    def _run_one_day(self, date, symbols_today):            # ── 2. Xử lý từng symbol trong ngày 
        for symbol in symbols_today:

            # Cập nhật giá hiện tại vào portfolio (để total_equity() đúng)
            close = self.handler.get_latest_bar_value(symbol, "close")
            if close is not None:
                self.portfolio.update_price(symbol, close)

        orders = self.strategy.generate_signals(date, symbols_today, self.portfolio)
        pending_fills = queue.Queue()
        self.broker.process_pending(date, pending_fills)
        while not pending_fills.empty():
            fill = pending_fills.get()
            if fill.type == EventType.FILL:
                self.portfolio.on_fill(fill)
 
        # 3b. Push lệnh MỚI từ strategy vào broker (sẽ fill ngày mai).
        for order in (orders or []):
            if isinstance(order, OrderEvent) and order.quantity > 0:
                self.broker.execute(order)
 
        # ── Phase 4: Settle T+2 + snapshot ───────────────────────────────────
        # settle_pending trước record_snapshot để NAV cuối ngày đúng.
        self.portfolio.settle_pending(date)
        self.portfolio.record_snapshot(date)