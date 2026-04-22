import queue
from dataclasses import dataclass, field
from core.event import EventType

class BacktestEngine:
    def __init__(self, feed, strategy, broker, portfolio):
        self.feed = feed  #Nguồn data
        self.strategy = strategy
        self.broker = broker
        self.portfolio = portfolio
    
    def run(self):
        for bar in self.feed:
            #Tạo queue mới
            events = queue.Queue()

            #Thêm MarketEvent vào queue
            from core.event import MarketEvent
            events.put(MarketEvent(**bar))

            while not events.empty():
                ev = events.get()

                if ev.type == EventType.MARKET:
                    #Settle T+2
                    self.portfolio.settle_pending(ev.date)
                    #Tính strategy quyết định
                    self.strategy.on_bar(ev,events)
                    #Broker xử lý lệnh chờ
                    self.broker.execute(ev,events)

                elif ev.type == EventType.ORDER:
                    self.broker.execute(ev, events)

                elif ev.type == EventType.FILL:
                    self.portfolio.on_fill(ev)
            # Lưu snapshot cuối mỗi bar
            self.portfolio.record_snapshot(ev.date)
