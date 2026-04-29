"""
数据库模块 — aiosqlite 异步操作
三张表：users(用户) + watchlist(自选股) + events(事件记录)
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
        # 用户表
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone TEXT UNIQUE NOT NULL,
                nickname TEXT DEFAULT '',
                avatar TEXT DEFAULT '',
                settings TEXT DEFAULT '{}',
                created_at TEXT NOT NULL,
                last_login TEXT
            )
        """)

        # 自选股表（加user_id字段）
        await db.execute("""
            CREATE TABLE IF NOT EXISTS watchlist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER DEFAULT 0,
                stock_code TEXT NOT NULL,
                stock_name TEXT NOT NULL,
                market TEXT DEFAULT '',
                added_at TEXT NOT NULL,
                alert_enabled INTEGER DEFAULT 1,
                UNIQUE(user_id, stock_code)
            )
        """)

        # 迁移：给旧表加user_id字段
        try:
            await db.execute("ALTER TABLE watchlist ADD COLUMN user_id INTEGER DEFAULT 0")
        except Exception:
            pass  # 字段已存在

        # 事件表
        await db.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER DEFAULT 0,
                stock_code TEXT NOT NULL,
                event_type TEXT NOT NULL,
                title TEXT NOT NULL,
                detail TEXT,
                ai_analysis TEXT,
                severity TEXT DEFAULT 'info',
                created_at TEXT NOT NULL
            )
        """)

        # 迁移：给旧events表加user_id字段
        try:
            await db.execute("ALTER TABLE events ADD COLUMN user_id INTEGER DEFAULT 0")
        except Exception:
            pass  # 字段已存在

        # 索引
        await db.execute("CREATE INDEX IF NOT EXISTS idx_watchlist_user ON watchlist(user_id)")
        try:
            await db.execute("CREATE INDEX IF NOT EXISTS idx_events_user ON events(user_id)")
        except Exception:
            pass
        await db.execute("CREATE INDEX IF NOT EXISTS idx_events_stock ON events(stock_code)")

        await db.commit()
        logger.info("✅ 数据库初始化完成")
    finally:
        await db.close()


# ── 用户操作 ──

async def create_user(phone: str, nickname: str = "") -> dict:
    """创建用户，返回用户信息"""
    db = await get_db()
    try:
        now = datetime.now().isoformat()
        if not nickname:
            nickname = f"用户{phone[-4:]}"
        cursor = await db.execute(
            "INSERT OR IGNORE INTO users (phone, nickname, created_at, last_login) VALUES (?, ?, ?, ?)",
            (phone, nickname, now, now)
        )
        await db.commit()
        if cursor.lastrowid:
            user_id = cursor.lastrowid
        else:
            # 用户已存在，查询
            row = await db.execute("SELECT id FROM users WHERE phone = ?", (phone,))
            user = await row.fetchone()
            user_id = user['id']
        # 更新最后登录
        await db.execute("UPDATE users SET last_login = ? WHERE id = ?", (now, user_id))
        await db.commit()
        return {"id": user_id, "phone": phone, "nickname": nickname}
    finally:
        await db.close()


async def get_user_by_phone(phone: str) -> dict | None:
    """通过手机号查找用户"""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM users WHERE phone = ?", (phone,))
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def update_user_settings(user_id: int, settings: dict) -> bool:
    """更新用户设置"""
    import json
    db = await get_db()
    try:
        await db.execute(
            "UPDATE users SET settings = ? WHERE id = ?",
            (json.dumps(settings, ensure_ascii=False), user_id)
        )
        await db.commit()
        return True
    finally:
        await db.close()


async def get_user_settings(user_id: int) -> dict:
    """获取用户设置"""
    import json
    db = await get_db()
    try:
        cursor = await db.execute("SELECT settings FROM users WHERE id = ?", (user_id,))
        row = await cursor.fetchone()
        if row and row['settings']:
            return json.loads(row['settings'])
        return {}
    finally:
        await db.close()


# ── 自选股操作（带用户隔离）──

async def add_watchlist(stock_code: str, stock_name: str, market: str = "", user_id: int = 0) -> bool:
    """添加自选股"""
    db = await get_db()
    try:
        await db.execute(
            "INSERT OR IGNORE INTO watchlist (user_id, stock_code, stock_name, market, added_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, stock_code, stock_name, market, datetime.now().isoformat())
        )
        await db.commit()
        return True
    finally:
        await db.close()


async def remove_watchlist(stock_code: str, user_id: int = 0) -> bool:
    """删除自选股"""
    db = await get_db()
    try:
        cursor = await db.execute(
            "DELETE FROM watchlist WHERE stock_code = ? AND user_id = ?",
            (stock_code, user_id)
        )
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


async def get_watchlist(user_id: int = 0) -> list[dict]:
    """获取自选股列表"""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM watchlist WHERE user_id = ? ORDER BY added_at DESC",
            (user_id,)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()


# ── 事件操作（带用户隔离）──

async def add_event(stock_code: str, event_type: str, title: str, detail: str,
                    ai_analysis: str = "", severity: str = "info", user_id: int = 0) -> int:
    """保存事件到数据库"""
    db = await get_db()
    try:
        cursor = await db.execute(
            "INSERT INTO events (user_id, stock_code, event_type, title, detail, ai_analysis, severity, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id, stock_code, event_type, title, detail, ai_analysis, severity, datetime.now().isoformat())
        )
        await db.commit()
        return cursor.lastrowid
    finally:
        await db.close()


async def get_events(stock_code: str = None, limit: int = 50, user_id: int = 0) -> list[dict]:
    """查询事件"""
    db = await get_db()
    try:
        if stock_code:
            cursor = await db.execute(
                "SELECT * FROM events WHERE stock_code = ? AND user_id = ? ORDER BY created_at DESC LIMIT ?",
                (stock_code, user_id, limit)
            )
        else:
            cursor = await db.execute(
                "SELECT * FROM events WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
                (user_id, limit)
            )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()


async def get_today_events_count(user_id: int = 0) -> int:
    """获取今日事件数"""
    db = await get_db()
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        cursor = await db.execute(
            "SELECT COUNT(*) FROM events WHERE created_at LIKE ? AND user_id = ?",
            (f"{today}%", user_id)
        )
        row = await cursor.fetchone()
        return row[0]
    finally:
        await db.close()


async def toggle_alert(stock_code: str, enabled: bool, user_id: int = 0) -> bool:
    """切换自选股告警开关"""
    db = await get_db()
    try:
        cursor = await db.execute(
            "UPDATE watchlist SET alert_enabled = ? WHERE stock_code = ? AND user_id = ?",
            (1 if enabled else 0, stock_code, user_id)
        )
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()
