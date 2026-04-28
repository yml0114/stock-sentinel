"""
FastAPI 路由 — 对外API统一用camelCase，匹配Flutter前端
v3: 多市场支持(A股/港股/美股) + 专业K线
"""
import json
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from pydantic import BaseModel

from app.database import (
    add_watchlist, remove_watchlist, get_watchlist,
    get_events, get_today_events_count,
)
from app.data.stock_data import (
    get_batch_quotes, get_realtime_quote, search_stocks, get_kline_data, detect_market,
)
from app.data.news_intel import fetch_all_news, fetch_all_raw
from app.data.research_intel import (
    get_stock_reports, get_analyst_ranking, get_stock_comment,
    get_stock_full_profile, format_profile_for_ai,
)
from app.analysis.ai_analyzer import get_ai_call_count
from app.analysis.indicators import generate_signals
from app.analysis.diagnose import diagnose_stock
from app.engine.pusher import ws_clients, broadcast_ws

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


# ── 字段转换工具 ──

def _watchlist_to_api(row: dict) -> dict:
    return {
        "code": row.get("stock_code", ""),
        "name": row.get("stock_name", ""),
        "market": row.get("market", ""),
        "addedAt": row.get("added_at", ""),
        "alertEnabled": bool(row.get("alert_enabled", 1)),
    }


def _event_to_api(row: dict) -> dict:
    return {
        "id": row.get("id", 0),
        "code": row.get("stock_code", ""),
        "type": row.get("event_type", ""),
        "title": row.get("title", ""),
        "detail": row.get("detail", ""),
        "aiAnalysis": row.get("ai_analysis", ""),
        "severity": row.get("severity", "info"),
        "createdAt": row.get("created_at", ""),
    }


def _quote_to_api(q: dict) -> dict:
    return {
        "code": q.get("code", q.get("stock_code", "")),
        "name": q.get("name", q.get("stock_name", "")),
        "market": q.get("market", ""),
        "price": q.get("price", 0),
        "changePct": q.get("change_pct", 0),
        "changeAmt": q.get("change_amt", 0),
        "volume": q.get("volume", 0),
        "amount": q.get("amount", 0),
        "high": q.get("high", 0),
        "low": q.get("low", 0),
        "open": q.get("open", 0),
        "prevClose": q.get("prev_close", 0),
        "turnover": q.get("turnover", 0),
        "amplitude": q.get("amplitude", 0),
        "peRatio": q.get("pe_ratio", 0),
        "marketCap": q.get("market_cap", 0),
        "timestamp": q.get("timestamp", ""),
    }


# ── 请求模型 ──

class WatchlistAdd(BaseModel):
    code: str
    name: str = ""
    market: str = ""


# ── 自选股管理 ──

@router.get("/watchlist")
async def api_get_watchlist():
    items = await get_watchlist()
    return {"code": 0, "data": [_watchlist_to_api(i) for i in items]}


@router.post("/watchlist")
async def api_add_watchlist(body: WatchlistAdd):
    name = body.name
    market = body.market
    if not market:
        market = detect_market(body.code)
    if not name:
        quote = get_realtime_quote(body.code, market=market)
        name = quote.get("stock_name", body.code) if quote else body.code
    await add_watchlist(body.code, name, market=market)
    return {"code": 0, "data": {"code": body.code, "name": name, "market": market}}


@router.delete("/watchlist/{code}")
async def api_remove_watchlist(code: str):
    ok = await remove_watchlist(code)
    if ok:
        return {"code": 0, "message": f"已删除 {code}"}
    return {"code": 404, "message": f"未找到 {code}"}


# ── 股票搜索 ──

@router.get("/search")
async def api_search_stocks(q: str = Query("", min_length=1), limit: int = Query(20, ge=1, le=100)):
    """股票模糊搜索 — A股/港股/美股"""
    results = search_stocks(q, limit=limit)
    return {"code": 0, "data": results}


# ── K线数据 ──

@router.get("/kline/{stock_code}")
async def api_get_kline(stock_code: str, period: str = Query("daily"), days: int = Query(120, ge=5, le=1000), market: str = Query("")):
    """获取K线历史数据 — 自动识别市场选择数据源"""
    data = get_kline_data(stock_code, period=period, days=days, market=market)
    return {"code": 0, "data": data}
# ── 技术指标 ──

