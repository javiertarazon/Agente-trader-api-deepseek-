#!/bin/bash
# Script para generar el repositorio "autonomous-trading-agent-deepseek"
# Ejecutar: bash build_repo.sh
# Luego: zip -r autonomous-trading-agent-deepseek.zip autonomous-trading-agent-deepseek/

set -e

REPO="autonomous-trading-agent-deepseek"
echo "Creando repositorio $REPO ..."
rm -rf $REPO
mkdir -p $REPO/{data,filters,brain,execution,risk,memory,dashboard,logs,backtesting,optimization}

# ========== Archivos raíz ==========
cat > $REPO/requirements.txt << 'EOF'
pandas>=2.0
numpy>=1.24
ta>=0.10
ccxt[pro]>=4.0
streamlit>=1.25
plotly>=5.15
python-dotenv>=1.0
aiohttp>=3.8
MetaTrader5>=5.0
arch>=5.0
scipy>=1.10
optuna>=3.0
EOF

cat > $REPO/.env.example << 'EOF'
DEEPSEEK_API_KEY=sk-xxx
CRYPTOPANIC_API_KEY=
WHALE_ALERT_API_KEY=
FRED_API_KEY=
MT5_LOGIN=
MT5_PASSWORD=
MT5_SERVER=
EXCHANGE_ID=binance
EXCHANGE_API_KEY=
EXCHANGE_SECRET=
EOF

# config.py
cat > $REPO/config.py << 'EOF'
import os
from dotenv import load_dotenv
load_dotenv()

MODE = os.getenv("MODE", "paper")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_MODEL = "deepseek-chat"
SYMBOLS = ["SOL/USDT", "BTC/USDT", "ETH/USDT"]
PRIMARY_TIMEFRAME = "M5"
SECONDARY_TIMEFRAMES = ["M1", "M15"]
INITIAL_BALANCE = 10000.0
MAX_POSITIONS = 5
RISK_PER_TRADE = 0.005
MAX_DAILY_DRAWDOWN = 0.02
MAX_TOTAL_DRAWDOWN = 0.15
MIN_CONFIDENCE = 70
MIN_RISK_REWARD = 1.5
LATENCY_MS = 200
SLIPPAGE_FACTOR = 0.5
COMMISSION_RATE = 0.001
SIGNAL_GATE_ATR_THRESHOLD_PCT = 0.15
SIGNAL_GATE_MIN_SCORE = 2
MAX_DAILY_TOKEN_BUDGET = 0.10
CRYPTOPANIC_API_KEY = os.getenv("CRYPTOPANIC_API_KEY", "")
WHALE_ALERT_API_KEY = os.getenv("WHALE_ALERT_API_KEY", "")
WHALE_MIN_VALUE = 500000
FRED_API_KEY = os.getenv("FRED_API_KEY", "")
FRED_SERIES = "FEDFUNDS"
MT5_LOGIN = int(os.getenv("MT5_LOGIN", 0))
MT5_PASSWORD = os.getenv("MT5_PASSWORD", "")
MT5_SERVER = os.getenv("MT5_SERVER", "")
EXCHANGE_ID = os.getenv("EXCHANGE_ID", "binance")
EXCHANGE_API_KEY = os.getenv("EXCHANGE_API_KEY", "")
EXCHANGE_SECRET = os.getenv("EXCHANGE_SECRET", "")
DATABASE_PATH = "agent_memory.db"
SCAN_INTERVAL_SECONDS = 1
REFLECTION_HOUR = 0
EOF

# main.py
cat > $REPO/main.py << 'EOF'
import asyncio, logging, os, time
from datetime import datetime
from config import *
from data.live_feed import LiveMarketFeed
from data.impact_monitor import ImpactMonitor
from data.features import compute_features
from brain.prompt_builder import build_rich_prompt
from brain.llm_client import query_deepseek
from brain.decision_parser import parse_decision
from execution.time_gate import TimeGate, Timeframe
from filters import load_filter
from risk.manager import RiskManager
from memory.storage import MemoryDB
from memory.reflection import daily_reflection

logger = logging.getLogger("Agent")
TF_MAP = {"M1": Timeframe.M1, "M5": Timeframe.M5, "M15": Timeframe.M15, "H1": Timeframe.H1}

async def main():
    logging.basicConfig(level=logging.INFO)
    logger.info(f"Iniciando agente en modo {MODE}")
    memory = MemoryDB(DATABASE_PATH)
    market = LiveMarketFeed()
    asyncio.create_task(market.watch_tickers())
    impact_monitor = ImpactMonitor(SYMBOLS)
    asyncio.create_task(impact_monitor.start())
    
    pre_filter = load_filter(os.getenv("PRE_FILTER", "technical"))
    logger.info(f"Filtro: {type(pre_filter).__name__}")
    time_gate = TimeGate(TF_MAP[PRIMARY_TIMEFRAME])
    risk_manager = RiskManager(INITIAL_BALANCE, MAX_POSITIONS, RISK_PER_TRADE, 
                               MAX_DAILY_DRAWDOWN, MAX_TOTAL_DRAWDOWN)
    
    if MODE == "live":
        from execution.mt5_executor import MT5Executor
        from execution.exchange_executor import ExchangeExecutor
        executor = MT5Executor() if MT5_LOGIN else ExchangeExecutor()
    else:
        from execution.paper_engine import PaperEngine
        executor = PaperEngine(INITIAL_BALANCE)
    
    daily_tokens = 0
    last_reflection_date = None
    
    while True:
        try:
            now = datetime.now()
            if last_reflection_date != now.date() and now.hour == REFLECTION_HOUR:
                await daily_reflection(memory, now)
                last_reflection_date = now.date()
                daily_tokens = 0
            
            for symbol in SYMBOLS:
                ticker = market.get_ticker(symbol)
                if not ticker:
                    continue
                
                ohlcv_1m = market.get_ohlcv(symbol, "M1")
                ohlcv_5m = market.get_ohlcv(symbol, "M5")
                ohlcv_15m = market.get_ohlcv(symbol, "M15")
                
                if len(ohlcv_5m) < 50 or len(ohlcv_1m) < 20:
                    continue
                
                f1m = compute_features(ohlcv_1m)
                f5m = compute_features(ohlcv_5m)
                f15m = compute_features(ohlcv_15m)
                
                vol_profile = market.get_volume_profile(symbol)
                order_book = market.get_order_book(symbol)
                
                should_analyze, reason = pre_filter.should_analyze(
                    symbol, ticker, f1m, f5m, vol_profile, order_book)
                
                if not should_analyze:
                    logger.debug(f"{symbol}: {reason}")
                    continue
                
                impact = await impact_monitor.get_impact(symbol)
                if impact and impact.get('score', 0) < 3:
                    logger.info(f"{symbol}: Impacto bajo ({impact.get('score')})")
                    continue
                
                if not time_gate.is_valid_entry(f5m):
                    continue
                
                prompt = build_rich_prompt(symbol, ticker, f1m, f5m, f15m, 
                                           vol_profile, order_book, impact)
                
                if daily_tokens > MAX_DAILY_TOKEN_BUDGET * 1000000:
                    logger.warning("Presupuesto diario de tokens alcanzado")
                    continue
                
                decision_text = await query_deepseek(prompt)
                decision = parse_decision(decision_text)
                
                if not decision or decision.get('confidence', 0) < MIN_CONFIDENCE:
                    continue
                
                rr = decision.get('risk_reward', 0)
                if rr < MIN_RISK_REWARD:
                    continue
                
                position_size, stop_loss, take_profit = risk_manager.calculate_position(
                    symbol, ticker['last'], decision.get('direction'), 
                    decision.get('stop_loss_pct', 0.02), decision.get('take_profit_pct', 0.04))
                
                if position_size <= 0:
                    continue
                
                result = await executor.execute(symbol, decision.get('direction'),
                                                position_size, stop_loss, take_profit)
                
                if result:
                    memory.save_trade(symbol, decision, result)
                    daily_tokens += len(prompt) + len(decision_text)
                    
                    logger.info(f"{symbol}: {decision.get('direction')} | "
                                f"Conf: {decision.get('confidence')}% | RR: {rr:.2f}")
            
            await asyncio.sleep(SCAN_INTERVAL_SECONDS)
            
        except Exception as e:
            logger.error(f"Error en bucle principal: {e}")
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())
EOF

