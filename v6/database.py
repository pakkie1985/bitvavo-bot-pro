import sqlite3
from datetime import datetime

DB_PATH = "/opt/bitvavo-bot/v6/trades.db"


def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        opened_at TEXT,
        closed_at TEXT,
        market TEXT,
        buy_price REAL,
        sell_price REAL,
        amount_eur REAL,
        profit_eur REAL,
        profit_pct REAL,
        rsi REAL,
        ema20 REAL,
        ema50 REAL,
        reason TEXT
    )
    """)

    conn.commit()
    conn.close()


def save_trade(market, buy_price, sell_price, amount_eur, rsi, ema20, ema50, reason):
    profit_eur = amount_eur * ((sell_price - buy_price) / buy_price)
    profit_pct = ((sell_price - buy_price) / buy_price) * 100

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO trades (
        opened_at, closed_at, market, buy_price, sell_price,
        amount_eur, profit_eur, profit_pct, rsi, ema20, ema50, reason
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.now().isoformat(),
        datetime.now().isoformat(),
        market,
        buy_price,
        sell_price,
        amount_eur,
        profit_eur,
        profit_pct,
        rsi,
        ema20,
        ema50,
        reason
    ))

    conn.commit()
    conn.close()


def get_stats():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*), COALESCE(SUM(profit_eur), 0) FROM trades")
    total_trades, total_profit = cur.fetchone()

    cur.execute("SELECT COUNT(*) FROM trades WHERE profit_eur > 0")
    wins = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM trades WHERE profit_eur <= 0")
    losses = cur.fetchone()[0]

    winrate = (wins / total_trades * 100) if total_trades else 0

    conn.close()

    return {
        "total_trades": total_trades,
        "wins": wins,
        "losses": losses,
        "winrate": round(winrate, 2),
        "total_profit": round(total_profit, 2)
    }
