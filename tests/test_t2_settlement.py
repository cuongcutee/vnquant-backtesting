from datetime import date
from core.portfolio import Portfolio
from core.event import FillEvent
from data.calendar import VNTradingCalendar

def make_buy_fill(symbol="VCB", quantity=100, fill_price=87500,
                  fill_date=date(2024, 3, 1), settlement_date=date(2024, 3, 5)):
    commission = fill_price * quantity * 0.0015
    return FillEvent(
        symbol=symbol, direction="BUY",
        quantity=quantity, fill_price=fill_price,
        date=fill_date, commission=commission, tax=0.0,
        settlement_date=settlement_date,
    )

def make_sell_fill(symbol="VCB", quantity=100, fill_price=88000,
                   fill_date=date(2024, 3, 1), settlement_date=date(2024, 3, 5)):
    commission = fill_price * quantity * 0.0015
    tax        = fill_price * quantity * 0.001
    return FillEvent(
        symbol=symbol, direction="SELL",
        quantity=quantity, fill_price=fill_price,
        date=fill_date, commission=commission, tax=tax,
        settlement_date=settlement_date,
    )


def test_buy_friday_shares_arrive_tuesday():
    portfolio = Portfolio(100_000_000)
    fill = make_buy_fill(fill_date=date(2024, 3, 1), settlement_date=date(2024, 3, 5))
    portfolio.on_fill(fill)

    portfolio.settle_pending(date(2024, 3, 4))          # T+1 — chưa về
    assert portfolio.positions.get("VCB", 0) == 0, "T+1: CP chưa được về"

    portfolio.settle_pending(date(2024, 3, 5))          # T+2 — về rồi
    assert portfolio.positions.get("VCB", 0) == 100, "T+2: CP phải về đủ 100"


def test_sell_friday_cash_arrives_tuesday():
    portfolio = Portfolio(100_000_000)
    portfolio.positions["VCB"] = 100
    cash_before = portfolio.cash

    fill = make_sell_fill(fill_date=date(2024, 3, 1), settlement_date=date(2024, 3, 5))
    portfolio.on_fill(fill)

    portfolio.settle_pending(date(2024, 3, 4))          # T+1 — cash chưa về
    assert portfolio.cash == cash_before, "T+1: cash chưa được thay đổi"

    portfolio.settle_pending(date(2024, 3, 5))          # T+2 — cash về
    net = 88000 * 100 - 88000 * 100 * 0.0015 - 88000 * 100 * 0.001
    assert abs(portfolio.cash - (cash_before + net)) < 1, "T+2: cash phải về đúng"


def test_settle_t1_does_nothing():
    portfolio = Portfolio(100_000_000)
    fill = make_buy_fill(fill_date=date(2024, 3, 1), settlement_date=date(2024, 3, 5))
    portfolio.on_fill(fill)
    cash_after_fill = portfolio.cash

    portfolio.settle_pending(date(2024, 3, 2))
    assert portfolio.positions.get("VCB", 0) == 0,  "T+1: CP không được về sớm"
    assert portfolio.cash == cash_after_fill,         "T+1: cash không được thay đổi"


def test_multi_fill_same_settlement_date():
    portfolio = Portfolio(200_000_000)
    fill1 = make_buy_fill(symbol="VCB", quantity=100,
                          fill_date=date(2024, 3, 1), settlement_date=date(2024, 3, 5))
    fill2 = make_buy_fill(symbol="VCB", quantity=200,
                          fill_date=date(2024, 3, 1), settlement_date=date(2024, 3, 5))
    portfolio.on_fill(fill1)
    portfolio.on_fill(fill2)

    portfolio.settle_pending(date(2024, 3, 5))
    assert portfolio.positions.get("VCB", 0) == 300, "Multi-fill: phải cộng dồn 100+200"


def test_calendar_through_holiday():
    cal = VNTradingCalendar()
    result = cal.settlement_date(date(2025, 1, 28))
    assert result >= date(2025, 2, 3), "Mua trước Tết phải nhảy qua ngày nghỉ"


def test_calendar_friday_to_tuesday():
    cal = VNTradingCalendar()
    result = cal.settlement_date(date(2024, 3, 1))
    assert result == date(2024, 3, 5), f"Thứ 6 → thứ 3, expected 5/3, got {result}"

if __name__ == "__main__":
    tests = [
        test_buy_friday_shares_arrive_tuesday,
        test_sell_friday_cash_arrives_tuesday,
        test_settle_t1_does_nothing,
        test_multi_fill_same_settlement_date,
        test_calendar_through_holiday,
        test_calendar_friday_to_tuesday,
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