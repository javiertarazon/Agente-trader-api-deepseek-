import asyncio
import ccxt.async_support as ccxt
from datetime import datetime
from config import EXCHANGE_ID, EXCHANGE_API_KEY, EXCHANGE_SECRET, COMMISSION_RATE

class ExchangeExecutor:
    def __init__(self):
        self.exchange = getattr(ccxt, EXCHANGE_ID)({
            'apiKey': EXCHANGE_API_KEY,
            'secret': EXCHANGE_SECRET,
            'enableRateLimit': True,
        })

    async def execute(self, symbol, direction, size, stop_loss, take_profit):
        try:
            order_type = 'market'
            side = direction
            
            order = await self.exchange.create_order(symbol, order_type, side, size)
            
            return {
                'symbol': symbol,
                'direction': direction,
                'size': size,
                'order_id': order.get('id'),
                'price': order.get('average'),
                'timestamp': datetime.now().isoformat(),
                'status': order.get('status')
            }
        except Exception as e:
            print(f"Exchange execute error: {e}")
            return None

    async def close(self):
        await self.exchange.close()
