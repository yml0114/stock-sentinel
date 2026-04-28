# Stock Sentinel（AI盯盘哨兵）实施计划

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** 一个手机APP，用户添加自选股后，AI自动盯盘+监控重大事件，异常时推送AI研判报告到手机。

**Architecture:** Python FastAPI 后端（数据采集 + 规则引擎 + AI分析）+ Flutter 手机端（自选股管理 + 行情展示 + 推送接收）+ ntfy.sh 推送通道

**Tech Stack:**
- 后端: Python 3.11, FastAPI, AKShare, SQLite, APScheduler, OpenAI SDK
- AI: DeepSeek (via tokex.top API, OpenAI兼容协议)
- 推送: ntfy.sh (免费, 手机装APP即可)
- 前端: Flutter 3.x, dio, web_socket_channel
- 数据库: SQLite (自选股 + 事件历史)

---

## 全球新闻情报层（核心差异化能力）

### 数据源（全部免费，AKShare封装，已验证可用）

| 数据源 | AKShare接口 | 更新频率 | 覆盖范围 |
|--------|------------|---------|---------|
| 财联社全球快讯 | `stock_info_global_cls()` | 实时 | A股/政策/宏观，含标题+全文 |
| 东方财富全球快讯 | `stock_info_global_em()` | 实时 | 全球市场，含链接 |
| 东方财富个股新闻 | `stock_news_em(symbol)` | 按需 | 个股关联新闻，含来源 |
| 百度经济日历 | `news_economic_baidu()` | 每日 | 全球宏观经济事件，含重要性评级 |

### 两层过滤策略（控制AI成本）

```
第1层：关键词过滤（免费，毫秒级）
  ├─ 高影响词库：降息/加息/制裁/暴跌/关税/战争/退市/GDP/CPI/PMI...
  └─ 板块关联词库：AI/芯片/新能源/医药/稀土...→ 自动映射概念股

第2层：AI影响评估（仅对第1层命中新闻，~500 tokens/条）
  └─ 综合研判："对A股哪些板块/个股有什么影响？利好还是利空？"
```

### 成本估算
一次轮询抓取约50-100条新闻 → 关键词过滤后约5-10条 → AI评估约3-5条
每天AI调用约30-50次，成本 < ¥0.5

---

## Phase 1: 后端基础 (Tasks 1-7)

### Task 1: 项目骨架 + 依赖

**Objective:** 创建 stock-sentinel 后端项目结构

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/main.py`
- Create: `backend/config.py`
- Create: `backend/database.py`

**Step 1: 创建项目结构**
```bash
mkdir -p backend/app/{data,engine,analysis,api}
mkdir -p backend/app/data backend/app/engine backend/app/analysis backend/app/api
```

**Step 2: requirements.txt**
```
fastapi==0.115.0
uvicorn[standard]==0.30.0
akshare>=1.16.98
openai>=1.0.0
apscheduler==3.10.4
pydantic>=2.0.0
python-dotenv>=1.0.0
aiosqlite>=0.20.0
httpx>=0.27.0
```

**Step 3: config.py — 环境变量配置**
```python
import os
from dotenv import load_dotenv

load_dotenv()

# AI模型配置（兼容任何OpenAI协议API）
AI_API_KEY = os.getenv("AI_API_KEY", "")
AI_API_URL = os.getenv("AI_API_URL", "https://api.tokex.top/v1")
AI_MODEL = os.getenv("AI_MODEL", "deepseek-ai/deepseek-v4-pro")

# 推送配置
NTFY_TOPIC = os.getenv("NTFY_TOPIC", "stock-sentinel-demo")
NTFY_SERVER = os.getenv("NTFY_SERVER", "https://ntfy.sh")

# 数据库
DB_PATH = os.getenv("DB_PATH", "data/stock_sentinel.db")

# 轮询间隔（秒）
POLL_REALTIME = 30       # 实时行情
POLL_ANNOUNCEMENT = 300  # 公告（5分钟）
POLL_NEWS = 600          # 新闻（10分钟）
POLL_NORTHBOUND = 60     # 北向资金（1分钟）

