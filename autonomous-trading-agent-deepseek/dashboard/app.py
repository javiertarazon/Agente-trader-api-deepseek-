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
