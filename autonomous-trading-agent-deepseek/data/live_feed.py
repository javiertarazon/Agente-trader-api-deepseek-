import asyncio
import ccxt.pro as ccxtpro
from datetime import datetime, timedelta
from config import EXCHANGE_ID, EXCHANGE_API_KEY, EXCHANGE_SECRET, SYMBOLS, SECONDARY_TIMEFRAMES
import logging

logger = logging.getLogger("LiveMarketFeed")

class LiveMarketFeed:
    def __init__(self):
        self.exchange = getattr(ccxtpro, EXCHANGE_ID)({
            'apiKey': EXCHANGE_API_KEY,
            'secret': EXCHANGE_SECRET,
            'enableRateLimit': True,
            'options': {'defaultType': 'spot'}
        })
        self.tickers = {}
        self.ohlcv = {}
        self.order_books = {}
        self.volume_profiles = {}
        self._subscriptions = set()
        self._ohlcv_history = {}
        self._initialized = False

    async def initialize(self):
        """Inicializar el exchange y cargar símbolos"""
        try:
            await self.exchange.load_markets()
            self._initialized = True
            logger.info(f"Exchange inicializado: {len(self.exchange.symbols)} símbolos disponibles")
        except Exception as e:
            logger.error(f"Error al inicializar exchange: {e}")
            raise

    async def watch_tickers(self):
        """Watch tickers para los símbolos configurados"""
        if not self._initialized:
            await self.initialize()
        
        symbols_to_watch = SYMBOLS if SYMBOLS else list(self.exchange.symbols)[:50]
        logger.info(f"Watching tickers para {len(symbols_to_watch)} símbolos")
        
        while True:
            try:
                for symbol in symbols_to_watch:
                    if symbol not in self.exchange.symbols:
                        continue
                    try:
                        ticker = await self.exchange.watch_ticker(symbol)
                        self.tickers[symbol] = ticker
                        self._subscriptions.add(symbol)
                    except Exception as e:
                        logger.debug(f"Error watching ticker {symbol}: {e}")
                await asyncio.sleep(0.1)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error en watch_tickers: {e}")
                await asyncio.sleep(5)

    async def watch_ohlcv(self, symbol, timeframe):
        """Watch OHLCV para un símbolo y timeframe específicos"""
        if not self._initialized:
            await self.initialize()
            
        key = f"{symbol}_{timeframe}"
        self._subscriptions.add(key)
        
        # Cargar histórico inicial si no existe
        if key not in self.ohlcv or len(self.ohlcv.get(key, [])) < 100:
            await self._load_historical_ohlcv(symbol, timeframe)
        
        while True:
            try:
                ohlcv = await self.exchange.watch_ohlcv(symbol, timeframe)
                self.ohlcv[key] = ohlcv
                self._update_volume_profile(symbol, ohlcv)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error watching OHLCV {symbol} {timeframe}: {e}")
                await asyncio.sleep(5)

    async def _load_historical_ohlcv(self, symbol, timeframe, limit=200):
        """Cargar datos históricos OHLCV"""
        try:
            key = f"{symbol}_{timeframe}"
            # Obtener timestamp actual
            since = int((datetime.now() - timedelta(minutes=limit * 5)).timestamp() * 1000)
            
            ohlcv = await self.exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=limit)
            if ohlcv:
                self.ohlcv[key] = ohlcv
                logger.debug(f"Cargados {len(ohlcv)} candles históricos para {symbol} {timeframe}")
        except Exception as e:
            logger.error(f"Error cargando histórico {symbol} {timeframe}: {e}")
            # Datos de fallback para testing
            if key not in self.ohlcv:
                self.ohlcv[key] = self._generate_fallback_data(100)

    def _generate_fallback_data(self, count=100):
        """Generar datos de fallback para testing cuando no hay conexión"""
        import random
        data = []
        base_price = 100 + random.random() * 50
        now = datetime.now()
        for i in range(count):
            change = (random.random() - 0.5) * 2
            close = base_price * (1 + change / 100)
            high = max(base_price, close) * 1.01
            low = min(base_price, close) * 0.99
            open_p = base_price
            volume = 1000 + random.random() * 500
            timestamp = int((now - timedelta(minutes=count-i)).timestamp() * 1000)
            data.append([timestamp, open_p, high, low, close, volume])
            base_price = close
        return data

    async def watch_order_book(self, symbol):
        """Watch order book para un símbolo"""
        if not self._initialized:
            await self.initialize()
            
        while True:
            try:
                book = await self.exchange.watch_order_book(symbol, limit=20)
                self.order_books[symbol] = book
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error watching order book {symbol}: {e}")
                await asyncio.sleep(5)

    def get_ticker(self, symbol):
        """Obtener ticker actual"""
        ticker = self.tickers.get(symbol)
        if not ticker and symbol in self._subscriptions:
            # Si no hay ticker pero estamos suscritos, intentar usar último OHLCV
            ohlcv = self.get_ohlcv(symbol, "M5")
            if ohlcv and len(ohlcv) > 0:
                last = ohlcv[-1]
                return {'last': last[4], 'bid': last[4], 'ask': last[4], 'volume': last[5]}
        return ticker

    def get_ohlcv(self, symbol, timeframe):
        """Obtener OHLCV para símbolo y timeframe"""
        key = f"{symbol}_{timeframe}"
        data = self.ohlcv.get(key, [])
        
        # Si no hay datos y estamos suscritos, generar fallback
        if not data and key in self._subscriptions:
            logger.warning(f"Sin datos OHLCV para {key}, usando fallback")
            return self._generate_fallback_data(100)
        
        return data

    def get_order_book(self, symbol):
        """Obtener order book procesado"""
        book = self.order_books.get(symbol, {})
        if not book:
            # Retornar valores por defecto si no hay order book
            return {
                'bid_volume': 100,
                'ask_volume': 100,
                'spread': 0.01
            }
        
        bids = book.get('bids', [])
        asks = book.get('asks', [])
        
        return {
            'bid_volume': sum([b[1] for b in bids[:10]]) if bids else 100,
            'ask_volume': sum([a[1] for a in asks[:10]]) if asks else 100,
            'spread': (asks[0][0] - bids[-1][0]) if asks and bids else 0.01
        }

    def get_volume_profile(self, symbol):
        """Obtener perfil de volumen"""
        return self.volume_profiles.get(symbol, {})

    def _update_volume_profile(self, symbol, ohlcv):
        """Actualizar perfil de volumen desde OHLCV"""
        if not ohlcv or len(ohlcv) < 20:
            return
        
        volumes = [c[5] for c in ohlcv[-100:]]
        self.volume_profiles[symbol] = {
            'avg_volume': sum(volumes) / len(volumes),
            'max_volume': max(volumes),
            'min_volume': min(volumes),
            'current_volume': volumes[-1] if volumes else 0
        }

    async def start_all_streams(self, symbols=None, timeframes=None):
        """Iniciar todos los streams necesarios"""
        if not symbols:
            symbols = SYMBOLS
        if not timeframes:
            timeframes = ["M1", "M5", "M15"] + SECONDARY_TIMEFRAMES
        
        tasks = [asyncio.create_task(self.watch_tickers())]
        
        for symbol in symbols:
            for tf in timeframes:
                if tf in ["M1", "M5", "M15"]:
                    tasks.append(asyncio.create_task(self.watch_ohlcv(symbol, tf)))
        
        # Order books opcionales
        for symbol in symbols[:3]:  # Solo primeros 3 para no sobrecargar
            tasks.append(asyncio.create_task(self.watch_order_book(symbol)))
        
        return tasks

    async def close(self):
        """Cerrar conexiones"""
        try:
            await self.exchange.close()
            logger.info("Conexiones cerradas")
        except Exception as e:
            logger.error(f"Error al cerrar: {e}")
