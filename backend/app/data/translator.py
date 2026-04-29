"""
翻译模块 — Google Translate被墙，改用有道翻译
有道翻译：免费、无需Key、从腾讯云可访问
备用：搜狗翻译、MyMemory
"""
import re
import json
import logging
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)

# 翻译缓存
_cache: dict[str, str] = {}
_CACHE_MAX = 1000

# 并发翻译线程池
_executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix='translate')


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


def _translate_single_item(item: dict) -> dict:
    """翻译单条新闻的标题和内容（线程安全）"""
    title = item.get('title', '')
    content = item.get('content', '')

    if title and not _is_chinese(title):
        new_title = translate_to_zh(title)
        if new_title != title:
            item['title'] = new_title
            item['title_en'] = title

    if content and not _is_chinese(content):
        summary = content[:200]
        new_content = translate_to_zh(summary)
        if new_content != summary:
            item['content'] = new_content
            item['content_en'] = content

    return item


def translate_news_items(items: list, source_filter: str = '') -> list:
    """
    并发批量翻译新闻标题和内容为中文
    只翻译非中文内容，中文源自动跳过
    最多翻译 max_translate 条，8线程并发
    """
    # 先过滤出需要翻译的目标
    to_translate = []
    for item in items:
        if source_filter and source_filter.lower() not in item.get('source', '').lower():
            continue
        title = item.get('title', '')
        content = item.get('content', '')
        # 只要标题或内容不是中文就需要翻译
        if (title and not _is_chinese(title)) or (content and not _is_chinese(content)):
            to_translate.append(item)

    # 限制最多翻译30条
    max_translate = 30
    to_translate = to_translate[:max_translate]

    if not to_translate:
        return items

    # 并发翻译
    translated_count = 0
    futures = {_executor.submit(_translate_single_item, item): item for item in to_translate}
    for future in as_completed(futures, timeout=30):
        try:
            future.result(timeout=10)
            translated_count += 1
        except Exception as e:
            logger.debug(f"翻译单条失败: {e}")

    if translated_count > 0:
        logger.info(f"✅ 并发翻译完成: {translated_count}/{len(to_translate)} 条新闻")
    return items
