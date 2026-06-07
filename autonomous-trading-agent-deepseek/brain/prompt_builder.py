def build_rich_prompt(symbol, ticker, f1m, f5m, f15m, vol_profile, order_book, impact):
    prompt = f"""Analiza {symbol} y decide si operar.

DATOS DE MERCADO:
- Precio actual: ${ticker.get('last', 0):.4f}
- Cambio 24h: {ticker.get('percentage', 0):.2f}%
- Volumen 24h: {ticker.get('baseVolume', 0):.2f}

INDICADORES TÉCNICOS (5m):
- RSI: {f5m.get('rsi', 0):.2f}
- MACD: {f5m.get('macd', 0):.4f} | Señal: {f5m.get('macd_signal', 0):.4f}
- ATR: {f5m.get('atr', 0):.4f}
- Bandas Bollinger posición: {f5m.get('bb_position', 0):.2f}
- Volumen vs promedio: {f5m.get('volume', 0):.2f} / {f5m.get('volume_ma', 0):.2f}

CONTEXTO MULTITEMPORAL:
- Tendencia 1m: {'alcista' if f1m.get('return_1', 0) > 0 else 'bajista'}
- Tendencia 15m: {'alcista' if f15m.get('return_5', 0) > 0 else 'bajista'}

IMPACTO EXTERNO:
{f"- Noticias: {impact.get('news', {}).get('headline', 'Ninguna')}" if impact.get('news') else "- Sin noticias recientes"}
{f"- Alerta whale: ${impact.get('whale', {}).get('value_usd', 0):,.0f}" if impact.get('whale') else "- Sin alertas whale"}

ORDER BOOK:
- Bid vol: {order_book.get('bid_volume', 0):.2f}
- Ask vol: {order_book.get('ask_volume', 0):.2f}

Responde SOLO en formato JSON:
{{
    "direction": "buy" o "sell" o "wait",
    "confidence": 0-100,
    "reasoning": "breve explicación",
    "stop_loss_pct": 0.0-0.2,
    "take_profit_pct": 0.0-0.5,
    "risk_reward": ratio_rr
}}"""
    return prompt
