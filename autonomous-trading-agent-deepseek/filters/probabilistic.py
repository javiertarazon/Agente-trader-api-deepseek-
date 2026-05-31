from .base import BasePreFilter
import numpy as np
from scipy import stats

class ProbabilisticFilter(BasePreFilter):
    def __init__(self, confidence_level=0.95, min_samples=30, edge_threshold=0.55, min_score=2):
        self.confidence_level = confidence_level
        self.min_samples = min_samples
        self.edge_threshold = edge_threshold
        self.min_score = min_score
        self.returns_history = {}

    def should_analyze(self, symbol, market_data, f1m, f5m, vol_prof, ob):
        if not f5m:
            return False, "Sin datos 5m"
        
        score = 0
        
        if symbol not in self.returns_history:
            self.returns_history[symbol] = []
        
        ret = f5m.get('return_1', 0)
        self.returns_history[symbol].append(ret)
        if len(self.returns_history[symbol]) > 100:
            self.returns_history[symbol] = self.returns_history[symbol][-100:]
        
        if len(self.returns_history[symbol]) >= self.min_samples:
            returns = np.array(self.returns_history[symbol])
            mean_ret = np.mean(returns)
            std_ret = np.std(returns)
            if std_ret > 0:
                t_stat = mean_ret / (std_ret / np.sqrt(len(returns)))
                p_value = 2 * (1 - stats.t.cdf(abs(t_stat), len(returns)-1))
                if p_value < (1 - self.confidence_level):
                    score += 1
        
        skew = f5m.get('skewness', 0)
        if abs(skew) > 0.5:
            score += 1
        
        kurt = f5m.get('kurtosis', 0)
        if abs(kurt) > 1:
            score += 1
        
        prob_up = f5m.get('prob_up', 0.5)
        if prob_up > self.edge_threshold or prob_up < (1 - self.edge_threshold):
            score += 1
        
        if score >= self.min_score:
            return True, f"Prob score {score}"
        return False, f"Prob score {score} < {self.min_score}"

    def get_parameters(self):
        return {
            'confidence_level': self.confidence_level,
            'min_samples': self.min_samples,
            'edge_threshold': self.edge_threshold,
            'min_score': self.min_score
        }
    
    def set_parameters(self, params):
        self.confidence_level = params['confidence_level']
        self.min_samples = params['min_samples']
        self.edge_threshold = params['edge_threshold']
        self.min_score = params['min_score']
