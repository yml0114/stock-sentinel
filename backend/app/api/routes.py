"""
FastAPI 路由 — 对外API统一用camelCase，匹配Flutter前端
v4: 手机验证码登录 + 用户数据隔离
"""
import asyncio
import json
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Header, Request
from pydantic import BaseModel

from app.database import (
    add_watchlist, remove_watchlist, get_watchlist,
    get_events, get_today_events_count,
    create_user, get_user_by_phone, update_user_settings, get_user_settings,
)
from app.auth import send_code, verify_code, create_token, verify_token
from app.data.stock_data import (
    get_batch_quotes, get_realtime_quote, search_stocks, get_kline_data, detect_market,
    get_intraday_trend,
)
from app.data.news_intel import fetch_all_news, fetch_all_raw
from app.news_cache import get_raw_news, get_filtered_news, refresh_news_background, cache_stats
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


# ── 认证工具 ──

def _get_user_id(request: Request) -> int:
    """从Authorization header提取user_id，无token返回0（匿名）"""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        payload = verify_token(auth[7:])
        if payload:
            return payload.get("user_id", 0)
    return 0


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


class PhoneLogin(BaseModel):
    phone: str


class CodeVerify(BaseModel):
    phone: str
    code: str


class SettingsUpdate(BaseModel):
    settings: dict


# ══════════════════════════════════════════════
# 认证 API
# ══════════════════════════════════════════════

@router.post("/auth/send-code")
async def api_send_code(body: PhoneLogin):
    """发送手机验证码"""
    result = send_code(body.phone)
    if result["success"]:
        data = {"message": result["message"]}
        if "code" in result:
            data["code"] = result["code"]
        return {"code": 0, "data": data}
    return {"code": 400, "message": result["message"]}


@router.post("/auth/login")
async def api_login(body: CodeVerify):
    """验证码登录（自动注册）"""
    if not verify_code(body.phone, body.code):
        return {"code": 401, "message": "验证码错误或已过期"}

    # 查找或创建用户
    user = await get_user_by_phone(body.phone)
    if not user:
        user = await create_user(body.phone)

    token = create_token(user["id"], body.phone)
    return {
        "code": 0,
        "data": {
            "token": token,
            "user": {
                "id": user["id"],
                "phone": body.phone,
                "nickname": user.get("nickname", f"用户{body.phone[-4:]}"),
            }
        }
    }


@router.get("/auth/me")
async def api_get_me(request: Request):
    """获取当前用户信息"""
    user_id = _get_user_id(request)
    if not user_id:
        return {"code": 401, "message": "未登录"}
    user = await get_user_by_phone("")  # need to look up by id
    # Actually need get_user_by_id, let me use phone from token
    auth = request.headers.get("Authorization", "")
    payload = verify_token(auth[7:]) if auth.startswith("Bearer ") else None
    if payload:
        phone = payload.get("phone", "")
        user = await get_user_by_phone(phone)
        if user:
            settings = await get_user_settings(user_id)
            return {
                "code": 0,
                "data": {
                    "id": user["id"],
                    "phone": phone,
                    "nickname": user.get("nickname", ""),
                    "settings": settings,
                }
            }
    return {"code": 401, "message": "用户不存在"}


@router.post("/auth/settings")
async def api_update_settings(body: SettingsUpdate, request: Request):
    """更新用户设置"""
    user_id = _get_user_id(request)
    if not user_id:
        return {"code": 401, "message": "未登录"}
    await update_user_settings(user_id, body.settings)
    return {"code": 0, "data": {"message": "设置已保存"}}


# ══════════════════════════════════════════════
# 自选股管理（带用户隔离）
# ══════════════════════════════════════════════

@router.get("/watchlist")
async def api_get_watchlist(request: Request):
    user_id = _get_user_id(request)
    items = await get_watchlist(user_id=user_id)
    return {"code": 0, "data": [_watchlist_to_api(i) for i in items]}


@router.post("/watchlist")
async def api_add_watchlist(body: WatchlistAdd, request: Request):
    user_id = _get_user_id(request)
    name = body.name
    market = body.market
    if not market:
        market = detect_market(body.code)
    if not name:
        quote = get_realtime_quote(body.code, market=market)
        name = quote.get("stock_name", body.code) if quote else body.code
    await add_watchlist(body.code, name, market=market, user_id=user_id)
    return {"code": 0, "data": {"code": body.code, "name": name, "market": market}}


@router.delete("/watchlist/{code}")
async def api_remove_watchlist(code: str, request: Request):
    user_id = _get_user_id(request)
    ok = await remove_watchlist(code, user_id=user_id)
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


@router.get("/trend/{stock_code}")
async def api_get_trend(stock_code: str, market: str = Query("")):
    """获取今日分时趋势 + 实时行情 — 用于绘制分时图"""
    data = get_intraday_trend(stock_code, market=market)
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


# ── 行情（带用户隔离）──

@router.get("/quotes")
async def api_get_quotes(request: Request):
    user_id = _get_user_id(request)
    watchlist = await get_watchlist(user_id=user_id)
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


# ── 事件（带用户隔离）──

@router.get("/events")
async def api_get_events(
    request: Request,
    code: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
):
    user_id = _get_user_id(request)
    events = await get_events(stock_code=code, limit=limit, user_id=user_id)
    return {"code": 0, "data": [_event_to_api(e) for e in events]}


# ── 全球新闻（过滤后）──

@router.get("/news")
async def api_get_news(limit: int = Query(50, ge=1, le=200)):
    events = await get_events(stock_code="GLOBAL", limit=limit)
    return {"code": 0, "data": [_event_to_api(e) for e in events]}


