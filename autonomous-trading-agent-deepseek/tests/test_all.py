# tests/test_all.py
import pytest
import asyncio
from datetime import datetime
import numpy as np
import sys
import os

# Añadir el path del proyecto para importar módulos
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Importar módulos bajo test
from filters.technical import TechnicalFilter
from filters.composite import CompositeFilter
from risk.manager import RiskManager
from brain.decision_parser import parse_decision
from data.features import compute_features
from execution.signal_gate import SignalGate
from memory.storage import MemoryDB

# ==================== FIXTURES ====================
@pytest.fixture
def sample_ohlcv():
    """Genera OHLCV sintético para pruebas"""
    data = []
    base = 100
    for i in range(100):
        change = np.random.normal(0, 1)
        close = base * (1 + change / 100)
        high = close * (1 + abs(np.random.normal(0, 0.005)))
        low = close * (1 - abs(np.random.normal(0, 0.005)))
        open_p = base
        volume = np.random.uniform(500, 2000)
        data.append([i, open_p, high, low, close, volume])
        base = close
    return data

@pytest.fixture
def sample_features(sample_ohlcv):
    return compute_features(sample_ohlcv)

@pytest.fixture
def temp_db(tmp_path):
    db_file = tmp_path / "test.db"
    return MemoryDB(str(db_file))

# ==================== TESTS: FILTERS ====================
class TestTechnicalFilter:
    def test_should_analyze_high_volatility(self, sample_features):
        filt = TechnicalFilter(atr_threshold=0.15, min_score=1)
        symbol = "BTC/USDT"
        market_data = {'last': sample_features['price']}
        vol_prof = {symbol: sample_features['volume'] * 0.5}
        
        should, reason = filt.should_analyze(
            symbol, market_data, {}, sample_features, vol_prof, {})
        
        assert isinstance(should, bool)
        assert isinstance(reason, str)
    
    def test_should_analyze_low_volatility(self):
        filt = TechnicalFilter(atr_threshold=0.5, min_score=2)
        low_vol_features = {
            'price': 100, 'atr': 0.01, 'rsi': 50, 
            'macd': 0.1, 'macd_signal': 0.1, 'volume': 100
        }
        should, reason = filt.should_analyze(
            "BTC/USDT", {}, {}, low_vol_features, {"BTC/USDT": 100}, {})
        
        assert should is False
        assert "Volatilidad baja" in reason or "Score" in reason
    
    def test_parameters_serialization(self):
        filt = TechnicalFilter(atr_threshold=0.2, rsi_low=25, rsi_high=75)
        params = filt.get_parameters()
        
        assert params['atr_threshold'] == 0.2
        assert params['rsi_low'] == 25
        assert params['rsi_high'] == 75
        
        new_params = {'atr_threshold': 0.3, 'rsi_low': 30, 'rsi_high': 70, 
                      'min_score': 3, 'volume_mult': 2.0}
        filt.set_parameters(new_params)
        assert filt.atr_threshold == 0.3
        assert filt.rsi_low == 30
        assert filt.rsi_high == 70
        assert filt.min_score == 3
        assert filt.volume_mult == 2.0

    def test_should_analyze_with_volume_profile_dict(self, sample_features):
        filt = TechnicalFilter(atr_threshold=0.15, min_score=1, volume_mult=1.2)
        symbol = "BTC/USDT"
        market_data = {'last': sample_features['price']}

        vol_prof = {'avg_volume': sample_features['volume'] * 0.5}
        should, _reason = filt.should_analyze(symbol, market_data, {}, sample_features, vol_prof, {})
        assert isinstance(should, bool)

class TestCompositeFilter:
    def test_composite_score_calculation(self, sample_features):
        filt = CompositeFilter(min_total_score=2)
        should, reason = filt.should_analyze(
            "BTC/USDT", {}, {}, sample_features, {}, {})
        
        assert isinstance(should, bool)
        assert "Composite score" in reason

