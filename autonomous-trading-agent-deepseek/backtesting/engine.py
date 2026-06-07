from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import ccxt.async_support as ccxt

from config import COMMISSION_RATE, EXCHANGE_ID, MAX_DAILY_DRAWDOWN, MAX_TOTAL_DRAWDOWN, RISK_PER_TRADE
from data.features import compute_features
from risk.manager import RiskManager

logger = logging.getLogger("BacktestEngine")


@dataclass(frozen=True)
class BacktestConfig:
    timeframe: str = "15m"
    window_size: int = 100
    max_hold_candles: int = 96  # ~24h en 15m
    rate_limit_sleep_s: float = 0.25


class BacktestEngine:
    def __init__(
        self,
        symbols: List[str],
        start: datetime,
        end: datetime,
        pre_filter=None,
        timeframe: str = "15m",
        exchange_id: str = EXCHANGE_ID,
        config: Optional[BacktestConfig] = None,
        exchange_factory=None,
    ):
        self.symbols = symbols
        self.start = start
        self.end = end
        self.pre_filter = pre_filter
        self.exchange_id = exchange_id
        self.config = config or BacktestConfig(timeframe=timeframe)
        self._exchange_factory = exchange_factory

        self.trades: List[Dict[str, Any]] = []

        self.initial_balance = 10000.0
        self.balance = self.initial_balance
        self.max_drawdown = 0.0
        self.equity_curve: List[Dict[str, Any]] = []

        self.total_trades = 0
        self.winning_trades = 0

        self.risk_manager = RiskManager(
            initial_balance=self.balance,
            max_positions=1,
            risk_per_trade=RISK_PER_TRADE,
            max_daily_drawdown=MAX_DAILY_DRAWDOWN,
            max_total_drawdown=MAX_TOTAL_DRAWDOWN,
        )

    async def run(self) -> List[Dict[str, Any]]:
        logger.info(f"Iniciando backtest: {self.start} a {self.end}")
        logger.info(f"Símbolos: {self.symbols} | TF: {self.config.timeframe}")

        for symbol in self.symbols:
            await self._backtest_symbol(symbol)

        metrics = self._calculate_metrics()
        logger.info("=== Métricas del Backtest ===")
        logger.info(f"Trades totales: {self.total_trades}")
        logger.info(f"Win rate: {metrics['win_rate']:.2f}%")
        logger.info(f"Profit factor: {metrics['profit_factor']:.2f}")
        logger.info(f"Sharpe ratio: {metrics['sharpe_ratio']:.2f}")
        logger.info(f"Max drawdown: {metrics['max_drawdown']:.2f}%")
        logger.info(f"Balance final: ${self.balance:.2f}")

        return self.trades

    def _create_exchange(self):
        if self._exchange_factory:
            return self._exchange_factory()
        return getattr(ccxt, self.exchange_id)({"enableRateLimit": True})

    async def _fetch_historical_data(self, exchange, symbol: str) -> List[List]:
        since = int(self.start.timestamp() * 1000)
        end_ts = int(self.end.timestamp() * 1000)
        all_data: List[List] = []

        while since < end_ts:
            ohlcv = await exchange.fetch_ohlcv(symbol, self.config.timeframe, since=since, limit=1000)
            if not ohlcv:
                break

            # Mantener solo hasta end_ts
            for row in ohlcv:
                if row[0] <= end_ts:
                    all_data.append(row)

            last_ts = ohlcv[-1][0]
            if last_ts <= since:
                break

            since = last_ts + 1
            await asyncio.sleep(self.config.rate_limit_sleep_s)

        # Deduplicar por timestamp (algunos exchanges repiten el último candle)
        dedup: Dict[int, List] = {}
        for row in all_data:
            dedup[int(row[0])] = row
        return [dedup[k] for k in sorted(dedup.keys())]

    async def _backtest_symbol(self, symbol: str):
        exchange = self._create_exchange()
        try:
            await exchange.load_markets()
            if symbol not in getattr(exchange, "symbols", []):
                logger.error(f"Símbolo no soportado por {self.exchange_id}: {symbol}")
                return
            logger.info(f"Descargando OHLCV {symbol} ({self.config.timeframe})...")
            ohlcv = await self._fetch_historical_data(exchange, symbol)
        except Exception as e:
            logger.error(f"Error descargando datos de {symbol}: {e}")
            ohlcv = []
        finally:
            try:
                await exchange.close()
            except Exception as e:
                logger.warning(f"Error cerrando exchange ({self.exchange_id}): {e}")
            # Fallback extra: cerrar cualquier ClientSession colgada
            try:
                import aiohttp

                for attr_name in dir(exchange):
                    try:
                        attr = getattr(exchange, attr_name)
                    except Exception:
                        continue
                    if isinstance(attr, aiohttp.ClientSession) and not attr.closed:
                        try:
                            await attr.close()
                        except Exception:
                            pass
            except Exception:
                pass

        if len(ohlcv) < self.config.window_size + 2:
            logger.warning(f"Datos insuficientes para {symbol}: {len(ohlcv)} candles")
            return

        i = self.config.window_size
        while i < len(ohlcv) - 2:
            window = ohlcv[i - self.config.window_size : i]
            current = ohlcv[i]

            f = compute_features(window)
            if not f or "rsi" not in f:
                i += 1
                continue

            ticker = {"last": current[4]}

            if self.pre_filter:
                should_analyze, _reason = self.pre_filter.should_analyze(symbol, ticker, {}, f, {}, {})
                if not should_analyze:
                    i += 1
                    continue

            decision = self._make_decision(f)
            if not decision:
                i += 1
                continue

            trade, exit_index = self._simulate_trade(symbol, decision, ohlcv, i)
            if trade:
                self.trades.append(trade)
            i = max(i + 1, exit_index + 1)

            self.equity_curve.append({"timestamp": current[0], "balance": self.balance})

    def _make_decision(self, f: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        rsi = float(f.get("rsi") or 50)
        macd = float(f.get("macd") or 0)
        macd_signal = float(f.get("macd_signal") or 0)
        bb_pos = float(f.get("bb_position") or 0.5)

        direction: Optional[str] = None
        confidence = 0

        if rsi <= 30 and bb_pos <= 0.25 and macd >= macd_signal:
            direction = "buy"
            confidence = int(min(95, 70 + (30 - rsi)))
        elif rsi >= 70 and bb_pos >= 0.75 and macd <= macd_signal:
            direction = "sell"
            confidence = int(min(95, 70 + (rsi - 70)))
        else:
            return None

        # SL/TP conservadores para backtest
        sl_pct = 0.02
        tp_pct = 0.04

        rr = tp_pct / sl_pct
        return {
            "direction": direction,
            "confidence": confidence,
            "stop_loss_pct": sl_pct,
            "take_profit_pct": tp_pct,
            "risk_reward": rr,
        }

    def _simulate_trade(self, symbol: str, decision: Dict[str, Any], ohlcv: List[List], entry_index: int) -> Tuple[Optional[Dict[str, Any]], int]:
        entry_candle = ohlcv[entry_index]
        entry_price = float(entry_candle[4])
        direction = decision["direction"]
        sl_pct = float(decision.get("stop_loss_pct") or 0.02)
        tp_pct = float(decision.get("take_profit_pct") or 0.04)

        if entry_price <= 0:
            return None, entry_index

        size, sl_price, tp_price = self.risk_manager.calculate_position(symbol, entry_price, direction, sl_pct, tp_pct)
        if size <= 0:
            return None, entry_index

        exit_price = entry_price
        exit_index = entry_index
        exit_reason = "timeout"

        last = min(len(ohlcv) - 1, entry_index + self.config.max_hold_candles)
        for j in range(entry_index + 1, last + 1):
            candle = ohlcv[j]
            high = float(candle[2])
            low = float(candle[3])

            if direction == "buy":
                if low <= sl_price:
                    exit_price = sl_price
                    exit_index = j
                    exit_reason = "stop_loss"
                    break
                if high >= tp_price:
                    exit_price = tp_price
                    exit_index = j
                    exit_reason = "take_profit"
                    break
            else:
                if high >= sl_price:
                    exit_price = sl_price
                    exit_index = j
                    exit_reason = "stop_loss"
                    break
                if low <= tp_price:
                    exit_price = tp_price
                    exit_index = j
                    exit_reason = "take_profit"
                    break

        # PnL
        direction_mult = 1 if direction == "buy" else -1
        pnl = (exit_price - entry_price) * size * direction_mult
        commission = size * entry_price * COMMISSION_RATE
        pnl -= commission * 2

        self.balance += pnl
        self.risk_manager.update_pnl(pnl)

        self.total_trades += 1
        if pnl > 0:
            self.winning_trades += 1

        peak = max(self.initial_balance, self.balance)
        if peak > self.initial_balance:
            self.initial_balance = peak
        dd = (self.initial_balance - self.balance) / self.initial_balance if self.initial_balance else 0
        self.max_drawdown = max(self.max_drawdown, dd)

        trade = {
            "symbol": symbol,
            "direction": direction,
            "entry": entry_price,
            "exit": exit_price,
            "size": size,
            "pnl": pnl,
            "confidence": decision.get("confidence"),
            "timestamp": datetime.fromtimestamp(entry_candle[0] / 1000).isoformat(),
            "exit_reason": exit_reason,
            "timeframe": self.config.timeframe,
        }

        return trade, exit_index

    def _calculate_metrics(self) -> Dict[str, float]:
        if not self.trades:
            return {"win_rate": 0, "profit_factor": 0, "sharpe_ratio": 0, "max_drawdown": 0}

        win_rate = (self.winning_trades / self.total_trades) * 100 if self.total_trades else 0
        gross_profits = sum(t["pnl"] for t in self.trades if t["pnl"] > 0)
        gross_losses = abs(sum(t["pnl"] for t in self.trades if t["pnl"] < 0))
        profit_factor = gross_profits / gross_losses if gross_losses > 0 else float("inf")

        sharpe_ratio = 0.0
        if len(self.equity_curve) > 2:
            returns: List[float] = []
            for i in range(1, len(self.equity_curve)):
                prev = float(self.equity_curve[i - 1]["balance"])
                cur = float(self.equity_curve[i]["balance"])
                if prev > 0:
                    returns.append((cur - prev) / prev)
            if returns:
                import numpy as np

                avg_return = float(np.mean(returns))
                std_return = float(np.std(returns))
                sharpe_ratio = (avg_return / std_return) * (252**0.5) if std_return > 0 else 0.0

        return {
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "sharpe_ratio": sharpe_ratio,
            "max_drawdown": self.max_drawdown * 100,
        }
