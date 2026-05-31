# 📘 Guía Completa: Funcionamiento del Agente de Trading Autónomo

## Tabla de Contenidos
1. [Arquitectura General](#arquitectura-general)
2. [Flujo de Operación Paso a Paso](#flujo-de-operación-paso-a-paso)
3. [Módulos Detallados](#módulos-detallados)
4. [Errores Críticos Identificados](#errores-críticos-identificados)
5. [Correcciones Necesarias (con Código)](#correcciones-necesarias-con-código)
6. [Mejoras Recomendadas](#mejoras-recomendadas)
7. [Plan de Implementación](#plan-de-implementación)

---

## 🏗️ Arquitectura General

El agente sigue una arquitectura **modular en capas** con 8 componentes principales:

```
┌─────────────────────────────────────────────────────────────────┐
│                     CAPA DE DECISIÓN                            │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────────┐    │
│  │   Filtros   │→ │ Prompt Builder│→ │  LLM (DeepSeek)     │    │
│  │  (Pre-SEL)  │  │              │  │  + Decision Parser   │    │
│  └─────────────┘  └──────────────┘  └─────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                    CAPA DE EJECUCIÓN                            │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────────┐    │
│  │  Time Gate  │→ │ Signal Gate  │→ │ Risk Manager        │    │
│  │(Ventana Temp)│  │(Confirmación)│  │ (Posición/SL/TP)    │    │
│  └─────────────┘  └──────────────┘  └─────────────────────┘    │
│                              ↓                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              Executors (Paper/Live/MT5)                 │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                    CAPA DE DATOS                                │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────────┐    │
│  │ Live Feed   │→ │  Features    │→ │  Impact Monitor     │    │
│  │ (ccxt.pro)  │  │  (ta-lib)    │  │  (Noticias/Whales)  │    │
│  └─────────────┘  └──────────────┘  └─────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                    CAPA DE MEMORIA                              │
│  ┌─────────────┐  ┌──────────────┐                             │
│  │  SQLite DB  │← │  Reflection  │                             │
│  │  (Trades)   │  │  (Aprendizaje)│                            │
│  └─────────────┘  └──────────────┘                             │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔄 Flujo de Operación Paso a Paso

### Ciclo Principal (cada `SCAN_INTERVAL_SECONDS = 1s`)

```python
# Pseudocódigo del bucle en main.py
while True:
    for symbol in SYMBOLS:  # ["SOL/USDT", "BTC/USDT", "ETH/USDT"]
        
        # PASO 1: Obtener datos de mercado
        ticker = market.get_ticker(symbol)
        ohlcv_1m = market.get_ohlcv(symbol, "M1")
        ohlcv_5m = market.get_ohlcv(symbol, "M5")
        ohlcv_15m = market.get_ohlcv(symbol, "M15")
        
        # PASO 2: Calcular indicadores técnicos
        f1m = compute_features(ohlcv_1m)  # RSI, MACD, ATR, etc.
        f5m = compute_features(ohlcv_5m)
        f15m = compute_features(ohlcv_15m)
        
        # PASO 3: Pre-filtro técnico (evita consultar LLM innecesariamente)
        should_analyze, reason = pre_filter.should_analyze(...)
        # Ejemplo de criterios:
        # - ATR/price > 0.15% (volatilidad mínima)
        # - RSI < 30 o RSI > 70 (sobreventa/sobrecompra)
        # - Cruce de MACD reciente
        # - Volumen > 1.5x promedio
        
        if not should_analyze:
            continue  # Salta al siguiente símbolo
        
        # PASO 4: Verificar impacto de noticias/eventos
        impact = await impact_monitor.get_impact(symbol)
        if impact['score'] < 3:
            continue  # Evita operar durante eventos de alto impacto
        
        # PASO 5: Time Gate (verifica ventana temporal adecuada)
        if not time_gate.is_valid_entry(f5m):
            continue  # Espera confirmación de tendencia
        
        # PASO 6: Construir prompt para LLM
        prompt = build_rich_prompt(symbol, ticker, f1m, f5m, f15m, 
                                   vol_profile, order_book, impact)
        
        # PASO 7: Consultar DeepSeek (si hay presupuesto de tokens)
        decision_text = await query_deepseek(prompt)
        decision = parse_decision(decision_text)
        
        # PASO 8: Validar decisión del LLM
        if decision['confidence'] < MIN_CONFIDENCE (70%):
            continue
        if decision['risk_reward'] < MIN_RISK_REWARD (1.5):
            continue
        
        # PASO 9: Calcular tamaño de posición y niveles
        position_size, stop_loss, take_profit = risk_manager.calculate_position(
            symbol, 
            ticker['last'], 
            direction=decision['direction'],
            stop_loss_pct=decision['stop_loss_pct'],
            take_profit_pct=decision['take_profit_pct']
        )
        
        # PASO 10: Ejecutar orden
        result = await executor.execute(symbol, direction, size, SL, TP)
        
        # PASO 11: Guardar en memoria
        memory.save_trade(symbol, decision, result)
    
    await asyncio.sleep(1)  # Esperar 1 segundo
```

---

## 📦 Módulos Detallados

### 1. **data/live_feed.py** - Alimentación de Datos en Tiempo Real

**Función:** Conecta a exchanges vía `ccxt.pro` para obtener:
- Tickers (precios actuales)
- OHLCV (velas históricas)
- Order Book (libro de órdenes)

**Estado Actual:** ⚠️ **CRÍTICO - No funcional**

**Problema:**
```python
# Línea 18-26: watch_tickers() itera sobre símbolos del exchange
for symbol in self.exchange.symbols[:50]:
    ticker = await self.exchange.watch_ticker(symbol)
    self.tickers[symbol] = ticker

# PROBLEMA: get_ohlcv() retorna [] porque nadie llama watch_ohlcv()
def get_ohlcv(self, symbol, timeframe):
    key = f"{symbol}_{timeframe}"
    return self.ohlcv.get(key, [])  # ← Siempre retorna []
```

**Consecuencia:** El agente nunca analiza porque `len(ohlcv_5m) < 50` siempre es True.

---

### 2. **data/features.py** - Cálculo de Indicadores Técnicos

**Función:** Transforma OHLCV en 25+ features usando `ta-lib`:
- **Momentum:** RSI, MACD, Retornos (1 período, 5 períodos)
- **Volatilidad:** ATR, Bandas de Bollinger (posición, ancho)
- **Volumen:** Volume Z-Score, VWAP
- **Tendencia:** SMA corto/largo, fuerza de tendencia
- **Patrones:** Candlestick patterns (body ratio, wicks)
- **Estadísticos:** Skewness, Kurtosis, probabilidad alcista

**Estado Actual:** ✅ **Funcional** (corregido en versión actual)

**Características calculadas:**
```python
features = {
    'price': 150.25,
    'rsi': 28.5,              # Sobreventa (<30)
    'macd': 0.45,
    'macd_signal': 0.32,
    'macd_hist': 0.13,        # Cruce alcista
    'atr': 2.5,               # Volatilidad absoluta
    'bb_position': 0.15,      # Cerca de banda inferior
    'volume_zscore': 2.1,     # Volumen 2.1 desviaciones arriba
    'trend_strength': 0.03,
    'consolidation': False
}
```

---

### 3. **filters/technical.py** - Pre-Filtro Técnico

**Función:** Reduce llamadas al LLM filtrando ~80% de las oportunidades no prometedoras.

**Criterios de Score:**
| Condición | Puntos |
|-----------|--------|
| RSI < 30 o RSI > 70 | +1 |
| Cruce de MACD (cambio de estado) | +1 |
| Volumen > 1.5x promedio | +1 |

**Umbral:** `min_score = 2` → Necesita al menos 2 de 3 condiciones.

**Estado Actual:** ✅ **Funcional**

**Ejemplo de ejecución:**
```python
# Entrada:
f5m = {'rsi': 25, 'macd': 0.5, 'macd_signal': 0.3, 'atr': 2.0, 'price': 100}
vol_prof = {'SOL/USDT': 500}
f5m['volume'] = 800  # > 500 * 1.5 = 750

# Proceso:
# 1. RSI 25 < 30 → +1 punto
# 2. MACD 0.5 > Signal 0.3 (prev was False) → +1 punto  
# 3. Volume 800 > 750 → +1 punto
# Score = 3 ≥ 2 → TRUE

should_analyze, reason = filter.should_analyze(...)
# Resultado: (True, "Score 3")
```

---

### 4. **brain/prompt_builder.py** - Constructor de Prompts

**Función:** Crea prompts estructurados para DeepSeek con:
- Contexto de mercado multi-timeframe
- Indicadores técnicos clave
- Perfil de volumen y order book
- Eventos de impacto recientes
- Historial de trades anteriores

**Formato del prompt:**
```markdown
ANÁLISIS DE TRADING PARA SOL/USDT
==================================

CONTEXTO ACTUAL:
- Precio: $150.25
- Timeframe M5: Tendencia alcista
- RSI(14): 28.5 (SOBREVENTA)
- MACD: Cruce alcista confirmado
- ATR: $2.50 (1.66% del precio)
- Volumen: 2.1x promedio (ALTO)

EVENTOS DE IMPACTO:
- Score: 4/5 - Anuncio de Fed en 2 horas

HISTORIAL RECIENTE:
- Últimos 3 trades: 2 ganadores, 1 perdedor
- Win rate: 67%

INSTRUCCIONES:
Analiza la situación y proporciona una decisión en formato JSON:
{
  "direction": "buy"|"sell"|"wait",
  "confidence": 0-100,
  "reasoning": "...",
  "entry_price": ...,
  "stop_loss_pct": ...,
  "take_profit_pct": ...,
  "risk_reward": ...
}
```

---

### 5. **brain/llm_client.py** - Cliente de DeepSeek API

**Función:** Consulta el modelo `deepseek-chat` con temperatura baja (0.3) para decisiones consistentes.

**Estado Actual:** ⚠️ **FALLA CRÍTICA - Sin manejo de errores**

**Problema:**
```python
async with session.post(url, headers=headers, json=payload) as resp:
    data = await resp.json()
    return data['choices'][0]['message']['content']  # ← Puede fallar
```

**Escenarios de fallo:**
1. API key inválida → HTTP 401
2. Rate limit excedido → HTTP 429
3. Timeout de red → aiohttp.ClientError
4. Respuesta vacía → IndexError en `data['choices'][0]`

**Consecuencia:** El agente se crasha completamente.

---

### 6. **brain/decision_parser.py** - Parser de Decisiones

**Función:** Extrae JSON de la respuesta del LLM (puede contener texto adicional).

**Estado Actual:** ✅ **Funcional pero básico**

**Limitación:** No valida campos requeridos ni rangos válidos.

```python
# Entrada del LLM:
"""
Basado en el análisis, recomiendo comprar. Aquí está mi decisión:
{
  "direction": "buy",
  "confidence": 85,
  "reasoning": "RSI en sobreventa con divergencia alcista",
  "stop_loss_pct": 0.02,
  "take_profit_pct": 0.04,
  "risk_reward": 2.0
}
"""

# Salida del parser:
{
  "direction": "buy",
  "confidence": 85,
  "reasoning": "RSI en sobreventa...",
  "stop_loss_pct": 0.02,
  "take_profit_pct": 0.04,
  "risk_reward": 2.0
}
```

---

### 7. **execution/time_gate.py** - Puerta de Tiempo

**Función:** Verifica que la entrada ocurra en el momento adecuado del ciclo de mercado.

**Lógica:**
- En timeframe M5, espera confirmación de 2-3 velas en la misma dirección
- Evita entradas en máximos/mínimos locales sin confirmación

**Estado Actual:** ✅ **Funcional**

---

### 8. **risk/manager.py** - Gestor de Riesgo

**Función:** Calcula tamaño de posición basado en riesgo por trade.

**Fórmulas:**
```python
risk_amount = balance * risk_per_trade  # Ej: $10000 * 0.005 = $50
risk_distance = abs(entry - stop_loss) / entry
position_size = risk_amount / (price * risk_distance)
```

**Controles:**
| Control | Umbral | Acción |
|---------|--------|--------|
| Max posiciones abiertas | 5 | Bloquea nuevas |
| Drawdown diario | 2% | Bloquea hasta reset |
| Drawdown total | 15% | Detiene agente |

**Estado Actual:** ✅ **Funcional**

**Ejemplo:**
```python
# Entrada:
balance = $10,000
risk_per_trade = 0.5%
entry = $100
stop_loss = $98 (2% abajo)

# Cálculo:
risk_amount = 10000 * 0.005 = $50
risk_distance = |100 - 98| / 100 = 0.02
position_size = 50 / (100 * 0.02) = 25 unidades

# Si el precio cae a $98:
pérdida = 25 * (100 - 98) = $50 (exactamente el riesgo planeado)
```

---

### 9. **execution/paper_engine.py** - Executor en Modo Paper

**Función:** Simula ejecuciones sin dinero real.

**Estado Actual:** ⚠️ **PROBLEMA MAYOR - Precios ficticios**

**Problema:**
```python
async def execute(self, symbol, direction, size, stop_loss, take_profit):
    entry = 100  # ← PRECIO FIJO SIMULADO, no el precio real
    ...
```

**Consecuencia:** 
- Las pruebas en paper trading no reflejan la realidad
- Imposible validar la estrategia antes de live

---

### 10. **memory/storage.py** - Base de Datos SQLite

**Función:** Persiste trades y reflexiones para análisis posterior.

**Tablas:**
```sql
CREATE TABLE trades (
    id INTEGER PRIMARY KEY,
    symbol TEXT,
    direction TEXT,
    entry REAL,          -- ← Se guarda
    exit REAL,           -- ← NUNCA se actualiza (BUG)
    size REAL,
    pnl REAL,            -- ← NUNCA se actualiza (BUG)
    confidence INTEGER,
    reasoning TEXT,
    timestamp DATETIME
);
```

**Estado Actual:** ⚠️ **FALLA CRÍTICA - No guarda salidas**

**Problema:**
```python
def save_trade(self, symbol, decision, result):
    cursor.execute('''
        INSERT INTO trades (symbol, direction, entry, size, confidence, reasoning)
        VALUES (?, ?, ?, ?, ?, ?)  # ← NO incluye exit ni pnl
    ''', ...)
```

**Consecuencia:** 
- Imposible calcular métricas reales (win rate, profit factor)
- El dashboard muestra datos incompletos

---

### 11. **backtesting/engine.py** - Motor de Backtest

**Función:** Simula estrategia en datos históricos.

**Estado Actual:** 🔴 **CRÍTICO - Datos aleatorios**

**Problema:**
```python
async def _fetch_historical_data(self, symbol: str):
    import random
    base_price = 100 + random.random() * 50
    for i in range(days * 288):  # 288 velas M5 por día
        change = (random.random() - 0.5) * 2
        base_price *= (1 + change / 100)  # ← Random walk puro
```

**Consecuencia:**
- Los resultados del backtest son **inútiles**
- No se puede optimizar parámetros ni validar estrategias

---

### 12. **data/impact_monitor.py** - Monitor de Impacto

**Función:** Monitorea noticias (CryptoPanic), alertas de ballenas (Whale Alert) y datos macro (FRED).

**Estado Actual:** ⚠️ **Parcialmente funcional**

**Dependencias externas:**
- CryptoPanic API (noticias crypto)
- Whale Alert API (transacciones grandes)
- FRED API (datos económicos EE.UU.)

**Sin estas APIs:** Solo opera con score = 0 (no filtra nada).

---

## 🚨 Errores Críticos Identificados

### Resumen por Severidad

| ID | Módulo | Error | Severidad | Impacto |
|----|--------|-------|-----------|---------|
| **C01** | `live_feed.py` | `get_ohlcv()` retorna `[]` | 🔴 CRÍTICO | Agente nunca analiza |
| **C02** | `backtesting/engine.py` | Genera datos aleatorios | 🔴 CRÍTICO | Backtests inútiles |
| **C03** | `memory/storage.py` | No guarda exit/pnl | 🔴 CRÍTICO | Métricas imposibles |
| **C04** | `llm_client.py` | Sin manejo de errores HTTP | 🔴 CRÍTICO | Caídas del agente |
| **M01** | `paper_engine.py` | Precio fijo en $100 | 🟠 MAYOR | Paper trading irreal |
| **M02** | `main.py` | No inicia tasks OHLCV | 🟠 MAYOR | Sin datos de velas |
| **M03** | `features.py` | Division by zero en volume_zscore | 🟠 MAYOR | Crash con datos constantes |
| **M04** | `decision_parser.py` | Sin validación de campos | 🟠 MAYOR | Decisiones corruptas |
| **M05** | `risk/manager.py` | No actualiza open_positions correctamente | 🟠 MAYOR | Límite de posiciones incorrecto |
| **m01** | `technical.py` | prev_macd no se inicializa por símbolo | 🟢 MENOR | Falso cruce en primer análisis |
| **m02** | `time_gate.py` | Lógica de confirmación muy simple | 🟢 MENOR | Entradas prematuras |
| **m03** | `prompt_builder.py` | Prompt muy largo (gasta tokens) | 🟢 MENOR | Presupuesto agotado rápido |
| **m04** | `config.py` | Hardcoded values sin validación | 🟢 MENOR | Errores silenciosos |
| **m05** | `dashboard/app.py` | Asume datos completos en DB | 🟢 MENOR | Gráficos rotos |

---

## 🛠️ Correcciones Necesarias (con Código)

### CORRECCIÓN C01: Pipeline de Datos OHLCV

**Archivo:** `data/live_feed.py`

**Problema:** Nadie llama a `watch_ohlcv()`, entonces `self.ohlcv` está vacío.

**Solución:** Iniciar tareas de watch para cada símbolo y timeframe en `main.py`.

```python
# live_feed.py - MODIFICAR watch_tickers()
async def watch_tickers(self, symbols=None):
    """Watch tickers for specific symbols only"""
    target_symbols = symbols or self.exchange.symbols[:50]
    while True:
        try:
            for symbol in target_symbols:
                ticker = await self.exchange.watch_ticker(symbol)
                self.tickers[symbol] = ticker
        except Exception as e:
            print(f"Error watching tickers: {e}")
            await asyncio.sleep(5)

# live_feed.py - AGREGAR nuevo método
async def watch_all_ohlcv(self, symbols, timeframes):
    """Start OHLCV watchers for all symbol/timeframe combinations"""
    tasks = []
    for symbol in symbols:
        for tf in timeframes:
            task = asyncio.create_task(self._watch_single_ohlcv(symbol, tf))
            tasks.append(task)
    await asyncio.gather(*tasks, return_exceptions=True)

async def _watch_single_ohlcv(self, symbol, timeframe):
    """Internal watcher for one symbol/timeframe"""
    key = f"{symbol}_{timeframe}"
    while True:
        try:
            ohlcv = await self.exchange.watch_ohlcv(symbol, timeframe)
            self.ohlcv[key] = ohlcv
        except Exception as e:
            print(f"Error watching OHLCV {symbol} {timeframe}: {e}")
            await asyncio.sleep(5)

# live_feed.py - AGREGAR cleanup
async def close(self):
    await self.exchange.close()
```

**Archivo:** `main.py`

```python
# main.py - MODIFICAR sección de inicialización
async def main():
    logging.basicConfig(level=logging.INFO)
    logger.info(f"Iniciando agente en modo {MODE}")
    
    memory = MemoryDB(DATABASE_PATH)
    market = LiveMarketFeed()
    
    # INICIAR todos los watchers necesarios
    asyncio.create_task(market.watch_tickers(SYMBOLS))
    asyncio.create_task(market.watch_all_ohlcv(SYMBOLS, SECONDARY_TIMEFRAMES + [PRIMARY_TIMEFRAME]))
    
    impact_monitor = ImpactMonitor(SYMBOLS)
    asyncio.create_task(impact_monitor.start())
    
    # ... resto del código
```

---

### CORRECCIÓN C02: Backtest con Datos Reales

**Archivo:** `backtesting/engine.py`

**Problema:** Genera datos aleatorios en lugar de usar históricos reales.

**Solución:** Integrar con ccxt para descargar datos históricos reales.

```python
# backtesting/engine.py - REEMPLAZAR _fetch_historical_data
import ccxt.async_support as ccxt_async

async def _fetch_historical_data(self, symbol: str):
    """Fetch real historical OHLCV from exchange"""
    exchange = getattr(ccxt_async, EXCHANGE_ID)({
        'enableRateLimit': True,
    })
    
    timeframe = '5m'  # Para backtest M5
    since = int(self.start.timestamp() * 1000)
    until = int(self.end.timestamp() * 1000)
    
    all_ohlcv = []
    while since < until:
        try:
            ohlcv = await exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=1000)
            if not ohlcv:
                break
            all_ohlcv.extend(ohlcv)
            since = ohlcv[-1][0] + 1  # Continuar desde última vela
        except Exception as e:
            print(f"Error fetching {symbol}: {e}")
            break
    
    await exchange.close()
    return all_ohlcv
```

**Alternativa offline:** Descargar datos previamente y guardarlos en CSV.

```python
# backtesting/data_downloader.py (NUEVO ARCHIVO)
import ccxt.async_support as ccxt_async
import pandas as pd
import asyncio

async def download_historical(symbol, start, end, timeframe='5m'):
    exchange = getattr(ccxt_async, 'binance')({'enableRateLimit': True})
    
    since = int(start.timestamp() * 1000)
    end_ms = int(end.timestamp() * 1000)
    
    all_data = []
    while since < end_ms:
        ohlcv = await exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=1000)
        if not ohlcv:
            break
        all_data.extend(ohlcv)
        since = ohlcv[-1][0] + 1
    
    await exchange.close()
    
    df = pd.DataFrame(all_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('timestamp', inplace=True)
    
    filename = f"data/historical/{symbol.replace('/', '_')}_{timeframe}.csv"
    df.to_csv(filename)
    print(f"Descargado {len(df)} velas → {filename}")
    return df
```

---

### CORRECCIÓN C03: Guardar Exit/PnL en Memoria

**Archivo:** `memory/storage.py`

**Problema:** `save_trade()` no guarda exit price ni pnl.

**Solución:** Modificar para incluir estos campos y actualizar cuando se cierra la posición.

```python
# memory/storage.py - MODIFICAR save_trade
def save_trade(self, symbol: str, decision: Dict[str, Any], result: Dict[str, Any]):
    conn = sqlite3.connect(self.db_path)
    cursor = conn.cursor()
    
    # INCLUIR exit y pnl desde el inicio (aunque sean None)
    cursor.execute('''
        INSERT INTO trades (symbol, direction, entry, exit, size, pnl, confidence, reasoning)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        symbol,
        decision.get('direction'),
        result.get('entry'),  # Usar entry del resultado
        result.get('exit'),   # Puede ser None si aún está abierto
        result.get('size'),
        result.get('pnl', 0), # Default 0 si no hay pnl
        decision.get('confidence'),
        decision.get('reasoning')
    ))
    
    conn.commit()
    conn.close()

# memory/storage.py - AGREGAR método para cerrar trade
def close_trade(self, trade_id: int, exit_price: float, pnl: float):
    """Update an open trade with exit price and pnl"""
    conn = sqlite3.connect(self.db_path)
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE trades 
        SET exit = ?, pnl = ?, status = 'closed'
        WHERE id = ?
    ''', (exit_price, pnl, trade_id))
    
    conn.commit()
    conn.close()

# memory/storage.py - AGREGAR método para obtener trades abiertos
def get_open_trades(self) -> List[Dict[str, Any]]:
    """Get all trades that haven't been closed yet"""
    conn = sqlite3.connect(self.db_path)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT * FROM trades 
        WHERE exit IS NULL OR pnl = 0
        ORDER BY timestamp DESC
    ''')
    columns = [desc[0] for desc in cursor.description]
    trades = [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    conn.close()
    return trades
```

**Archivo:** `main.py` - Actualizar para cerrar trades

```python
# main.py - AGREGAR gestión de cierre de posiciones
async def manage_open_positions(executor, memory, risk_manager):
    """Check and close positions that hit SL or TP"""
    open_trades = memory.get_open_trades()
    
    for trade in open_trades:
        symbol = trade['symbol']
        ticker = market.get_ticker(symbol)
        if not ticker:
            continue
        
        current_price = ticker['last']
        entry = trade['entry']
        direction = trade['direction']
        
        # Obtener SL y TP del resultado original (debería estar en otra tabla)
        # Por ahora, usamos lógica simple
        should_close = False
        pnl = 0
        
        if direction == 'buy':
            if current_price <= entry * 0.98:  # SL 2%
                should_close = True
                pnl = (current_price - entry) * trade['size']
            elif current_price >= entry * 1.04:  # TP 4%
                should_close = True
                pnl = (current_price - entry) * trade['size']
        else:  # sell
            if current_price >= entry * 1.02:  # SL 2%
                should_close = True
                pnl = (entry - current_price) * trade['size']
            elif current_price <= entry * 0.96:  # TP 4%
                should_close = True
                pnl = (entry - current_price) * trade['size']
        
        if should_close:
            # Actualizar en memoria
            memory.close_trade(trade['id'], current_price, pnl)
            
            # Actualizar risk manager
            risk_manager.update_pnl(pnl)
            
            logger.info(f"Cerrado {symbol}: PnL = ${pnl:.2f}")
```

---

### CORRECCIÓN C04: Manejo de Errores en LLM Client

**Archivo:** `brain/llm_client.py`

**Problema:** Sin try/except, cualquier error crasha el agente.

**Solución:** Agregar manejo robusto de errores con retries.

```python
# brain/llm_client.py - REESCRIBIR completo
import aiohttp
import json
import asyncio
from config import DEEPSEEK_API_KEY, DEEPSEEK_MODEL

async def query_deepseek(prompt, max_retries=3, timeout=30):
    """Query DeepSeek API with error handling and retries"""
    
    if not DEEPSEEK_API_KEY:
        return json.dumps({
            "direction": "wait", 
            "confidence": 0, 
            "reasoning": "API key no configurada"
        })
    
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
    
    for attempt in range(max_retries):
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as session:
                async with session.post(
                    'https://api.deepseek.com/v1/chat/completions',
                    headers=headers,
                    json=payload
                ) as resp:
                    
                    # Manejar errores HTTP
                    if resp.status == 401:
                        print("❌ Error 401: API key inválida")
                        return json.dumps({"direction": "wait", "confidence": 0, "reasoning": "API key inválida"})
                    
                    if resp.status == 429:
                        print(f"⚠️ Rate limit excedido. Esperando...")
                        retry_after = int(resp.headers.get('Retry-After', 60))
                        await asyncio.sleep(min(retry_after, 300))
                        continue
                    
                    if resp.status != 200:
                        print(f"⚠️ Error HTTP {resp.status}. Intento {attempt + 1}/{max_retries}")
                        await asyncio.sleep(2 ** attempt)  # Backoff exponencial
                        continue
                    
                    data = await resp.json()
                    
                    # Validar estructura de respuesta
                    if not data.get('choices') or len(data['choices']) == 0:
                        print("⚠️ Respuesta vacía del LLM")
                        return json.dumps({"direction": "wait", "confidence": 0, "reasoning": "Sin respuesta del LLM"})
                    
                    content = data['choices'][0]['message']['content']
                    return content
                    
        except aiohttp.ClientError as e:
            print(f"⚠️ Error de red: {e}. Intento {attempt + 1}/{max_retries}")
            await asyncio.sleep(2 ** attempt)
            
        except asyncio.TimeoutError:
            print(f"⚠️ Timeout después de {timeout}s. Intento {attempt + 1}/{max_retries}")
            await asyncio.sleep(2 ** attempt)
            
        except Exception as e:
            print(f"❌ Error inesperado: {e}")
            return json.dumps({"direction": "wait", "confidence": 0, "reasoning": f"Error: {str(e)}"})
    
    # Todos los retries fallaron
    return json.dumps({"direction": "wait", "confidence": 0, "reasoning": "Múltiples fallos en API"})
```

---

### CORRECCIÓN M01: Paper Engine con Precios Reales

**Archivo:** `execution/paper_engine.py`

**Problema:** Usa precio fijo de $100 en lugar del precio real del mercado.

**Solución:** Recibir el precio actual como parámetro.

```python
# execution/paper_engine.py - MODIFICAR execute
async def execute(self, symbol, direction, size, stop_loss, take_profit, current_price=None):
    """Execute paper trade with real market price"""
    
    if direction not in ['buy', 'sell']:
        return None
    
    # USAR precio real si se proporciona
    if current_price is None:
        print(f"⚠️ Warning: current_price no proporcionado para {symbol}")
        return None
    
    entry = current_price
    
    # Calcular slippage simulado
    slippage = entry * (SLIPPAGE_FACTOR / 1000)  # 0.05% slippage
    if direction == 'buy':
        entry += slippage  # Compras ligeramente más caro
    else:
        entry -= slippage  # Vendes ligeramente más barato
    
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
        'status': 'open',
        'exit': None,
        'pnl': None
    }
    
    self.positions[symbol] = result
    self.trades.append(result)
    
    return result

# AGREGAR método para cerrar con precio real
def close_position(self, symbol, exit_price):
    pos = self.positions.pop(symbol, None)
    if not pos:
        return None
    
    # Aplicar slippage en salida también
    slippage = exit_price * (SLIPPAGE_FACTOR / 1000)
    if pos['direction'] == 'buy':
        actual_exit = exit_price - slippage  # Vendes más barato
    else:
        actual_exit = exit_price + slippage  # Compras más caro
    
    direction_mult = 1 if pos['direction'] == 'buy' else -1
    pnl = (actual_exit - pos['entry']) * pos['size'] * direction_mult
    pnl -= pos['commission'] * 2  # Comisión en entrada y salida
    
    self.balance += pnl
    
    return {
        **pos,
        'exit': actual_exit,
        'pnl': pnl,
        'status': 'closed'
    }
```

**Archivo:** `main.py` - Pasar precio real al executor

```python
# main.py - MODIFICAR llamada a executor
ticker = market.get_ticker(symbol)
if not ticker:
    continue

current_price = ticker['last']

# ... después de validar decisión ...

result = await executor.execute(
    symbol, 
    decision.get('direction'),
    position_size, 
    stop_loss, 
    take_profit,
    current_price=current_price  # ← NUEVO parámetro
)
```

---

### CORRECCIÓN M02: Inicializar Tasks OHLCV en Main

**Archivo:** `main.py`

Ya cubierto en CORRECCIÓN C01, pero aquí está el código completo:

```python
# main.py - Sección de inicialización CORREGIDA
async def main():
    logging.basicConfig(level=logging.INFO)
    logger.info(f"Iniciando agente en modo {MODE}")
    
    memory = MemoryDB(DATABASE_PATH)
    market = LiveMarketFeed()
    
    # ✅ INICIAR todos los watchers
    asyncio.create_task(market.watch_tickers(SYMBOLS))
    asyncio.create_task(market.watch_all_ohlcv(
        SYMBOLS, 
        list(set([PRIMARY_TIMEFRAME] + SECONDARY_TIMEFRAMES))
    ))
    
    impact_monitor = ImpactMonitor(SYMBOLS)
    asyncio.create_task(impact_monitor.start())
    
    pre_filter = load_filter(os.getenv("PRE_FILTER", "technical"))
    logger.info(f"Filtro: {type(pre_filter).__name__}")
    
    time_gate = TimeGate(TF_MAP[PRIMARY_TIMEFRAME])
    risk_manager = RiskManager(
        INITIAL_BALANCE, MAX_POSITIONS, RISK_PER_TRADE, 
        MAX_DAILY_DRAWDOWN, MAX_TOTAL_DRAWDOWN
    )
    
    if MODE == "live":
        from execution.mt5_executor import MT5Executor
        from execution.exchange_executor import ExchangeExecutor
        executor = MT5Executor() if MT5_LOGIN else ExchangeExecutor()
    else:
        from execution.paper_engine import PaperEngine
        executor = PaperEngine(INITIAL_BALANCE)
    
    daily_tokens = 0
    last_reflection_date = None
    
    # Bucle principal...
```

---

### CORRECCIÓN M03: Evitar División por Cero en Volume Z-Score

**Archivo:** `data/features.py`

**Problema:** `np.std(volume[-20:])` puede ser 0 si todos los volúmenes son iguales.

**Solución:** Agregar verificación y epsilon.

```python
# data/features.py - MODIFICAR cálculo de volume_zscore
volume_ma = np.mean(volume[-20:])
volume_std = np.std(volume[-20:])

# Evitar división por cero con epsilon
epsilon = 1e-10
features['volume_zscore'] = (volume[-1] - volume_ma) / max(volume_std, epsilon)
```

---

### CORRECCIÓN M04: Validación de Decisión del LLM

**Archivo:** `brain/decision_parser.py`

**Problema:** No valida que los campos existan o tengan valores razonables.

**Solución:** Agregar validación exhaustiva.

```python
# brain/decision_parser.py - REESCRIBIR completo
import json
import re
from typing import Optional, Dict, Any

VALID_DIRECTIONS = ['buy', 'sell', 'wait']

def parse_decision(text: str) -> Optional[Dict[str, Any]]:
    """Parse LLM response with validation"""
    
    try:
        # Extraer JSON del texto
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if not match:
            print(f"⚠️ No se encontró JSON en: {text[:100]}")
            return None
        
        data = json.loads(match.group())
        
        # Validar campos requeridos
        required_fields = ['direction', 'confidence', 'reasoning']
        for field in required_fields:
            if field not in data:
                print(f"⚠️ Campo faltante: {field}")
                return None
        
        # Validar direction
        if data['direction'] not in VALID_DIRECTIONS:
            print(f"⚠️ Dirección inválida: {data['direction']}")
            return None
        
        # Validar confidence (0-100)
        confidence = data.get('confidence', 0)
        if not isinstance(confidence, (int, float)) or confidence < 0 or confidence > 100:
            print(f"⚠️ Confidence inválido: {confidence}")
            return None
        
        # Validar risk_reward (debe ser positivo)
        rr = data.get('risk_reward', 0)
        if not isinstance(rr, (int, float)) or rr < 0:
            print(f"⚠️ Risk/Reward inválido: {rr}")
            return None
        
        # Validar stop_loss_pct y take_profit_pct (0-1)
        for pct_field in ['stop_loss_pct', 'take_profit_pct']:
            val = data.get(pct_field, 0)
            if not isinstance(val, (int, float)) or val < 0 or val > 1:
                print(f"⚠️ {pct_field} inválido: {val}")
                # Corregir automáticamente
                data[pct_field] = 0.02 if pct_field == 'stop_loss_pct' else 0.04
        
        return data
        
    except json.JSONDecodeError as e:
        print(f"⚠️ Error parsing JSON: {e}")
        return None
    except Exception as e:
        print(f"⚠️ Error inesperado: {e}")
        return None
```

---

### CORRECCIÓN M05: Gestión Correcta de Posiciones Abiertas

**Archivo:** `risk/manager.py`

**Problema:** `open_positions` se decrementa incluso si el trade fue rechazado.

**Solución:** Separar tracking de posiciones reales vs intentos.

```python
# risk/manager.py - MODIFICAR calculate_position y agregar track_real_position
def calculate_position(self, symbol, price, direction, 
                      stop_loss_pct: float, take_profit_pct: float):
    """Solo calcula, no incrementa open_positions"""
    
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
    
    # NO incrementar open_positions aquí
    # Se incrementará solo cuando la orden se ejecute realmente
    
    return position_size, stop_loss, take_profit

def confirm_position_opened(self):
    """Call this when an order is actually executed"""
    self.open_positions += 1

def update_pnl(self, pnl: float):
    self.daily_pnl += pnl
    self.total_pnl += pnl
    # Solo decrementar si había posiciones reales
    if self.open_positions > 0:
        self.open_positions = max(0, self.open_positions - 1)
```

**Archivo:** `main.py` - Llamar a confirm_position_opened

```python
# main.py - Después de ejecutar orden exitosa
result = await executor.execute(...)

if result:
    risk_manager.confirm_position_opened()  # ← NUEVA llamada
    memory.save_trade(symbol, decision, result)
    # ...
```

---

## 🚀 Mejoras Recomendadas

### Mejora 1: Sistema de Circuit Breaker

**Propósito:** Detener automáticamente el agente si detecta comportamiento anómalo.

```python
# risk/circuit_breaker.py (NUEVO ARCHIVO)
class CircuitBreaker:
    def __init__(self, max_consecutive_losses=5, max_hourly_loss_pct=0.05):
        self.consecutive_losses = 0
        self.hourly_pnl = 0
        self.max_consecutive_losses = max_consecutive_losses
        self.max_hourly_loss_pct = max_hourly_loss_pct
        self.is_open = False  # Circuito abierto = detener trading
    
    def record_trade(self, pnl: float):
        if pnl < 0:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0
        
        self.hourly_pnl += pnl
        
        # Verificar condiciones de disparo
        if self.consecutive_losses >= self.max_consecutive_losses:
            self.is_open = True
            print(f"🚨 CIRCUIT BREAKER: {self.max_consecutive_losses} pérdidas consecutivas")
        
        if abs(self.hourly_pnl) / 10000 >= self.max_hourly_loss_pct:  # Asumiendo balance inicial
            self.is_open = True
            print(f"🚨 CIRCUIT BREAKER: Pérdida horaria máxima alcanzada")
    
    def reset_hourly(self):
        self.hourly_pnl = 0
    
    def can_trade(self) -> bool:
        return not self.is_open
```

---

### Mejora 2: Optimización de Prompts (Reducir Tokens)

**Propósito:** Reducir costo de API manteniendo calidad de decisión.

```python
# brain/prompt_builder.py - OPTIMIZAR
def build_rich_prompt(symbol, ticker, f1m, f5m, f15m, vol_profile, order_book, impact):
    """Build concise prompt to save tokens"""
    
    # Solo incluir features relevantes
    key_features = {
        'RSI': round(f5m.get('rsi', 50), 1),
        'MACD': 'bull' if f5m.get('macd', 0) > f5m.get('macd_signal', 0) else 'bear',
        'ATR%': round(f5m.get('atr', 0) / f5m.get('price', 1) * 100, 2),
        'Vol': 'HIGH' if f5m.get('volume_zscore', 0) > 1.5 else 'NORM',
        'BB%': round(f5m.get('bb_position', 0.5) * 100, 0)
    }
    
    # Formato compacto
    prompt = f"""[{symbol}]
P:${ticker['last']:.2f} | RSI:{key_features['RSI']} | MACD:{key_features['MACD']} | ATR:{key_features['ATR%']}% | Vol:{key_features['Vol']} | BB:{key_features['BB%']}%"""
    
    if impact and impact.get('score', 0) >= 4:
        prompt += f" | IMPACTO:{impact.get('score')}/5"
    
    prompt += "\nDecisión JSON: {direction, confidence(0-100), reasoning, stop_loss_pct, take_profit_pct, risk_reward}"
    
    return prompt
```

**Ahorro estimado:** ~70% de tokens por consulta.

---

### Mejora 3: Ensemble de Filtros

**Propósito:** Combinar múltiples filtros para mayor precisión.

```python
# filters/ensemble.py (NUEVO ARCHIVO)
from .technical import TechnicalFilter
from .price_action import PriceActionFilter
from .volume_sentiment import VolumeSentimentFilter

class EnsembleFilter:
    def __init__(self, weights=None):
        self.filters = {
            'technical': TechnicalFilter(),
            'price_action': PriceActionFilter(),
            'volume': VolumeSentimentFilter()
        }
        self.weights = weights or {'technical': 0.5, 'price_action': 0.3, 'volume': 0.2}
    
    def should_analyze(self, symbol, market_data, f1m, f5m, vol_prof, ob):
        scores = {}
        reasons = {}
        
        for name, filt in self.filters.items():
            should, reason = filt.should_analyze(symbol, market_data, f1m, f5m, vol_prof, ob)
            scores[name] = 1 if should else 0
            reasons[name] = reason
        
        # Weighted score
        total_score = sum(scores[n] * self.weights[n] for n in scores)
        
        # Requiere al menos 0.6 para pasar
        if total_score >= 0.6:
            return True, f"Ensemble: {total_score:.2f} ({reasons})"
        
        return False, f"Ensemble score bajo: {total_score:.2f}"
```

---

### Mejora 4: Dashboard en Tiempo Real con Métricas

**Propósito:** Visualizar performance del agente live.

```python
# dashboard/app.py - AGREGAR métricas en tiempo real
import streamlit as st
import plotly.graph_objects as go
from memory.storage import MemoryDB

st.title("🤖 Autonomous Trading Agent Dashboard")

# Sidebar con controles
mode = st.sidebar.selectbox("Modo", ["Live", "Backtest"])
symbol_filter = st.sidebar.multiselect("Símbolos", ["BTC/USDT", "ETH/USDT", "SOL/USDT"], default=["BTC/USDT"])

# Conectar a DB
db = MemoryDB("agent_memory.db")
trades = db.get_trades(limit=1000)

if trades:
    # KPIs principales
    col1, col2, col3, col4 = st.columns(4)
    
    total_pnl = sum(t['pnl'] for t in trades if t['pnl'] is not None)
    win_trades = [t for t in trades if t['pnl'] and t['pnl'] > 0]
    win_rate = len(win_trades) / len(trades) * 100 if trades else 0
    
    col1.metric("PnL Total", f"${total_pnl:.2f}")
    col2.metric("Win Rate", f"{win_rate:.1f}%")
    col3.metric("Total Trades", len(trades))
    col4.metric("Balance", f"${10000 + total_pnl:.2f}")
    
    # Gráfico de equity curve
    df = pd.DataFrame(trades)
    df['cumulative_pnl'] = df['pnl'].cumsum()
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df['timestamp'], y=df['cumulative_pnl'], mode='lines', name='Equity'))
    fig.update_layout(title="Curva de Capital", xaxis_title="Tiempo", yaxis_title="PnL Acumulado ($)")
    st.plotly_chart(fig)
    
    # Distribución de PnL
    fig2 = go.Figure(data=[go.Histogram(x=df['pnl'], nbinsx=20)])
    fig2.update_layout(title="Distribución de PnL por Trade")
    st.plotly_chart(fig2)
else:
    st.info("No hay trades registrados aún")
```

---

### Mejora 5: Walk-Forward Optimization

**Propósito:** Evitar overfitting en optimización de parámetros.

```python
# optimization/walk_forward.py (NUEVO ARCHIVO)
from datetime import timedelta

class WalkForwardOptimizer:
    def __init__(self, symbols, start, end, train_days=30, test_days=7):
        self.symbols = symbols
        self.start = start
        self.end = end
        self.train_days = train_days
        self.test_days = test_days
    
    def run(self):
        """Run walk-forward optimization"""
        results = []
        current = self.start
        
        while current + self.train_days + self.test_days <= self.end:
            train_start = current
            train_end = current + timedelta(days=self.train_days)
            test_start = train_end
            test_end = test_start + timedelta(days=self.test_days)
            
            print(f"📊 Periodo: {train_start.date()} → {test_end.date()}")
            
            # Optimizar en periodo de entrenamiento
            opt = FilterOptimizer(self.symbols, train_start, train_end)
            best_params, _ = opt.optimize()
            
            # Testear en periodo fuera de muestra
            engine = BacktestEngine(self.symbols, test_start, test_end)
            engine.pre_filter = load_filter('technical')
            engine.pre_filter.set_parameters(best_params)
            trades = asyncio.run(engine.run())
            
            # Calcular métricas out-of-sample
            metrics = self._calculate_metrics(trades)
            results.append({
                'period': f"{train_start.date()} → {test_end.date()}",
                'params': best_params,
                **metrics
            })
            
            # Deslizar ventana
            current = test_end
        
        return results
    
    def _calculate_metrics(self, trades):
        if not trades:
            return {'sharpe': 0, 'profit_factor': 0, 'win_rate': 0}
        
        pnls = [t['pnl'] for t in trades if t['pnl']]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]
        
        profit_factor = abs(sum(wins) / sum(losses)) if losses else 0
        win_rate = len(wins) / len(pnls) * 100
        
        return {
            'sharpe': np.mean(pnls) / np.std(pnls) * np.sqrt(252) if pnls else 0,
            'profit_factor': profit_factor,
            'win_rate': win_rate,
            'total_trades': len(trades)
        }
```

---

## 📋 Plan de Implementación

### Fase 1: Correcciones Críticas (Semana 1)
- [ ] **C01**: Implementar pipeline OHLCV completo
- [ ] **C02**: Integrar datos históricos reales en backtest
- [ ] **C03**: Fix en memoria para guardar exit/pnl
- [ ] **C04**: Agregar manejo de errores en LLM client
- [ ] Ejecutar tests unitarios después de cada fix

### Fase 2: Validación en Paper Trading (Semana 2-3)
- [ ] **M01**: Fix paper engine con precios reales
- [ ] Configurar 3 símbolos principales (BTC, ETH, SOL)
- [ ] Ejecutar 7 días continuos en paper
- [ ] Recolectar mínimo 50 trades
- [ ] Analizar métricas preliminares

### Fase 3: Mejoras de Robustez (Semana 4)
- [ ] **M02-M05**: Correcciones menores restantes
- [ ] Implementar circuit breaker
- [ ] Optimizar prompts para reducir costos
- [ ] Agregar ensemble de filtros

### Fase 4: Optimización (Semana 5-6)
- [ ] Ejecutar walk-forward optimization
- [ ] Identificar mejores parámetros por régimen de mercado
- [ ] Validar estabilidad de parámetros

### Fase 5: Producción (Semana 7+)
- [ ] Deploy en servidor 24/7
- [ ] Configurar alertas (Telegram/Discord)
- [ ] Dashboard en tiempo real
- [ ] Inicio con capital mínimo ($100-500)
- [ ] Escalar gradualmente tras 30 días positivos

---

## 📊 Métricas Clave a Monitorear

### Durante Paper Trading
| Métrica | Objetivo Mínimo | Óptimo |
|---------|-----------------|--------|
| Win Rate | > 45% | > 55% |
| Profit Factor | > 1.2 | > 1.8 |
| Sharpe Ratio | > 0.5 | > 1.5 |
| Max Drawdown | < 10% | < 5% |
| Avg Trade Duration | < 4 horas | 30 min - 2h |
| Slippage Average | < 0.1% | < 0.05% |

### Antes de Ir a Live
- ✅ Mínimo 100 trades en paper
- ✅ 30 días consecutivos operando
- ✅ Drawdown máximo < 10%
- ✅ Profit factor estable (> 1.3) en últimos 50 trades
- ✅ Al menos 3 símbolos probados

---

## 🎯 Conclusión

El agente tiene una **arquitectura sólida** pero requiere correcciones críticas antes de ser usable:

1. **Sin las correcciones C01-C04**: El agente **NO FUNCIONA** en absoluto
2. **Con correcciones pero sin mejoras**: Funciona pero con limitaciones importantes
3. **Con correcciones + mejoras**: Lista para paper trading serio

**Recomendación inmediata:** Implementar Fase 1 completa antes de considerar cualquier operación real.
