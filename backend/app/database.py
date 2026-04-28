"""
数据库模块 — aiosqlite 异步操作
两张表：watchlist(自选股) + events(事件记录)
"""
import aiosqlite
import logging
from datetime import datetime

import config

logger = logging.getLogger(__name__)


async def get_db() -> aiosqlite.Connection:
    """获取数据库连接"""
    db = await aiosqlite.connect(config.DB_PATH)
    db.row_factory = aiosqlite.Row
    return db


async def init_db():
    """初始化数据库表"""
    db = await get_db()
    try:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS watchlist (
                stock_code TEXT PRIMARY KEY,
                stock_name TEXT NOT NULL,
                added_at TEXT NOT NULL,
                alert_enabled INTEGER DEFAULT 1
            )
        """)
        # 迁移: 添加market字段(如果不存在)
        try:
            await db.execute("ALTER TABLE watchlist ADD COLUMN market TEXT DEFAULT ''")
        except Exception:
            pass  # 字段已存在
        await db.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stock_code TEXT NOT NULL,
                event_type TEXT NOT NULL,
                title TEXT NOT NULL,
                detail TEXT,
                ai_analysis TEXT,
                severity TEXT DEFAULT 'info',
                created_at TEXT NOT NULL
            )
        """)
        await db.commit()
        logger.info("✅ 数据库初始化完成")
    finally:
        await db.close()


async def add_watchlist(stock_code: str, stock_name: str, market: str = "") -> bool:
    """添加自选股"""
    db = await get_db()
    try:
        await db.execute(
            "INSERT OR IGNORE INTO watchlist (stock_code, stock_name, market, added_at) VALUES (?, ?, ?, ?)",
            (stock_code, stock_name, market, datetime.now().isoformat())
        )
        await db.commit()
        return True
    finally:
        await db.close()


async def remove_watchlist(stock_code: str) -> bool:
    """删除自选股"""
    db = await get_db()
    try:
        cursor = await db.execute("DELETE FROM watchlist WHERE stock_code = ?", (stock_code,))
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


async def get_watchlist() -> list[dict]:
    """获取自选股列表（异步）"""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM watchlist ORDER BY added_at DESC")
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()


async def add_event(stock_code: str, event_type: str, title: str, detail: str,
                    ai_analysis: str = "", severity: str = "info") -> int:
    """保存事件到数据库"""
    db = await get_db()
    try:
        cursor = await db.execute(
            "INSERT INTO events (stock_code, event_type, title, detail, ai_analysis, severity, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (stock_code, event_type, title, detail, ai_analysis, severity, datetime.now().isoformat())
        )
        await db.commit()
        return cursor.lastrowid
    finally:
        await db.close()


async def get_events(stock_code: str = None, limit: int = 50) -> list[dict]:
    """查询事件"""
    db = await get_db()
    try:
        if stock_code:
            cursor = await db.execute(
                "SELECT * FROM events WHERE stock_code = ? ORDER BY created_at DESC LIMIT ?",
                (stock_code, limit)
            )
        else:
            cursor = await db.execute(
                "SELECT * FROM events ORDER BY created_at DESC LIMIT ?", (limit,)
            )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()


async def get_today_events_count() -> int:
    """获取今日事件数"""
    db = await get_db()
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        cursor = await db.execute(
            "SELECT COUNT(*) FROM events WHERE created_at LIKE ?",
            (f"{today}%",)
        )
        row = await cursor.fetchone()
        return row[0]
    finally:
        await db.close()


async def toggle_alert(stock_code: str, enabled: bool) -> bool:
    """切换自选股告警开关"""
    db = await get_db()
    try:
        cursor = await db.execute(
            "UPDATE watchlist SET alert_enabled = ? WHERE stock_code = ?",
            (1 if enabled else 0, stock_code)
        )
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()
