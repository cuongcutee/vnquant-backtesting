from datetime import date
from core.event import FillEvent


class Portfolio:
    def __init__(self, cash: float = 100_000_000):
        self.cash               = cash
        self.initial_cash       = cash          # để tính tổng return sau này
        self.positions          = {}            # {symbol: qty} — cổ phiếu đã về tài khoản
        self.current_prices     = {}            # {symbol: price} — giá close mới nhất
        self.pending_cash       = {}            # {settlement_date: amount} — tiền bán chờ về
        self.pending_shares     = {}            # {settlement_date: {symbol: qty}} — CP mua chờ về
        self.equity_curve       = []            # list[dict] — lịch sử NAV mỗi ngày
        self._peak_equity       = cash          # đỉnh NAV — dùng tính drawdown
        self._today_open_equity = cash          # NAV đầu ngày — dùng tính PnL hôm nay

    def update_price(self, symbol: str, price: float):
        """Engine gọi mỗi ngày sau khi có bar mới."""
        self.current_prices[symbol] = price


    def total_equity(self) -> float:
        """Cash + market value của tất cả positions đã settled."""
        pos_val = sum(
            qty * self.current_prices.get(sym, 0)
            for sym, qty in self.positions.items()
        )
        return self.cash + pos_val

    def today_pnl_pct(self) -> float:
        """% lời/lỗ so với đầu ngày. Dùng trong RiskLimits."""
        return (self.total_equity() - self._today_open_equity) / self._today_open_equity

    def current_drawdown(self) -> float:
        """Drawdown hiện tại từ đỉnh. Luôn <= 0. Dùng trong RiskLimits."""
        eq = self.total_equity()
        self._peak_equity = max(self._peak_equity, eq)
        return (eq - self._peak_equity) / self._peak_equity

    def on_fill(self, fill: FillEvent):
        """
        Xử lý FillEvent từ broker.
        BUY  → trừ cash ngay, CP vào pending_shares chờ T+2.
        SELL → trừ positions ngay, tiền vào pending_cash chờ T+2.
        """
        if fill.direction == "BUY":
            # Trừ cash ngay (tiền đã bị phong tỏa khi đặt lệnh)
            self.cash -= fill.fill_price * fill.quantity + fill.commission

            # CP chưa về ngay — nằm pending đến settlement_date
            self.pending_shares.setdefault(fill.settlement_date, {})
            self.pending_shares[fill.settlement_date][fill.symbol] = (
                self.pending_shares[fill.settlement_date].get(fill.symbol, 0)
                + fill.quantity
            )

        elif fill.direction == "SELL":
            # Trừ positions ngay (không thể bán lại CP này)
            self.positions[fill.symbol] = (
                self.positions.get(fill.symbol, 0) - fill.quantity
            )

            # Tiền chưa về ngay — nằm pending đến settlement_date
            net = fill.fill_price * fill.quantity - fill.commission - fill.tax
            self.pending_cash[fill.settlement_date] = (
                self.pending_cash.get(fill.settlement_date, 0) + net
            )

 
    def settle_pending(self, today: date):
        """
        Engine gọi mỗi đầu ngày.
        Giải phóng tất cả pending có settlement_date <= today.
        """
        # Tiền bán về tài khoản
        for d in [d for d in list(self.pending_cash) if d <= today]:
            self.cash += self.pending_cash.pop(d)

        # CP mua về tài khoản
        for d in [d for d in list(self.pending_shares) if d <= today]:
            for sym, qty in self.pending_shares.pop(d).items():
                self.positions[sym] = self.positions.get(sym, 0) + qty

    def record_snapshot(self, d: date):
        """
        Engine gọi cuối mỗi ngày, SAU settle_pending().
        Lưu NAV vào equity_curve và reset _today_open_equity cho ngày hôm sau.
        """
        eq = self.total_equity()
        self._peak_equity       = max(self._peak_equity, eq)
        self._today_open_equity = eq    # reset — ngày mai so sánh với mức này
        self.equity_curve.append({
            "date":     d,
            "cash":     self.cash,
            "equity":   eq,
            "drawdown": self.current_drawdown(),
        })