# 触发阈值
THRESHOLD_PRICE_CHANGE = 3.0     # 涨跌幅 > 3%
THRESHOLD_VOLUME_RATIO = 3.0     # 成交量放大 > 3倍
THRESHOLD_NORTHBOUND_NET = 5.0   # 北向净买入 > 5亿
```

**Step 4: main.py — FastAPI入口**
```python
from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.api.routes import router
from app.engine.scheduler import start_scheduler
from database import init_db

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    start_scheduler()
    yield

app = FastAPI(title="Stock Sentinel", lifespan=lifespan)
app.include_router(router)

@app.get("/health")
async def health():
    return {"status": "ok"}
```

**Step 5: database.py — SQLite初始化**
```python
import aiosqlite
from config import DB_PATH

async def get_db():
    async with aiosqlite.connect(DB_PATH) as db:
        yield db

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS watchlist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stock_code TEXT NOT NULL UNIQUE,
                stock_name TEXT NOT NULL,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                alert_enabled INTEGER DEFAULT 1
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stock_code TEXT NOT NULL,
                event_type TEXT NOT NULL,
                title TEXT NOT NULL,
                detail TEXT,
                ai_analysis TEXT,
                severity TEXT DEFAULT 'info',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()
```

**Verify:** `cd backend && python -c "from config import *; print('OK')"`

---

### Task 2: 数据采集层 — AKShare实时行情

**Objective:** 封装AKShare获取A股实时行情的函数

**Files:**
- Create: `backend/app/data/stock_data.py`

```python
"""AKShare数据采集层 — 行情/公告/资金流"""
import akshare as ak
import pandas as pd
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def get_realtime_quote(stock_code: str) -> dict:
    """获取单只股票实时行情"""
    try:
        df = ak.stock_zh_a_spot_em()
        row = df[df['代码'] == stock_code]
        if row.empty:
            return None
        r = row.iloc[0]
        return {
            'code': stock_code,
            'name': r['名称'],
            'price': float(r['最新价']),
            'change_pct': float(r['涨跌幅']),
            'change_amt': float(r['涨跌额']),
            'volume': float(r['成交量']),
            'amount': float(r['成交额']),
            'high': float(r['最高']),
            'low': float(r['最低']),
            'open': float(r['今开']),
            'prev_close': float(r['昨收']),
            'turnover': float(r['换手率']),
            'pe_ratio': float(r.get('市盈率-动态', 0)),
            'timestamp': datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"获取行情失败 {stock_code}: {e}")
        return None


def get_batch_quotes(stock_codes: list[str]) -> list[dict]:
    """批量获取行情（一次API调用取全部，省请求）"""
    try:
        df = ak.stock_zh_a_spot_em()
        results = []
        for code in stock_codes:
            row = df[df['代码'] == code]
            if row.empty:
                continue
            r = row.iloc[0]
            results.append({
                'code': code,
                'name': r['名称'],
                'price': float(r['最新价']),
                'change_pct': float(r['涨跌幅']),
                'volume': float(r['成交量']),
                'amount': float(r['成交额']),
                'high': float(r['最高']),
                'low': float(r['最低']),
                'turnover': float(r['换手率']),
                'timestamp': datetime.now().isoformat(),
            })
        return results
    except Exception as e:
        logger.error(f"批量获取行情失败: {e}")
        return []


def get_stock_announcements(stock_code: str, days: int = 1) -> list[dict]:
    """获取最新公告"""
    try:
        df = ak.stock_notice_report(symbol=stock_code)
        if df is None or df.empty:
            return []
        results = []
        for _, row in df.head(10).iterrows():
            results.append({
                'code': stock_code,
                'title': str(row.get('公告标题', '')),
                'date': str(row.get('公告日期', '')),
                'type': str(row.get('公告类型', '')),
                'url': str(row.get('公告链接', '')),
            })
        return results
    except Exception as e:
        logger.error(f"获取公告失败 {stock_code}: {e}")
        return []


