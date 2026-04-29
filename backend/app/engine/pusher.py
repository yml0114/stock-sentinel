"""
ntfy.sh 推送模块
- 异步 httpx POST 到 ntfy.sh
- WebSocket 客户端管理
"""
import logging
import httpx
from typing import Optional
from fastapi import WebSocket

import config

logger = logging.getLogger(__name__)

# ── WebSocket 客户端列表 ──
ws_clients: list[WebSocket] = []

# ── severity → emoji 映射 ──
SEVERITY_EMOJI = {
    "high": "🚨",
    "medium": "⚠️",
    "info": "ℹ️",
}


async def push_ntfy(title: str, body: str, severity: str = "info"):
    """
    异步推送消息到 ntfy.sh
    """
    emoji = SEVERITY_EMOJI.get(severity, "ℹ️")
    full_title = f"{emoji} {title}"

    url = f"{config.NTFY_SERVER}/{config.NTFY_TOPIC}"
    headers = {
        "Priority": "high" if severity == "high" else ("default" if severity == "medium" else "low"),
        "Tags": severity,
    }
    # Use JSON body to avoid latin-1 header encoding errors with emoji
    import json
    payload = {
        "topic": config.NTFY_TOPIC,
        "title": full_title,
        "message": body,
        "priority": headers["Priority"],
        "tags": [headers["Tags"]],
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                config.NTFY_SERVER,
                content=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                headers={"Content-Type": "application/json; charset=utf-8"},
            )
            if resp.status_code == 200:
                logger.info(f"✅ ntfy 推送成功: {full_title}")
            else:
                logger.warning(f"ntfy 推送异常 {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        logger.error(f"ntfy 推送失败: {e}")


async def broadcast_ws(data: dict):
    """
    广播消息到所有 WebSocket 客户端
    """
    import json
    message = json.dumps(data, ensure_ascii=False, default=str)
    disconnected = []

    for ws in ws_clients:
        try:
            await ws.send_text(message)
        except Exception:
            disconnected.append(ws)

    # 清理断开的连接
    for ws in disconnected:
        ws_clients.remove(ws)
        logger.info(f"WebSocket 客户端断开，剩余 {len(ws_clients)} 个")


async def notify_all(title: str, body: str, severity: str = "info", data: dict = None):
    """
    同时推送到 ntfy.sh 和 WebSocket
    """
    # ntfy 推送
    await push_ntfy(title, body, severity)

    # WebSocket 广播
    ws_data = {
        "type": "event",
        "title": title,
        "body": body,
        "severity": severity,
    }
    if data:
        ws_data.update(data)
    await broadcast_ws(ws_data)