# ── 全球新闻流（原始，含全部源，带持久化缓存）──

def _format_news_item(item):
    entry = {
        "source": item.get("source", ""),
        "sourceType": item.get("source_type", ""),
        "title": item.get("title", ""),
        "content": item.get("content", "")[:800],
        "time": item.get("time", ""),
        "url": item.get("url", ""),
    }
    if item.get("title_en"):
        entry["title_en"] = item["title_en"]
        entry["titleEn"] = item["title_en"]
    if item.get("content_en"):
        entry["content_en"] = item["content_en"][:800]
        entry["contentEn"] = item["content_en"][:800]
    return entry


@router.get("/news/raw")
async def api_get_news_raw(limit: int = Query(80, ge=1, le=500)):
    """获取全部新闻源原始数据（持久化缓存，秒返回）"""
    loop = asyncio.get_event_loop()
    items = await loop.run_in_executor(None, get_raw_news, limit)
    result = [_format_news_item(item) for item in items]
    return {"code": 0, "data": result}


# ── 全球新闻（智能去重+过滤后）──

@router.get("/news/filtered")
async def api_get_news_filtered():
    """获取智能去重+关键词过滤后的新闻（持久化缓存）"""
    loop = asyncio.get_event_loop()
    items = await loop.run_in_executor(None, get_filtered_news)
    result = []
    for item in items[:100]:
        entry = _format_news_item(item)
        entry["matchedKeywords"] = item.get("matched_keywords", [])
        entry["relatedSectors"] = item.get("related_sectors", [])
        entry["severity"] = item.get("severity", "info")
        result.append(entry)
    return {"code": 0, "data": result}


# ── 缓存状态（调试用）──

@router.get("/news/cache-stats")
async def api_get_news_cache_stats():
    """查看新闻缓存状态"""
    return {"code": 0, "data": cache_stats()}


# ── 文章正文抓取 ──

@router.get("/article")
async def api_get_article(url: str = Query(...), translate: bool = Query(True)):
    """从URL抓取文章正文，自动翻译成中文（translate=false返回原文）
    缓存同时保存中英文版本，根据 translate 参数返回对应版本"""
    from app.data.article_fetcher import extract_article
    from app.data.translator import translate_to_zh
    from app.data.article_cache import get_article_for_display, cache_article

    # 1. 优先走缓存（中英文版本都有，秒返回）
    cached = get_article_for_display(url, translate=translate)
    if cached:
        logger.debug(f"💾 文章缓存命中: {cached.get('title', '')[:40]}")
        return {"code": 0, "data": cached}

    # 2. 未命中 → 实时抓取
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, extract_article, url)

    if not result.get('success') or not result.get('content'):
        return {"code": 404, "message": "文章抓取失败", "data": result}

    content_en = result.get('content', '')
    title_en = result.get('title', '')

    # 3. 翻译（如果有非中文内容，且用户要求翻译）
    import re as _re
    chinese_chars = len(_re.findall(r'[\u4e00-\u9fff]', content_en))
    is_chinese = chinese_chars / max(len(content_en), 1) > 0.3

    title_zh = title_en
    content_zh = content_en
    if translate and not is_chinese:
        title_zh = await loop.run_in_executor(None, translate_to_zh, title_en)
        content_zh = await loop.run_in_executor(None, translate_to_zh, content_en)

    # 4. 存缓存（同时保存中英文版本）
    cache_article(url, {
        'title_zh': title_zh,
        'title_en': title_en,
        'content_zh': content_zh,
        'content_en': content_en,
        'isTranslated': translate and not is_chinese,
    })

    # 5. 根据 translate 参数返回对应版本
    if translate:
        return {"code": 0, "data": {
            "title": title_zh, "content": content_zh,
            "title_en": title_en, "content_en": content_en,
            "isTranslated": not is_chinese,
        }}
    else:
        return {"code": 0, "data": {
            "title": title_en, "content": content_en,
            "title_zh": title_zh, "content_zh": content_zh,
            "isTranslated": False,
        }}


# ── 系统状态 ──

@router.get("/status")
async def api_get_status(request: Request):
    user_id = _get_user_id(request)
    watchlist = await get_watchlist(user_id=user_id)
    today_count = await get_today_events_count(user_id=user_id)
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

@router.get("/research/{stock_code}")
async def api_get_research(stock_code: str, limit: int = Query(10, ge=1, le=50)):
    """获取个股券商研报（评级、盈利预测、PDF链接）"""
    data = get_stock_reports(stock_code, limit=limit)
    return {"code": 0, "data": data}


@router.get("/profile/{stock_code}")
async def api_get_profile(stock_code: str, price: float = Query(0)):
    """获取个股完整画像（研报+评级+机构+千股千评+目标价推算）"""
    profile = get_stock_full_profile(stock_code, current_price=price)
    return {"code": 0, "data": profile}


@router.get("/profile/{stock_code}/ai")
async def api_get_profile_ai(stock_code: str, price: float = Query(0)):
    """获取个股画像的AI综合研判"""
    from app.analysis.ai_analyzer import analyze_profile

    profile = get_stock_full_profile(stock_code, current_price=price)
    ai_result = analyze_profile(profile)
    return {"code": 0, "data": {"analysis": ai_result, "profile": profile}}


@router.get("/analysts")
async def api_get_analysts(limit: int = Query(20, ge=1, le=100)):
    """获取分析师排行"""
    analysts = get_analyst_ranking(limit=limit)
    return {"code": 0, "data": analysts}


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
