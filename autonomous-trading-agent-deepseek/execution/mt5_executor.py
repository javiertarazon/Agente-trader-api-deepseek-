import asyncio
from datetime import datetime

class MT5Executor:
    def __init__(self):
        self.initialized = False

    async def initialize(self):
        try:
            import MetaTrader5 as mt5
            from config import MT5_LOGIN, MT5_PASSWORD, MT5_SERVER
            
            if not mt5.initialize(login=MT5_LOGIN, password=MT5_PASSWORD, server=MT5_SERVER):
                print(f"MT5 init failed: {mt5.last_error()}")
                return False
            
            self.initialized = True
            return True
        except Exception as e:
            print(f"MT5 error: {e}")
            return False

    async def execute(self, symbol, direction, size, stop_loss, take_profit, entry_price=None):
        if not self.initialized:
            if not await self.initialize():
                return None
        
        try:
            import MetaTrader5 as mt5
            
            order_type = mt5.ORDER_TYPE_BUY if direction == 'buy' else mt5.ORDER_TYPE_SELL
            
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": size,
                "type": order_type,
                "price": mt5.symbol_info_tick(symbol).ask if direction == 'buy' else mt5.symbol_info_tick(symbol).bid,
                "sl": stop_loss,
                "tp": take_profit,
                "deviation": 10,
                "magic": 123456,
                "comment": "DeepSeek Agent",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            
            result = mt5.order_send(request)
            
            return {
                'symbol': symbol,
                'direction': direction,
                'size': size,
                'order_id': result.order if result else None,
                'timestamp': datetime.now().isoformat(),
                'status': 'sent'
            }
        except Exception as e:
            print(f"MT5 execute error: {e}")
            return None

    async def close(self):
        try:
            import MetaTrader5 as mt5
            mt5.shutdown()
        except:
            pass