# backtest.py
cat > $REPO/backtest.py << 'EOF'
import asyncio, argparse
from datetime import datetime
from backtesting.engine import BacktestEngine
from config import SYMBOLS
from filters import load_filter

async def run_backtest(symbols, start, end, filter_name='technical'):
    filt = load_filter(filter_name)
    engine = BacktestEngine(symbols, start, end, pre_filter=filt)
    trades = await engine.run()
    print(f"Backtest finalizado: {len(trades)} operaciones")
    return trades

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--start', required=True)
    parser.add_argument('--end', required=True)
    parser.add_argument('--filter', default='technical')
    args = parser.parse_args()
    asyncio.run(run_backtest(SYMBOLS, datetime.fromisoformat(args.start), 
                             datetime.fromisoformat(args.end), filter_name=args.filter))
EOF

# optimize.py
cat > $REPO/optimize.py << 'EOF'
import asyncio, argparse
from datetime import datetime
from optimization.filter_optimizer import FilterOptimizer
from config import SYMBOLS

async def optimize(start, end, trials=50):
    opt = FilterOptimizer(SYMBOLS, start, end, n_trials=trials)
    best_params, best_metric = opt.optimize()
    print(f"Mejor filtro: {best_params} con métrica {best_metric:.2f}")
    return best_params

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--start', required=True)
    parser.add_argument('--end', required=True)
    parser.add_argument('--trials', type=int, default=50)
    args = parser.parse_args()
    asyncio.run(optimize(datetime.fromisoformat(args.start), 
                         datetime.fromisoformat(args.end), trials=args.trials))
EOF

# ========== Filtros ==========
cat > $REPO/filters/__init__.py << 'EOF'
from .base import BasePreFilter
from .technical import TechnicalFilter
from .quantitative import QuantitativeFilter
from .price_action import PriceActionFilter
from .probabilistic import ProbabilisticFilter
from .volume_sentiment import VolumeSentimentFilter
from .composite import CompositeFilter

FILTER_REGISTRY = {
    'technical': TechnicalFilter,
    'quantitative': QuantitativeFilter,
    'price_action': PriceActionFilter,
    'probabilistic': ProbabilisticFilter,
    'volume_sentiment': VolumeSentimentFilter,
    'composite': CompositeFilter,
}

def load_filter(name: str, **kwargs) -> BasePreFilter:
    cls = FILTER_REGISTRY.get(name)
    if not cls:
        raise ValueError(f"Filtro desconocido: {name}")
    return cls(**kwargs)

def list_filters():
    return list(FILTER_REGISTRY.keys())
EOF

cat > $REPO/filters/base.py << 'EOF'
from abc import ABC, abstractmethod
from typing import Dict, Any, Tuple

class BasePreFilter(ABC):
    @abstractmethod
    def should_analyze(self, symbol: str, market_data: Dict[str, Any],
                       features_1m: Dict, features_5m: Dict,
                       volume_profile: Dict, order_book: Dict) -> Tuple[bool, str]:
        pass
    
    @abstractmethod
    def get_parameters(self) -> Dict[str, Any]:
        pass
    
    @abstractmethod
    def set_parameters(self, params: Dict[str, Any]):
        pass
EOF

cat > $REPO/filters/technical.py << 'EOF'
from .base import BasePreFilter
import numpy as np

class TechnicalFilter(BasePreFilter):
    def __init__(self, atr_threshold=0.15, rsi_low=30, rsi_high=70, min_score=2, volume_mult=1.5):
        self.atr_threshold = atr_threshold
        self.rsi_low = rsi_low
        self.rsi_high = rsi_high
        self.min_score = min_score
        self.volume_mult = volume_mult
        self.prev_macd = {}

    def should_analyze(self, symbol, market_data, f1m, f5m, vol_prof, ob):
        if not f5m:
            return False, "Sin datos 5m"
        
        price = f5m.get('price', 0)
        atr = f5m.get('atr', 0)
        
        if price == 0 or atr / price < self.atr_threshold / 100:
            return False, "Volatilidad baja"
        
        score = 0
        
        rsi = f5m.get('rsi', 50)
        if rsi < self.rsi_low or rsi > self.rsi_high:
            score += 1
        
        macd = f5m.get('macd', 0)
        signal = f5m.get('macd_signal', 0)
        prev = self.prev_macd.get(symbol)
        cur_above = macd > signal
        if prev is not None and cur_above != prev:
            score += 1
        self.prev_macd[symbol] = cur_above
        
        vol = f5m.get('volume', 0)
        avg = vol_prof.get(symbol, vol)
        if vol > avg * self.volume_mult:
            score += 1
        
        if score >= self.min_score:
            return True, f"Score {score}"
        return False, f"Score {score} < {self.min_score}"

    def get_parameters(self):
        return {
            'atr_threshold': self.atr_threshold,
            'rsi_low': self.rsi_low,
            'rsi_high': self.rsi_high,
            'min_score': self.min_score,
            'volume_mult': self.volume_mult
        }
    
    def set_parameters(self, params):
        self.atr_threshold = params['atr_threshold']
        self.rsi_low = params['rsi_low']
        self.rsi_high = params['rsi_high']
        self.min_score = params['min_score']
        self.volume_mult = params['volume_mult']
