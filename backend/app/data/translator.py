"""
翻译模块 — SimplyTranslate (Google Translate代理) 为主
SimplyTranslate 从国内服务器可用，底层就是 Google Translate
备用：jina.ai LLM翻译、有道
"""
import re
import json
import logging
import requests
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)

# 翻译缓存（内存）
_cache: dict[str, str] = {}
_CACHE_MAX = 2000

# 并发翻译线程池
_executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix='translate')

# SimplyTranslate 每次最大字符限制（URL长度限制）
_MAX_CHUNK = 450


def _is_chinese(text: str) -> bool:
    if not text:
        return True
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    return chinese_chars / max(len(text), 1) > 0.3


def _simplytranslate(text: str) -> str:
    """SimplyTranslate — 底层是 Google Translate，国内可用"""
    try:
        encoded = urllib.parse.quote(text[:_MAX_CHUNK])
        resp = requests.get(
            f"https://simplytranslate.org/api/translate?from=en&to=zh&text={encoded}",
            timeout=8,
        )
        if resp.status_code == 200:
            data = resp.json()
            result = data.get("translated_text", "")
            if result:
                return result
    except Exception as e:
        logger.debug(f"SimplyTranslate失败: {e}")
    return ""


def _jina_translate(text: str) -> str:
    """jina.ai 翻译 — 用 LLM 做翻译，免费"""
    try:
        prompt = f"Translate to Chinese. Output ONLY the translation, nothing else:\n{text[:400]}"
        encoded = urllib.parse.quote(prompt)
        resp = requests.get(
            f"https://s.jina.ai/{encoded}",
            headers={"Accept": "text/plain"},
            timeout=12,
        )
        if resp.status_code == 200:
            result = resp.text.strip()
            result = re.sub(r'^["\']|["\']$', '', result)
            result = re.sub(r'^(Translation|翻译)[：:]\s*', '', result)
            if result and result != text:
                return result
    except Exception as e:
        logger.debug(f"jina翻译失败: {e}")
    return ""


def _youdao_translate(text: str) -> str:
    """有道翻译 — 备用"""
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


def _translate_chunk(text: str) -> str:
    """翻译单个chunk"""
    if not text or len(text.strip()) < 3:
        return text

    if _is_chinese(text):
        return text

    # 查缓存
    if text in _cache:
        return _cache[text]

    # 依次尝试
    translated = _simplytranslate(text)
    if not translated:
        translated = _jina_translate(text)
    if not translated:
        translated = _youdao_translate(text)

    if translated and translated != text:
        if len(_cache) < _CACHE_MAX:
            _cache[text] = translated
        return translated

    return text


def translate_to_zh(text: str) -> str:
    """
    翻译英文 → 中文（支持长文本分块翻译）
    按段落分割，每段独立翻译，最后拼接
    """
    if not text or len(text.strip()) < 3:
        return text

    if _is_chinese(text):
        return text

    # 按双换行分割段落
    paragraphs = text.split('\n\n')
    
    if len(text) <= _MAX_CHUNK:
        # 短文本直接翻译
        return _translate_chunk(text)

    # 长文本：分段翻译
    translated_parts = []
    for para in paragraphs:
        para = para.strip()
        if not para:
            translated_parts.append('')
            continue
        if _is_chinese(para):
            translated_parts.append(para)
            continue
        if len(para) <= _MAX_CHUNK:
            translated_parts.append(_translate_chunk(para))
        else:
            # 超长段落按句子分割
            sentences = re.split(r'(?<=[.!?。！？])\s+', para)
            chunk = ''
            for sent in sentences:
                if len(chunk) + len(sent) < _MAX_CHUNK:
                    chunk += (' ' if chunk else '') + sent
                else:
                    if chunk:
                        translated_parts.append(_translate_chunk(chunk))
                    chunk = sent
            if chunk:
                translated_parts.append(_translate_chunk(chunk))

    return '\n\n'.join(translated_parts)


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
        # 内容摘要翻译（前800字符）
        summary = content[:800]
        new_content = translate_to_zh(summary)
        if new_content != summary:
            item['content'] = new_content
            item['content_en'] = content

    return item


def translate_news_items(items: list, source_filter: str = '') -> list:
    """
    并发批量翻译新闻标题和内容为中文
    只翻译非中文内容，中文源自动跳过
    """
    to_translate = []
    for item in items:
        if source_filter and source_filter.lower() not in item.get('source', '').lower():
            continue
        title = item.get('title', '')
        content = item.get('content', '')
        if (title and not _is_chinese(title)) or (content and not _is_chinese(content)):
            to_translate.append(item)

    max_translate = 30
    to_translate = to_translate[:max_translate]

    if not to_translate:
        return items

    translated_count = 0
    futures = {_executor.submit(_translate_single_item, item): item for item in to_translate}
    for future in as_completed(futures, timeout=60):
        try:
            future.result(timeout=15)
            translated_count += 1
        except Exception as e:
            logger.debug(f"翻译单条失败: {e}")

    if translated_count > 0:
        logger.info(f"✅ 并发翻译完成: {translated_count}/{len(to_translate)} 条新闻")
    return items
