"""
事件检测引擎
- 内存缓存上一轮行情
- 价格异动、成交量放大、新公告检测
"""
import logging
from typing import Optional

import config

logger = logging.getLogger(__name__)

# ── 内存缓存：上一轮行情 {stock_code: quote_dict} ──
_prev_quotes: dict[str, dict] = {}
# 已见公告标题（去重）
_seen_announcements: set[str] = set()


def detect_price_alert(current: dict) -> Optional[dict]:
    """
    检测涨跌幅超过阈值
    """
    change_pct = current.get("change_pct", 0)
    if abs(change_pct) >= config.THRESHOLD_PRICE_CHANGE:
        direction = "📈 大涨" if change_pct > 0 else "📉 大跌"
        severity = "high" if abs(change_pct) >= 5.0 else "medium"
        return {
            "stock_code": current["stock_code"],
            "event_type": "price_alert",
            "title": f"{current.get('stock_name', '')}({current['stock_code']}) {direction} {change_pct:+.2f}%",
            "detail": (
                f"现价: {current.get('price', 0):.2f} | "
                f"涨跌幅: {change_pct:+.2f}% | "
                f"成交量: {current.get('volume', 0):.0f} | "
                f"成交额: {current.get('amount', 0):.0f}"
            ),
            "severity": severity,
            "quote": current,
        }
    return None


def detect_volume_spike(current: dict) -> Optional[dict]:
    """
    检测成交量放大 > 阈值倍数
    与上一轮行情对比
    """
    code = current["stock_code"]
    prev = _prev_quotes.get(code)
    if not prev:
        return None

    prev_vol = prev.get("volume", 0)
    curr_vol = current.get("volume", 0)

    if prev_vol > 0 and curr_vol > 0:
        ratio = curr_vol / prev_vol
        if ratio >= config.THRESHOLD_VOLUME_RATIO:
            return {
                "stock_code": code,
                "event_type": "volume_spike",
                "title": f"{current.get('stock_name', '')}({code}) 成交量异常放大 {ratio:.1f}倍",
                "detail": (
                    f"当前成交量: {curr_vol:.0f} | "
                    f"上轮成交量: {prev_vol:.0f} | "
                    f"放大倍数: {ratio:.1f}x | "
                    f"现价: {current.get('price', 0):.2f}"
                ),
                "severity": "medium",
                "quote": current,
            }
    return None


def detect_new_announcement(stock_code: str, announcements: list[dict]) -> list[dict]:
    """
    检测新公告，关键词分级
    - high: 减持、ST、退市、立案、处罚、暴雷
    - medium: 增持、回购、分红、送转
    """
    high_keywords = ["减持", "ST", "退市", "立案", "处罚", "暴雷", "违规", "亏损", "质押"]
    medium_keywords = ["增持", "回购", "分红", "送转", "中标", "业绩预增", "战略合作"]

    events = []
    for ann in announcements:
        title = ann.get("title", "")
        ann_key = f"{stock_code}:{title}"

        if ann_key in _seen_announcements or not title:
            continue

        _seen_announcements.add(ann_key)

        severity = "info"
        for kw in high_keywords:
            if kw in title:
                severity = "high"
                break
        if severity == "info":
            for kw in medium_keywords:
                if kw in title:
                    severity = "medium"
                    break

        events.append({
            "stock_code": stock_code,
            "event_type": "announcement",
            "title": f"📋 新公告: {title}",
            "detail": f"日期: {ann.get('date', '')} | 类型: {ann.get('type', '')}",
            "severity": severity,
        })

    return events


def update_prev_quotes(quotes: list[dict]):
    """更新上一轮行情缓存"""
    global _prev_quotes
    for q in quotes:
        _prev_quotes[q["stock_code"]] = q


def run_detection(
    quotes: list[dict],
    announcements_map: dict[str, list[dict]],
    news_events: list[dict] = None,
) -> list[dict]:
    """
    综合检测：价格异动 + 成交量放大 + 新公告 + 新闻事件
    返回所有触发的事件列表
    """
    all_events = []

    for quote in quotes:
        code = quote["stock_code"]

        # 价格异动
        event = detect_price_alert(quote)
        if event:
            all_events.append(event)

        # 成交量放大
        event = detect_volume_spike(quote)
        if event:
            all_events.append(event)

        # 新公告
        anns = announcements_map.get(code, [])
        ann_events = detect_new_announcement(code, anns)
        all_events.extend(ann_events)

    # 新闻事件（由 news_intel 模块过滤后的结果）
    if news_events:
        for news in news_events:
            all_events.append({
                "stock_code": "GLOBAL",
                "event_type": "news",
                "title": f"🌐 {news.get('title', '')}",
                "detail": news.get("content", "")[:500],
                "severity": news.get("severity", "info"),
                "news_data": news,
            })

    # 更新缓存
    update_prev_quotes(quotes)

    logger.info(f"🔍 检测完成: {len(quotes)}只股票, 触发 {len(all_events)} 个事件")
    return all_events