EOF

cat > $REPO/filters/quantitative.py << 'EOF'
from .base import BasePreFilter
import numpy as np

class QuantitativeFilter(BasePreFilter):
    def __init__(self, zscore_threshold=2.0, mean_rev_window=20, momentum_window=10, min_score=2):
        self.zscore_threshold = zscore_threshold
        self.mean_rev_window = mean_rev_window
        self.momentum_window = momentum_window
        self.min_score = min_score
        self.price_history = {}

    def should_analyze(self, symbol, market_data, f1m, f5m, vol_prof, ob):
        if not f5m:
            return False, "Sin datos 5m"
        
        score = 0
        price = f5m.get('price', 0)
        
        if symbol not in self.price_history:
            self.price_history[symbol] = []
        self.price_history[symbol].append(price)
        if len(self.price_history[symbol]) > self.mean_rev_window * 2:
            self.price_history[symbol] = self.price_history[symbol][-self.mean_rev_window * 2:]
        
        if len(self.price_history[symbol]) >= self.mean_rev_window:
            hist = np.array(self.price_history[symbol])
            mean = np.mean(hist[-self.mean_rev_window:])
            std = np.std(hist[-self.mean_rev_window:])
            if std > 0:
                zscore = (price - mean) / std
                if abs(zscore) > self.zscore_threshold:
                    score += 1
        
        momentum = f5m.get('momentum', 0)
        if abs(momentum) > 0.02:
            score += 1
        
        vol_zscore = f5m.get('volume_zscore', 0)
        if abs(vol_zscore) > 1.5:
            score += 1
        
        bb_width = f5m.get('bb_width', 0)
        if bb_width > 0 and bb_width < 0.02:
            score += 1
        
        if score >= self.min_score:
            return True, f"Quant score {score}"
        return False, f"Quant score {score} < {self.min_score}"

    def get_parameters(self):
        return {
            'zscore_threshold': self.zscore_threshold,
            'mean_rev_window': self.mean_rev_window,
            'momentum_window': self.momentum_window,
            'min_score': self.min_score
        }
    
    def set_parameters(self, params):
        self.zscore_threshold = params['zscore_threshold']
        self.mean_rev_window = params['mean_rev_window']
        self.momentum_window = params['momentum_window']
        self.min_score = params['min_score']
EOF

cat > $REPO/filters/price_action.py << 'EOF'
from .base import BasePreFilter

class PriceActionFilter(BasePreFilter):
    def __init__(self, min_body_ratio=0.6, wick_ratio_max=0.4, consecutive_candles=3, min_score=2):
        self.min_body_ratio = min_body_ratio
        self.wick_ratio_max = wick_ratio_max
        self.consecutive_candles = consecutive_candles
        self.min_score = min_score

    def should_analyze(self, symbol, market_data, f1m, f5m, vol_prof, ob):
        if not f5m:
            return False, "Sin datos 5m"
        
        score = 0
        candle_pattern = f5m.get('candle_pattern', {})
        
        body_ratio = candle_pattern.get('body_ratio', 0)
        if body_ratio >= self.min_body_ratio:
            score += 1
        
        upper_wick = candle_pattern.get('upper_wick_ratio', 1)
        lower_wick = candle_pattern.get('lower_wick_ratio', 1)
        if upper_wick <= self.wick_ratio_max or lower_wick <= self.wick_ratio_max:
            score += 1
        
        trend_strength = f5m.get('trend_strength', 0)
        if trend_strength > 0.7:
            score += 1
        
        consolidation = f5m.get('consolidation', False)
        if not consolidation:
            score += 1
        
        if score >= self.min_score:
            return True, f"PA score {score}"
        return False, f"PA score {score} < {self.min_score}"

    def get_parameters(self):
        return {
            'min_body_ratio': self.min_body_ratio,
            'wick_ratio_max': self.wick_ratio_max,
            'consecutive_candles': self.consecutive_candles,
            'min_score': self.min_score
        }
    
    def set_parameters(self, params):
        self.min_body_ratio = params['min_body_ratio']
        self.wick_ratio_max = params['wick_ratio_max']
        self.consecutive_candles = params['consecutive_candles']
        self.min_score = params['min_score']
EOF

cat > $REPO/filters/probabilistic.py << 'EOF'
from .base import BasePreFilter
import numpy as np
from scipy import stats

class ProbabilisticFilter(BasePreFilter):
    def __init__(self, confidence_level=0.95, min_samples=30, edge_threshold=0.55, min_score=2):
        self.confidence_level = confidence_level
        self.min_samples = min_samples
        self.edge_threshold = edge_threshold
        self.min_score = min_score
        self.returns_history = {}

    def should_analyze(self, symbol, market_data, f1m, f5m, vol_prof, ob):
        if not f5m:
            return False, "Sin datos 5m"
        
        score = 0
        
        if symbol not in self.returns_history:
            self.returns_history[symbol] = []
        
        ret = f5m.get('return_1', 0)
        self.returns_history[symbol].append(ret)
        if len(self.returns_history[symbol]) > 100:
            self.returns_history[symbol] = self.returns_history[symbol][-100:]
        
        if len(self.returns_history[symbol]) >= self.min_samples:
            returns = np.array(self.returns_history[symbol])
            mean_ret = np.mean(returns)
            std_ret = np.std(returns)
            if std_ret > 0:
                t_stat = mean_ret / (std_ret / np.sqrt(len(returns)))
                p_value = 2 * (1 - stats.t.cdf(abs(t_stat), len(returns)-1))
                if p_value < (1 - self.confidence_level):
                    score += 1
        
        skew = f5m.get('skewness', 0)
        if abs(skew) > 0.5:
            score += 1
        
        kurt = f5m.get('kurtosis', 0)
        if abs(kurt) > 1:
            score += 1
        
        prob_up = f5m.get('prob_up', 0.5)
        if prob_up > self.edge_threshold or prob_up < (1 - self.edge_threshold):
            score += 1
        
        if score >= self.min_score:
            return True, f"Prob score {score}"
        return False, f"Prob score {score} < {self.min_score}"

    def get_parameters(self):
        return {
            'confidence_level': self.confidence_level,
            'min_samples': self.min_samples,
            'edge_threshold': self.edge_threshold,
            'min_score': self.min_score
        }
    
    def set_parameters(self, params):
        self.confidence_level = params['confidence_level']
        self.min_samples = params['min_samples']
        self.edge_threshold = params['edge_threshold']
        self.min_score = params['min_score']
