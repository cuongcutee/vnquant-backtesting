
from datetime import date
from core.engine import BacktestEngine

class MockFeed:
    def __iter__(self):
        for i in range(2, 7):  # 5 bars
            yield {"symbol":"VCB","date":date(2024,1,i),
                   "open":85000.0,"high":86000.0,
                   "low":84000.0,"close":85500.0,"volume":1_000_000}

class MockStrategy:
    def on_bar(self, event, events): pass

class MockBroker:
    def process_pending(self, event, events): pass
    def execute(self, order, events): pass

class MockPortfolio:
    def __init__(self):
        self.snapshots = []
    def settle_pending(self, date): pass
    def on_fill(self, fill): pass
    def record_snapshot(self, date):
        self.snapshots.append(date)

# Chạy
engine = BacktestEngine(MockFeed(), MockStrategy(), MockBroker(), MockPortfolio())
engine.run()

assert len(engine.portfolio.snapshots) == 5
print("✅ Engine OK —", len(engine.portfolio.snapshots), "snapshots")