# ==================== TESTS: RISK ====================
class TestRiskManager:
    def test_can_open_position_under_limits(self):
        rm = RiskManager(
            initial_balance=10000, max_positions=5, risk_per_trade=0.01,
            max_daily_drawdown=0.02, max_total_drawdown=0.15)
        
        assert rm.can_open_position() is True
    
    def test_cannot_open_max_positions_reached(self):
        rm = RiskManager(10000, 2, 0.01, 0.02, 0.15)
        rm.open_positions = 2
        
        assert rm.can_open_position() is False
    
    def test_cannot_open_daily_drawdown_exceeded(self):
        rm = RiskManager(10000, 5, 0.01, 0.02, 0.15)
        rm.daily_pnl = -250  # 2.5% drawdown
        
        assert rm.can_open_position() is False
    
    def test_cannot_open_total_drawdown_exceeded(self):
        rm = RiskManager(10000, 5, 0.01, 0.02, 0.15)
        rm.total_pnl = -1600  # 16% drawdown
        
        assert rm.can_open_position() is False
    
    def test_calculate_position_buy(self):
        rm = RiskManager(10000, 5, 0.01, 0.02, 0.15)
        size, sl, tp = rm.calculate_position(
            symbol="BTC/USDT", price=100, direction='buy',
            stop_loss_pct=0.02, take_profit_pct=0.04)
        
        assert size > 0
        assert sl == 98  # 2% below
        assert tp == 104  # 4% above
    
    def test_calculate_position_sell(self):
        rm = RiskManager(10000, 5, 0.01, 0.02, 0.15)
        size, sl, tp = rm.calculate_position(
            symbol="BTC/USDT", price=100, direction='sell',
            stop_loss_pct=0.02, take_profit_pct=0.04)
        
        assert sl == 102  # 2% above for short
        assert tp == 96   # 4% below for short
    
    def test_calculate_position_no_risk_distance(self):
        rm = RiskManager(10000, 5, 0.01, 0.02, 0.15)
        size, sl, tp = rm.calculate_position(
            symbol="BTC/USDT", price=100, direction='buy',
            stop_loss_pct=0.0, take_profit_pct=0.04)
        
        assert size == 0
        assert sl == 0
        assert tp == 0
    
    def test_update_pnl(self):
        rm = RiskManager(10000, 5, 0.01, 0.02, 0.15)
        rm.open_positions = 1
        rm.update_pnl(50)
        
        assert rm.daily_pnl == 50
        assert rm.total_pnl == 50
        assert rm.open_positions == 0
    
    def test_reset_daily(self):
        rm = RiskManager(10000, 5, 0.01, 0.02, 0.15)
        rm.daily_pnl = -100
        rm.reset_daily()
        
        assert rm.daily_pnl == 0

# ==================== TESTS: BRAIN ====================
class TestDecisionParser:
    def test_parse_valid_json(self):
        text = '''Análisis del mercado...
        {"direction": "buy", "confidence": 75, "reasoning": "RSI bajo"}
        Conclusión...'''
        
        result = parse_decision(text)
        assert result is not None
        assert result['direction'] == 'buy'
        assert result['confidence'] == 75
    
    def test_parse_invalid_json_returns_none(self):
        text = "No hay señal clara hoy"
        assert parse_decision(text) is None
    
    def test_parse_partial_json(self):
        text = '{"direction": "sell"'  # JSON incompleto
        assert parse_decision(text) is None
    
    def test_parse_empty_string(self):
        assert parse_decision("") is None
    
    def test_parse_nested_json(self):
        text = '''{
            "direction": "buy",
            "confidence": 80,
            "levels": {"support": 95, "resistance": 105}
        }'''
        result = parse_decision(text)
        assert result['direction'] == 'buy'
        assert result['confidence'] == 80
        assert result['levels']['support'] == 95

