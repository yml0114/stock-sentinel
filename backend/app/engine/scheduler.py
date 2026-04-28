"""
APScheduler 定时任务
- poll_realtime(): 每30秒拉行情→检测→AI分析→推送
- poll_news(): 每5分钟拉全球新闻→关键词过滤→AI评估→推送
"""
import asyncio
import logging
import sqlite3
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from apscheduler.schedulers.background import BackgroundScheduler

import config
from app.data.stock_data import get_batch_quotes, get_stock_announcements
from app.data.news_intel import fetch_all_news, format_for_ai
from app.engine.detector import run_detection
from app.engine.pusher import notify_all
from app.analysis.ai_analyzer import analyze_event, analyze_news
from app.database import add_event, get_watchlist

logger = logging.getLogger(__name__)

# APScheduler 实例
scheduler = BackgroundScheduler()

# 线程池用于执行 AI 分析（避免阻塞）
_executor = ThreadPoolExecutor(max_workers=4)


def get_watchlist_sync() -> list[dict]:
    """同步获取自选股列表（在线程中使用 sqlite3 同步连接）"""
    try:
        conn = sqlite3.connect(config.DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("SELECT * FROM watchlist WHERE alert_enabled = 1")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"获取自选股列表失败: {e}")
        return []


def _run_async(coro):
    """在新事件循环中运行异步任务"""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def poll_realtime():
    """
    定时任务：拉取实时行情 → 检测 → AI分析 → 推送
    """
    logger.info("⏰ poll_realtime 开始执行...")
    try:
        # 1. 获取自选股列表
        watchlist = get_watchlist_sync()
        if not watchlist:
            logger.debug("自选股列表为空，跳过")
            return

        stock_codes = [w["stock_code"] for w in watchlist]
        stock_names = {w["stock_code"]: w["stock_name"] for w in watchlist}

        # 2. 批量拉取行情
        quotes = get_batch_quotes(stock_codes)
        if not quotes:
            logger.warning("行情数据为空")
            return

        # 补充名称
        for q in quotes:
            if q.get("stock_name") == "" or q.get("stock_name") == "未知":
                q["stock_name"] = stock_names.get(q["stock_code"], "")

        # 3. 拉取公告
        announcements_map = {}
        for code in stock_codes:
            try:
                announcements_map[code] = get_stock_announcements(code)
            except Exception:
                announcements_map[code] = []

        # 4. 运行检测
        events = run_detection(quotes, announcements_map)

        # 5. 处理每个事件：AI分析 → 存库 → 推送
        for event in events:
            try:
                # AI 分析
                ai_result = analyze_event(event, event.get("quote"))
                event["ai_analysis"] = ai_result

                # 存入数据库
                _run_async(add_event(
                    stock_code=event["stock_code"],
                    event_type=event["event_type"],
                    title=event["title"],
                    detail=event.get("detail", ""),
                    ai_analysis=ai_result,
                    severity=event.get("severity", "info"),
                ))

                # 推送
                _run_async(notify_all(
                    title=event["title"],
                    body=f"{event.get('detail', '')}\n\n🤖 AI分析:\n{ai_result}",
                    severity=event.get("severity", "info"),
                    data={"stock_code": event["stock_code"], "event_type": event["event_type"]},
                ))

            except Exception as e:
                logger.error(f"处理事件失败: {e}")

        logger.info(f"✅ poll_realtime 完成: {len(quotes)} 只股票, {len(events)} 个事件")

    except Exception as e:
        logger.error(f"poll_realtime 执行失败: {e}", exc_info=True)


def poll_news():
    """
    定时任务：拉取全球新闻 → 关键词过滤 → AI评估 → 推送
    """
    logger.info("⏰ poll_news 开始执行...")
    try:
        # 1. 获取自选股代码（用于个股新闻）
        watchlist = get_watchlist_sync()
        stock_codes = [w["stock_code"] for w in watchlist] if watchlist else None

        # 2. 聚合新闻 + 关键词过滤
        filtered_news = fetch_all_news(stock_codes)
        if not filtered_news:
            logger.debug("无新的需关注新闻")
            return

        # 3. 对过滤后的新闻做 AI 评估 + 推送
        for news in filtered_news[:10]:  # 限制单次最多10条，控制成本
            try:
                ai_result = analyze_news(news)
                news["ai_analysis"] = ai_result

                # 存入数据库
                _run_async(add_event(
                    stock_code="GLOBAL",
                    event_type="news",
                    title=news.get("title", ""),
                    detail=news.get("content", "")[:500],
                    ai_analysis=ai_result,
                    severity=news.get("severity", "info"),
                ))

                # 推送
                _run_async(notify_all(
                    title=f"🌐 {news.get('title', '')}",
                    body=f"{news.get('content', '')[:300]}\n\n🤖 AI分析:\n{ai_result}",
                    severity=news.get("severity", "info"),
                    data={"event_type": "news", "source": news.get("source", "")},
                ))

            except Exception as e:
                logger.error(f"处理新闻失败: {e}")

        logger.info(f"✅ poll_news 完成: 过滤后 {len(filtered_news)} 条新闻")

    except Exception as e:
        logger.error(f"poll_news 执行失败: {e}", exc_info=True)


def start_scheduler():
    """启动定时任务调度器"""
    scheduler.add_job(
        poll_realtime,
        "interval",
        seconds=config.POLL_REALTIME,
        id="poll_realtime",
        name="实时行情轮询",
        replace_existing=True,
    )
    scheduler.add_job(
        poll_news,
        "interval",
        seconds=config.POLL_NEWS,
        id="poll_news",
        name="全球新闻轮询",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(f"🚀 调度器已启动: 行情轮询 {config.POLL_REALTIME}秒, 新闻轮询 {config.POLL_NEWS}秒")


def stop_scheduler():
    """停止调度器"""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("调度器已停止")
