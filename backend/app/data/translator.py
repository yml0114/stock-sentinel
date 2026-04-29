"""
翻译模块 — Google Translate被墙，改用有道翻译
有道翻译：免费、无需Key、从腾讯云可访问
备用：搜狗翻译、MyMemory
"""
import re
import json
import logging
import requests

logger = logging.getLogger(__name__)

# 翻译缓存
_cache: dict[str, str] = {}
_CACHE_MAX = 500


def _is_chinese(text: str) -> bool:
    if not text:
        return True
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    return chinese_chars / max(len(text), 1) > 0.3


def _youdao_translate(text: str) -> str:
    """有道翻译 — 免费、无需Key"""
    try:
        resp = requests.post(
            "https://fanyi.youdao.com/translate",
            params={"doctype": "json", "type": "AUTO2AUTO"},
            data={"i": text[:500]},
            timeout=5,
        )
        if resp.status_code == 200:
            data = resp.json()
            results = []
            for seg_list in data.get("translateResult", []):
                for seg in seg_list:
                    if seg.get("tgt"):
                        results.append(seg["tgt"])
            return "".join(results)
    except Exception as e:
        logger.debug(f"有道翻译失败: {e}")
    return ""


def _sogou_translate(text: str) -> str:
    """搜狗翻译 — 免费、无需Key"""
    try:
        resp = requests.post(
            "https://fanyi.sogou.com/texttranslate",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={"from": "auto", "to": "zh", "text": text[:500]},
            timeout=5,
        )
        if resp.status_code == 200:
            data = resp.json()
            items = data.get("data", [])
            return "".join(item.get("dst", "") for item in items)
    except Exception as e:
        logger.debug(f"搜狗翻译失败: {e}")
    return ""


def _mymemory_translate(text: str) -> str:
    """MyMemory翻译 — 免费、无需Key"""
    try:
        resp = requests.get(
            "https://api.mymemory.translated.net/get",
            params={"q": text[:500], "langpair": "en|zh-CN"},
            timeout=5,
        )
        if resp.status_code == 200:
            data = resp.json()
            return data.get("responseData", {}).get("translatedText", "")
    except Exception as e:
        logger.debug(f"MyMemory翻译失败: {e}")
    return ""


def translate_to_zh(text: str) -> str:
    """
    翻译英文/其他语言 → 中文（简体）
    优先有道 → 搜狗 → MyMemory，全部免费无需Key
    """
    if not text or len(text.strip()) < 3:
        return text

    if _is_chinese(text):
        return text

    # 查缓存
    if text in _cache:
        return _cache[text]

    # 依次尝试三个翻译服务
    translated = _youdao_translate(text)
    if not translated:
        translated = _sogou_translate(text)
    if not translated:
        translated = _mymemory_translate(text)

    if translated and translated != text:
        if len(_cache) < _CACHE_MAX:
            _cache[text] = translated
        return translated

    return text


def translate_news_items(items: list, source_filter: str = '') -> list:
    """
    批量翻译新闻标题和内容为中文
    只翻译非中文内容，中文源自动跳过
    """
    translated_count = 0
    max_translate = 15
    for item in items:
        if translated_count >= max_translate:
            break

        source = item.get('source', '')
        if source_filter and source_filter.lower() not in source.lower():
            continue

        title = item.get('title', '')
        content = item.get('content', '')

        if title and not _is_chinese(title):
            new_title = translate_to_zh(title)
            if new_title != title:
                item['title'] = new_title
                item['title_en'] = title
                translated_count += 1

        if content and not _is_chinese(content):
            summary = content[:200]
            new_content = translate_to_zh(summary)
            if new_content != summary:
                item['content'] = new_content
                item['content_en'] = content

    if translated_count > 0:
        logger.info(f"✅ 已翻译 {translated_count} 条新闻为中文")
    return items
