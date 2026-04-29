"""
新闻缓存服务 — 磁盘持久化 + 后台定时刷新
解决：首次加载慢、重启丢缓存、无自动更新
"""
import json
import os
import logging
import threading
import time
from datetime import datetime

import config
from app.data.news_intel import fetch_all_raw, fetch_all_news

logger = logging.getLogger(__name__)

# 磁盘缓存路径
_RAW_CACHE_PATH = os.path.join(os.path.dirname(config.DB_PATH), 'news_raw_cache.json')
_FILTERED_CACHE_PATH = os.path.join(os.path.dirname(config.DB_PATH), 'news_filtered_cache.json')

# 内存缓存
_raw_cache: list[dict] = []
_filtered_cache: list[dict] = []
_raw_ts: float = 0
_filtered_ts: float = 0
_fetching_raw = False
_fetching_filtered = False

# 缓存有效期（秒）
RAW_TTL = 180       # 3分钟
FILTERED_TTL = 300  # 5分钟


def _save_to_disk(data: list[dict], path: str):
    """保存缓存到磁盘"""
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump({
                'data': data,
                'ts': time.time(),
                'count': len(data),
            }, f, ensure_ascii=False)
        logger.debug(f"💾 缓存已保存: {len(data)}条 → {os.path.basename(path)}")
    except Exception as e:
        logger.warning(f"缓存保存失败: {e}")


def _load_from_disk(path: str) -> list[dict] | None:
    """从磁盘加载缓存"""
    try:
        if not os.path.exists(path):
            return None
        with open(path, 'r', encoding='utf-8') as f:
            cache = json.load(f)
        data = cache.get('data', [])
        if data:
            logger.info(f"💾 从磁盘加载缓存: {len(data)}条 ({os.path.basename(path)})")
        return data if data else None
    except Exception as e:
        logger.warning(f"缓存加载失败: {e}")
        return None


def _do_fetch_raw():
    """后台抓取原始新闻（确保翻译完成后再保存）"""
    global _raw_cache, _raw_ts, _fetching_raw
    if _fetching_raw:
        return
    _fetching_raw = True
    try:
        logger.info("🔄 后台抓取新闻(原始)...")
        items = fetch_all_raw()
        if items:
            # 确保英文标题已翻译（缓存中必须是中文）
            from app.data.translator import translate_news_items, _is_chinese
            untranslated = [i for i in items 
                          if i.get('source_type') == 'international' 
                          and i.get('title') 
                          and not _is_chinese(i['title'])]
            if untranslated:
                logger.info(f"🔤 补充翻译 {len(untranslated)} 条未翻译标题...")
                translate_news_items(untranslated)
            _raw_cache = items
            _raw_ts = time.time()
            _save_to_disk(items, _RAW_CACHE_PATH)
            logger.info(f"✅ 原始新闻缓存更新: {len(items)}条")
    except Exception as e:
        logger.error(f"原始新闻抓取失败: {e}")
    finally:
        _fetching_raw = False


def _do_fetch_filtered():
    """后台抓取过滤后新闻"""
    global _filtered_cache, _filtered_ts, _fetching_filtered
    if _fetching_filtered:
        return
    _fetching_filtered = True
    try:
        logger.info("🔄 后台抓取新闻(过滤)...")
        items = fetch_all_news()
        if items:
            _filtered_cache = items
            _filtered_ts = time.time()
            _save_to_disk(items, _FILTERED_CACHE_PATH)
            logger.info(f"✅ 过滤新闻缓存更新: {len(items)}条")
    except Exception as e:
        logger.error(f"过滤新闻抓取失败: {e}")
    finally:
        _fetching_filtered = False


def get_raw_news(limit: int = 200) -> list[dict]:
    """
    获取原始新闻（极速返回）
    1. 有内存缓存且未过期 → 直接返回
    2. 内存过期 → 后台刷新，但先返回旧数据
    3. 内存空 → 尝试磁盘缓存
    4. 磁盘空 → 同步等待首次抓取
    """
    global _raw_cache, _raw_ts
    now = time.time()

    # 有缓存且未过期
    if _raw_cache and (now - _raw_ts) < RAW_TTL:
        return _raw_cache[:limit]

    # 内存过期 → 后台刷新，先返回旧数据
    if _raw_cache:
        threading.Thread(target=_do_fetch_raw, daemon=True).start()
        return _raw_cache[:limit]

    # 内存空 → 尝试磁盘
    disk_data = _load_from_disk(_RAW_CACHE_PATH)
    if disk_data:
        _raw_cache = disk_data
        # 磁盘数据也后台刷新
        threading.Thread(target=_do_fetch_raw, daemon=True).start()
        return disk_data[:limit]

    # 完全没有 → 同步等待首次抓取
    logger.info("⏳ 首次抓取原始新闻（同步等待）...")
    # 如果后台已经在抓了，等它完成
    if _fetching_raw:
        for _ in range(60):  # 最多等30秒
            time.sleep(0.5)
            if _raw_cache:
                return _raw_cache[:limit]
    _do_fetch_raw()
    return _raw_cache[:limit]


def get_filtered_news() -> list[dict]:
    """
    获取过滤后新闻（极速返回）
    同样策略：内存 → 磁盘 → 首次同步
    """
    global _filtered_cache, _filtered_ts
    now = time.time()

    if _filtered_cache and (now - _filtered_ts) < FILTERED_TTL:
        return _filtered_cache

    if _filtered_cache:
        threading.Thread(target=_do_fetch_filtered, daemon=True).start()
        return _filtered_cache

    disk_data = _load_from_disk(_FILTERED_CACHE_PATH)
    if disk_data:
        _filtered_cache = disk_data
        threading.Thread(target=_do_fetch_filtered, daemon=True).start()
        return disk_data

    logger.info("⏳ 首次抓取过滤新闻（同步等待）...")
    if _fetching_filtered:
        for _ in range(60):
            time.sleep(0.5)
            if _filtered_cache:
                return _filtered_cache
    _do_fetch_filtered()
    return _filtered_cache


def refresh_news_background():
    """在后台线程中刷新所有新闻缓存（启动时调用 + 定时调用）"""
    t1 = threading.Thread(target=_do_fetch_raw, daemon=True)
    t2 = threading.Thread(target=_do_fetch_filtered, daemon=True)
    t1.start()
    t2.start()
    return t1, t2


def clear_cache():
    """清空所有缓存（内存+磁盘）"""
    global _raw_cache, _filtered_cache, _raw_ts, _filtered_ts
    _raw_cache = []
    _filtered_cache = []
    _raw_ts = 0
    _filtered_ts = 0
    for path in [_RAW_CACHE_PATH, _FILTERED_CACHE_PATH]:
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception:
            pass
    logger.info("🗑️ 新闻缓存已清空")


def cache_stats() -> dict:
    """缓存状态信息"""
    return {
        'raw_count': len(_raw_cache),
        'raw_age': int(time.time() - _raw_ts) if _raw_ts else -1,
        'raw_ttl': RAW_TTL,
        'filtered_count': len(_filtered_cache),
        'filtered_age': int(time.time() - _filtered_ts) if _filtered_ts else -1,
        'filtered_ttl': FILTERED_TTL,
        'disk_raw_exists': os.path.exists(_RAW_CACHE_PATH),
        'disk_filtered_exists': os.path.exists(_FILTERED_CACHE_PATH),
        'fetching_raw': _fetching_raw,
        'fetching_filtered': _fetching_filtered,
    }
