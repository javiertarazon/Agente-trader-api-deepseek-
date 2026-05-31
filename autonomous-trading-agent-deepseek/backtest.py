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
