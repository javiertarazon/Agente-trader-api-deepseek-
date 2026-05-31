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