EOF

cat > $REPO/filters/volume_sentiment.py << 'EOF'
from .base import BasePreFilter

class VolumeSentimentFilter(BasePreFilter):
    def __init__(self, volume_spike_threshold=2.0, imbalance_threshold=0.3, 
                 sentiment_score_min=3, min_score=2):
        self.volume_spike_threshold = volume_spike_threshold
        self.imbalance_threshold = imbalance_threshold
        self.sentiment_score_min = sentiment_score_min
        self.min_score = min_score

    def should_analyze(self, symbol, market_data, f1m, f5m, vol_prof, ob):
        if not f5m:
            return False, "Sin datos 5m"
        
        score = 0
        
        current_vol = f5m.get('volume', 0)
        avg_vol = vol_prof.get(symbol, current_vol)
        if avg_vol > 0 and current_vol / avg_vol >= self.volume_spike_threshold:
            score += 1
        
        bid_vol = ob.get('bid_volume', 0)
        ask_vol = ob.get('ask_volume', 0)
        total_vol = bid_vol + ask_vol
        if total_vol > 0:
            imbalance = abs(bid_vol - ask_vol) / total_vol
            if imbalance >= self.imbalance_threshold:
                score += 1
        
        sentiment = f5m.get('sentiment_score', 5)
        if sentiment >= self.sentiment_score_min or sentiment <= (10 - self.sentiment_score_min):
            score += 1
        
        vwap = f5m.get('vwap', 0)
        price = f5m.get('price', 0)
        if vwap > 0 and abs(price - vwap) / vwap > 0.01:
            score += 1
        
        if score >= self.min_score:
            return True, f"VolSent score {score}"
        return False, f"VolSent score {score} < {self.min_score}"

    def get_parameters(self):
        return {
            'volume_spike_threshold': self.volume_spike_threshold,
            'imbalance_threshold': self.imbalance_threshold,
            'sentiment_score_min': self.sentiment_score_min,
            'min_score': self.min_score
        }
    
    def set_parameters(self, params):
        self.volume_spike_threshold = params['volume_spike_threshold']
        self.imbalance_threshold = params['imbalance_threshold']
        self.sentiment_score_min = params['sentiment_score_min']
        self.min_score = params['min_score']
EOF

cat > $REPO/filters/composite.py << 'EOF'
from .base import BasePreFilter
from .technical import TechnicalFilter
from .quantitative import QuantitativeFilter
from .price_action import PriceActionFilter

class CompositeFilter(BasePreFilter):
    def __init__(self, weights=None, min_total_score=4):
        self.weights = weights or {'technical': 0.4, 'quantitative': 0.3, 'price_action': 0.3}
        self.min_total_score = min_total_score
        self.tech_filter = TechnicalFilter(min_score=1)
        self.quant_filter = QuantitativeFilter(min_score=1)
        self.pa_filter = PriceActionFilter(min_score=1)

    def should_analyze(self, symbol, market_data, f1m, f5m, vol_prof, ob):
        tech_ok, tech_reason = self.tech_filter.should_analyze(symbol, market_data, f1m, f5m, vol_prof, ob)
        quant_ok, quant_reason = self.quant_filter.should_analyze(symbol, market_data, f1m, f5m, vol_prof, ob)
        pa_ok, pa_reason = self.pa_filter.should_analyze(symbol, market_data, f1m, f5m, vol_prof, ob)
        
        total_score = 0
        if tech_ok:
            total_score += self.weights.get('technical', 0.4) * 3
        if quant_ok:
            total_score += self.weights.get('quantitative', 0.3) * 3
        if pa_ok:
            total_score += self.weights.get('price_action', 0.3) * 3
        
        if total_score >= self.min_total_score:
            return True, f"Composite score {total_score:.1f}"
        return False, f"Composite score {total_score:.1f} < {self.min_total_score}"

    def get_parameters(self):
        return {
            'weights': self.weights,
            'min_total_score': self.min_total_score
        }
    
    def set_parameters(self, params):
        self.weights = params.get('weights', self.weights)
        self.min_total_score = params.get('min_total_score', self.min_total_score)
EOF

# ========== Data modules ==========
cat > $REPO/data/__init__.py << 'EOF'
from .live_feed import LiveMarketFeed
from .impact_monitor import ImpactMonitor
from .features import compute_features
EOF

cat > $REPO/data/live_feed.py << 'EOF'
import asyncio
import ccxt.pro as ccxtpro
from datetime import datetime
from config import EXCHANGE_ID, EXCHANGE_API_KEY, EXCHANGE_SECRET

