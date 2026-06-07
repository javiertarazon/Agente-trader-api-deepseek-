from .base import BasePreFilter
import numpy as np

class TechnicalFilter(BasePreFilter):
    def __init__(self, atr_threshold=0.15, rsi_low=30, rsi_high=70, min_score=2, volume_mult=1.5):
        self.atr_threshold = atr_threshold
        self.rsi_low = rsi_low
        self.rsi_high = rsi_high
        self.min_score = min_score
        self.volume_mult = volume_mult
        self.prev_macd = {}

    def should_analyze(self, symbol, market_data, f1m, f5m, vol_prof, ob):
        if not f5m:
            return False, "Sin datos 5m"
        
        price = f5m.get('price', 0)
        atr = f5m.get('atr', 0)
        
        if price == 0 or atr / price < self.atr_threshold / 100:
            return False, "Volatilidad baja"
        
        score = 0
        
        rsi = f5m.get('rsi', 50)
        if rsi < self.rsi_low or rsi > self.rsi_high:
            score += 1
        
        macd = f5m.get('macd', 0)
        signal = f5m.get('macd_signal', 0)
        prev = self.prev_macd.get(symbol)
        cur_above = macd > signal
        if prev is not None and cur_above != prev:
            score += 1
        self.prev_macd[symbol] = cur_above
        
        vol = f5m.get('volume', 0)
        avg = vol
        if isinstance(vol_prof, dict):
            if 'avg_volume' in vol_prof:
                avg = vol_prof.get('avg_volume', vol)
            else:
                avg = vol_prof.get(symbol, vol)
        if vol > avg * self.volume_mult:
            score += 1
        
        if score >= self.min_score:
            return True, f"Score {score}"
        return False, f"Score {score} < {self.min_score}"

    def get_parameters(self):
        return {
            'atr_threshold': self.atr_threshold,
            'rsi_low': self.rsi_low,
            'rsi_high': self.rsi_high,
            'min_score': self.min_score,
            'volume_mult': self.volume_mult
        }
    
    def set_parameters(self, params):
        self.atr_threshold = params['atr_threshold']
        self.rsi_low = params['rsi_low']
        self.rsi_high = params['rsi_high']
        self.min_score = params['min_score']
        self.volume_mult = params['volume_mult']
