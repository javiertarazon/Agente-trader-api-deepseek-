import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Any

class MemoryDB:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT,
                direction TEXT,
                entry REAL,
                exit REAL,
                size REAL,
                pnl REAL,
                confidence INTEGER,
                reasoning TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reflections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATE,
                summary TEXT,
                lessons TEXT,
                adjustments TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()

    def save_trade(self, symbol: str, decision: Dict[str, Any], result: Dict[str, Any]):
        """Guardar trade con toda la información necesaria"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Extraer datos del resultado si existen
        exit_price = result.get('exit', None)
        pnl = result.get('pnl', None)
        size = result.get('size', decision.get('size', 0))
        
        cursor.execute('''
            INSERT INTO trades (symbol, direction, entry, exit, size, pnl, confidence, reasoning)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            symbol,
            decision.get('direction'),
            decision.get('entry_price'),
            exit_price,
            size,
            pnl,
            decision.get('confidence'),
            decision.get('reasoning')
        ))
        
        trade_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return trade_id

    def update_trade_exit(self, trade_id: int, exit_price: float, pnl: float):
        """Actualizar precio de salida y PnL de un trade"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE trades SET exit = ?, pnl = ? WHERE id = ?
        ''', (exit_price, pnl, trade_id))
        
        affected = cursor.rowcount
        conn.commit()
        conn.close()
        
        return affected > 0

    def get_trades(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Obtener trades recientes"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM trades ORDER BY timestamp DESC LIMIT ?', (limit,))
        columns = [desc[0] for desc in cursor.description]
        trades = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
        conn.close()
        return trades

    def get_trades_by_symbol(self, symbol: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Obtener trades para un símbolo específico"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM trades 
            WHERE symbol = ? 
            ORDER BY timestamp DESC LIMIT ?
        ''', (symbol, limit))
        
        columns = [desc[0] for desc in cursor.description]
        trades = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
        conn.close()
        return trades

    def get_trade_statistics(self) -> Dict[str, Any]:
        """Obtener estadísticas generales de trading"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Total trades
        cursor.execute('SELECT COUNT(*) FROM trades')
        total_trades = cursor.fetchone()[0]
        
        # Winning trades
        cursor.execute('SELECT COUNT(*) FROM trades WHERE pnl > 0')
        winning_trades = cursor.fetchone()[0]
        
        # Total PnL
        cursor.execute('SELECT SUM(pnl) FROM trades WHERE pnl IS NOT NULL')
        total_pnl = cursor.fetchone()[0] or 0
        
        # Average PnL
        cursor.execute('SELECT AVG(pnl) FROM trades WHERE pnl IS NOT NULL')
        avg_pnl = cursor.fetchone()[0] or 0
        
        # Win rate
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        conn.close()
        
        return {
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': total_trades - winning_trades,
            'win_rate': win_rate,
            'total_pnl': total_pnl,
            'avg_pnl': avg_pnl
        }

    def save_reflection(self, date: str, summary: str, lessons: str, adjustments: str):
        """Guardar reflexión diaria"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO reflections (date, summary, lessons, adjustments)
            VALUES (?, ?, ?, ?)
        ''', (date, summary, lessons, json.dumps(adjustments)))
        
        conn.commit()
        conn.close()

    def get_reflections(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Obtener reflexiones recientes"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM reflections ORDER BY created_at DESC LIMIT ?', (limit,))
        columns = [desc[0] for desc in cursor.description]
        reflections = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
        conn.close()
        return reflections

    def clear_trades(self):
        """Eliminar todos los trades (útil para testing)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM trades')
        
        conn.commit()
        conn.close()

    def get_recent_performance(self, days: int = 7) -> Dict[str, Any]:
        """Obtener rendimiento de los últimos días"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                DATE(timestamp) as date,
                COUNT(*) as trades_count,
                SUM(pnl) as daily_pnl,
                AVG(pnl) as avg_pnl,
                SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as wins
            FROM trades
            WHERE timestamp >= datetime('now', '-' || ? || ' days')
            GROUP BY DATE(timestamp)
            ORDER BY date DESC
        ''', (days,))
        
        columns = [desc[0] for desc in cursor.description]
        performance = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
        conn.close()
        return performance
