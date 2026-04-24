# tests/test_strategy.py
from queue import Queue
from unittest.mock import MagicMock
from strategy.base import BuyAndHold

def make_event(symbol="VCB", close=85000):
    event        = MagicMock()
    event.symbol = symbol
    event.close  = close
    return event

def make_portfolio(cash=100_000_000):
    portfolio           = MagicMock()
    portfolio.cash      = cash
    portfolio.positions = {}
    return portfolio


def test_buys_on_first_bar():
    strategy  = BuyAndHold(symbols=["VCB"])
    events    = Queue()

    strategy.on_bar(make_event(), make_portfolio(), events)

    assert not events.empty(), "Phải có lệnh BUY"
    order = events.get()
    assert order.direction == "BUY"
    assert order.symbol    == "VCB"
    assert order.quantity  % 100 == 0
    print("✅ test_buys_on_first_bar passed")


def test_quantity_correct():
    strategy  = BuyAndHold(symbols=["VCB"])
    events    = Queue()

    strategy.on_bar(make_event(close=85000), make_portfolio(cash=100_000_000), events)

    order = events.get()
    # budget = 100_000_000 * 0.95 = 95_000_000
    # raw    = 95_000_000 / 85000 = 1117
    # lot    = 1100
    assert order.quantity == 1100, f"Expected 1100, got {order.quantity}"
    print("✅ test_quantity_correct passed")


def test_no_order_after_first_bar():
    strategy  = BuyAndHold(symbols=["VCB"])
    events    = Queue()

    strategy.on_bar(make_event(), make_portfolio(), events)  # bar 1
    events.get()                                              # clear

    strategy.on_bar(make_event(), make_portfolio(), events)  # bar 2
    assert events.empty(), "Bar 2 không được tạo lệnh"
    print("✅ test_no_order_after_first_bar passed")


if __name__ == "__main__":
    test_buys_on_first_bar()
    test_quantity_correct()
    test_no_order_after_first_bar()
    print("\n✅ All tests passed")