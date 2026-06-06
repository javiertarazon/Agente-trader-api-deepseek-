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
