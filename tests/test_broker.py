# test/test_broker.py
import queue
from datetime import date
from core.event import OrderEvent, FillEvent
from core.broker import T2Broker



class MockHandler:
    """Giả lập HistoricDataHandler — chỉ cần get_latest_bar_value()."""
    def __init__(self, prices: dict):
        # prices = {"VCB": 87500, "FPT": 95000}
        self._prices = prices

    def get_latest_bar_value(self, symbol: str, field: str):
        if field == "close":
            return self._prices.get(symbol, None)
        return None



class MockPortfolio:
    """Giả lập Portfolio — chỉ cần positions."""
    def __init__(self, positions: dict = None):
        self.positions = positions or {}



def make_broker(prices: dict, positions: dict = None):
    handler = MockHandler(prices)
    broker  = T2Broker(handler)
    broker._portfolio_ref = MockPortfolio(positions or {})
    return broker


def get_fill(fills_queue: queue.Queue) -> FillEvent:
    assert not fills_queue.empty(), "fills_queue trống — không có fill nào"
    return fills_queue.get()


#Test 1: execute() chỉ append pending, không fill ngay
def test_execute_does_not_fill_immediately():
    broker = make_broker({"VCB": 87500})
    broker.execute(OrderEvent(symbol="VCB", direction="BUY", quantity=100,
                              date=date(2024, 1, 2)))
    assert len(broker._pending) == 1, "execute() phải append vào _pending"


#  Test 2: Commission tính đúng, BUY không có tax 
def test_commission_and_no_tax_on_buy():
    broker = make_broker({"VCB": 87500})
    broker.execute(OrderEvent(symbol="VCB", direction="BUY", quantity=100))

    fills = queue.Queue()
    broker.process_pending(date(2024, 1, 3), fills)
    fill = get_fill(fills)

    expected_commission = 87500 * 100 * 0.0015
    assert abs(fill.commission - expected_commission) < 0.01, \
        f"Commission sai: expected {expected_commission}, got {fill.commission}"
    assert fill.tax == 0.0, "BUY không có tax"


#  Test 3: Tax tính đúng khi SELL 
def test_tax_on_sell():
    broker = make_broker({"VCB": 87500}, positions={"VCB": 200})
    broker.execute(OrderEvent(symbol="VCB", direction="SELL", quantity=100))

    fills = queue.Queue()
    broker.process_pending(date(2024, 1, 3), fills)
    fill = get_fill(fills)

    expected_tax = 87500 * 100 * 0.001
    assert abs(fill.tax - expected_tax) < 0.01, \
        f"Tax sai: expected {expected_tax}, got {fill.tax}"


#Test 4: Fill xảy ra ngày T+1, không phải T+0 
def test_fill_happens_next_bar():
    broker = make_broker({"VCB": 87500})
    broker.execute(OrderEvent(symbol="VCB", direction="BUY", quantity=100,
                              date=date(2024, 1, 2)))

    # T+0: chưa fill
    fills = queue.Queue()
    assert len(broker._pending) == 1, "T+0: vẫn còn pending"

    # T+1: mới fill
    broker.process_pending(date(2024, 1, 3), fills)
    fill = get_fill(fills)

    assert fill.date == date(2024, 1, 3), \
        f"Fill date phải là T+1 (2024-01-03), got {fill.date}"
    assert len(broker._pending) == 0, "Sau fill: _pending phải rỗng"


# Test 5: Fill price lấy từ handler (close hôm nay)
def test_fill_price_from_handler():
    broker = make_broker({"VCB": 91000})
    broker.execute(OrderEvent(symbol="VCB", direction="BUY", quantity=100))

    fills = queue.Queue()
    broker.process_pending(date(2024, 1, 3), fills)
    fill = get_fill(fills)

    assert fill.fill_price == 91000, \
        f"fill_price phải lấy từ handler close, got {fill.fill_price}"


#  Test 6: Lot rounding — chỉ fill bội số 100 
def test_lot_rounding():
    broker = make_broker({"VCB": 87500})
    broker.execute(OrderEvent(symbol="VCB", direction="BUY", quantity=150))

    fills = queue.Queue()
    broker.process_pending(date(2024, 1, 3), fills)
    fill = get_fill(fills)

    assert fill.quantity == 100, \
        f"150 phải round xuống 100 (lô 100), got {fill.quantity}"


#  Test 7: Quantity < 100 → không fill gì cả
def test_lot_too_small_no_fill():
    broker = make_broker({"VCB": 87500})
    broker.execute(OrderEvent(symbol="VCB", direction="BUY", quantity=50))

    fills = queue.Queue()
    broker.process_pending(date(2024, 1, 3), fills)

    assert fills.empty(), "Quantity < 100 không được fill"


#Test 8: Symbol không có data → giữ lại pending 
def test_no_data_stays_pending():
    broker = make_broker({})   # handler không có VCB
    broker.execute(OrderEvent(symbol="VCB", direction="BUY", quantity=100))

    fills = queue.Queue()
    broker.process_pending(date(2024, 1, 3), fills)

    assert fills.empty(),         "Không có data → không fill"
    assert len(broker._pending) == 1, "Không có data → giữ lại pending"


if __name__ == "__main__":
    tests = [
        test_execute_does_not_fill_immediately,
        test_commission_and_no_tax_on_buy,
        test_tax_on_sell,
        test_fill_happens_next_bar,
        test_fill_price_from_handler,
        test_lot_rounding,
        test_lot_too_small_no_fill,
        test_no_data_stays_pending,
    ]

    passed = 0
    for test in tests:
        try:
            test()
            print(f"  PASS  {test.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  FAIL  {test.__name__} — {e}")
        except Exception as e:
            print(f"  ERROR {test.__name__} — {e}")

    print(f"\n{passed}/{len(tests)} passed")