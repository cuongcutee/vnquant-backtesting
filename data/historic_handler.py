from data.handler import DataHandler
import pandas as pd

#input mẫu data : {"VCB": df_vcb, "FPT": df_fpt}
#df_vcb thì index là ngày giao dịch
#Còn symbols thì nói lên những symbol nào mình sẽ sử dụng dể backtest(không nhất thiết là toàn bộ symbol trong data)
#self.date_idx thì nó sẽ tạo 1 bảng tra cứu trả về xem date(2024,1,2): 0 thì là ngày đầu tiên trong DataFrame của symbols đó
#self.current_idx thì sẽ thể hiện là con trỏ đang trỏ tới ngày nào: Mình khởi tạo = -1 để cho thấy là mình vẫn chưa bắt đầu
class HistoricDataHandler(DataHandler):
    def __init__(self,data:dict[str,pd.DataFrame],symbols: list):
        self._data = data
        self.symbols = symbols

        self._date_idx = {
            sym:{d:i for i,d in enumerate(df.index) }
            for sym, df in data.items()}
        
        self._current_idx = {sym:-1 for sym in symbols}
        self.current_date = None
    
    def heartbeats_by_date(self):
        all_dates = sorted(set(d for df in self._data.values() for d in df.index))
        for d in all_dates:
            self.current_date = d
            symbols_today = [s for s in self.symbols if d in self._date_idx.get(s, {})]
            for sym in symbols_today:
                self._current_idx[sym] = self._date_idx[sym][d]
            yield d , symbols_today
    
    def get_latest_bars(self,symbol,N = 1):
        idx = self._current_idx[symbol]
        if idx < 0 : 
            return pd.DataFrame()
        return self._data[symbol].iloc[max(0,idx - N+1):idx+1]
    

    def get_latest_bar_value(self, symbol, field):
        idx = self._current_idx[symbol]
        if idx < 0: 
            return None
        try:    
            return self._data[symbol].iloc[idx][field]
        except: 
            return None

    def to_wide(self, field: str) -> pd.DataFrame:
        """Export (dates × symbols) cho vectorized API."""
        return pd.DataFrame({s: df[field] for s, df in self._data.items()
                                if field in df.columns})