def get_northbound_flow() -> dict:
    """获取北向资金净流入"""
    try:
        df = ak.stock_hsgt_north_net_flow_in_em()
        if df is None or df.empty:
            return {}
        latest = df.iloc[-1]
        return {
            'date': str(latest.get('date', latest.index[-1])),
            'net_flow': float(latest.iloc[-1]),  # 单位：亿
        }
    except Exception as e:
        logger.error(f"获取北向资金失败: {e}")
        return {}
```

**Verify:** `cd backend && python -c "from app.data.stock_data import get_batch_quotes; print(get_batch_quotes(['600519']))"`

---

### Task 3: 事件检测引擎 — 规则触发器

**Objective:** 不用LLM，纯规则检测异常事件

**Files:**
- Create: `backend/app/engine/detector.py`

```python
"""事件检测引擎 — 纯规则，零token消耗"""
import logging
from config import (
    THRESHOLD_PRICE_CHANGE,
    THRESHOLD_VOLUME_RATIO,
    THRESHOLD_NORTHBOUND_NET,
)

logger = logging.getLogger(__name__)

# 内存缓存：上一轮行情快照
_prev_quotes: dict[str, dict] = {}
_prev_announcements: dict[str, set] = {}


def detect_price_alert(current: dict) -> dict | None:
    """检测价格异动（涨跌幅超阈值）"""
    change = abs(current.get('change_pct', 0))
    if change >= THRESHOLD_PRICE_CHANGE:
        direction = "📈 急涨" if current['change_pct'] > 0 else "📉 急跌"
        return {
            'type': 'price_alert',
            'code': current['code'],
            'name': current['name'],
            'title': f"{direction} {current['name']}({current['code']}) {current['change_pct']:+.2f}%",
            'detail': f"现价 {current['price']}，涨跌幅 {current['change_pct']:+.2f}%，"
                      f"成交额 {current['amount']/1e8:.2f}亿，换手率 {current['turnover']:.2f}%",
            'severity': 'high' if change >= 5 else 'medium',
        }
    return None


def detect_volume_spike(current: dict) -> dict | None:
    """检测成交量异常放大"""
    prev = _prev_quotes.get(current['code'])
    if prev and prev.get('volume', 0) > 0:
        ratio = current['volume'] / prev['volume']
        if ratio >= THRESHOLD_VOLUME_RATIO:
            return {
                'type': 'volume_spike',
                'code': current['code'],
                'name': current['name'],
                'title': f"🔊 放量 {current['name']}({current['code']}) 成交量放大 {ratio:.1f}倍",
                'detail': f"当前成交量 {current['volume']/1e4:.0f}万手，前期 {prev['volume']/1e4:.0f}万手",
                'severity': 'medium',
            }
    return None


def detect_new_announcement(stock_code: str, announcements: list[dict]) -> list[dict]:
    """检测新公告"""
    global _prev_announcements
    prev_set = _prev_announcements.get(stock_code, set())
    current_set = {a['title'] for a in announcements}
    new_titles = current_set - prev_set
    _prev_announcements[stock_code] = current_set

    events = []
    for ann in announcements:
        if ann['title'] in new_titles:
            # 敏感关键词 → 高优先级
            keywords_high = ['减持', '处罚', 'ST', '退市', '亏损', '暴跌', '立案']
            keywords_mid = ['增持', '回购', '分红', '业绩', '财报', '重组', '收购']
            severity = 'info'
            for kw in keywords_high:
                if kw in ann['title']:
                    severity = 'high'
                    break
            if severity == 'info':
                for kw in keywords_mid:
                    if kw in ann['title']:
                        severity = 'medium'
                        break

            events.append({
                'type': 'announcement',
                'code': stock_code,
                'name': '',
                'title': f"📋 新公告 [{stock_code}] {ann['title']}",
                'detail': f"日期: {ann['date']}，类型: {ann['type']}",
                'severity': severity,
            })
    return events


def update_quote_cache(quotes: list[dict]):
    """更新行情缓存"""
    global _prev_quotes
    for q in quotes:
        _prev_quotes[q['code']] = q