# ==================== TESTS: DATA ====================
class TestFeatures:
    def test_compute_features_min_length(self):
        short_ohlcv = [[i, 100, 102, 98, 101, 1000] for i in range(10)]
        features = compute_features(short_ohlcv)
        assert features == {}
    
    def test_compute_features_complete(self, sample_ohlcv):
        features = compute_features(sample_ohlcv)
        
        assert 'price' in features
        assert 'rsi' in features
        assert 'macd' in features
        assert 'atr' in features
        assert 'volume' in features
        assert 0 <= features['rsi'] <= 100
        assert features['price'] > 0
    
    def test_features_numeric_stability(self):
        ohlcv = [[i, 100, 100.1, 99.9, 100, 1000] for i in range(100)]
        features = compute_features(ohlcv)
        
        assert not np.isnan(features.get('rsi', 0))
        assert not np.isnan(features.get('macd', 0))
        assert not np.isnan(features.get('atr', 0))
    
    def test_features_has_all_indicators(self, sample_ohlcv):
        features = compute_features(sample_ohlcv)
        
        expected_keys = [
            'price', 'return_1', 'return_5', 'rsi', 'macd', 'macd_signal',
            'macd_hist', 'bb_upper', 'bb_lower', 'bb_width', 'bb_position',
            'atr', 'volume', 'volume_ma', 'volume_zscore', 'momentum', 'vwap',
            'candle_pattern', 'trend_strength', 'consolidation',
            'skewness', 'kurtosis', 'prob_up'
        ]
        
        for key in expected_keys:
            assert key in features, f"Falta la clave {key}"

# ==================== TESTS: EXECUTION ====================
class TestSignalGate:
    def test_validate_high_score(self, sample_features):
        gate = SignalGate(min_score=2)
        valid, reason = gate.validate(sample_features)
        
        assert isinstance(valid, bool)
        assert "Score:" in reason
    
    def test_validate_empty_features(self):
        gate = SignalGate(min_score=2)
        valid, reason = gate.validate({})
        
        assert valid is False
    
    def test_validate_custom_threshold(self):
        gate = SignalGate(min_score=1, atr_threshold_pct=0.01)
        features = {'price': 100, 'atr': 0.5, 'rsi': 50, 'volume': 100, 'volume_ma': 80}
        valid, reason = gate.validate(features)
        
        assert isinstance(valid, bool)

# ==================== TESTS: MEMORY ====================
class TestMemoryDB:
    def test_save_and_get_trades(self, temp_db):
        decision = {
            'direction': 'buy', 'confidence': 75, 'reasoning': 'Test',
            'entry_price': 100
        }
        result = {'size': 1.0}
        
        temp_db.save_trade("BTC/USDT", decision, result)
        trades = temp_db.get_trades(limit=10)
        
        assert len(trades) == 1
        assert trades[0]['symbol'] == "BTC/USDT"
        assert trades[0]['direction'] == 'buy'
        assert trades[0]['confidence'] == 75
    
    def test_save_multiple_trades(self, temp_db):
        for i in range(5):
            decision = {'direction': 'buy' if i % 2 == 0 else 'sell', 
                       'confidence': 70 + i, 'reasoning': f'Trade {i}',
                       'entry_price': 100 + i}
            result = {'size': 1.0}
            temp_db.save_trade(f"SYM{i}/USDT", decision, result)
        
        trades = temp_db.get_trades(limit=10)
        assert len(trades) == 5
    
    def test_get_trades_limit(self, temp_db):
        for i in range(20):
            decision = {'direction': 'buy', 'confidence': 75, 
                       'reasoning': 'Test', 'entry_price': 100}
            result = {'size': 1.0}
            temp_db.save_trade("BTC/USDT", decision, result)
        
        trades = temp_db.get_trades(limit=10)
        assert len(trades) == 10
    
    def test_save_reflection(self, temp_db):
        temp_db.save_reflection(
            date="2025-01-01",
            summary="Buen día",
            lessons="Aprender X",
            adjustments={"rsi_low": 25}
        )
        
        reflections = temp_db.get_reflections()
        assert len(reflections) == 1
        assert reflections[0]['date'] == "2025-01-01"
        assert reflections[0]['summary'] == "Buen día"
    
    def test_save_multiple_reflections(self, temp_db):
        for i in range(5):
            temp_db.save_reflection(
                date=f"2025-01-{i+1:02d}",
                summary=f"Resumen {i}",
                lessons=f"Lección {i}",
                adjustments={"param": i}
            )
        
        reflections = temp_db.get_reflections(limit=3)
        assert len(reflections) == 3

