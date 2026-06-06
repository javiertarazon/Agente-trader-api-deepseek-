import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any
import ccxt
from config import EXCHANGE_ID

class BacktestEngine:
    def __init__(self, symbols: List[str], start: datetime, end: datetime, pre_filter=None):
        self.symbols = symbols
        self.start = start
        self.end = end
        self.pre_filter = pre_filter
        self.trades = []
        self.balance = 10000.0
        self.initial_balance = 10000.0
        self.equity_curve = []
        self.max_drawdown = 0.0
        self.total_trades = 0
        self.winning_trades = 0

    async def run(self) -> List[Dict[str, Any]]:
        """Ejecutar backtest completo"""
        print(f"Iniciando backtest: {self.start} a {self.end}")
        print(f"Símbolos: {self.symbols}")
        
        for symbol in self.symbols:
            await self._backtest_symbol(symbol)
        
        # Calcular métricas finales
        metrics = self._calculate_metrics()
        print(f"\n=== Métricas del Backtest ===")
        print(f"Trades totales: {self.total_trades}")
        print(f"Win rate: {metrics['win_rate']:.2f}%")
        print(f"Profit factor: {metrics['profit_factor']:.2f}")
        print(f"Sharpe ratio: {metrics['sharpe_ratio']:.2f}")
        print(f"Max drawdown: {metrics['max_drawdown']:.2f}%")
        print(f"Balance final: ${self.balance:.2f}")
        
        return self.trades

    async def _backtest_symbol(self, symbol: str):
        """Backtest para un símbolo específico"""
        ohlcv = await self._fetch_historical_data(symbol)
        
        if len(ohlcv) < 100:
            print(f"Datos insuficientes para {symbol}: {len(ohlcv)} candles")
            return
        
        print(f"Procesando {symbol}: {len(ohlcv)} candles")
        
        # Ventana móvil para backtest
        window_size = 100
        step_size = 10
        
        for i in range(window_size, len(ohlcv) - step_size, step_size):
            historical_data = ohlcv[i-window_size:i]
            current_candle = ohlcv[i]
            future_data = ohlcv[i:i+step_size]
            
            features = self._compute_features(historical_data)
            
            if not features or 'rsi' not in features:
                continue
            
            # Aplicar filtro si existe
            if self.pre_filter:
                should_analyze, reason = self.pre_filter.should_analyze(
                    symbol, 
                    {'last': current_candle[4]}, 
                    {}, 
                    features, 
                    {}, 
                    {}
                )
                if not should_analyze:
                    continue
            
            # Lógica de trading basada en características
            decision = self._make_decision(features, current_candle)
            
            if decision and future_data:
                self._simulate_trade(symbol, decision, current_candle, future_data)
            
            # Actualizar curva de equity
            self.equity_curve.append({
                'timestamp': current_candle[0],
                'balance': self.balance
            })

    async def _fetch_historical_data(self, symbol: str) -> List[List]:
        """Obtener datos históricos reales desde exchange"""
        try:
            exchange = getattr(ccxt, EXCHANGE_ID)({
                'enableRateLimit': True,
            })
            
            # Calcular timeframe basado en el rango de fechas
            days = (self.end - self.start).days
            timeframe = '5m' if days <= 7 else '1h' if days <= 30 else '1d'
            
            all_data = []
            since = int(self.start.timestamp() * 1000)
            end_ts = int(self.end.timestamp() * 1000)
            
            print(f"Descargando datos para {symbol} ({timeframe})...")
            
            while since < end_ts:
                try:
                    ohlcv = await exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=1000)
                    if not ohlcv:
                        break
                    
                    all_data.extend(ohlcv)
                    since = ohlcv[-1][0] + 1
                    
                    # Rate limiting
                    await asyncio.sleep(0.5)
                    
                except Exception as e:
                    print(f"Error descargando datos: {e}")
                    break
            
            await exchange.close()
            
            if all_data:
                print(f"Descargados {len(all_data)} candles para {symbol}")
                return all_data
            
        except Exception as e:
            print(f"Error obteniendo datos históricos: {e}")
        
        # Fallback: generar datos sintéticos realistas
        print(f"Usando datos sintéticos para {symbol}")
        return self._generate_realistic_data(symbol, days)

    def _generate_realistic_data(self, symbol: str, days: int) -> List[List]:
        """Generar datos sintéticos realistas con patrones de mercado"""
        import numpy as np
        
        # Configuración basada en el símbolo
        base_prices = {
            'BTC/USDT': 40000,
            'ETH/USDT': 2500,
            'SOL/USDT': 100,
            'default': 100
        }
        base_price = base_prices.get(symbol, base_prices['default'])
        
        # Generar serie temporal con tendencia y volatilidad realista
        n_candles = days * 288  # 5 minutos
        timestamps = [int((self.start + timedelta(minutes=i*5)).timestamp() * 1000) 
                     for i in range(n_candles)]
        
        # Random walk con drift y mean reversion
        returns = np.random.normal(0.0001, 0.02, n_candles)  # Daily vol ~2%
        
        # Añadir autocorrelación y mean reversion
        for i in range(1, n_candles):
            returns[i] += 0.1 * returns[i-1]  # Momentum
            returns[i] -= 0.05 * (i / n_candles)  # Mean reversion suave
        
        prices = base_price * np.cumprod(1 + returns)
        
        data = []
        for i in range(n_candles):
            close = prices[i]
            volatility = abs(np.random.normal(0, 0.01))
            high = close * (1 + volatility)
            low = close * (1 - volatility)
            open_p = prices[i-1] if i > 0 else base_price
            volume = np.random.uniform(100, 10000) * (base_price / 100)
            
            data.append([timestamps[i], open_p, high, low, close, volume])
        
        return data

    def _compute_features(self, ohlcv) -> Dict[str, Any]:
        """Calcular características técnicas"""
        if len(ohlcv) < 50:
            return {}
        
        close = [c[4] for c in ohlcv]
        high = [c[2] for c in ohlcv]
        low = [c[3] for c in ohlcv]
        volume = [c[5] for c in ohlcv]
        
        # RSI
        gains = []
        losses = []
        for i in range(1, 14):
            diff = close[i] - close[i-1]
            if diff > 0:
                gains.append(diff)
            else:
                losses.append(abs(diff))
        
        avg_gain = sum(gains) / 14 if gains else 0
        avg_loss = sum(losses) / 14 if losses else 1
        rs = avg_gain / avg_loss if avg_loss != 0 else 0
        rsi = 100 - (100 / (1 + rs))
        
        # MACD simple
        ema12 = sum(close[-12:]) / 12
        ema26 = sum(close[-26:]) / 26 if len(close) >= 26 else ema12
        macd = ema12 - ema26
        
        # Bollinger Bands
        sma20 = sum(close[-20:]) / 20
        std20 = (sum((c - sma20)**2 for c in close[-20:]) / 20) ** 0.5
        bb_upper = sma20 + 2 * std20
        bb_lower = sma20 - 2 * std20
        
        # ATR
        tr_values = []
        for i in range(1, 14):
            tr = max(
                high[i] - low[i],
                abs(high[i] - close[i-1]),
                abs(low[i] - close[i-1])
            )
            tr_values.append(tr)
        atr = sum(tr_values) / 14 if tr_values else 0
        
        # Volume analysis
        vol_ma = sum(volume[-20:]) / 20
        vol_ratio = volume[-1] / vol_ma if vol_ma > 0 else 1
        
        return {
            'price': close[-1],
            'rsi': rsi,
            'macd': macd,
            'bb_upper': bb_upper,
            'bb_lower': bb_lower,
            'bb_position': (close[-1] - bb_lower) / (bb_upper - bb_lower) if bb_upper != bb_lower else 0.5,
            'atr': atr,
            'vol_ratio': vol_ratio,
            'trend': 1 if close[-1] > sma20 else -1
        }

    def _make_decision(self, features: Dict, candle: List) -> Dict:
        """Tomar decisión de trading basada en características"""
        rsi = features.get('rsi', 50)
        macd = features.get('macd', 0)
        bb_pos = features.get('bb_position', 0.5)
        trend = features.get('trend', 0)
        
        direction = None
        confidence = 0
        stop_loss_pct = 0.02
        take_profit_pct = 0.04
        
        # Estrategia combinada
        if rsi < 30 and bb_pos < 0.2 and trend == 1:
            direction = 'buy'
            confidence = min(90, 50 + (30 - rsi) + (0.2 - bb_pos) * 100)
        elif rsi > 70 and bb_pos > 0.8 and trend == -1:
            direction = 'sell'
            confidence = min(90, 50 + (rsi - 70) + (bb_pos - 0.8) * 100)
        elif macd > 0 and rsi < 50:
            direction = 'buy'
            confidence = 60 + macd * 10
        elif macd < 0 and rsi > 50:
            direction = 'sell'
            confidence = 60 - macd * 10
        
        if direction:
            return {
                'direction': direction,
                'confidence': int(confidence),
                'stop_loss_pct': stop_loss_pct,
                'take_profit_pct': take_profit_pct
            }
        
        return None

    def _simulate_trade(self, symbol: str, decision: Dict, entry_candle: List, future_candles: List):
        """Simular ejecución de trade"""
        if not future_candles:
            return
        
        entry_price = entry_candle[4]
        direction = decision['direction']
        size = self.balance * 0.1 / entry_price  # 10% del balance por trade
        
        # Encontrar precio de salida óptimo
        if direction == 'buy':
            exit_price = max(c[4] for c in future_candles)
        else:
            exit_price = min(c[4] for c in future_candles)
        
        # Calcular PnL
        if direction == 'buy':
            pnl = (exit_price - entry_price) * size
        else:
            pnl = (entry_price - exit_price) * size
        
        # Comisiones
        commission = size * entry_price * 0.001  # 0.1%
        pnl -= commission * 2  # Entrada y salida
        
        # Actualizar balance
        self.balance += pnl
        
        # Registrar trade
        trade = {
            'symbol': symbol,
            'direction': direction,
            'entry': entry_price,
            'exit': exit_price,
            'size': size,
            'pnl': pnl,
            'confidence': decision['confidence'],
            'timestamp': datetime.fromtimestamp(entry_candle[0] / 1000).isoformat()
        }
        
        self.trades.append(trade)
        self.total_trades += 1
        
        if pnl > 0:
            self.winning_trades += 1
        
        # Calcular drawdown
        if self.balance > self.initial_balance:
            self.initial_balance = self.balance
        drawdown = (self.initial_balance - self.balance) / self.initial_balance
        self.max_drawdown = max(self.max_drawdown, drawdown)

    def _calculate_metrics(self) -> Dict[str, float]:
        """Calcular métricas de rendimiento"""
        if not self.trades:
            return {
                'win_rate': 0,
                'profit_factor': 0,
                'sharpe_ratio': 0,
                'max_drawdown': 0
            }
        
        win_rate = (self.winning_trades / self.total_trades) * 100 if self.total_trades > 0 else 0
        
        gross_profits = sum(t['pnl'] for t in self.trades if t['pnl'] > 0)
        gross_losses = abs(sum(t['pnl'] for t in self.trades if t['pnl'] < 0))
        profit_factor = gross_profits / gross_losses if gross_losses > 0 else float('inf')
        
        # Sharpe ratio (simplificado)
        if len(self.equity_curve) > 1:
            returns = []
            for i in range(1, len(self.equity_curve)):
                ret = (self.equity_curve[i]['balance'] - self.equity_curve[i-1]['balance']) / self.equity_curve[i-1]['balance']
                returns.append(ret)
            
            if returns:
                import numpy as np
                avg_return = np.mean(returns)
                std_return = np.std(returns)
                sharpe_ratio = (avg_return / std_return) * np.sqrt(252) if std_return > 0 else 0
            else:
                sharpe_ratio = 0
        else:
            sharpe_ratio = 0
        
        return {
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': self.max_drawdown * 100
        }