def run_detection(quotes: list[dict], announcements_map: dict[str, list]) -> list[dict]:
    """运行所有检测规则，返回触发的事件列表"""
    events = []

    for q in quotes:
        ev = detect_price_alert(q)
        if ev:
            events.append(ev)

        ev = detect_volume_spike(q)
        if ev:
            events.append(ev)

    for code, anns in announcements_map.items():
        new_events = detect_new_announcement(code, anns)
        events.extend(new_events)

    # 更新缓存
    update_quote_cache(quotes)

    return events
```

---

### Task 4: AI分析引擎

**Objective:** 事件触发后调用LLM生成研判报告

**Files:**
- Create: `backend/app/analysis/ai_analyzer.py`

```python
"""AI分析引擎 — 仅在事件触发时调用，控制成本"""
import logging
from openai import OpenAI
from config import AI_API_KEY, AI_API_URL, AI_MODEL

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是一个专业的A股投资分析助手。当收到股票异常事件时，请：
1. 分析可能的原因（结合行情数据、公告、行业背景）
2. 评估对股价的短期影响（利好/利空/中性）
3. 给出操作建议（关注/加仓/减仓/观望）
4. 提示风险点

要求：简洁专业，100-200字。不要编造数据。"""


def get_client():
    if not AI_API_KEY:
        return None
    return OpenAI(api_key=AI_API_KEY, base_url=AI_API_URL, timeout=30.0)


def analyze_event(event: dict, quote: dict | None = None) -> str:
    """对事件进行AI分析，返回研判文本"""
    client = get_client()
    if not client:
        return "⚠️ AI分析未配置（缺少AI_API_KEY）"

    # 构造上下文
    context = f"事件类型: {event['type']}\n标题: {event['title']}\n详情: {event['detail']}"
    if quote:
        context += f"\n当前行情: 价格{quote.get('price','-')} 涨跌{quote.get('change_pct','-')}% "
        context += f"成交额{quote.get('amount',0)/1e8:.2f}亿 换手率{quote.get('turnover','-')}%"

    try:
        resp = client.chat.completions.create(
            model=AI_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": context},
            ],
            temperature=0.5,
            max_tokens=500,
        )
        return resp.choices[0].message.content
    except Exception as e:
        logger.error(f"AI分析失败: {e}")
        return f"⚠️ AI分析暂不可用: {str(e)}"
```

---

### Task 5: 推送服务

**Objective:** 通过 ntfy.sh 推送事件到手机

**Files:**
- Create: `backend/app/engine/pusher.py`

```python
"""推送服务 — ntfy.sh 免费推送 + 本地WebSocket"""
import httpx
import json
import logging
from config import NTFY_SERVER, NTFY_TOPIC

logger = logging.getLogger(__name__)

# WebSocket连接管理（给Flutter端用）
ws_clients: list = []


async def push_ntfy(event: dict, ai_analysis: str = ""):
    """推送到 ntfy.sh"""
    severity_emoji = {
        'high': '🚨',
        'medium': '⚠️',
        'info': 'ℹ️',
    }
    emoji = severity_emoji.get(event.get('severity', 'info'), '📢')
    title = f"{emoji} {event['title']}"
    body = event['detail']
    if ai_analysis:
        body += f"\n\n🤖 AI研判:\n{ai_analysis}"

    # ntfy tags 用于手机端分类和声音
    tags = "chart_with_upwards_trend" if event.get('severity') == 'high' else "bar_chart"
    priority = "high" if event.get('severity') == 'high' else "default"

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{NTFY_SERVER}/{NTFY_TOPIC}",
                content=body.encode('utf-8'),
                headers={
                    "Title": title.encode('utf-8').decode('utf-8'),
                    "Tags": tags,
                    "Priority": priority,
                    "Content-Type": "text/plain; charset=utf-8",
                },
                timeout=10.0,
            )
            if resp.status_code == 200:
                logger.info(f"✅ 推送成功: {title}")
            else:
                logger.error(f"❌ 推送失败: {resp.status_code}")
    except Exception as e:
        logger.error(f"❌ 推送异常: {e}")


async def broadcast_ws(event: dict, ai_analysis: str = ""):
    """广播到所有WebSocket客户端（Flutter实时连接）"""
    from fastapi import WebSocket
    message = json.dumps({
        "event": event,
        "ai_analysis": ai_analysis,
    }, ensure_ascii=False)
    disconnected = []
    for ws in ws_clients:
        try:
            await ws.send_text(message)
        except Exception:
            disconnected.append(ws)
    for ws in disconnected:
        ws_clients.remove(ws)
```

---

### Task 6: 定时调度器 + API路由

**Objective:** 把所有组件串起来：定时轮询 → 检测 → AI分析 → 推送

**Files:**
- Create: `backend/app/engine/scheduler.py`
- Create: `backend/app/api/routes.py`

**scheduler.py:**
```python
"""APScheduler 定时任务"""
import asyncio
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from app.data.stock_data import get_batch_quotes, get_stock_announcements
from app.engine.detector import run_detection
from app.analysis.ai_analyzer import analyze_event
from app.engine.pusher import push_ntfy, broadcast_ws
from config import POLL_REALTIME, POLL_ANNOUNCEMENT

logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler()


def get_watchlist_sync() -> list[str]:
    """同步获取自选股列表"""
    import sqlite3
    from config import DB_PATH
    try:
        conn = sqlite3.connect(DB_PATH)
        codes = [r[0] for r in conn.execute(
            "SELECT stock_code FROM watchlist WHERE alert_enabled=1"
        ).fetchall()]
        conn.close()
        return codes
    except Exception:
        return []


def poll_realtime():
    """实时行情轮询 + 检测"""
    codes = get_watchlist_sync()
    if not codes:
        return

    quotes = get_batch_quotes(codes)
    if not quotes:
        return

    # 公告检测（每5轮跑一次，即每2.5分钟）
    announcements_map = {}
    if not hasattr(poll_realtime, '_counter'):
        poll_realtime._counter = 0
    poll_realtime._counter += 1
    if poll_realtime._counter % 5 == 0:
        for code in codes:
            try:
                anns = get_stock_announcements(code)
                announcements_map[code] = anns
            except Exception:
                pass

    # 运行检测
    events = run_detection(quotes, announcements_map)

    # 对触发的事件做AI分析 + 推送
    for event in events:
        quote = next((q for q in quotes if q['code'] == event['code']), None)
        try:
            ai_text = analyze_event(event, quote)
        except Exception:
            ai_text = ""

        # 推送（同步包装异步调用）
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(push_ntfy(event, ai_text))
            loop.run_until_complete(broadcast_ws(event, ai_text))
        finally:
            loop.close()

        # 存储事件到数据库
        _save_event(event, ai_text)

    logger.info(f"📊 轮询完成: {len(codes)}只股, {len(events)}个事件触发")


def _save_event(event: dict, ai_text: str):
    import sqlite3
    from config import DB_PATH
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            "INSERT INTO events (stock_code, event_type, title, detail, ai_analysis, severity) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (event['code'], event['type'], event['title'], event['detail'], ai_text, event['severity'])
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"保存事件失败: {e}")


def start_scheduler():
    scheduler.add_job(poll_realtime, 'interval', seconds=POLL_REALTIME, id='poll_realtime')
    scheduler.start()
    logger.info(f"⏰ 调度器启动: 行情每{POLL_REALTIME}秒轮询")
```

**routes.py — API路由:**
```python
"""FastAPI路由 — 自选股CRUD + 事件查询 + WebSocket"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from pydantic import BaseModel
import aiosqlite
from config import DB_PATH
from app.engine.pusher import ws_clients