class LiveMarketFeed:
    def __init__(self):
        self.exchange = getattr(ccxtpro, EXCHANGE_ID)({
            'apiKey': EXCHANGE_API_KEY,
            'secret': EXCHANGE_SECRET,
            'enableRateLimit': True,
        })
        self.tickers = {}
        self.ohlcv = {}
        self.order_books = {}
        self.volume_profiles = {}

    async def watch_tickers(self):
        while True:
            try:
                for symbol in self.exchange.symbols[:50]:
                    ticker = await self.exchange.watch_ticker(symbol)
                    self.tickers[symbol] = ticker
            except Exception as e:
                print(f"Error watching tickers: {e}")
                await asyncio.sleep(5)

    async def watch_ohlcv(self, symbol, timeframe):
        key = f"{symbol}_{timeframe}"
        while True:
            try:
                ohlcv = await self.exchange.watch_ohlcv(symbol, timeframe)
                self.ohlcv[key] = ohlcv
            except Exception as e:
                print(f"Error watching OHLCV: {e}")
                await asyncio.sleep(5)

    async def watch_order_book(self, symbol):
        while True:
            try:
                book = await self.exchange.watch_order_book(symbol)
                self.order_books[symbol] = book
            except Exception as e:
                print(f"Error watching order book: {e}")
                await asyncio.sleep(5)

    def get_ticker(self, symbol):
        return self.tickers.get(symbol)

    def get_ohlcv(self, symbol, timeframe):
        key = f"{symbol}_{timeframe}"
        return self.ohlcv.get(key, [])

    def get_order_book(self, symbol):
        book = self.order_books.get(symbol, {})
        return {
            'bid_volume': sum([b[1] for b in book.get('bids', [])[:10]]),
            'ask_volume': sum([a[1] for a in book.get('asks', [])[:10]]),
            'spread': book.get('asks', [[1]])[0][0] - book.get('bids', [[0]])[-1][0] if book.get('asks') and book.get('bids') else 0
        }

    def get_volume_profile(self, symbol):
        return self.volume_profiles.get(symbol, {})

    async def close(self):
        await self.exchange.close()
EOF

cat > $REPO/data/impact_monitor.py << 'EOF'
import asyncio
import aiohttp
from datetime import datetime, timedelta
from config import CRYPTOPANIC_API_KEY, WHALE_ALERT_API_KEY, WHALE_MIN_VALUE

class ImpactMonitor:
    def __init__(self, symbols):
        self.symbols = symbols
        self.news_cache = {}
        self.whale_alerts = []
        self.session = None

    async def start(self):
        self.session = aiohttp.ClientSession()
        asyncio.create_task(self.monitor_news())
        asyncio.create_task(self.monitor_whales())

    async def monitor_news(self):
        if not CRYPTOPANIC_API_KEY:
            return
        while True:
            try:
                async with self.session.get(
                    f"https://cryptopanic.com/api/v1/posts/?auth_token={CRYPTOPANIC_API_KEY}&public=true"
                ) as resp:
                    data = await resp.json()
                    for post in data.get('results', [])[:20]:
                        self._process_news(post)
            except Exception as e:
                print(f"Error monitoring news: {e}")
            await asyncio.sleep(60)

    async def monitor_whales(self):
        if not WHALE_ALERT_API_KEY:
            return
        while True:
            try:
                async with self.session.get(
                    f"https://api.whale-alert.io/v1/transactions?api_key={WHALE_ALERT_API_KEY}&min_value={WHALE_MIN_VALUE}"
                ) as resp:
                    data = await resp.json()
                    for tx in data.get('transactions', [])[:10]:
                        self._process_whale(tx)
            except Exception as e:
                print(f"Error monitoring whales: {e}")
            await asyncio.sleep(30)

    def _process_news(self, post):
        title = post.get('title', '').lower()
        created = post.get('created_at', '')
        for symbol in self.symbols:
            base = symbol.split('/')[0].lower()
            if base in title:
                sentiment = self._analyze_sentiment(title)
                self.news_cache[symbol] = {
                    'headline': post.get('title'),
                    'sentiment': sentiment,
                    'timestamp': created,
                    'source': post.get('source', {}).get('title', 'unknown')
                }

    def _process_whale(self, tx):
        symbol = tx.get('currency_symbol', '').upper()
        value = tx.get('usd_value', 0)
        for s in self.symbols:
            if symbol in s or (symbol == 'ETH' and 'ETH' in s):
                self.whale_alerts.append({
                    'symbol': s,
                    'value_usd': value,
                    'type': tx.get('transaction_type'),
                    'timestamp': tx.get('timestamp')
                })
        self.whale_alerts = self.whale_alerts[-50:]

    def _analyze_sentiment(self, text):
        positive_words = ['surge', 'moon', 'bullish', 'breakout', 'rally', 'gain']
        negative_words = ['crash', 'dump', 'bearish', 'drop', 'loss', 'sell']
        score = 5
        for word in positive_words:
            if word in text:
                score += 1
        for word in negative_words:
            if word in text:
                score -= 1
        return max(1, min(10, score))

    async def get_impact(self, symbol):
        news = self.news_cache.get(symbol)
        whale = None
        for w in reversed(self.whale_alerts):
            if w['symbol'] == symbol:
                whale = w
                break
        
        impact_score = 5
        reasons = []
        
        if news:
            age = datetime.now() - datetime.fromisoformat(news['timestamp'].replace('Z', '+00:00'))
            if age < timedelta(hours=1):
                impact_score = news['sentiment']
                reasons.append(f"News: {news['headline'][:50]}")
        
        if whale:
            if whale['value_usd'] > 1000000:
                impact_score += 2
                reasons.append(f"Whale alert: ${whale['value_usd']:,.0f}")
        
        return {
            'score': impact_score,
            'reasons': reasons,
            'news': news,
            'whale': whale
        }

    async def close(self):
        if self.session:
            await self.session.close()
EOF

cat > $REPO/data/features.py << 'EOF'
import numpy as np
import ta

