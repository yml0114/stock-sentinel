"""
金融哨兵 — FastAPI 入口
"""
import sys
import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 将项目根目录加入 sys.path，确保模块导入正确
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from app.database import init_db
from app.engine.scheduler import start_scheduler, stop_scheduler
from app.api.routes import router

# ── 日志配置 ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("stock-sentinel")


# ── 生命周期管理 ──

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动/关闭生命周期"""
    # 启动
    logger.info("🚀 Stock Sentinel 启动中...")
    await init_db()
    start_scheduler()
    # 预加载新闻缓存（后台线程，不阻塞启动）
    import threading
    def _preload_news():
        try:
            from app.api.routes import _news_cache, _CACHE_TTL, _format_news_item
            from app.data.news_intel import fetch_all_raw, fetch_all_news
            import time as _time
            logger.info("📰 预加载新闻缓存...")
            raw_items = fetch_all_raw()
            _news_cache['raw'] = [_format_news_item(i) for i in raw_items]
            _news_cache['raw_ts'] = _time.time()
            filtered = fetch_all_news()
            result = []
            for item in filtered[:100]:
                entry = _format_news_item(item)
                entry["matchedKeywords"] = item.get("matched_keywords", [])
                entry["relatedSectors"] = item.get("related_sectors", [])
                entry["severity"] = item.get("severity", "info")
                result.append(entry)
            _news_cache['data'] = result
            _news_cache['ts'] = _time.time()
            logger.info(f"📰 新闻缓存就绪: {len(_news_cache['raw'])}条原始, {len(result)}条过滤")
        except Exception as e:
            logger.warning(f"📰 新闻缓存预加载失败: {e}")
    threading.Thread(target=_preload_news, daemon=True).start()
    logger.info("✅ Stock Sentinel 启动完成")
    yield
    # 关闭
    stop_scheduler()
    logger.info("👋 Stock Sentinel 已关闭")


# ── 创建 FastAPI 应用 ──

app = FastAPI(
    title="Stock Sentinel",
    description="A股智能监控哨兵 — 实时行情、异动检测、AI分析、消息推送",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS（开发阶段允许所有来源）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(router)


# ── 健康检查 ──

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "Stock Sentinel",
        "version": "1.0.0",
    }


# ── 直接运行 ──

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
