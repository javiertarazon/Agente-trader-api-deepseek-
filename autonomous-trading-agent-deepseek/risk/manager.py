from typing import Tuple, Optional

class RiskManager:
    def __init__(self, initial_balance, max_positions, risk_per_trade, 
                 max_daily_drawdown, max_total_drawdown):
        self.balance = initial_balance
        self.max_positions = max_positions
        self.risk_per_trade = risk_per_trade
        self.max_daily_drawdown = max_daily_drawdown
        self.max_total_drawdown = max_total_drawdown
        self.daily_pnl = 0
        self.total_pnl = 0
        self.open_positions = 0

    def can_open_position(self) -> bool:
        if self.open_positions >= self.max_positions:
            return False
        
        daily_dd = abs(min(0, self.daily_pnl)) / self.balance
        if daily_dd >= self.max_daily_drawdown:
            return False
        
        total_dd = abs(min(0, self.total_pnl)) / self.balance
        if total_dd >= self.max_total_drawdown:
            return False
        
        return True

    def calculate_position(self, symbol, price, direction, 
                          stop_loss_pct: float, take_profit_pct: float) -> Tuple[float, float, float]:
        if not self.can_open_position():
            return 0, 0, 0
        
        risk_amount = self.balance * self.risk_per_trade
        
        if direction == 'buy':
            stop_loss = price * (1 - stop_loss_pct)
            take_profit = price * (1 + take_profit_pct)
        else:
            stop_loss = price * (1 + stop_loss_pct)
            take_profit = price * (1 - take_profit_pct)
        
        risk_distance = abs(price - stop_loss) / price
        if risk_distance == 0:
            return 0, 0, 0
        
        position_size = risk_amount / (price * risk_distance)
        
        self.open_positions += 1
        
        return position_size, stop_loss, take_profit

    def update_pnl(self, pnl: float):
        self.daily_pnl += pnl
        self.total_pnl += pnl
        if pnl != 0:
            self.open_positions = max(0, self.open_positions - 1)

    def reset_daily(self):
        self.daily_pnl = 0
