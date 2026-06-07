import asyncio
import ccxt.async_support as ccxt
from datetime import datetime
import logging
from config import EXCHANGE_ID, EXCHANGE_API_KEY, EXCHANGE_SECRET

class ExchangeExecutor:
    def __init__(self):
        self.logger = logging.getLogger("ExchangeExecutor")
        self.exchange = getattr(ccxt, EXCHANGE_ID)({
            'apiKey': EXCHANGE_API_KEY,
            'secret': EXCHANGE_SECRET,
            'enableRateLimit': True,
        })

    async def _place_brackets(self, symbol, direction, size, stop_loss, take_profit):
        """
        Intenta colocar SL/TP como órdenes separadas (best-effort).
        No todos los exchanges/mercados soportan el mismo tipo de orden.
        """
        sl_order = None
        tp_order = None

        if not stop_loss or not take_profit:
            return sl_order, tp_order

        opposite_side = "sell" if direction == "buy" else "buy"

        # Candidatos de tipos unificados en CCXT (varía por exchange).
        candidates = [
            ("stop_loss_limit", {"stopPrice": stop_loss}),
            ("take_profit_limit", {"stopPrice": take_profit}),
        ]

        # Algunos exchanges usan strings distintos.
        alt_sl = [("STOP_LOSS_LIMIT", {"stopPrice": stop_loss}), ("stop", {"stopPrice": stop_loss})]
        alt_tp = [("TAKE_PROFIT_LIMIT", {"stopPrice": take_profit}), ("take_profit", {"stopPrice": take_profit})]

        async def try_orders(order_type_candidates, price, label):
            for order_type, params in order_type_candidates:
                try:
                    # Para órdenes "limit", CCXT requiere price (límite). Usamos el mismo trigger como precio.
                    return await self.exchange.create_order(symbol, order_type, opposite_side, size, price, params)
                except Exception as e:
                    self.logger.debug(f"{label} falló ({order_type}): {e}")
            return None

        sl_order = await try_orders([candidates[0], *alt_sl], float(stop_loss), "SL")
        tp_order = await try_orders([candidates[1], *alt_tp], float(take_profit), "TP")

        return sl_order, tp_order

    async def execute(self, symbol, direction, size, stop_loss, take_profit, entry_price=None):
        try:
            if not EXCHANGE_API_KEY or not EXCHANGE_SECRET:
                self.logger.error("EXCHANGE_API_KEY/EXCHANGE_SECRET no configuradas para modo live")
                return None

            order_type = 'market'
            side = direction
            
            order = await self.exchange.create_order(symbol, order_type, side, size)

            sl_order, tp_order = await self._place_brackets(symbol, direction, size, stop_loss, take_profit)
            
            return {
                'symbol': symbol,
                'direction': direction,
                'size': size,
                'order_id': order.get('id'),
                'price': order.get('average'),
                'stop_loss_order_id': sl_order.get('id') if sl_order else None,
                'take_profit_order_id': tp_order.get('id') if tp_order else None,
                'timestamp': datetime.now().isoformat(),
                'status': order.get('status')
            }
        except Exception as e:
            self.logger.error(f"Exchange execute error: {e}")
            return None

    async def close(self):
        await self.exchange.close()
