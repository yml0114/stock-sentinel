"""
翻译模块 v2 — 4引擎并行竞争，取最快结果 + 引擎黑名单 + 批量优化
"""
import re
import json
import time
import logging
import requests
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)

# 翻译缓存（内存）
_cache: dict[str, str] = {}
_CACHE_MAX = 5000

# SimplyTranslate 每次最大字符限制
_MAX_CHUNK = 450

# 引擎黑名单（运行时自动维护，避免反复等待超时引擎）
_engine_blacklist: dict[str, float] = {}  # engine_name -> blacklisted_until_time
_ENGINE_BLACKLIST_TTL = 600  # 10分钟后重试

# 全局线程池（复用，避免每次创建销毁）
_pool = ThreadPoolExecutor(max_workers=8, thread_name_prefix='translate')


def _is_chinese(text: str) -> bool:
    if not text:
        return True
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    return chinese_chars / max(len(text), 1) > 0.3


def _is_blacklisted(engine_name: str) -> bool:
    if engine_name not in _engine_blacklist:
        return False
    if time.time() > _engine_blacklist[engine_name]:
        del _engine_blacklist[engine_name]
        return False
    return True


def _blacklist_engine(engine_name: str):
    _engine_blacklist[engine_name] = time.time() + _ENGINE_BLACKLIST_TTL
    logger.debug(f"翻译引擎 {engine_name} 加入黑名单 {_ENGINE_BLACKLIST_TTL}s")


def _simplytranslate(text: str) -> str:
    """SimplyTranslate — Google Translate 代理，国内可用"""
    try:
        encoded = urllib.parse.quote(text[:_MAX_CHUNK])
        resp = requests.get(
            f"https://simplytranslate.org/api/translate?from=en&to=zh&text={encoded}",
            timeout=4,
        )
        if resp.status_code == 200:
            data = resp.json()
            result = data.get("translated_text", "")
            if result:
                return result
    except Exception:
        pass
    return ""


def _jina_translate(text: str) -> str:
    """jina.ai LLM 翻译，免费"""
    try:
        prompt = f"Translate to Chinese. Output ONLY the translation:\n{text[:400]}"
        encoded = urllib.parse.quote(prompt)
        resp = requests.get(
            f"https://s.jina.ai/{encoded}",
            headers={"Accept": "text/plain"},
            timeout=6,
        )
        if resp.status_code == 200:
            result = resp.text.strip()
            result = re.sub(r'^["\']|["\']$', '', result)
            result = re.sub(r'^(Translation|翻译)[：:]\s*', '', result)
            if result and result != text:
                return result
    except Exception:
        pass
    return ""


def _youdao_translate(text: str) -> str:
    """有道翻译 — 备用"""
    try:
        resp = requests.post(
            "https://fanyi.youdao.com/translate",
            params={"doctype": "json", "type": "AUTO2AUTO"},
            data={"i": text[:500]},
            timeout=4,
        )
        if resp.status_code == 200:
            data = resp.json()
            results = []
            for seg_list in data.get("translateResult", []):
                for seg in seg_list:
                    if seg.get("tgt"):
                        results.append(seg["tgt"])
            return "".join(results)
    except Exception:
        pass
    return ""


def _mymemory_translate(text: str) -> str:
    """MyMemory 翻译 — 第四备用"""
    try:
        encoded = urllib.parse.quote(text[:500])
        resp = requests.get(
            f"https://api.mymemory.translated.net/get?q={encoded}&langpair=en|zh-CN",
            timeout=5,
        )
        if resp.status_code == 200:
            data = resp.json()
            result = data.get("responseData", {}).get("translatedText", "")
            if result and result.lower() != text.lower():
                return result
    except Exception:
        pass
    return ""


# 引擎列表（按速度排序）
_ENGINES = [
    ('simply', _simplytranslate),
    ('youdao', _youdao_translate),
    ('mymemory', _mymemory_translate),
    ('jina', _jina_translate),
]


def _translate_chunk(text: str) -> str:
    """翻译单个chunk — 多引擎并行竞争，取最快结果 + 黑名单"""
    if not text or len(text.strip()) < 3:
        return text

    if _is_chinese(text):
        return text

    # 查缓存
    if text in _cache:
        return _cache[text]

    # 选出未黑名单的引擎
    active_engines = [(name, fn) for name, fn in _ENGINES if not _is_blacklisted(name)]
    if not active_engines:
        # 所有引擎都黑名单了，用第一个
        active_engines = [_ENGINES[0]]

    # 并行竞争
    translated = ""
    futures = {}
    for name, fn in active_engines:
        futures[_pool.submit(fn, text)] = name

    for future in as_completed(futures, timeout=8):
        engine_name = futures[future]
        try:
            result = future.result()
            if result and result != text:
                translated = result
                # 取消其他
                for f in futures:
                    f.cancel()
                break
        except Exception:
            _blacklist_engine(engine_name)
            continue

    if translated:
        if len(_cache) < _CACHE_MAX:
            _cache[text] = translated
        return translated

    return text


def translate_to_zh(text: str) -> str:
    """翻译英文 → 中文（支持长文本分块翻译）"""
    if not text or len(text.strip()) < 3:
        return text

    if _is_chinese(text):
        return text

    paragraphs = text.split('\n\n')

    if len(text) <= _MAX_CHUNK:
        return _translate_chunk(text)

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
        summary = content[:800]
        new_content = translate_to_zh(summary)
        if new_content != summary:
            item['content'] = new_content
            item['content_en'] = content

    return item


def translate_news_items(items: list, source_filter: str = '') -> list:
    """并发批量翻译新闻标题和内容为中文 — 容错：翻译失败不阻塞新闻返回"""
    to_translate = []
    for item in items:
        if source_filter and source_filter.lower() not in item.get('source', '').lower():
            continue
        title = item.get('title', '')
        content = item.get('content', '')
        if (title and not _is_chinese(title)) or (content and not _is_chinese(content)):
            to_translate.append(item)

    max_translate = 50
    to_translate = to_translate[:max_translate]

    if not to_translate:
        return items

    translated_count = 0
    failed_count = 0
    futures = {_pool.submit(_translate_single_item, item): item for item in to_translate}
    try:
        for future in as_completed(futures, timeout=90):
            try:
                future.result(timeout=10)
                translated_count += 1
            except Exception:
                failed_count += 1
    except Exception as e:
        # 超时：已完成的保留，未完成的不阻塞
        for f in futures:
            if f.done():
                try:
                    f.result()
                    translated_count += 1
                except Exception:
                    failed_count += 1
            else:
                failed_count += 1
        logger.warning(f"翻译超时: {translated_count}完成, {failed_count}未完成")

    if translated_count > 0:
        logger.info(f"翻译完成: {translated_count}/{len(to_translate)} 条 (失败{failed_count})")
    return items
