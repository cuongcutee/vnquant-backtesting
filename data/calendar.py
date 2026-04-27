from datetime import date, timedelta
#Phải cập nhật từng năm 
VN_FIXED_HOLIDAYS = [(1,1), (30,4),(1,5),(2,9)]
VN_LUNAR_HOLIDAYS: set[date]  = {
    date(2020, 1, 23), date(2020, 1, 24),date(2020, 1, 27), date(2020, 1, 28), 
    date(2020, 1, 29),date(2020, 4, 2),date(2021, 2, 11), date(2021, 2, 12),
    date(2021, 2, 15), date(2021, 2, 16),date(2021, 4, 21),date(2022, 1, 31),
    date(2022, 2,  1), date(2022, 2,  2), date(2022, 2,  3), date(2022, 2,  4),
    date(2022, 4, 11),date(2023, 1, 20),date(2023, 1, 23), date(2023, 1, 24), 
    date(2023, 1, 25), date(2023, 1, 26),date(2023, 5, 2), date(2023, 5, 3),
    date(2024, 2,  8), date(2024, 2,  9),date(2024, 2, 12), date(2024, 2, 13),
    date(2024, 2, 14),date(2024, 4, 18),date(2024, 9,  3),date(2025, 1, 27), 
    date(2025, 1, 28), date(2025, 1, 29),date(2025, 1, 30), date(2025, 1, 31),
    date(2025, 4,  7),date(2025, 5,  2),date(2026, 2, 16), date(2026, 2, 17),
    date(2026, 2, 18),date(2026, 2, 19), date(2026, 2, 20),date(2026, 4, 27),
    date(2026, 8, 31), date(2026, 9,  1),}

class VNTradingCalendar:
    def is_trading_day(self,d:date) -> bool:
        if d.weekday()>= 5:
            return False
        if (d.day,d.month) in VN_FIXED_HOLIDAYS:
            return False
        if d in VN_LUNAR_HOLIDAYS:
            return False
        return True
    def add_trading_days(self,d:date,n:int) -> date:
        count = 0
        cur = d
        while count < n:
            cur+= timedelta(days = 1)
            if self.is_trading_day(cur) == True:
                count += 1
        return cur
    def settlement_date(self, trade_date: date) -> date:
        #T+2 VN: ngày CP/tiền thực sự về tài khoản
        return self.add_trading_days(trade_date, 2)

