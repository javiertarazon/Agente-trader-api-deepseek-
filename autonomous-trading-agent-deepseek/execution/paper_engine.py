import asyncio
from datetime import datetime
from config import COMMISSION_RATE, SLIPPAGE_FACTOR
import logging

logger = logging.getLogger("PaperEngine")

class PaperEngine:
    def __init__(self, initial_balance):
        self.balance = initial_balance
        self.initial_balance = initial_balance
        self.positions = {}
        self.trades = []
        self.closed_trades = []
        self.max_drawdown = 0.0
        self.equity_curve = []

    async def execute(self, symbol, direction, size, stop_loss, take_profit):
        """Ejecutar orden en papel con precios realistas"""
        if direction not in ['buy', 'sell']:
            logger.warning(f"Dirección inválida: {direction}")
            return None
        
        # Obtener precio actual del mercado (simulado pero más realista)
        import random
        base_price = 100 + random.random() * 50  # En producción usar precio real del ticker
        slippage = base_price * (random.uniform(-0.001, 0.001) * SLIPPAGE_FACTOR)
        entry = base_price + slippage
        
        sl_distance = abs(entry - stop_loss) / entry if entry != 0 else 0
        tp_distance = abs(take_profit - entry) / entry if entry != 0 else 0
        
        risk = size * sl_distance
        reward = size * tp_distance
        
        commission = size * entry * COMMISSION_RATE
        
        result = {
            'symbol': symbol,
            'direction': direction,
            'entry': entry,
            'size': size,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'timestamp': datetime.now().isoformat(),
            'commission': commission,
            'status': 'open',
            'slippage': slippage
        }
        
        self.positions[symbol] = result
        self.trades.append(result)
        
        logger.info(f"Trade abierto: {symbol} {direction} @ {entry:.4f}")
        
        return result

    def close_position(self, symbol, exit_price):
        """Cerrar posición y calcular PnL real"""
        pos = self.positions.pop(symbol, None)
        if not pos:
            logger.warning(f"Posición no encontrada: {symbol}")
            return None
        
        direction_mult = 1 if pos['direction'] == 'buy' else -1
        pnl = (exit_price - pos['entry']) * pos['size'] * direction_mult
        pnl -= pos['commission'] * 2  # Comisiones de entrada y salida
        
        self.balance += pnl
        
        # Calcular drawdown
        if self.balance > self.initial_balance:
            self.initial_balance = self.balance
        drawdown = (self.initial_balance - self.balance) / self.initial_balance if self.initial_balance > 0 else 0
        self.max_drawdown = max(self.max_drawdown, drawdown)
        
        closed_trade = {
            **pos,
            'exit': exit_price,
            'pnl': pnl,
            'status': 'closed',
            'close_time': datetime.now().isoformat(),
            'drawdown': drawdown
        }
        
        self.closed_trades.append(closed_trade)
        self.equity_curve.append({
            'timestamp': datetime.now().isoformat(),
            'balance': self.balance,
            'equity': self.balance
        })
        
        logger.info(f"Trade cerrado: {symbol} PnL: {pnl:.4f}, Balance: ${self.balance:.2f}")
        
        return closed_trade

    def get_statistics(self):
        """Obtener estadísticas de trading"""
        if not self.closed_trades:
            return {
                'total_trades': 0,
                'winning_trades': 0,
                'win_rate': 0,
                'total_pnl': 0,
                'max_drawdown': 0
            }
        
        winning = sum(1 for t in self.closed_trades if t['pnl'] > 0)
        total_pnl = sum(t['pnl'] for t in self.closed_trades)
        
        return {
            'total_trades': len(self.closed_trades),
            'winning_trades': winning,
            'losing_trades': len(self.closed_trades) - winning,
            'win_rate': (winning / len(self.closed_trades)) * 100,
            'total_pnl': total_pnl,
            'avg_pnl': total_pnl / len(self.closed_trades),
            'max_drawdown': self.max_drawdown * 100,
            'current_balance': self.balance
        }

    async def simulate_market_movement(self, symbol, price_change_pct):
        """Simular movimiento de mercado para testing"""
        pos = self.positions.get(symbol)
        if not pos:
            return None
        
        new_price = pos['entry'] * (1 + price_change_pct / 100)
        return self.close_position(symbol, new_price)