@router.get("/indicators/{stock_code}")
async def api_get_indicators(stock_code: str, period: str = Query("daily"), days: int = Query(120, ge=10, le=1000), market: str = Query("")):
    """获取技术指标(MA/RSI/MACD/KDJ/BOLL) + 信号"""
    data = get_kline_data(stock_code, period=period, days=days, market=market)
    if not data:
        return {"code": 0, "data": {"signals": [], "patterns": [], "score": 50, "summary": "数据不足"}}
    result = generate_signals(data)
    return {"code": 0, "data": {
        "signals": result["signals"],
        "patterns": result["patterns"],
        "score": result["score"],
        "summary": result["summary"],
        "latest": result["latest"],
    }}


# ── AI诊断 ──

@router.get("/diagnose/{stock_code}")
async def api_diagnose_stock(stock_code: str, market: str = Query(""), period: str = Query("daily"), days: int = Query(120)):
    """AI综合诊断 — 技术指标+K线形态+DeepSeek分析"""
    m = market or detect_market(stock_code)
    kline_data = get_kline_data(stock_code, period=period, days=days, market=m)
    result = diagnose_stock(stock_code, stock_code, m, kline_data)
    return {"code": 0, "data": result}


# ── 行情 ──

@router.get("/quotes")
async def api_get_quotes():
    watchlist = await get_watchlist()
    if not watchlist:
        return {"code": 0, "data": []}
    stock_codes = [w["stock_code"] for w in watchlist]
    market_map = {w["stock_code"]: w.get("market", "") for w in watchlist}
    quotes = get_batch_quotes(stock_codes, market_map=market_map)
    name_map = {w["stock_code"]: w["stock_name"] for w in watchlist}
    for q in quotes:
        if not q.get("stock_name") or q.get("stock_name") == "未知":
            q["stock_name"] = name_map.get(q.get("stock_code", ""), "")
    return {"code": 0, "data": [_quote_to_api(q) for q in quotes]}


# ── 事件 ──

@router.get("/events")
async def api_get_events(
    code: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
):
    events = await get_events(stock_code=code, limit=limit)
    return {"code": 0, "data": [_event_to_api(e) for e in events]}


# ── 全球新闻（过滤后）──

# 新闻缓存（避免每次请求都抓14+秒）
import time as _time
_news_cache = {'data': None, 'ts': 0, 'raw': None, 'raw_ts': 0}
_CACHE_TTL = 180  # 3分钟缓存


@router.get("/news")
async def api_get_news(limit: int = Query(50, ge=1, le=200)):
    events = await get_events(stock_code="GLOBAL", limit=limit)
    return {"code": 0, "data": [_event_to_api(e) for e in events]}


# ── 全球新闻流（原始，含全部12源，带缓存）──

def _format_news_item(item):
    entry = {
        "source": item.get("source", ""),
        "sourceType": item.get("source_type", ""),
        "title": item.get("title", ""),
        "content": item.get("content", "")[:800],
        "time": item.get("time", ""),
        "url": item.get("url", ""),
    }
    # 同时输出两种字段名，兼容前端
    if item.get("title_en"):
        entry["title_en"] = item["title_en"]
        entry["titleEn"] = item["title_en"]
    if item.get("content_en"):
        entry["content_en"] = item["content_en"][:800]
        entry["contentEn"] = item["content_en"][:800]
    return entry


@router.get("/news/raw")
async def api_get_news_raw(limit: int = Query(80, ge=1, le=500)):
    """获取全部新闻源原始数据（带3分钟缓存）"""
    now = _time.time()
    if _news_cache['raw'] and now - _news_cache['raw_ts'] < _CACHE_TTL:
        return {"code": 0, "data": _news_cache['raw'][:limit]}
    # 缓存过期，重新抓取
    items = fetch_all_raw()
    result = [_format_news_item(item) for item in items]
    _news_cache['raw'] = result
    _news_cache['raw_ts'] = now
    return {"code": 0, "data": result[:limit]}


# ── 全球新闻（智能去重+过滤后）──

@router.get("/news/filtered")
async def api_get_news_filtered():
    """获取智能去重+关键词过滤后的新闻（带3分钟缓存）"""
    now = _time.time()
    if _news_cache['data'] and now - _news_cache['ts'] < _CACHE_TTL:
        return {"code": 0, "data": _news_cache['data']}
    filtered = fetch_all_news()
    result = []
    for item in filtered[:100]:
        entry = _format_news_item(item)
        entry["matchedKeywords"] = item.get("matched_keywords", [])
        entry["relatedSectors"] = item.get("related_sectors", [])
        entry["severity"] = item.get("severity", "info")
        result.append(entry)
    _news_cache['data'] = result
    _news_cache['ts'] = now
    return {"code": 0, "data": result}


