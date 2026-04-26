from abc import ABC, abstractmethod
from datetime import date, timedelta
from typing import Optional

from core.event import OrderEvent


class Strategy(ABC):

    def __init__(self, symbols, handler, sizer=None):
        self.symbols = symbols
        self.handler = handler  # DataHandler — dùng để lấy giá, bars, indicators
        self.sizer   = sizer

    @abstractmethod
    def generate_signals(
        self,
        date:          date,
        symbols_today: list[str],
        portfolio,
    ) -> list[OrderEvent]:
        pass

    # ── Order helpers ─────────────────────────────────────────────────────────

    def _order(
        self,
        symbol:      str,
        direction:   str,
        quantity:    int,
        order_type:  str             = "MARKET",
        limit_price: Optional[float] = None,
        date:        Optional[date]  = None,
    ) -> Optional[OrderEvent]:
        
        if quantity <= 0:
            return None
        return OrderEvent(
            symbol=symbol,
            direction=direction,
            quantity=quantity,
            order_type=order_type,
            limit_price=limit_price,
            date=date,
        )

    def _buy(self, symbol: str, quantity: int, date=None, **kw) -> Optional[OrderEvent]:
        return self._order(symbol, "BUY", quantity, date=date, **kw)

    def _sell(self, symbol: str, quantity: int, date=None, **kw) -> Optional[OrderEvent]:
        return self._order(symbol, "SELL", quantity, date=date, **kw)

    def _rebalance_to(
        self,
        symbol:      str,
        target_qty:  int,
        portfolio,
        date:        Optional[date]  = None,
        order_type:  str             = "MARKET",
        limit_price: Optional[float] = None,
    ) -> Optional[OrderEvent]:
        current = portfolio.positions.get(symbol, 0)
        diff    = target_qty - current
        if diff > 0:
            return self._order(symbol, "BUY",  diff,      order_type, limit_price, date)
        if diff < 0:
            return self._order(symbol, "SELL", abs(diff), order_type, limit_price, date)
        
        return None

    
    def _rebalance_many(
        self,
        targets:  dict[str, int],
        portfolio,
        date:     Optional[date] = None,
    ) -> list[OrderEvent]:
        orders = []
        all_syms = set(targets) | set(portfolio.positions)
        for sym in all_syms:
            target = targets.get(sym, 0)
            order  = self._rebalance_to(sym, target, portfolio, date=date)
            if order:
                orders.append(order)
        # SELL trước BUY để giải phóng cash
        orders.sort(key=lambda o: 0 if o.direction == "SELL" else 1)
        return orders

    

    def _is_month_end(self, d: date) -> bool:
        return (d + timedelta(days=1)).month != d.month

    def _is_quarter_end(self, d: date) -> bool:
        next_day = d + timedelta(days=1)
        return (next_day.month - 1) // 3 != (d.month - 1) // 3