from .base import BasePreFilter
from .technical import TechnicalFilter
from .quantitative import QuantitativeFilter
from .price_action import PriceActionFilter

class CompositeFilter(BasePreFilter):
    def __init__(self, weights=None, min_total_score=4):
        self.weights = weights or {'technical': 0.4, 'quantitative': 0.3, 'price_action': 0.3}
        self.min_total_score = min_total_score
        self.tech_filter = TechnicalFilter(min_score=1)
        self.quant_filter = QuantitativeFilter(min_score=1)
        self.pa_filter = PriceActionFilter(min_score=1)

    def should_analyze(self, symbol, market_data, f1m, f5m, vol_prof, ob):
        tech_ok, tech_reason = self.tech_filter.should_analyze(symbol, market_data, f1m, f5m, vol_prof, ob)
        quant_ok, quant_reason = self.quant_filter.should_analyze(symbol, market_data, f1m, f5m, vol_prof, ob)
        pa_ok, pa_reason = self.pa_filter.should_analyze(symbol, market_data, f1m, f5m, vol_prof, ob)
        
        total_score = 0
        if tech_ok:
            total_score += self.weights.get('technical', 0.4) * 3
        if quant_ok:
            total_score += self.weights.get('quantitative', 0.3) * 3
        if pa_ok:
            total_score += self.weights.get('price_action', 0.3) * 3
        
        if total_score >= self.min_total_score:
            return True, f"Composite score {total_score:.1f}"
        return False, f"Composite score {total_score:.1f} < {self.min_total_score}"

    def get_parameters(self):
        return {
            'weights': self.weights,
            'min_total_score': self.min_total_score
        }
    
    def set_parameters(self, params):
        self.weights = params.get('weights', self.weights)
        self.min_total_score = params.get('min_total_score', self.min_total_score)
