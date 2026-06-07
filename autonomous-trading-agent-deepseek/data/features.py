import numpy as np
import pandas as pd
import ta

def compute_features(ohlcv):
    if len(ohlcv) < 20:
        return {}
    
    df = np.array(ohlcv)
    close = df[:, 4]
    high = df[:, 2]
    low = df[:, 3]
    open_p = df[:, 1]
    volume = df[:, 5]
    
    # Convertir a pandas Series para compatibilidad con ta
    close_series = pd.Series(close)
    high_series = pd.Series(high)
    low_series = pd.Series(low)
    open_series = pd.Series(open_p)
    volume_series = pd.Series(volume)
    
    features = {
        'price': close[-1],
        'return_1': (close[-1] - close[-2]) / close[-2] if close[-2] != 0 else 0,
        'return_5': (close[-1] - close[-6]) / close[-6] if len(close) > 5 and close[-6] != 0 else 0,
    }
    
    # RSI
    rsi_indicator = ta.momentum.RSIIndicator(close_series, window=14)
    features['rsi'] = rsi_indicator.rsi().iloc[-1]
    
    # MACD
    macd_indicator = ta.trend.MACD(close_series)
    features['macd'] = macd_indicator.macd().iloc[-1]
    features['macd_signal'] = macd_indicator.macd_signal().iloc[-1]
    features['macd_hist'] = macd_indicator.macd_diff().iloc[-1]
    
    # Bollinger Bands
    bb_indicator = ta.volatility.BollingerBands(close_series)
    bb_upper = bb_indicator.bollinger_hband().iloc[-1]
    bb_lower = bb_indicator.bollinger_lband().iloc[-1]
    bb_mid = bb_indicator.bollinger_mavg().iloc[-1]
    features['bb_upper'] = bb_upper
    features['bb_lower'] = bb_lower
    features['bb_width'] = (bb_upper - bb_lower) / bb_mid if bb_mid != 0 else 0
    features['bb_position'] = (close[-1] - bb_lower) / (bb_upper - bb_lower) if bb_upper != bb_lower else 0.5
    
    # ATR
    atr_indicator = ta.volatility.AverageTrueRange(high_series, low_series, close_series, window=14)
    features['atr'] = atr_indicator.average_true_range().iloc[-1]
    
    # Volume
    features['volume'] = volume[-1]
    features['volume_ma'] = np.mean(volume[-20:])
    if len(volume) > 20:
        vol_std = np.std(volume[-20:])
        features['volume_zscore'] = (volume[-1] - features['volume_ma']) / vol_std if vol_std != 0 else 0
    else:
        features['volume_zscore'] = 0
    
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
