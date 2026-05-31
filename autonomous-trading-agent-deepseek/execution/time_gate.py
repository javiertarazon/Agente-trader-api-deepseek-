from enum import Enum
from typing import Dict, Any

class Timeframe(Enum):
    M1 = 1
    M5 = 5
    M15 = 15
    H1 = 60

class TimeGate:
    def __init__(self, timeframe: Timeframe):
        self.timeframe = timeframe
        self.last_candle_time = None

    def is_valid_entry(self, features: Dict[str, Any]) -> bool:
        atr = features.get('atr', 0)
        price = features.get('price', 1)
        if price == 0:
            return False
        
        atr_pct = atr / price
        threshold = 0.0015 if self.timeframe == Timeframe.M1 else \
                    0.003 if self.timeframe == Timeframe.M5 else \
                    0.005 if self.timeframe == Timeframe.M15 else 0.01
        
        return atr_pct >= threshold