def compute_features(ohlcv):
    if len(ohlcv) < 20:
        return {}
    
    df = np.array(ohlcv)
    close = df[:, 4]
    high = df[:, 3]
    low = df[:, 2]
    open_p = df[:, 1]
    volume = df[:, 5]
    
    features = {
        'price': close[-1],
        'return_1': (close[-1] - close[-2]) / close[-2] if close[-2] != 0 else 0,
        'return_5': (close[-1] - close[-6]) / close[-6] if len(close) > 5 and close[-6] != 0 else 0,
    }
    
    # RSI
    rsi_indicator = ta.momentum.RSIIndicator(close, window=14)
    features['rsi'] = rsi_indicator.rsi()[-1]
    
    # MACD
    macd_indicator = ta.trend.MACD(close)
    features['macd'] = macd_indicator.macd()[-1]
    features['macd_signal'] = macd_indicator.macd_signal()[-1]
    features['macd_hist'] = macd_indicator.macd_diff()[-1]
    
    # Bollinger Bands
    bb_indicator = ta.volatility.BollingerBands(close)
    bb_upper = bb_indicator.bollinger_hband()[-1]
    bb_lower = bb_indicator.bollinger_lband()[-1]
    bb_mid = bb_indicator.bollinger_mavg()[-1]
    features['bb_upper'] = bb_upper
    features['bb_lower'] = bb_lower
    features['bb_width'] = (bb_upper - bb_lower) / bb_mid if bb_mid != 0 else 0
    features['bb_position'] = (close[-1] - bb_lower) / (bb_upper - bb_lower) if bb_upper != bb_lower else 0.5
    
    # ATR
    atr_indicator = ta.volatility.AverageTrueRange(high, low, close, window=14)
    features['atr'] = atr_indicator.average_true_range()[-1]
    
    # Volume
    features['volume'] = volume[-1]
    features['volume_ma'] = np.mean(volume[-20:])
    features['volume_zscore'] = (volume[-1] - features['volume_ma']) / np.std(volume[-20:]) if len(volume) > 20 else 0
    
    # Momentum
    features['momentum'] = close[-1] - close[-10] if len(close) > 10 else 0
    
    # VWAP
    typical_price = (high + low + close) / 3
    features['vwap'] = np.sum(typical_price[-20:] * volume[-20:]) / np.sum(volume[-20:]) if np.sum(volume[-20:]) != 0 else close[-1]
    
    # Candlestick pattern
    body = abs(close[-1] - open_p[-1])
    range_p = high[-1] - low[-1]
    features['candle_pattern'] = {
        'body_ratio': body / range_p if range_p != 0 else 0,
        'upper_wick_ratio': (high[-1] - max(open_p[-1], close[-1])) / range_p if range_p != 0 else 0,
        'lower_wick_ratio': (min(open_p[-1], close[-1]) - low[-1]) / range_p if range_p != 0 else 0
    }
    
    # Trend strength
    sma_short = np.mean(close[-10:])
    sma_long = np.mean(close[-50:]) if len(close) > 50 else sma_short
    features['trend_strength'] = abs(sma_short - sma_long) / sma_long if sma_long != 0 else 0
    
    # Consolidation detection
    recent_std = np.std(close[-20:])
    features['consolidation'] = recent_std / close[-1] < 0.01 if close[-1] != 0 else False
    
    # Statistical features
    if len(close) > 30:
        returns = np.diff(close) / close[:-1]
        features['skewness'] = float(np.mean(((returns - np.mean(returns)) / np.std(returns))**3)) if np.std(returns) != 0 else 0
        features['kurtosis'] = float(np.mean(((returns - np.mean(returns)) / np.std(returns))**4) - 3) if np.std(returns) != 0 else 0
        features['prob_up'] = np.mean(returns > 0)
    else:
        features['skewness'] = 0
        features['kurtosis'] = 0
        features['prob_up'] = 0.5
    
    return features
EOF

# ========== Brain modules ==========
cat > $REPO/brain/__init__.py << 'EOF'
from .prompt_builder import build_rich_prompt
from .llm_client import query_deepseek
from .decision_parser import parse_decision
EOF

