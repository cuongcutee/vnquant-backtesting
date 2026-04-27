from abc import ABC, abstractmethod
from datetime import date
import pandas as pd
class DataHandler(ABC):
    _current_date: date = None

    @abstractmethod
    def heartbeats_by_date(self):
        ...

    @abstractmethod
    def get_latest_bars(self,symbol:str,N:int = 1) -> pd.DataFrame:
        ...

    @abstractmethod
    def get_latest_bar_value(self,symbol:str,field:str) -> float:
        ...
    
    
    
    def get_fundamental(self, symbol, field): 
        return None
    def get_foreign_flow(self, symbol, N=5):
        return None
    def get_macro(self, field):
        return None
