"""
翻译模块 — 从腾讯云服务器无法访问Google Translate
改用DeepSeek AI翻译（同服务器的AI API，已配置）
"""
import re
import logging
import os
import requests
import json

logger = logging.getLogger(__name__)

# AI翻译配置（复用主API）
_AI_URL = os.getenv("AI_API_URL", "https://api.tokex.top/v1")
_AI_KEY = os.getenv("AI_API_KEY", "")
_AI_MODEL = os.getenv("AI_MODEL", "deepseek-ai/deepseek-v4-pro")

# 翻译缓存避免重复调用
_cache: dict[str, str] = {}
_CACHE_MAX = 500


def _is_chinese(text: str) -> bool:
    """检测文本是否主要是中文"""
    if not text:
        return True
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    return chinese_chars / max(len(text), 1) > 0.3


def translate_to_zh(text: str) -> str:
    """
    翻译英文/其他语言 → 中文（简体）
    使用DeepSeek AI翻译，超时5秒，失败返回原文
    """
    if not text or len(text.strip()) < 3:
        return text

    if _is_chinese(text):
        return text

    # 查缓存
    if text in _cache:
        return _cache[text]

    if not _AI_KEY:
        return text

    try:
        resp = requests.post(
            f"{_AI_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {_AI_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": _AI_MODEL,
                "messages": [
                    {"role": "system", "content": "你是翻译专家。把用户输入翻译成中文简体。只输出翻译结果，不要解释。"},
                    {"role": "user", "content": text[:500]},
                ],
                "temperature": 0.1,
                "max_tokens": 300,
            },
            timeout=5,
        )
        if resp.status_code == 200:
            result = resp.json()
            translated = result["choices"][0]["message"]["content"].strip()
            # 缓存
            if len(_cache) < _CACHE_MAX:
                _cache[text] = translated
            return translated
    except Exception as e:
        logger.debug(f"翻译失败: {e}")

    return text


def translate_news_items(items: list, source_filter: str = '') -> list:
    """
    批量翻译新闻标题和内容为中文
    只翻译非中文内容，中文源自动跳过
    限制翻译数量避免API过多调用
    """
    translated_count = 0
    max_translate = 10  # 最多翻译10条，避免太多AI调用
    for item in items:
        if translated_count >= max_translate:
            break

        source = item.get('source', '')
        if source_filter and source_filter.lower() not in source.lower():
            continue

        title = item.get('title', '')
        content = item.get('content', '')

        # 翻译标题
        if title and not _is_chinese(title):
            new_title = translate_to_zh(title)
            if new_title != title:
                item['title'] = new_title
                item['title_en'] = title
                translated_count += 1

        # 翻译内容摘要（不翻译全文，太长）
        if content and not _is_chinese(content):
            summary = content[:200]
            new_content = translate_to_zh(summary)
            if new_content != summary:
                item['content'] = new_content
                item['content_en'] = content

    if translated_count > 0:
        logger.info(f"✅ 已翻译 {translated_count} 条新闻为中文")
    return items