# ── 文章正文抓取 ──

@router.get("/article")
async def api_get_article(url: str = Query(...), translate: bool = Query(True)):
    """从URL抓取文章正文，自动翻译成中文（translate=false返回原文）"""
    from app.data.article_fetcher import extract_article
    from app.data.translator import translate_to_zh
    import asyncio
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, extract_article, url)
    
    # 保留英文原文，同时提供中文翻译
    content_en = result.get('content', '')
    title_en = result.get('title', '')
    
    if translate and content_en:
        # 检测是否为非中文内容，翻译
        import re as _re
        chinese_chars = len(_re.findall(r'[\u4e00-\u9fff]', content_en))
        is_chinese = chinese_chars / max(len(content_en), 1) > 0.3
        
        if not is_chinese:
            result['content_zh'] = await loop.run_in_executor(None, translate_to_zh, content_en)
            result['title_zh'] = await loop.run_in_executor(None, translate_to_zh, title_en)
            result['content'] = result['content_zh']
            result['title'] = result['title_zh']
            result['content_en'] = content_en
            result['title_en'] = title_en
            result['isTranslated'] = True
        else:
            result['isTranslated'] = False
    else:
        result['isTranslated'] = False
    
    return {"code": 0, "data": result}


# ── 系统状态 ──

@router.get("/status")
async def api_get_status():
    watchlist = await get_watchlist()
    today_count = await get_today_events_count()
    return {
        "code": 0,
        "data": {
            "watchlistCount": len(watchlist),
            "todayEvents": today_count,
            "aiCalls": get_ai_call_count(),
            "wsClients": len(ws_clients),
            "time": datetime.now().isoformat(),
        },
    }


# ══════════════════════════════════════════════
# v2: 研报/分析师/机构数据接口
# ══════════════════════════════════════════════

# ── 个股研报 ──

@router.get("/research/{stock_code}")
async def api_get_research(stock_code: str, limit: int = Query(10, ge=1, le=50)):
    """获取个股券商研报（评级、盈利预测、PDF链接）"""
    data = get_stock_reports(stock_code, limit=limit)
    return {"code": 0, "data": data}


# ── 个股完整画像 ──

@router.get("/profile/{stock_code}")
async def api_get_profile(stock_code: str, price: float = Query(0)):
    """获取个股完整画像（研报+评级+机构+千股千评+目标价推算）"""
    profile = get_stock_full_profile(stock_code, current_price=price)
    return {"code": 0, "data": profile}


# ── 个股画像AI分析 ──

@router.get("/profile/{stock_code}/ai")
async def api_get_profile_ai(stock_code: str, price: float = Query(0)):
    """获取个股画像的AI综合研判"""
    from app.analysis.ai_analyzer import analyze_profile

    profile = get_stock_full_profile(stock_code, current_price=price)
    ai_result = analyze_profile(profile)
    return {"code": 0, "data": {"analysis": ai_result, "profile": profile}}


# ── 分析师排行 ──

@router.get("/analysts")
async def api_get_analysts(limit: int = Query(20, ge=1, le=100)):
    """获取分析师排行"""
    analysts = get_analyst_ranking(limit=limit)
    return {"code": 0, "data": analysts}


# ── 千股千评 ──

@router.get("/comment/{stock_code}")
async def api_get_comment(stock_code: str):
    """获取个股千股千评（机构参与度、综合得分、主力成本）"""
    comment = get_stock_comment(stock_code)
    return {"code": 0, "data": comment}


# ── WebSocket 实时推送 ──

@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    ws_clients.append(ws)
    logger.info(f"WebSocket 客户端连接，当前 {len(ws_clients)} 个")
    await ws.send_text(json.dumps({
        "type": "connected",
        "message": "Stock Sentinel 已连接",
        "time": datetime.now().isoformat(),
    }, ensure_ascii=False))
    try:
        while True:
            data = await ws.receive_text()
            if data == "ping":
                await ws.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        if ws in ws_clients:
            ws_clients.remove(ws)
        logger.info(f"WebSocket 客户端断开，剩余 {len(ws_clients)} 个")
