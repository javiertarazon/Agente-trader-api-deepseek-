from .base import BasePreFilter

class PriceActionFilter(BasePreFilter):
    def __init__(self, min_body_ratio=0.6, wick_ratio_max=0.4, consecutive_candles=3, min_score=2):
        self.min_body_ratio = min_body_ratio
        self.wick_ratio_max = wick_ratio_max
        self.consecutive_candles = consecutive_candles
        self.min_score = min_score

    def should_analyze(self, symbol, market_data, f1m, f5m, vol_prof, ob):
        if not f5m:
            return False, "Sin datos 5m"
        
        score = 0
        candle_pattern = f5m.get('candle_pattern', {})
        
        body_ratio = candle_pattern.get('body_ratio', 0)
        if body_ratio >= self.min_body_ratio:
            score += 1
        
        upper_wick = candle_pattern.get('upper_wick_ratio', 1)
        lower_wick = candle_pattern.get('lower_wick_ratio', 1)
        if upper_wick <= self.wick_ratio_max or lower_wick <= self.wick_ratio_max:
            score += 1
        
        trend_strength = f5m.get('trend_strength', 0)
        if trend_strength > 0.7:
            score += 1
        
        consolidation = f5m.get('consolidation', False)
        if not consolidation:
            score += 1
        
        if score >= self.min_score:
            return True, f"PA score {score}"
        return False, f"PA score {score} < {self.min_score}"

    def get_parameters(self):
        return {
            'min_body_ratio': self.min_body_ratio,
            'wick_ratio_max': self.wick_ratio_max,
            'consecutive_candles': self.consecutive_candles,
            'min_score': self.min_score
        }
    
    def set_parameters(self, params):
        self.min_body_ratio = params['min_body_ratio']
        self.wick_ratio_max = params['wick_ratio_max']
        self.consecutive_candles = params['consecutive_candles']
        self.min_score = params['min_score']
