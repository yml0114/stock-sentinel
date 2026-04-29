"""
免费翻译模块 — Google Translate 无需API Key

用途：将彭博社等英文新闻翻译为中文
批量翻译效率：15条约8秒，不影响整体采集
"""
import urllib.request
import urllib.parse
import json
import re
import logging

logger = logging.getLogger(__name__)

# Google Translate 免费接口（无需Key）
_TRANSLATE_URL = "https://translate.googleapis.com/translate_a/single"


def translate_to_zh(text: str) -> str:
    """
    翻译英文/其他语言 → 中文（简体）
    免费，无需API Key
    """
    if not text or len(text.strip()) < 3:
        return text

    # 检测是否已经是中文
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    if chinese_chars / max(len(text), 1) > 0.3:
        return text  # 已是中文，不翻译

    try:
        params = urllib.parse.urlencode({
            'client': 'gtx',
            'sl': 'auto',
            'tl': 'zh-CN',
            'dt': 't',
            'q': text,
        })
        url = f"{_TRANSLATE_URL}?{params}"
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'
        })
        resp = urllib.request.urlopen(req, timeout=8)
        data = json.loads(resp.read().decode('utf-8', errors='ignore'))

        # 拼接翻译结果
        translated = ''.join(seg[0] for seg in data[0] if seg[0])
        return translated
    except Exception as e:
        logger.warning(f"翻译失败，返回原文: {e}")
        return text


def translate_news_items(items: list[dict], source_filter: str = '') -> list[dict]:
    """
    批量翻译新闻标题和内容为中文
    只翻译非中文内容，中文源自动跳过
    source_filter为空时翻译所有国际源
    """
    translated_count = 0
    for item in items:
        source = item.get('source', '')
        if source_filter and source_filter.lower() not in source.lower():
            continue  # 跳过非目标源

        title = item.get('title', '')
        content = item.get('content', '')

        # 翻译标题
        if title:
            new_title = translate_to_zh(title)
            if new_title != title:
                item['title'] = new_title
                item['title_en'] = title  # 保留英文原标题
                translated_count += 1

        # 翻译内容
        if content:
            new_content = translate_to_zh(content)
            if new_content != content:
                item['content'] = new_content
                item['content_en'] = content  # 保留英文原内容

    if translated_count > 0:
        logger.info(f"✅ 已翻译 {translated_count} 条 {source_filter} 新闻为中文")
    return items
