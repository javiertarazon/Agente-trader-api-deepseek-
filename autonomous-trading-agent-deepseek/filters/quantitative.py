from .base import BasePreFilter
import numpy as np

class QuantitativeFilter(BasePreFilter):
    def __init__(self, zscore_threshold=2.0, mean_rev_window=20, momentum_window=10, min_score=2):
        self.zscore_threshold = zscore_threshold
        self.mean_rev_window = mean_rev_window
        self.momentum_window = momentum_window
        self.min_score = min_score
        self.price_history = {}

    def should_analyze(self, symbol, market_data, f1m, f5m, vol_prof, ob):
        if not f5m:
            return False, "Sin datos 5m"
        
        score = 0
        price = f5m.get('price', 0)
        
        if symbol not in self.price_history:
            self.price_history[symbol] = []
        self.price_history[symbol].append(price)
        if len(self.price_history[symbol]) > self.mean_rev_window * 2:
            self.price_history[symbol] = self.price_history[symbol][-self.mean_rev_window * 2:]
        
        if len(self.price_history[symbol]) >= self.mean_rev_window:
            hist = np.array(self.price_history[symbol])
            mean = np.mean(hist[-self.mean_rev_window:])
            std = np.std(hist[-self.mean_rev_window:])
            if std > 0:
                zscore = (price - mean) / std
                if abs(zscore) > self.zscore_threshold:
                    score += 1
        
        momentum = f5m.get('momentum', 0)
        if abs(momentum) > 0.02:
            score += 1
        
        vol_zscore = f5m.get('volume_zscore', 0)
        if abs(vol_zscore) > 1.5:
            score += 1
        
        bb_width = f5m.get('bb_width', 0)
        if bb_width > 0 and bb_width < 0.02:
            score += 1
        
        if score >= self.min_score:
            return True, f"Quant score {score}"
        return False, f"Quant score {score} < {self.min_score}"

    def get_parameters(self):
        return {
            'zscore_threshold': self.zscore_threshold,
            'mean_rev_window': self.mean_rev_window,
            'momentum_window': self.momentum_window,
            'min_score': self.min_score
        }
    
    def set_parameters(self, params):
        self.zscore_threshold = params['zscore_threshold']
        self.mean_rev_window = params['mean_rev_window']
        self.momentum_window = params['momentum_window']
        self.min_score = params['min_score']
