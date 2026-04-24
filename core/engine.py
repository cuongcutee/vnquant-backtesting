import queue
from dataclasses import dataclass, field
from core.event import EventType,MarketEvent

class BacktestEngine:
    def __init__(self, handler, strategy, broker, portfolio):
        self.handler = handler  #Nguồn data
        self.strategy = strategy
        self.broker = broker
        self.portfolio = portfolio
    
    def run(self):
        # heartbeats_by_date() yield (date, [symbols]) — gom tất cả symbols trong 1 ngày
        for date, symbols_today in self.handler.heartbeats_by_date():
 
            # ── 1. Settle T+2 — CHỈ 1 LẦN mỗi ngày
            self.portfolio.settle_pending(date)
 
            # ── 2. Xử lý từng symbol trong ngày 
            for symbol in symbols_today:
 
                # Cập nhật giá hiện tại vào portfolio (để total_equity() đúng)
                close = self.handler.get_latest_bar_value(symbol, "close")
                self.portfolio.update_price(symbol, close)
 
                # Tạo queue riêng cho mỗi symbol trong ngày
                events = queue.Queue()
                events.put(MarketEvent(symbol=symbol, date=date))
 
                # Vòng lặp event
                while not events.empty():
                    ev = events.get()
 
                    if ev.type == EventType.MARKET:
                        # Strategy quyết định → có thể put OrderEvent vào queue
                        self.strategy.on_bar(ev, self.portfolio, events)
                        # Broker fill các lệnh pending của symbol này
                        self.broker.process_pending(ev, events)
 
                    elif ev.type == EventType.ORDER:
                        # Broker nhận lệnh → add vào pending, fill bar tiếp theo
                        self.broker.execute(ev, events)
 
                    elif ev.type == EventType.FILL:
                        # Portfolio cập nhật positions / cash / pending T+2
                        self.portfolio.on_fill(ev)
 
            #  3. Snapshot cuối ngày — CHỈ 1 LẦN mỗi ngày
            # Gọi SAU khi xử lý xong tất cả symbols → tránh duplicate snapshot
            self.portfolio.record_snapshot(date)
 