from typing import Dict, Any

class SignalGate:
    def __init__(self, min_score=2, atr_threshold_pct=0.15):
        self.min_score = min_score
        self.atr_threshold_pct = atr_threshold_pct

    def validate(self, features: Dict[str, Any]) -> tuple:
        score = 0
        reasons = []
        
        atr = features.get('atr', 0)
        price = features.get('price', 1)
        if price > 0 and atr / price >= self.atr_threshold_pct / 100:
            score += 1
            reasons.append("ATR suficiente")
        
        rsi = features.get('rsi', 50)
        if rsi < 30 or rsi > 70:
            score += 1
            reasons.append(f"RSI extremo ({rsi:.1f})")
        
        vol = features.get('volume', 0)
        vol_ma = features.get('volume_ma', 1)
        if vol > vol_ma * 1.5:
            score += 1
            reasons.append("Volumen alto")
        
        return score >= self.min_score, f"Score: {score}, Reasons: {', '.join(reasons)}"
