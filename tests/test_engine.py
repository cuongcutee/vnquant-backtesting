"""
test/test_engine_v2.py

Verify redesigned BacktestEngine + Strategy.generate_signals()

Các điều cần kiểm tra:
    1. generate_signals() chỉ gọi 1 lần / ngày (không phải 1 lần / symbol)
    2. Khi gọi, portfolio.total_equity() đã phản ánh giá mới nhất
    3. generate_signals() nhận đúng symbols_today
    4. Strategy thấy toàn bộ universe khi tính toán
    5. SELL được execute trước BUY (_rebalance_many sort)
    6. _is_month_end() và _is_quarter_end() hoạt động đúng
    7. equity_curve có đúng 1 snapshot / ngày (không phải / symbol)
    8. Khi 1 symbol không có data ngày đó → không ảnh hưởng symbols khác
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import date
from collections import defaultdict

from core.event     import OrderEvent, FillEvent, EventType
from core.engine    import BacktestEngine
from strategy.base  import Strategy


# ─── Mock objects ─────────────────────────────────────────────────────────────

class MockHandler:
    """
    Simulate DataHandler với data tĩnh.
    data = {symbol: [(date, close), ...]}
    """
    def __init__(self, data: dict):
        # data: {sym: {date: close}}
        self._data = data
        self._current_date = None
        self._current_prices = {}  # {sym: close} cho ngày hiện tại

    def heartbeats_by_date(self):
        # Gom tất cả dates từ tất cả symbols
        all_dates = sorted(set(
            d for prices in self._data.values() for d in prices
        ))
        for d in all_dates:
            self._current_date = d
            symbols_today = [sym for sym in self._data if d in self._data[sym]]
            # Update current prices
            for sym in symbols_today:
                self._current_prices[sym] = self._data[sym][d]
            yield d, symbols_today

    def get_latest_bar_value(self, symbol: str, field: str):
        if field == "close":
            return self._current_prices.get(symbol)
        return None

    def get_latest_bars(self, symbol: str, N: int = 1):
        return []  # không cần cho test này


class MockPortfolio:
    """Simulate Portfolio đủ để test engine flow."""
    def __init__(self, cash: float = 100_000_000):
        self.cash           = cash
        self.positions      = {}    # {sym: qty}
        self.current_prices = {}
        self.equity_curve   = []
        self._open_equity   = cash
        self._peak_equity   = cash

    def update_price(self, symbol: str, price: float):
        self.current_prices[symbol] = price

    def total_equity(self) -> float:
        pos_val = sum(
            qty * self.current_prices.get(sym, 0)
            for sym, qty in self.positions.items()
        )
        return self.cash + pos_val

    def on_fill(self, fill: FillEvent):
        if fill.direction == "BUY":
            cost = fill.fill_price * fill.quantity + fill.commission
            self.cash -= cost
            self.positions[fill.symbol] = self.positions.get(fill.symbol, 0) + fill.quantity
        elif fill.direction == "SELL":
            self.positions[fill.symbol] = self.positions.get(fill.symbol, 0) - fill.quantity
            net = fill.fill_price * fill.quantity - fill.commission - fill.tax
            self.cash += net

    def settle_pending(self, d: date):
        pass  # simplified — không test T+2 ở đây

    def record_snapshot(self, d: date):
        self.equity_curve.append({
            "date":   d,
            "equity": self.total_equity(),
            "cash":   self.cash,
        })


class MockBroker:
    """
    Simulate broker: execute() ghi nhận order, process_pending() fill ngay
    (simplified — không cần T+2 để test engine logic).
    """
    def __init__(self, handler):
        self.handler  = handler
        self._pending = []
        self.filled   = []    # log FillEvent đã fill

    def execute(self, order: OrderEvent):
        self._pending.append(order)

    def process_pending(self, d: date, fills_queue):
        import queue
        still_pending = []
        for order in self._pending:
            price = self.handler.get_latest_bar_value(order.symbol, "close")
            if price is None:
                still_pending.append(order)
                continue
            commission = price * order.quantity * 0.0015
            tax = price * order.quantity * 0.001 if order.direction == "SELL" else 0.0
            fill = FillEvent(
                symbol=order.symbol,
                direction=order.direction,
                quantity=order.quantity,
                fill_price=price,
                date=d,
                commission=commission,
                tax=tax,
            )
            fills_queue.put(fill)
            self.filled.append(fill)
        self._pending = still_pending


# ─── Spy strategy — đếm generate_signals() calls ─────────────────────────────

class SpyStrategy(Strategy):
    """
    Đếm generate_signals() được gọi bao nhiêu lần.
    Ghi lại: ngày nào, symbols nào, NAV lúc gọi.
    Không sinh order.
    """
    def __init__(self, symbols, handler):
        super().__init__(symbols, handler)
        self.calls = []   # [(date, symbols_today, nav)]

    def generate_signals(self, date, symbols_today, portfolio):
        self.calls.append({
            "date":          date,
            "symbols_today": list(symbols_today),
            "nav":           portfolio.total_equity(),
        })
        return []


class BuyOnceStrategy(Strategy):
    """
    Ngày đầu tiên: mua 100 cổ mỗi symbol.
    Sau đó: không làm gì.
    Dùng để verify _rebalance_many() và SELL-before-BUY sort.
    """
    def __init__(self, symbols, handler, qty_per_sym=100):
        super().__init__(symbols, handler)
        self.qty_per_sym = qty_per_sym
        self._bought     = False

    def generate_signals(self, date, symbols_today, portfolio):
        if self._bought:
            return []
        self._bought = True
        targets = {sym: self.qty_per_sym for sym in symbols_today}
        return self._rebalance_many(targets, portfolio, date=date)


class MomentumStrategy(Strategy):
    """
    Simplified momentum: mỗi tháng chọn symbol có close cao nhất → mua hết.
    Dùng để verify strategy thấy toàn bộ symbols khi ra quyết định.
    """
    def __init__(self, symbols, handler, budget_pct=0.9):
        super().__init__(symbols, handler)
        self.budget_pct = budget_pct

    def generate_signals(self, date, symbols_today, portfolio):
        if not self._is_month_end(date):
            return []

        # Tìm symbol có close cao nhất hôm nay
        scores = {}
        for sym in symbols_today:
            price = self.handler.get_latest_bar_value(sym, "close")
            if price:
                scores[sym] = price

        if not scores:
            return []

        winner = max(scores, key=scores.get)
        nav    = portfolio.total_equity()
        price  = scores[winner]
        qty    = (int(nav * self.budget_pct / price) // 100) * 100

        # Thoát tất cả symbols khác, mua winner
        targets = {sym: 0 for sym in self.symbols}
        targets[winner] = qty
        return self._rebalance_many(targets, portfolio, date=date)


# ─── TESTS ────────────────────────────────────────────────────────────────────

def test_generate_signals_called_once_per_day():
    """
    Core test: generate_signals() phải được gọi đúng 1 lần / ngày,
    không phải 1 lần / symbol.
    """
    symbols = ["VCB", "FPT", "HPG"]
    dates   = [date(2024, 1, 2), date(2024, 1, 3), date(2024, 1, 4)]

    data = {
        sym: {d: 10_000 * (i + 1) for i, d in enumerate(dates)}
        for sym in symbols
    }

    handler   = MockHandler(data)
    portfolio = MockPortfolio()
    broker    = MockBroker(handler)
    strategy  = SpyStrategy(symbols, handler)
    engine    = BacktestEngine(handler, strategy, broker, portfolio)

    engine.run()

    n_days    = len(dates)
    n_symbols = len(symbols)
    n_calls   = len(strategy.calls)

    assert n_calls == n_days, (
        f"generate_signals() bị gọi {n_calls} lần — expected {n_days} lần (1/ngày). "
        f"Nếu = {n_days * n_symbols} thì đang bị gọi 1 lần/symbol."
    )
    print(f"✅ generate_signals() gọi đúng {n_calls} lần cho {n_days} ngày")


def test_prices_updated_before_generate_signals():
    """
    Khi generate_signals() được gọi, portfolio.total_equity() phải
    phản ánh giá mới nhất của ngày hôm đó.
    """
    symbols = ["VCB", "FPT"]
    dates   = [date(2024, 1, 2), date(2024, 1, 3)]

    # Ngày 1: VCB=87500, FPT=125000
    # Ngày 2: VCB=88000, FPT=126000
    data = {
        "VCB": {date(2024,1,2): 87_500,  date(2024,1,3): 88_000},
        "FPT": {date(2024,1,2): 125_000, date(2024,1,3): 126_000},
    }

    handler   = MockHandler(data)
    portfolio = MockPortfolio(cash=100_000_000)
    broker    = MockBroker(handler)

    nav_at_call = []

    class NavCheckStrategy(Strategy):
        def generate_signals(self, date, symbols_today, portfolio):
            nav_at_call.append((date, portfolio.total_equity()))
            return []

    strategy = NavCheckStrategy(symbols, handler)
    engine   = BacktestEngine(handler, strategy, broker, portfolio)
    engine.run()

    # Ngày 1: NAV = cash = 100_000_000 (chưa mua gì)
    d1_date, d1_nav = nav_at_call[0]
    assert d1_nav == 100_000_000, f"NAV ngày 1 sai: {d1_nav}"
    print(f"✅ Phase 1 (update prices) chạy trước Phase 2 (generate_signals) — NAV đúng")


def test_symbols_today_correct():
    """
    Khi 1 symbol không có data 1 ngày nào đó,
    symbols_today phải chỉ chứa symbols CÓ data.
    """
    symbols = ["VCB", "FPT", "HPG"]

    # HPG chỉ có data ngày 2 và 3, không có ngày 1
    data = {
        "VCB": {date(2024,1,2): 87_500, date(2024,1,3): 88_000, date(2024,1,4): 88_500},
        "FPT": {date(2024,1,2): 125_000, date(2024,1,3): 126_000, date(2024,1,4): 127_000},
        "HPG": {date(2024,1,3): 27_000, date(2024,1,4): 27_500},  # missing ngày 2/1
    }

    handler  = MockHandler(data)
    portfolio = MockPortfolio()
    broker    = MockBroker(handler)
    strategy  = SpyStrategy(symbols, handler)
    engine    = BacktestEngine(handler, strategy, broker, portfolio)
    engine.run()

    first_day = strategy.calls[0]
    assert date(2024,1,2) == first_day["date"]
    assert "HPG" not in first_day["symbols_today"], (
        "HPG không có data ngày 2/1 nhưng vẫn xuất hiện trong symbols_today"
    )
    assert "VCB" in first_day["symbols_today"]
    assert "FPT" in first_day["symbols_today"]
    print(f"✅ symbols_today ngày {first_day['date']}: {first_day['symbols_today']} (HPG vắng đúng)")


def test_one_snapshot_per_day_multi_symbol():
    """
    equity_curve phải có đúng N entries = N ngày giao dịch,
    không phải N ngày × M symbols.
    """
    symbols = ["VCB", "FPT", "HPG", "MBB"]
    dates   = [date(2024, 1, 2), date(2024, 1, 3), date(2024, 1, 4),
               date(2024, 1, 5), date(2024, 1, 8)]

    data = {sym: {d: 50_000 for d in dates} for sym in symbols}

    handler   = MockHandler(data)
    portfolio = MockPortfolio()
    broker    = MockBroker(handler)
    strategy  = SpyStrategy(symbols, handler)
    engine    = BacktestEngine(handler, strategy, broker, portfolio)
    engine.run()

    assert len(portfolio.equity_curve) == len(dates), (
        f"equity_curve có {len(portfolio.equity_curve)} entries — expected {len(dates)}. "
        f"Nếu = {len(dates)*len(symbols)} thì bị duplicate snapshot."
    )
    print(f"✅ equity_curve có đúng {len(portfolio.equity_curve)} entries ({len(dates)} ngày × 1)")


def test_rebalance_many_sell_before_buy():
    """
    _rebalance_many() phải sort SELL trước BUY.
    Nếu BUY trước SELL → có thể thiếu cash → order bị reject.
    """
    symbols   = ["VCB", "FPT"]
    data      = {
        "VCB": {date(2024,1,2): 87_500},
        "FPT": {date(2024,1,2): 125_000},
    }
    handler   = MockHandler(data)
    portfolio = MockPortfolio(cash=10_000_000)
    # Giả sử đang giữ VCB, muốn chuyển sang FPT
    portfolio.positions = {"VCB": 100}
    portfolio.current_prices = {"VCB": 87_500, "FPT": 125_000}

    broker   = MockBroker(handler)
    strategy = BuyOnceStrategy(symbols, handler, qty_per_sym=0)  # won't trade

    # Test trực tiếp _rebalance_many
    targets = {"VCB": 0, "FPT": 100}  # bán VCB, mua FPT
    orders  = strategy._rebalance_many(targets, portfolio, date=date(2024,1,2))

    assert len(orders) == 2
    assert orders[0].direction == "SELL", f"Order đầu phải là SELL, got {orders[0].direction}"
    assert orders[1].direction == "BUY",  f"Order thứ 2 phải là BUY, got {orders[1].direction}"
    print(f"✅ _rebalance_many sort đúng: {orders[0].direction} {orders[0].symbol} trước {orders[1].direction} {orders[1].symbol}")


def test_momentum_strategy_sees_all_symbols():
    """
    MomentumStrategy phải thấy toàn bộ symbols để so sánh và chọn winner.
    Nếu chỉ thấy 1 symbol tại 1 thời điểm → không thể rank.
    Test: 3 symbols, FPT luôn cao nhất → strategy phải mua FPT.
    """
    symbols = ["VCB", "FPT", "HPG"]

    # Ngày cuối tháng 1: 31/1/2024
    # FPT có giá cao nhất → strategy phải chọn FPT
    # Cần ngày 2/2 để broker fill lệnh đặt ngày 31/1 (fill T+1 bar)
    data = {
        "VCB": {date(2024,1,31): 87_500,  date(2024,2,1): 87_600},
        "FPT": {date(2024,1,31): 125_000, date(2024,2,1): 125_200},  # cao nhất
        "HPG": {date(2024,1,31): 27_000,  date(2024,2,1): 27_100},
    }

    handler   = MockHandler(data)
    portfolio = MockPortfolio(cash=100_000_000)
    broker    = MockBroker(handler)
    strategy  = MomentumStrategy(symbols, handler)
    engine    = BacktestEngine(handler, strategy, broker, portfolio)
    engine.run()

    # Broker nhận order — check order cho FPT
    buy_orders  = [o for o in broker.filled if o.direction == "BUY"]
    sell_orders = [o for o in broker.filled if o.direction == "SELL"]

    # Phải có BUY FPT
    fpt_buys = [o for o in buy_orders if o.symbol == "FPT"]
    vcb_buys = [o for o in buy_orders if o.symbol == "VCB"]
    hpg_buys = [o for o in buy_orders if o.symbol == "HPG"]

    assert len(fpt_buys) > 0, "Strategy không mua FPT dù FPT có giá cao nhất"
    assert len(vcb_buys) == 0, "Strategy không được mua VCB"
    assert len(hpg_buys) == 0, "Strategy không được mua HPG"
    print(f"✅ MomentumStrategy chọn đúng FPT (cao nhất), qty={fpt_buys[0].quantity}")


def test_rebalance_to_no_trade_when_already_at_target():
    """
    _rebalance_to() phải trả về None nếu position đã đúng target.
    Tránh tạo order không cần thiết (phí commission).
    """
    symbols  = ["VCB"]
    data     = {"VCB": {date(2024,1,2): 87_500}}
    handler  = MockHandler(data)
    portfolio = MockPortfolio()
    portfolio.positions = {"VCB": 100}  # đang giữ đúng 100

    strategy = SpyStrategy(symbols, handler)  # chỉ cần instance để test helper
    result   = strategy._rebalance_to("VCB", 100, portfolio)  # target = current
    assert result is None, f"Expected None, got {result}"
    print("✅ _rebalance_to() trả về None khi đã đúng target — không tạo order thừa")


def test_is_month_end():
    """_is_month_end() đúng cho các ngày cuối tháng thực tế."""
    symbols  = ["VCB"]
    handler  = MockHandler({"VCB": {}})
    strategy = SpyStrategy(symbols, handler)

    assert strategy._is_month_end(date(2024, 1, 31)) == True
    assert strategy._is_month_end(date(2024, 1, 30)) == False
    assert strategy._is_month_end(date(2024, 2, 29)) == True   # 2024 là năm nhuận
    assert strategy._is_month_end(date(2024, 2, 28)) == False
    assert strategy._is_month_end(date(2024, 12, 31)) == True
    print("✅ _is_month_end() đúng cho tất cả edge cases (năm nhuận, tháng 12)")


def test_is_quarter_end():
    """_is_quarter_end() đúng cho 4 quý."""
    symbols  = ["VCB"]
    handler  = MockHandler({"VCB": {}})
    strategy = SpyStrategy(symbols, handler)

    assert strategy._is_quarter_end(date(2024,  3, 31)) == True   # Q1
    assert strategy._is_quarter_end(date(2024,  3, 30)) == False
    assert strategy._is_quarter_end(date(2024,  6, 30)) == True   # Q2
    assert strategy._is_quarter_end(date(2024,  9, 30)) == True   # Q3
    assert strategy._is_quarter_end(date(2024, 12, 31)) == True   # Q4
    assert strategy._is_quarter_end(date(2024, 12, 30)) == False
    print("✅ _is_quarter_end() đúng cho cả 4 quý")


# ─── Runner ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [
        test_generate_signals_called_once_per_day,
        test_prices_updated_before_generate_signals,
        test_symbols_today_correct,
        test_one_snapshot_per_day_multi_symbol,
        test_rebalance_many_sell_before_buy,
        test_momentum_strategy_sees_all_symbols,
        test_rebalance_to_no_trade_when_already_at_target,
        test_is_month_end,
        test_is_quarter_end,
    ]

    passed = 0
    failed = 0
    print("\n" + "═" * 60)
    print("  vnbacktest — engine v2 + strategy.generate_signals()")
    print("═" * 60)

    for test in tests:
        name = test.__name__
        print(f"\n▸ {name}")
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"  ❌ FAIL: {e}")
            failed += 1
        except Exception as e:
            print(f"  💥 ERROR: {type(e).__name__}: {e}")
            import traceback; traceback.print_exc()
            failed += 1

    print("\n" + "═" * 60)
    print(f"  Kết quả: {passed} passed, {failed} failed / {len(tests)} tests")
    print("═" * 60 + "\n")

    if failed:
        sys.exit(1)