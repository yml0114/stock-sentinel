"""翻译模块 v4 — Google Translate 免费API（HK服务器直连）"""

from __future__ import annotations

import re
import json
import logging
import urllib.parse
import concurrent.futures
import time

import requests

logger = logging.getLogger(__name__)

# 翻译缓存（内存）
_cache: dict[str, str] = {}
_CACHE_MAX = 5000

# Google Translate API 参数
_GOOGLE_TL = "zh-CN"  # 目标语言
_GOOGLE_SL = "en"     # 源语言
_MAX_WORKERS = 5      # 并发请求数
_REQUEST_DELAY = 0.2  # 请求间隔（秒），避免被限流


def _is_chinese(text: str) -> bool:
    """判断是否主要为中文"""
    if not text:
        return True
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    return chinese_chars / max(len(text), 1) > 0.3


def _google_translate_single(text: str):
    """使用Google Translate免费API翻译单条文本"""
    if not text or text.strip() == '':
        return None

    try:
        url = (
            f"https://translate.googleapis.com/translate_a/single"
            f"?client=gtx"
            f"&sl={_GOOGLE_SL}"
            f"&tl={_GOOGLE_TL}"
            f"&dt=t"
            f"&q={urllib.parse.quote(text[:2000])}"  # 限制长度避免URL过长
        )
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200:
            logger.warning(f"Google翻译HTTP {resp.status_code}: {text[:40]}")
            return None

        data = resp.json()
        # 响应格式: [[["翻译结果","原文",...]], null, "en", ...]
        if data and data[0] and data[0][0]:
            translated = data[0][0][0]
            if translated and translated.strip():
                return translated.strip()
    except Exception as e:
        logger.debug(f"Google翻译失败: {e} — {text[:40]}")

    return None


def _google_translate_batch(texts: list[str]) -> dict[str, str]:
    """批量翻译 — 并发请求，自动限流"""
    result = {}
    if not texts:
        return result

    # 去重
    unique = list(dict.fromkeys(texts))
    logger.info(f"🌐 Google翻译: {len(unique)}条 (并发{_MAX_WORKERS}线程)")

    def _translate_one(t: str) -> tuple[str, str | None]:
        time.sleep(_REQUEST_DELAY)  # 限流
        translated = _google_translate_single(t)
        return t, translated

    with concurrent.futures.ThreadPoolExecutor(max_workers=_MAX_WORKERS) as executor:
        futures = {executor.submit(_translate_one, t): t for t in unique}
        for future in concurrent.futures.as_completed(futures):
            try:
                orig, translated = future.result(timeout=15)
                if translated and _is_chinese(translated):
                    result[orig] = translated
                else:
                    logger.debug(f"翻译结果非中文或为空: {orig[:40]} → {str(translated)[:40] if translated else 'None'}")
            except Exception as e:
                orig = futures[future]
                logger.debug(f"翻译线程异常 [{orig[:40]}]: {e}")

    ok = len(result)
    fail = len(unique) - ok
    if fail > 0:
        logger.info(f"  成功: {ok}/{len(unique)}, 失败: {fail}")
    else:
        logger.info(f"  成功: {ok}/{len(unique)} ✅")

    return result


def translate_to_zh(text: str) -> str:
    """单条翻译（兼容旧接口）"""
    if not text or _is_chinese(text):
        return text
    if text in _cache:
        return _cache[text]
    translated = _google_translate_single(text)
    if translated:
        _cache[text] = translated
        # 控制缓存大小
        if len(_cache) > _CACHE_MAX:
            _cache.clear()
        return translated
    return text


def translate_news_items(items: list, source_filter: str = '') -> list:
    """批量翻译新闻标题（和可能的内容摘要）"""
    to_translate = []
    seen = set()
    for item in items:
        if source_filter and source_filter.lower() not in item.get('source', '').lower():
            continue
        title = item.get('title', '')
        if title and not _is_chinese(title) and title not in seen:
            if title in _cache:
                item['title_cn'] = _cache[title]
            else:
                to_translate.append(title)
                seen.add(title)
        # 也翻译content摘要（如果是英文且长度适中）
        content = item.get('content', '')[:500]
        if content and not _is_chinese(content) and content not in seen and len(content) > 50:
            if content in _cache:
                item['content_cn'] = _cache[content]
            else:
                to_translate.append(content)
                seen.add(content)

    if not to_translate:
        return items

    translations = _google_translate_batch(to_translate)

    # 更新缓存
    _cache.update(translations)
    if len(_cache) > _CACHE_MAX:
        # 只保留最近的一半
        keys_to_keep = list(_cache.keys())[-_CACHE_MAX // 2:]
        _cache.clear()
        for k in keys_to_keep:
            if k in translations:
                _cache[k] = translations[k]

    translated_count = 0
    for item in items:
        title = item.get('title', '')
        if title in translations:
            item['title_cn'] = translations[title]
            translated_count += 1
        content = item.get('content', '')[:500]
        if content in translations:
            item['content_cn'] = translations[content]

    content_translated = sum(1 for item in items if item.get('content', '')[:500] in translations)
    logger.info(f"翻译完成: {translated_count}条标题 + {content_translated}条内容")
    return items
