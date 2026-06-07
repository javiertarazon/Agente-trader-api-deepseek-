import asyncio, logging, os, time
from datetime import datetime
from config import *
from data.live_feed import LiveMarketFeed
from data.impact_monitor import ImpactMonitor
from data.features import compute_features
from brain.decision_maker import decide as decide_trade
from execution.time_gate import TimeGate, Timeframe
from filters import load_filter
from risk.manager import RiskManager
from memory.storage import MemoryDB
from memory.reflection import daily_reflection

logger = logging.getLogger("Agent")
TF_MAP = {"M1": Timeframe.M1, "M5": Timeframe.M5, "M15": Timeframe.M15, "H1": Timeframe.H1}

async def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger.info(f"Iniciando agente en modo {MODE}")
    
    memory = MemoryDB(DATABASE_PATH)
    market = LiveMarketFeed()
    
    # Inicializar todas las tareas de datos correctamente
    try:
        await market.initialize()
        data_tasks = await market.start_all_streams()
        logger.info(f"Iniciadas {len(data_tasks)} tareas de datos")
    except Exception as e:
        logger.error(f"Error inicializando market feed: {e}")
        # Continuar con datos de fallback
    
    impact_monitor = ImpactMonitor(SYMBOLS)
    asyncio.create_task(impact_monitor.start())
    logger.info("Impact monitor iniciado")
    
    pre_filter = load_filter(os.getenv("PRE_FILTER", "technical"))
    logger.info(f"Filtro cargado: {type(pre_filter).__name__}")
    
    time_gate = TimeGate(TF_MAP[PRIMARY_TIMEFRAME])
    risk_manager = RiskManager(INITIAL_BALANCE, MAX_POSITIONS, RISK_PER_TRADE, 
                               MAX_DAILY_DRAWDOWN, MAX_TOTAL_DRAWDOWN)
    
    if MODE == "live":
        from execution.mt5_executor import MT5Executor
        from execution.exchange_executor import ExchangeExecutor
        executor = MT5Executor() if MT5_LOGIN else ExchangeExecutor()
        logger.info(f"Executor: {'MT5' if MT5_LOGIN else 'Exchange'}")
    else:
        from execution.paper_engine import PaperEngine
        executor = PaperEngine(INITIAL_BALANCE)
        logger.info("Executor: Paper Trading")
    
    daily_tokens = 0
    last_reflection_date = None
    
    logger.info("=== Agente iniciado, comenzando bucle principal ===")
    
    while True:
        try:
            now = datetime.now()
            
            # Reflexión diaria
            if last_reflection_date != now.date() and now.hour == REFLECTION_HOUR:
                await daily_reflection(memory, now)
                last_reflection_date = now.date()
                daily_tokens = 0
                logger.info("Reflexión diaria completada")
            
            for symbol in SYMBOLS:
                # Obtener ticker con fallback
                ticker = market.get_ticker(symbol)
                if not ticker:
                    logger.debug(f"Sin ticker para {symbol}, usando fallback")
                    continue
                
                # Obtener OHLCV para todos los timeframes
                ohlcv_1m = market.get_ohlcv(symbol, "M1")
                ohlcv_5m = market.get_ohlcv(symbol, "M5")
                ohlcv_15m = market.get_ohlcv(symbol, "M15")
                
                # Verificar datos mínimos necesarios
                if len(ohlcv_5m) < 50 or len(ohlcv_1m) < 20:
                    logger.debug(f"Datos insuficientes para {symbol}: M1={len(ohlcv_1m)}, M5={len(ohlcv_5m)}")
                    continue
                
                # Calcular características
                f1m = compute_features(ohlcv_1m)
                f5m = compute_features(ohlcv_5m)
                f15m = compute_features(ohlcv_15m)
                
                if not f5m:
                    logger.warning(f"No se pudieron calcular features para {symbol} M5")
                    continue
                
                vol_profile = market.get_volume_profile(symbol)
                order_book = market.get_order_book(symbol)
                
                # Aplicar pre-filtro
                should_analyze, reason = pre_filter.should_analyze(
                    symbol, ticker, f1m, f5m, vol_profile, order_book)
                
                if not should_analyze:
                    logger.debug(f"{symbol} filtrado: {reason}")
                    continue
                
                # Verificar impacto de noticias
                impact = await impact_monitor.get_impact(symbol)
                if impact and impact.get('score', 0) < 3:
                    logger.info(f"{symbol}: Impacto bajo ({impact.get('score')}), esperando")
                    continue
                
                # Time gate para entrada
                if not time_gate.is_valid_entry(f5m):
                    logger.debug(f"{symbol}: Time gate no válido")
                    continue
                
                # Verificar presupuesto de tokens (solo relevante cuando se usa LLM)
                if DEEPSEEK_API_KEY and daily_tokens > MAX_DAILY_TOKEN_BUDGET * 1000000:
                    logger.warning("Presupuesto diario de tokens alcanzado")
                    continue

                decision = await decide_trade(
                    symbol=symbol,
                    ticker=ticker,
                    f1m=f1m,
                    f5m=f5m,
                    f15m=f15m,
                    vol_profile=vol_profile,
                    order_book=order_book,
                    impact=impact,
                )
                
                if not decision or decision.get('confidence', 0) < MIN_CONFIDENCE:
                    logger.debug(f"{symbol}: Decisión inválida o confianza baja")
                    continue
                
                rr = decision.get('risk_reward', 0)
                if rr < MIN_RISK_REWARD:
                    logger.debug(f"{symbol}: Risk/Reward {rr:.2f} < mínimo {MIN_RISK_REWARD}")
                    continue
                
                # Calcular posición
                position_size, stop_loss, take_profit = risk_manager.calculate_position(
                    symbol, ticker['last'], decision.get('direction'), 
                    decision.get('stop_loss_pct', 0.02), decision.get('take_profit_pct', 0.04))
                
                if position_size <= 0:
                    logger.debug(f"{symbol}: Tamaño de posición inválido")
                    continue
                
                # Ejecutar trade
                result = await executor.execute(
                    symbol,
                    decision.get('direction'),
                    position_size,
                    stop_loss,
                    take_profit,
                    entry_price=ticker.get("last"),
                )
                
                if result:
                    # Guardar en memoria con resultado completo
                    memory.save_trade(symbol, decision, result)
                    if DEEPSEEK_API_KEY:
                        # Aproximación conservadora: se usa el prompt completo dentro de decide_trade().
                        daily_tokens += 1
                    
                    logger.info(f"✅ {symbol}: {decision.get('direction').upper()} | "
                                f"Conf: {decision.get('confidence')}% | RR: {rr:.2f} | "
                                f"Size: {position_size:.4f}")
            
            await asyncio.sleep(SCAN_INTERVAL_SECONDS)
            
        except asyncio.CancelledError:
            logger.info("Agente detenido por cancelación")
            break
        except Exception as e:
            logger.error(f"Error en bucle principal: {e}", exc_info=True)
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())
