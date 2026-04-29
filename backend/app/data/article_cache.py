"""
文章全文缓存 — 磁盘持久化
点击过的文章：抓取+翻译 → 存磁盘 → 下次秒开
后台预抓取热门文章：翻译好直接推送
"""
import json
import os
import logging
import threading
import time

import config

logger = logging.getLogger(__name__)

# 增加版本号即可强制清空旧缓存（例如 dedup 逻辑升级后）
_CACHE_VERSION = 2
_CACHE_VERSION_KEY = '_cache_version'

# 磁盘缓存路径
_CACHE_DIR = os.path.join(os.path.dirname(config.DB_PATH), 'article_cache')
_INDEX_PATH = os.path.join(_CACHE_DIR, 'index.json')

# 内存索引: url → {title, title_en, content, content_en, fetched_at, ...}
_index: dict[str, dict] = {}
_lock = threading.Lock()


def _ensure_dir():
    os.makedirs(_CACHE_DIR, exist_ok=True)


def _save_index():
    """保存索引到磁盘"""
    try:
        _ensure_dir()
        save_data = dict(_index)
        save_data[_CACHE_VERSION_KEY] = _CACHE_VERSION
        with open(_INDEX_PATH, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, ensure_ascii=False, indent=0)
    except Exception as e:
        logger.warning(f"索引保存失败: {e}")


def _load_index():
    """从磁盘加载索引"""
    global _index
    try:
        if os.path.exists(_INDEX_PATH):
            with open(_INDEX_PATH, 'r', encoding='utf-8') as f:
                _index = json.load(f)
            # 版本不匹配则清空旧缓存（dedup 升级等场景）
            if _index.get(_CACHE_VERSION_KEY) != _CACHE_VERSION:
                logger.info(f"🔄 文章缓存版本不匹配，清空旧缓存")
                _index = {}
                _save_index()
            else:
                _index.pop(_CACHE_VERSION_KEY, None)
                logger.info(f"💾 文章缓存索引加载: {len(_index)} 篇")
    except Exception as e:
        logger.warning(f"索引加载失败: {e}")
        _index = {}


def get_cached_article(url: str) -> dict | None:
    """从缓存获取已翻译的文章，没有返回None"""
    with _lock:
        entry = _index.get(url)
    if not entry:
        return None
    # 检查缓存是否过期（7天）
    age = time.time() - entry.get('fetched_at', 0)
    if age > 7 * 86400:
        return None
    return entry


def cache_article(url: str, data: dict):
    """
    缓存已抓取+翻译的文章
    存储结构：content_en=原始英文, content_zh=翻译中文, content=当前显示版本
    """
    entry = {
        'url': url,
        # 中文版本
        'title': data.get('title_zh', data.get('title', '')),
        'title_zh': data.get('title_zh', data.get('title', '')),
        # 英文版本
        'title_en': data.get('title_en', ''),
        # 中文内容
        'content': data.get('content_zh', data.get('content', '')),
        'content_zh': data.get('content_zh', data.get('content', '')),
        # 英文内容
        'content_en': data.get('content_en', ''),
        'isTranslated': data.get('isTranslated', False),
        'fetched_at': time.time(),
    }
    with _lock:
        _index[url] = entry
        _save_index()
    logger.debug(f"💾 文章已缓存: {entry.get('title', '')[:40]}")


def get_article_for_display(url: str, translate: bool = True) -> dict | None:
    """
    从缓存获取文章，根据 translate 参数返回对应版本
    translate=True → 返回中文版 (content_zh)
    translate=False → 返回英文版 (content_en)
    """
    cached = get_cached_article(url)
    if not cached:
        return None

    if translate:
        # 返回中文版
        return {
            'url': url,
            'title': cached.get('title_zh', cached.get('title', '')),
            'content': cached.get('content_zh', cached.get('content', '')),
            'title_en': cached.get('title_en', ''),
            'content_en': cached.get('content_en', ''),
            'isTranslated': cached.get('isTranslated', False),
        }
    else:
        # 返回英文原版
        return {
            'url': url,
            'title': cached.get('title_en', ''),
            'content': cached.get('content_en', ''),
            'title_zh': cached.get('title_zh', ''),
            'content_zh': cached.get('content_zh', ''),
            'isTranslated': False,
        }


def prefetch_articles(urls: list[str]):
    """
    后台预抓取+翻译多篇文章
    用法：启动时传入top新闻的URL列表
    """
    from app.data.article_fetcher import extract_article
    from app.data.translator import translate_to_zh, _is_chinese

    def _prefetch():
        count = 0
        for url in urls[:15]:
            try:
                # 跳过已缓存的
                if get_cached_article(url):
                    continue

                result = extract_article(url)
                if not result.get('success') or not result.get('content'):
                    continue

                title = result.get('title', '')
                content = result.get('content', '')

                # 翻译
                title_en = title
                content_en = content
                title_zh = title
                content_zh = content
                is_translated = False

                if content and not _is_chinese(content):
                    title_zh = translate_to_zh(title)
                    content_zh = translate_to_zh(content)
                    is_translated = True

                cache_article(url, {
                    'title_zh': title_zh,
                    'title_en': title_en,
                    'content_zh': content_zh,
                    'content_en': content_en,
                    'isTranslated': is_translated,
                })
                count += 1
                logger.info(f"📡 预抓取 {count}/{min(len(urls), 15)}: {title_zh[:40]}")
            except Exception as e:
                logger.debug(f"预抓取失败: {e}")

        if count > 0:
            logger.info(f"✅ 预抓取完成: {count} 篇文章已缓存")

    threading.Thread(target=_prefetch, daemon=True).start()


def get_all_urls() -> list[str]:
    """获取所有已缓存的URL"""
    with _lock:
        return list(_index.keys())


def cache_stats() -> dict:
    """缓存统计"""
    with _lock:
        return {
            'article_count': len(_index),
            'cache_dir': _CACHE_DIR,
        }


def clear_cache():
    """清空文章缓存"""
    global _index
    with _lock:
        _index = {}
        if os.path.exists(_INDEX_PATH):
            try:
                os.remove(_INDEX_PATH)
            except:
                pass
    logger.info("🗑️ 文章缓存已清空")


# 启动时加载索引
_load_index()
