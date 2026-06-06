from datetime import datetime
from typing import Dict, Any

async def daily_reflection(memory, date: datetime):
    trades = memory.get_trades(limit=100)
    
    if not trades:
        return
    
    total_trades = len(trades)
    winning = sum(1 for t in trades if t.get('pnl', 0) > 0)
    losing = sum(1 for t in trades if t.get('pnl', 0) < 0)
    win_rate = winning / total_trades if total_trades > 0 else 0
    
    total_pnl = sum(t.get('pnl', 0) for t in trades)
    avg_win = sum(t.get('pnl', 0) for t in trades if t.get('pnl', 0) > 0) / winning if winning > 0 else 0
    avg_loss = sum(t.get('pnl', 0) for t in trades if t.get('pnl', 0) < 0) / losing if losing > 0 else 0
    
    summary = f"Día {date.strftime('%Y-%m-%d')}: {total_trades} operaciones, {win_rate*100:.1f}% win rate, PnL: ${total_pnl:.2f}"
    
    lessons = []
    if win_rate < 0.4:
        lessons.append("Revisar criterios de entrada - win rate bajo")
    if avg_loss > avg_win * 2:
        lessons.append("Mejorar gestión de stops - pérdidas mayores que ganancias")
    if total_trades > 20:
        lessons.append("Considerar reducir frecuencia de operaciones")
    
    adjustments = {
        'min_confidence_adjustment': 5 if win_rate < 0.4 else 0,
        'risk_per_trade_adjustment': -0.001 if total_pnl < 0 else 0,
        'notes': lessons
    }
    
    memory.save_reflection(date.strftime('%Y-%m-%d'), summary, '; '.join(lessons), adjustments)
    
    return {
        'summary': summary,
        'lessons': lessons,
        'adjustments': adjustments
    }
