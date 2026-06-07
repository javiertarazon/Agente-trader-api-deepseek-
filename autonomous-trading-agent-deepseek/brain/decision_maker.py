from __future__ import annotations

from typing import Any, Dict, Optional

from config import DEEPSEEK_API_KEY, MIN_RISK_REWARD
from brain.decision_parser import parse_decision
from brain.llm_client import query_deepseek
from brain.prompt_builder import build_rich_prompt


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _fallback_decision(symbol: str, ticker: Dict[str, Any], f5m: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Estrategia offline (sin LLM) para que el agente pueda operar en paper/live
    sin depender de una API key.
    """
    price = float(ticker.get("last") or 0)
    if price <= 0 or not f5m:
        return None

    rsi = float(f5m.get("rsi") or 50)
    macd = float(f5m.get("macd") or 0)
    macd_signal = float(f5m.get("macd_signal") or 0)
    bb_pos = float(f5m.get("bb_position") or 0.5)
    atr = float(f5m.get("atr") or 0)

    direction: Optional[str] = None
    confidence = 0.0

    if rsi <= 30 and bb_pos <= 0.25 and macd >= macd_signal:
        direction = "buy"
        confidence = 70 + (30 - rsi) * 0.8 + (0.25 - bb_pos) * 40
    elif rsi >= 70 and bb_pos >= 0.75 and macd <= macd_signal:
        direction = "sell"
        confidence = 70 + (rsi - 70) * 0.8 + (bb_pos - 0.75) * 40
    else:
        return None

    # Stop/TP basados en ATR si existe, con límites razonables.
    if atr > 0 and price > 0:
        sl_pct = _clamp((atr * 2) / price, 0.005, 0.05)
        tp_pct = _clamp((atr * 4) / price, 0.01, 0.12)
    else:
        sl_pct = 0.02
        tp_pct = 0.04

    risk_reward = tp_pct / sl_pct if sl_pct > 0 else 0
    if risk_reward < MIN_RISK_REWARD:
        return None

    return {
        "direction": direction,
        "confidence": int(_clamp(confidence, 0, 100)),
        "reasoning": "fallback_strategy",
        "stop_loss_pct": float(sl_pct),
        "take_profit_pct": float(tp_pct),
        "risk_reward": float(risk_reward),
    }


async def decide(
    symbol: str,
    ticker: Dict[str, Any],
    f1m: Dict[str, Any],
    f5m: Dict[str, Any],
    f15m: Dict[str, Any],
    vol_profile: Dict[str, Any],
    order_book: Dict[str, Any],
    impact: Dict[str, Any] | None,
) -> Optional[Dict[str, Any]]:
    """
    Devuelve una decisión normalizada para el motor:
    - stop_loss_pct / take_profit_pct (porcentajes)
    - risk_reward
    """
    if DEEPSEEK_API_KEY:
        prompt = build_rich_prompt(symbol, ticker, f1m, f5m, f15m, vol_profile, order_book, impact or {})
        decision_text = await query_deepseek(prompt)
        decision = parse_decision(decision_text) or {}

        if decision.get("direction") in {"buy", "sell", "wait"}:
            # Normalizar claves esperadas
            if "stop_loss_pct" in decision and "take_profit_pct" in decision:
                return decision

            # Compatibilidad: si el LLM devolviera precios absolutos, convertirlos a %.
            price = float(ticker.get("last") or 0)
            sl = decision.get("stop_loss")
            tp = decision.get("take_profit")
            if price > 0 and isinstance(sl, (int, float)) and isinstance(tp, (int, float)):
                sl_pct = abs(price - float(sl)) / price
                tp_pct = abs(float(tp) - price) / price
                decision["stop_loss_pct"] = sl_pct
                decision["take_profit_pct"] = tp_pct
                decision["risk_reward"] = tp_pct / sl_pct if sl_pct else 0
                return decision

    return _fallback_decision(symbol, ticker, f5m)

