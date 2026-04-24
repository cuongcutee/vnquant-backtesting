from datetime import date
from core.engine import BacktestEngine
from core.event import MarketEvent, OrderEvent, FillEvent
from strategy.base import Strategy


# ── Feed ──────────────────────────────────────────────────────────────
class MockFeed:
    def __iter__(self):
        for i in [2, 3, 4, 5, 8, 9]:
            yield {
                "symbol": "VCB",
                "date":   date(2024, 1, i),
                "open":   85000.0 + i * 1000,
                "high":   86000.0 + i * 1000,
                "low":    84000.0 + i * 1000,
                "close":  85500.0 + i * 1000,
                "volume": 1_000_000,
            }


# ── Broker ────────────────────────────────────────────────────────────
from core.event import FillEvent, EventType
from datetime import timedelta

class MockBroker:
    COMMISSION_RATE = 0.0015
    TAX_RATE        = 0.001

    def __init__(self):
        self._last_prices = {}

    def process_pending(self, market_event, events):
        self._last_prices[market_event.symbol] = market_event.close
        

    def execute(self, order_event, events):
        print(f"DEBUG order: {order_event}") 
        price      = self._last_prices.get(order_event.symbol, 0.0)
        commission = price * order_event.quantity * self.COMMISSION_RATE
        tax        = (price * order_event.quantity * self.TAX_RATE
                      if order_event.direction == "SELL" else 0.0)
        settlement = order_event.date + timedelta(days=2)

        events.put(FillEvent(
            symbol          = order_event.symbol,
            direction       = order_event.direction,
            quantity        = order_event.quantity,
            fill_price      = price,
            fill_date       = order_event.date,
            commission      = commission,
            tax             = tax,
            slippage        = 0.0,
            settlement_date = settlement,
        ))


# ── Portfolio ─────────────────────────────────────────────────────────
class MockPortfolio:
    def __init__(self, cash=100_000_000):
        self.cash           = cash
        self.positions      = {}
        self.pending_cash   = {}
        self.pending_shares = {}
        self.equity_curve   = []
        self.current_prices = {}

    def settle_pending(self, date):
        pass

    def on_fill(self, fill):
        if fill.direction == "BUY":
            # Trừ cash ngay T+0
            total_cost = fill.fill_price * fill.quantity + fill.commission
            self.cash -= total_cost
            # CP về T+2 — tạm thời cộng thẳng vào positions cho đơn giản
            self.positions[fill.symbol] = (
                self.positions.get(fill.symbol, 0) + fill.quantity
            )

        elif fill.direction == "SELL":
            proceeds = fill.fill_price * fill.quantity - fill.commission - fill.tax
            self.cash += proceeds
            self.positions[fill.symbol] = (
                self.positions.get(fill.symbol, 0) - fill.quantity
            )

    def record_snapshot(self, date):
        positions_value = sum(
            qty * self.current_prices.get(sym, 0)
            for sym, qty in self.positions.items()
        )
        self.equity_curve.append({
            "date":            date,
            "cash":            self.cash,
            "positions_value": positions_value,
            "equity":          self.cash + positions_value,
        })

    def update_price(self, symbol, price):          # ← thêm lại
        self.current_prices[symbol] = price

# ── Strategy ──────────────────────────────────────────────────────────
class MockStrategy(Strategy):
    def __init__(self, symbols, sizer=None):
        super().__init__(symbols, sizer)
        self._initialized = False

    def on_bar(self, event, portfolio, events):
        if self._initialized:
            return
        price    = event.close
        budget   = portfolio.cash * 0.95
        raw_qty  = int(budget / price)
        quantity = (raw_qty // 100) * 100
        self.rebalance_to(event.symbol, quantity, portfolio, events, date=event.date)
        self._initialized = True


# ── Chạy test ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    feed      = MockFeed()
    portfolio = MockPortfolio(cash=100_000_000)
    broker    = MockBroker()
    strategy  = MockStrategy(["VCB"])

    engine = BacktestEngine(feed, strategy, broker, portfolio)
    engine.run()

    print("\nEquity curve:")
    for snap in portfolio.equity_curve:
        print(f"  {snap['date']}  "
            f"cash={snap['cash']:>13,.0f}  "
            f"positions={snap['positions_value']:>13,.0f}  "
            f"NAV={snap['equity']:>13,.0f}")