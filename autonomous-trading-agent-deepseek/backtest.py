import asyncio, argparse
from datetime import datetime
from backtesting.engine import BacktestEngine
from config import SYMBOLS
from filters import load_filter

async def run_backtest(symbols, start, end, filter_name='technical', timeframe='15m'):
    filt = load_filter(filter_name)
    engine = BacktestEngine(symbols, start, end, pre_filter=filt, timeframe=timeframe)
    trades = await engine.run()
    print(f"Backtest finalizado: {len(trades)} operaciones")
    return trades

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--start', required=True)
    parser.add_argument('--end', required=True)
    parser.add_argument('--filter', default='technical')
    parser.add_argument('--timeframe', default='15m', help="Timeframe CCXT (ej: 15m, 5m, 1h)")
    parser.add_argument('--symbols', default=",".join(SYMBOLS), help="Lista CSV de símbolos (ej: SOL/USDT,BTC/USDT)")
    args = parser.parse_args()
    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    asyncio.run(
        run_backtest(
            symbols,
            datetime.fromisoformat(args.start),
            datetime.fromisoformat(args.end),
            filter_name=args.filter,
            timeframe=args.timeframe,
        )
    )