# ==================== TESTS: INTEGRATION ====================
class TestIntegration:
    def test_filter_to_risk_pipeline(self, sample_features):
        filt = TechnicalFilter(min_score=1)
        rm = RiskManager(10000, 5, 0.01, 0.02, 0.15)
        
        should, _ = filt.should_analyze(
            "BTC/USDT", {'last': sample_features['price']}, 
            {}, sample_features, {"BTC/USDT": sample_features['volume']}, {})
        
        if should and rm.can_open_position():
            size, sl, tp = rm.calculate_position(
                "BTC/USDT", sample_features['price'], 'buy', 0.02, 0.04)
            assert size > 0
            assert sl < sample_features['price']
            assert tp > sample_features['price']
    
    def test_full_decision_pipeline(self, sample_features):
        # Simular pipeline completo: filtro -> signal gate -> risk
        filt = TechnicalFilter(min_score=2)
        gate = SignalGate(min_score=2)
        rm = RiskManager(10000, 5, 0.01, 0.02, 0.15)
        
        # Filtro
        filter_ok, _ = filt.should_analyze(
            "BTC/USDT", {'last': sample_features['price']},
            {}, sample_features, {}, {})
        
        # Signal gate
        signal_ok, _ = gate.validate(sample_features)
        
        # Risk
        risk_ok = rm.can_open_position()
        
        # Si todo pasa, calcular posición
        if filter_ok and signal_ok and risk_ok:
            size, sl, tp = rm.calculate_position(
                "BTC/USDT", sample_features['price'], 'buy', 0.02, 0.04)
            assert size > 0


class TestBacktestEngine:
    def test_fetch_historical_data_dedup_and_end_ts(self):
        import asyncio
        from datetime import datetime, timezone, timedelta

        from backtesting.engine import BacktestEngine, BacktestConfig

        start = datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc)
        end = start + timedelta(minutes=45)  # 3 candles en 15m

        # timestamps in ms
        t0 = int(start.timestamp() * 1000)
        t1 = int((start + timedelta(minutes=15)).timestamp() * 1000)
        t2 = int((start + timedelta(minutes=30)).timestamp() * 1000)
        t3 = int((start + timedelta(minutes=45)).timestamp() * 1000)
        t4 = int((start + timedelta(minutes=60)).timestamp() * 1000)  # fuera de rango

        class FakeExchange:
            def __init__(self):
                self.calls = 0

            async def fetch_ohlcv(self, symbol, timeframe, since=None, limit=None):
                self.calls += 1
                if self.calls == 1:
                    # incluye duplicado intencional (t1 repetido)
                    return [
                        [t0, 1, 2, 0.5, 1.5, 10],
                        [t1, 1.5, 2.2, 1.2, 2.0, 11],
                        [t1, 1.5, 2.2, 1.2, 2.0, 11],
                    ]
                if self.calls == 2:
                    # incluye candle fuera de rango (t4)
                    return [
                        [t2, 2.0, 2.5, 1.8, 2.2, 12],
                        [t3, 2.2, 2.4, 2.0, 2.1, 13],
                        [t4, 2.1, 2.3, 1.9, 2.0, 14],
                    ]
                return []

        fake = FakeExchange()
        engine = BacktestEngine(
            symbols=["SOL/USDT"],
            start=start,
            end=end,
            timeframe="15m",
            config=BacktestConfig(timeframe="15m", rate_limit_sleep_s=0),
        )

        data = asyncio.run(engine._fetch_historical_data(fake, "SOL/USDT"))
        # Debe incluir hasta t3 y sin duplicados
        assert [row[0] for row in data] == [t0, t1, t2, t3]

# ==================== RUN WITH: pytest tests/test_all.py -v ====================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