cat > $REPO/brain/prompt_builder.py << 'EOF'
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
    "entry_price": precio_entrada,
    "stop_loss": precio_sl,
    "take_profit": precio_tp,
    "risk_reward": ratio_rr
}}"""
    return prompt
EOF

cat > $REPO/brain/llm_client.py << 'EOF'
import aiohttp
import json
from config import DEEPSEEK_API_KEY, DEEPSEEK_MODEL

async def query_deepseek(prompt):
    if not DEEPSEEK_API_KEY:
        return '{"direction": "wait", "confidence": 0, "reasoning": "API key no configurada"}'
    
    headers = {
        'Authorization': f'Bearer {DEEPSEEK_API_KEY}',
        'Content-Type': 'application/json'
    }
    
    payload = {
        'model': DEEPSEEK_MODEL,
        'messages': [{'role': 'user', 'content': prompt}],
        'temperature': 0.3,
        'max_tokens': 500
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            'https://api.deepseek.com/v1/chat/completions',
            headers=headers,
            json=payload
        ) as resp:
            data = await resp.json()
            return data['choices'][0]['message']['content']
EOF

cat > $REPO/brain/decision_parser.py << 'EOF'
import json
import re

def parse_decision(text):
    try:
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            return json.loads(match.group())
    except:
        pass
    return None
EOF

# ========== Execution modules ==========
cat > $REPO/execution/__init__.py << 'EOF'
from .time_gate import TimeGate, Timeframe
from .signal_gate import SignalGate
from .paper_engine import PaperEngine
from .mt5_executor import MT5Executor
from .exchange_executor import ExchangeExecutor
EOF

cat > $REPO/execution/time_gate.py << 'EOF'
from enum import Enum
from typing import Dict, Any

class Timeframe(Enum):
    M1 = 1
    M5 = 5
    M15 = 15
    H1 = 60

class TimeGate:
    def __init__(self, timeframe: Timeframe):
        self.timeframe = timeframe
        self.last_candle_time = None

    def is_valid_entry(self, features: Dict[str, Any]) -> bool:
        atr = features.get('atr', 0)
        price = features.get('price', 1)
        if price == 0:
            return False
        
        atr_pct = atr / price
        threshold = 0.0015 if self.timeframe == Timeframe.M1 else \
                    0.003 if self.timeframe == Timeframe.M5 else \
                    0.005 if self.timeframe == Timeframe.M15 else 0.01
        
        return atr_pct >= threshold
EOF

cat > $REPO/execution/signal_gate.py << 'EOF'
from typing import Dict, Any

class SignalGate:
    def __init__(self, min_score=2, atr_threshold_pct=0.15):
        self.min_score = min_score
        self.atr_threshold_pct = atr_threshold_pct

    def validate(self, features: Dict[str, Any]) -> tuple:
        score = 0
        reasons = []
        
        atr = features.get('atr', 0)
        price = features.get('price', 1)
        if price > 0 and atr / price >= self.atr_threshold_pct / 100:
            score += 1
            reasons.append("ATR suficiente")
        
        rsi = features.get('rsi', 50)
        if rsi < 30 or rsi > 70:
            score += 1
            reasons.append(f"RSI extremo ({rsi:.1f})")
        
        vol = features.get('volume', 0)
        vol_ma = features.get('volume_ma', 1)
        if vol > vol_ma * 1.5:
            score += 1
            reasons.append("Volumen alto")
        
        return score >= self.min_score, f"Score: {score}, Reasons: {', '.join(reasons)}"
EOF

cat > $REPO/execution/paper_engine.py << 'EOF'
import asyncio
from datetime import datetime
from config import COMMISSION_RATE, SLIPPAGE_FACTOR

class PaperEngine:
    def __init__(self, initial_balance):
        self.balance = initial_balance
        self.positions = {}
        self.trades = []

    async def execute(self, symbol, direction, size, stop_loss, take_profit):
        if direction not in ['buy', 'sell']:
            return None
        
        entry = 100  # Precio simulado
        sl_distance = abs(entry - stop_loss) / entry
        tp_distance = abs(take_profit - entry) / entry
        
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
            'status': 'open'
        }
        
        self.positions[symbol] = result
        self.trades.append(result)
        
        return result

    def close_position(self, symbol, exit_price):
        pos = self.positions.pop(symbol, None)
        if not pos:
            return None
        
        direction_mult = 1 if pos['direction'] == 'buy' else -1
        pnl = (exit_price - pos['entry']) * pos['size'] * direction_mult
        pnl -= pos['commission'] * 2
        
        self.balance += pnl
        
        return {
            **pos,
            'exit': exit_price,
            'pnl': pnl,
            'status': 'closed'
        }
EOF

cat > $REPO/execution/mt5_executor.py << 'EOF'
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

    async def execute(self, symbol, direction, size, stop_loss, take_profit):
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
EOF

cat > $REPO/execution/exchange_executor.py << 'EOF'
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
EOF

# ========== Risk module ==========
cat > $REPO/risk/__init__.py << 'EOF'
from .manager import RiskManager
EOF

cat > $REPO/risk/manager.py << 'EOF'
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
EOF

# ========== Memory module ==========
cat > $REPO/memory/__init__.py << 'EOF'
from .storage import MemoryDB
from .reflection import daily_reflection
EOF

cat > $REPO/memory/storage.py << 'EOF'
import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Any

class MemoryDB:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT,
                direction TEXT,
                entry REAL,
                exit REAL,
                size REAL,
                pnl REAL,
                confidence INTEGER,
                reasoning TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reflections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATE,
                summary TEXT,
                lessons TEXT,
                adjustments TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()

    def save_trade(self, symbol: str, decision: Dict[str, Any], result: Dict[str, Any]):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO trades (symbol, direction, entry, size, confidence, reasoning)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            symbol,
            decision.get('direction'),
            decision.get('entry_price'),
            result.get('size'),
            decision.get('confidence'),
            decision.get('reasoning')
        ))
        
        conn.commit()
        conn.close()

    def update_trade_exit(self, trade_id: int, exit_price: float, pnl: float):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE trades SET exit = ?, pnl = ? WHERE id = ?
        ''', (exit_price, pnl, trade_id))
        
        conn.commit()
        conn.close()

    def get_trades(self, limit: int = 100) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM trades ORDER BY timestamp DESC LIMIT ?', (limit,))
        columns = [desc[0] for desc in cursor.description]
        trades = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
        conn.close()
        return trades

    def save_reflection(self, date: str, summary: str, lessons: str, adjustments: str):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO reflections (date, summary, lessons, adjustments)
            VALUES (?, ?, ?, ?)
        ''', (date, summary, lessons, json.dumps(adjustments)))
        
        conn.commit()
        conn.close()

    def get_reflections(self, limit: int = 10) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM reflections ORDER BY created_at DESC LIMIT ?', (limit,))
        columns = [desc[0] for desc in cursor.description]
        reflections = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
        conn.close()
        return reflections
EOF

cat > $REPO/memory/reflection.py << 'EOF'
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
EOF

# ========== Dashboard (Streamlit) ==========
cat > $REPO/dashboard/app.py << 'EOF'
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from memory.storage import MemoryDB
from config import DATABASE_PATH

st.set_page_config(page_title="Trading Agent Dashboard", layout="wide")
st.title("🤖 Autonomous Trading Agent Dashboard")

memory = MemoryDB(DATABASE_PATH)
trades = memory.get_trades(limit=500)

if trades:
    df = pd.DataFrame(trades)
    
    col1, col2, col3, col4 = st.columns(4)
    
    total_pnl = df['pnl'].sum() if 'pnl' in df.columns else 0
    win_rate = (df['pnl'] > 0).sum() / len(df) * 100 if 'pnl' in df.columns else 0
    total_trades = len(df)
    avg_rr = df['confidence'].mean() if 'confidence' in df.columns else 0
    
    col1.metric("Total PnL", f"${total_pnl:.2f}")
    col2.metric("Win Rate", f"{win_rate:.1f}%")
    col3.metric("Total Trades", total_trades)
    col4.metric("Avg Confidence", f"{avg_rr:.1f}%")
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(y=df['pnl'].cumsum() if 'pnl' in df.columns else [], mode='lines', name='PnL Acumulado'))
    fig.update_layout(title='Evolución del PnL', xaxis_title='Operaciones', yaxis_title='PnL ($)')
    st.plotly_chart(fig, use_container_width=True)
    
    st.subheader("Últimas Operaciones")
    st.dataframe(df[['symbol', 'direction', 'entry', 'pnl', 'confidence', 'timestamp']].head(20))
else:
    st.info("No hay operaciones registradas aún")
EOF

# ========== Backtesting module ==========
cat > $REPO/backtesting/__init__.py << 'EOF'
from .engine import BacktestEngine
EOF

cat > $REPO/backtesting/engine.py << 'EOF'
import asyncio
from datetime import datetime
from typing import List, Dict, Any

class BacktestEngine:
    def __init__(self, symbols: List[str], start: datetime, end: datetime, pre_filter=None):
        self.symbols = symbols
        self.start = start
        self.end = end
        self.pre_filter = pre_filter
        self.trades = []
        self.balance = 10000.0

    async def run(self) -> List[Dict[str, Any]]:
        for symbol in self.symbols:
            await self._backtest_symbol(symbol)
        return self.trades

    async def _backtest_symbol(self, symbol: str):
        ohlcv = await self._fetch_historical_data(symbol)
        
        for i in range(50, len(ohlcv) - 1):
            candle = ohlcv[i]
            features = self._compute_features(ohlcv[:i+1])
            
            if self.pre_filter:
                should_analyze, _ = self.pre_filter.should_analyze(
                    symbol, {'last': candle[4]}, {}, features, {}, {})
                if not should_analyze:
                    continue
            
            if features.get('rsi', 50) < 30:
                self._simulate_trade(symbol, 'buy', candle[4], ohlcv[i+1:i+10])
            elif features.get('rsi', 50) > 70:
                self._simulate_trade(symbol, 'sell', candle[4], ohlcv[i+1:i+10])

    async def _fetch_historical_data(self, symbol: str):
        import random
        days = (self.end - self.start).days
        data = []
        base_price = 100 + random.random() * 50
        for i in range(days * 288):
            change = (random.random() - 0.5) * 2
            base_price *= (1 + change / 100)
            data.append([i, base_price * 1.01, base_price * 1.02, base_price * 0.98, base_price, 1000])
        return data

    def _compute_features(self, ohlcv):
        import numpy as np
        close = [c[4] for c in ohlcv]
        if len(close) < 14:
            return {}
        
        gains = []
        losses = []
        for i in range(1, min(14, len(close))):
            diff = close[i] - close[i-1]
            if diff > 0:
                gains.append(diff)
            else:
                losses.append(abs(diff))
        
        avg_gain = sum(gains) / 14 if gains else 0
        avg_loss = sum(losses) / 14 if losses else 1
        rs = avg_gain / avg_loss if avg_loss != 0 else 0
        rsi = 100 - (100 / (1 + rs))
        
        return {'rsi': rsi, 'price': close[-1]}

    def _simulate_trade(self, symbol: str, direction: str, entry: float, future_candles):
        if not future_candles:
            return
        
        if direction == 'buy':
            exit_price = max(c[4] for c in future_candles)
        else:
            exit_price = min(c[4] for c in future_candles)
        
        pnl = (exit_price - entry) * (1 if direction == 'buy' else -1)
        
        self.trades.append({
            'symbol': symbol,
            'direction': direction,
            'entry': entry,
            'exit': exit_price,
            'pnl': pnl,
            'timestamp': datetime.now().isoformat()
        })
        self.balance += pnl
EOF

# ========== Optimization module ==========
cat > $REPO/optimization/__init__.py << 'EOF'
from .filter_optimizer import FilterOptimizer
EOF

cat > $REPO/optimization/filter_optimizer.py << 'EOF'
import asyncio
from datetime import datetime
from typing import List, Tuple, Dict, Any
import optuna

class FilterOptimizer:
    def __init__(self, symbols: List[str], start: datetime, end: datetime, n_trials: int = 50):
        self.symbols = symbols
        self.start = start
        self.end = end
        self.n_trials = n_trials

    def optimize(self) -> Tuple[Dict[str, Any], float]:
        study = optuna.create_study(direction='maximize')
        study.optimize(self._objective, n_trials=self.n_trials)
        
        return study.best_params, study.best_value

    def _objective(self, trial):
        params = {
            'atr_threshold': trial.suggest_float('atr_threshold', 0.1, 0.3),
            'rsi_low': trial.suggest_int('rsi_low', 20, 35),
            'rsi_high': trial.suggest_int('rsi_high', 65, 80),
            'min_score': trial.suggest_int('min_score', 1, 3),
            'volume_mult': trial.suggest_float('volume_mult', 1.2, 2.0)
        }
        
        from filters.technical import TechnicalFilter
        filt = TechnicalFilter(**params)
        
        total_pnl = 0
        for symbol in self.symbols:
            pnl = self._evaluate_filter(symbol, filt)
            total_pnl += pnl
        
        return total_pnl

    def _evaluate_filter(self, symbol: str, filt) -> float:
        import random
        trades = 0
        wins = 0
        for _ in range(100):
            mock_features = {
                'price': 100 + random.random() * 10,
                'atr': random.random() * 2,
                'rsi': random.random() * 100,
                'macd': random.random() * 0.5,
                'macd_signal': random.random() * 0.5,
                'volume': random.random() * 1000
            }
            should_analyze, _ = filt.should_analyze(symbol, {}, {}, mock_features, {}, {})
            if should_analyze:
                trades += 1
                if random.random() > 0.45:
                    wins += 1
        
        return wins - trades * 0.1 if trades > 0 else -100
EOF

# ========== README ==========
cat > $REPO/README.md << 'EOF'
# Autonomous Trading Agent con DeepSeek

Agente de trading autónomo impulsado por IA (DeepSeek) que opera en mercados cripto y Forex.

## Características

- 🧠 **IA integrada**: Decisiones basadas en DeepSeek API
- 📊 **Análisis multi-temporal**: M1, M5, M15, H1
- 🔍 **Filtros personalizables**: Technical, Quantitative, Price Action, etc.
- ⚡ **Ejecución en tiempo real**: MetaTrader 5 y Exchanges (ccxt)
- 📈 **Backtesting y Optimización**: Incluye herramientas de optimización con Optuna
- 💾 **Memoria persistente**: SQLite para registro de operaciones
- 📉 **Gestión de riesgo avanzada**: Position sizing, drawdown limits

## Instalación

```bash
pip install -r requirements.txt
cp .env.example .env
# Editar .env con tus API keys
```

## Uso

### Modo Paper Trading
```bash
python main.py
```

### Backtesting
```bash
python backtest.py --start 2024-01-01 --end 2024-12-31 --filter technical
```

### Optimización
```bash
python optimize.py --start 2024-01-01 --end 2024-06-30 --trials 50
```

### Dashboard
```bash
streamlit run dashboard/app.py
```

## Estructura

```
autonomous-trading-agent-deepseek/
├── data/           # Feed de mercado y features
├── brain/          # Prompt building y LLM client
├── filters/        # Filtros pre-análisis
├── execution/      # Ejecución de órdenes
├── risk/           # Gestión de riesgo
├── memory/         # Persistencia y reflexión
├── dashboard/      # UI Streamlit
├── backtesting/    # Motor de backtest
└── optimization/   # Optimizador de parámetros
```

## Configuración

Editar `.env`:
- `DEEPSEEK_API_KEY`: Tu API key de DeepSeek
- `MODE`: paper o live
- `MT5_*`: Credenciales de MetaTrader 5 (opcional)
- `EXCHANGE_*`: Credenciales de exchange (opcional)

## Licencia

MIT
EOF

echo "✅ Repositorio generado en ./$REPO"
echo ""
echo "Estructura creada:"
find $REPO -type f | head -30
echo ""
echo "Para comprimir: zip -r $REPO.zip $REPO/"
