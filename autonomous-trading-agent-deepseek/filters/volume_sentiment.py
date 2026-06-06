from .base import BasePreFilter

class VolumeSentimentFilter(BasePreFilter):
    def __init__(self, volume_spike_threshold=2.0, imbalance_threshold=0.3, 
                 sentiment_score_min=3, min_score=2):
        self.volume_spike_threshold = volume_spike_threshold
        self.imbalance_threshold = imbalance_threshold
        self.sentiment_score_min = sentiment_score_min
        self.min_score = min_score

    def should_analyze(self, symbol, market_data, f1m, f5m, vol_prof, ob):
        if not f5m:
            return False, "Sin datos 5m"
        
        score = 0
        
        current_vol = f5m.get('volume', 0)
        avg_vol = vol_prof.get(symbol, current_vol)
        if avg_vol > 0 and current_vol / avg_vol >= self.volume_spike_threshold:
            score += 1
        
        bid_vol = ob.get('bid_volume', 0)
        ask_vol = ob.get('ask_volume', 0)
        total_vol = bid_vol + ask_vol
        if total_vol > 0:
            imbalance = abs(bid_vol - ask_vol) / total_vol
            if imbalance >= self.imbalance_threshold:
                score += 1
        
        sentiment = f5m.get('sentiment_score', 5)
        if sentiment >= self.sentiment_score_min or sentiment <= (10 - self.sentiment_score_min):
            score += 1
        
        vwap = f5m.get('vwap', 0)
        price = f5m.get('price', 0)
        if vwap > 0 and abs(price - vwap) / vwap > 0.01:
            score += 1
        
        if score >= self.min_score:
            return True, f"VolSent score {score}"
        return False, f"VolSent score {score} < {self.min_score}"

    def get_parameters(self):
        return {
            'volume_spike_threshold': self.volume_spike_threshold,
            'imbalance_threshold': self.imbalance_threshold,
            'sentiment_score_min': self.sentiment_score_min,
            'min_score': self.min_score
        }
    
    def set_parameters(self, params):
        self.volume_spike_threshold = params['volume_spike_threshold']
        self.imbalance_threshold = params['imbalance_threshold']
        self.sentiment_score_min = params['sentiment_score_min']
        self.min_score = params['min_score']
