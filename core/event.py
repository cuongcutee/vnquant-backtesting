from dataclasses import dataclass, field
from datetime import date
from enum import Enum


class EventType(Enum):
    MARKET  = "MARKET"
    SIGNAL  = "SIGNAL"
    ORDER   = "ORDER"
    FILL    = "FILL"

@dataclass
class MarketEvent:
    type:   EventType = field(default=EventType.MARKET, init=False)
    symbol: str   = ""
    date:   date  = None
    open:   float = 0.0
    high:   float = 0.0
    low:    float = 0.0
    close:  float = 0.0
    volume: int   = 0


@dataclass
class SignalEvent:
   #Phát hiện tín hiệu thôi, chưa là lệnh thật
    type:      EventType = field(default=EventType.SIGNAL, init=False)
    symbol:    str   = ""
    direction: str   = ""    # "LONG" hoặc "EXIT"
    strength:  float = 1.0   # 0.0 → 1.0


@dataclass
class OrderEvent:
    #Gửi lệnh đi
    type:       EventType = field(default=EventType.ORDER, init=False)
    symbol:     str = ""
    direction:  str = ""     # "BUY" hoặc "SELL"
    quantity:   int = 0
    order_type: str = "MARKET" #Có thể Market hoặc Limit
    limit_price: float = None  #Chỉ dùng khi là Limit thôi

@dataclass
class FillEvent:
    #Lệnh đã khớp
    type:            EventType = field(default=EventType.FILL, init=False)
    symbol:          str   = ""
    direction:       str   = ""
    quantity:        int   = 0
    fill_price:      float = 0.0
    fill_date:       date  = None
    commission:      float = 0.0
    tax:             float = 0.0   # 0.1% sell-side, BUY = 0
    slippage:        float = 0.0
    settlement_date: date  = None  # T+2