router = APIRouter(prefix="/api")


class StockAdd(BaseModel):
    stock_code: str
    stock_name: str = ""


# ── 自选股管理 ──

@router.get("/watchlist")
async def list_watchlist():
    async with aiosqlite.connect(DB_PATH) as db:
        rows = await db.execute_fetchall(
            "SELECT id, stock_code, stock_name, added_at, alert_enabled FROM watchlist ORDER BY id"
        )
        return [{"id": r[0], "code": r[1], "name": r[2], "added_at": r[3], "alert_enabled": r[4]} for r in rows]


@router.post("/watchlist")
async def add_stock(item: StockAdd):
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            # 如果没传名字，从AKShare查
            name = item.stock_name
            if not name:
                from app.data.stock_data import get_realtime_quote
                quote = get_realtime_quote(item.stock_code)
                name = quote['name'] if quote else item.stock_code

            await db.execute(
                "INSERT OR IGNORE INTO watchlist (stock_code, stock_name) VALUES (?, ?)",
                (item.stock_code, name)
            )
            await db.commit()
            return {"ok": True, "code": item.stock_code, "name": name}
        except Exception as e:
            return {"ok": False, "error": str(e)}


@router.delete("/watchlist/{stock_code}")
async def remove_stock(stock_code: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM watchlist WHERE stock_code=?", (stock_code,))
        await db.commit()
        return {"ok": True}


# ── 事件查询 ──

@router.get("/events")
async def list_events(stock_code: str = None, limit: int = Query(default=50, le=200)):
    async with aiosqlite.connect(DB_PATH) as db:
        if stock_code:
            rows = await db.execute_fetchall(
                "SELECT id, stock_code, event_type, title, detail, ai_analysis, severity, created_at "
                "FROM events WHERE stock_code=? ORDER BY id DESC LIMIT ?",
                (stock_code, limit)
            )
        else:
            rows = await db.execute_fetchall(
                "SELECT id, stock_code, event_type, title, detail, ai_analysis, severity, created_at "
                "FROM events ORDER BY id DESC LIMIT ?",
                (limit,)
            )
        return [
            {"id": r[0], "code": r[1], "type": r[2], "title": r[3], "detail": r[4],
             "ai_analysis": r[5], "severity": r[6], "created_at": r[7]}
            for r in rows
        ]


# ── 实时行情查询 ──

@router.get("/quotes")
async def get_quotes():
    from app.data.stock_data import get_batch_quotes
    async with aiosqlite.connect(DB_PATH) as db:
        rows = await db.execute_fetchall("SELECT stock_code FROM watchlist")
        codes = [r[0] for r in rows]
    quotes = get_batch_quotes(codes)
    return quotes


# ── WebSocket 实时推送 ──

@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    ws_clients.append(ws)
    try:
        while True:
            await ws.receive_text()  # 保持连接
    except WebSocketDisconnect:
        ws_clients.remove(ws)
```

---

## Phase 2: Flutter手机端 (Tasks 7-12)

### Task 7: Flutter项目初始化

**Objective:** 创建Flutter项目骨架

```bash
cd /Users/liangliang/workspace/stock-sentinel
flutter create --org com.stocksentinel stock_sentinel_app
cd stock_sentinel_app
flutter pub add dio web_socket_channel flutter_local_notifications provider
```

---

### Task 8: 自选股页面

**Objective:** 展示自选股列表 + 添加/删除

主页面：卡片式列表，每只股显示代码、名称、最新价、涨跌幅（红涨绿跌）

---

### Task 9: 实时行情页

**Objective:** 选择某只股后显示实时行情详情

K线图 + 基本面数据 + 最近事件列表

---

### Task 10: 事件推送页

**Objective:** 展示所有AI研判事件，按时间排序

事件卡片：标题 + AI分析 + 时间 + 严重程度颜色标记

---

### Task 11: 推送通知集成

**Objective:** 手机端接收实时推送

方案：ntfy APP独立推送（零代码）+ WebSocket实时通道（APP内实时）

---

### Task 12: 打包 + 测试

**Objective:** 编译release APK/IPA，真机测试

---

## Phase 3: 上线优化 (Tasks 13-15)

### Task 13: 后端部署到服务器
### Task 14: 推送优化（聚合、静默时段、频率限制）
### Task 15: AI分析优化（多轮上下文、历史学习）

---

## 快速启动命令

```bash
# 后端
cd backend
pip install -r requirements.txt
export AI_API_KEY="your-key"
export AI_API_URL="https://api.tokex.top/v1"
export AI_MODEL="deepseek-ai/deepseek-v4-pro"
python main.py

# 测试添加自选股
curl -X POST http://localhost:8000/api/watchlist \
  -H "Content-Type: application/json" \
  -d '{"stock_code": "600519", "stock_name": "贵州茅台"}'

# 手机装 ntfy APP，订阅 topic: stock-sentinel-demo
```
