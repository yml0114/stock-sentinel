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
    # 后台预加载新闻缓存（持久化磁盘 + 内存，不阻塞启动）
    from app.news_cache import refresh_news_background, _load_from_disk, _RAW_CACHE_PATH, _FILTERED_CACHE_PATH
    import app.news_cache as nc
    # 先加载磁盘缓存（秒级）
    disk_raw = _load_from_disk(_RAW_CACHE_PATH)
    if disk_raw:
        nc._raw_cache = disk_raw
    disk_filtered = _load_from_disk(_FILTERED_CACHE_PATH)
    if disk_filtered:
        nc._filtered_cache = disk_filtered
    logger.info(f"📰 磁盘缓存加载: {len(nc._raw_cache)}条原始, {len(nc._filtered_cache)}条过滤")
    # 再后台刷新最新数据
    refresh_news_background()
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
