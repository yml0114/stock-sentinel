"""
翻译模块 v3 — 用AI模型(mimo-v2.5-pro)批量翻译，替代不可靠的免费API
"""
import re
import json
import logging
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

import config

logger = logging.getLogger(__name__)

# 翻译缓存（内存）
_cache: dict[str, str] = {}
_CACHE_MAX = 5000


def _is_chinese(text: str) -> bool:
    if not text:
        return True
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    return chinese_chars / max(len(text), 1) > 0.3


def _batch_translate_ai(texts: list[str], batch_size: int = 20) -> dict[str, str]:
    """用AI模型批量翻译 — 一次请求翻译多条，高效可靠"""
    result = {}
    if not texts:
        return result

    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        # 构建编号列表
        numbered = "\n".join(f"{j+1}. {t}" for j, t in enumerate(batch))
        prompt = f"""请将以下英文/葡语/德语新闻标题翻译为中文。直接输出翻译结果，保持编号格式，不要添加任何解释。

{numbered}"""

        try:
            resp = requests.post(
                f"{config.AI_API_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {config.AI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": config.AI_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 2000,
                    "temperature": 0.1,
                },
                timeout=30,
            )
            data = resp.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            if not content:
                content = data.get("choices", [{}])[0].get("message", {}).get("reasoning_content", "")

            # 解析编号结果: "1. 中文翻译\n2. 中文翻译"
            for line in content.strip().split("\n"):
                line = line.strip()
                m = re.match(r'^(\d+)[.\s、]+(.+)', line)
                if m:
                    idx = int(m.group(1)) - 1
                    translated = m.group(2).strip()
                    if 0 <= idx < len(batch) and translated:
                        result[batch[idx]] = translated

            logger.info(f"AI翻译批次 {i//batch_size + 1}: 输入{len(batch)}条, 成功{sum(1 for t in batch if t in result)}条")

        except Exception as e:
            logger.error(f"AI翻译批次 {i//batch_size + 1} 失败: {e}")

    return result


def translate_news_items(items: list, source_filter: str = '') -> list:
    """批量翻译新闻标题和内容为中文 — 用AI模型，一次搞定"""
    # 收集需要翻译的文本（去重）
    to_translate = []
    seen = set()
    for item in items:
        if source_filter and source_filter.lower() not in item.get('source', '').lower():
            continue
        title = item.get('title', '')
        if title and not _is_chinese(title) and title not in seen:
            # 检查内存缓存
            if title in _cache:
                item['title_cn'] = _cache[title]
            else:
                to_translate.append(title)
                seen.add(title)

    if not to_translate:
        return items

    logger.info(f"AI翻译: {len(to_translate)}条英文标题待翻译")

    # 批量翻译
    translations = _batch_translate_ai(to_translate)

    # 更新缓存
    _cache.update(translations)
    if len(_cache) > _CACHE_MAX:
        # 简单清理：删除一半旧缓存
        keys = list(_cache.keys())
        for k in keys[:len(keys)//2]:
            del _cache[k]

    # 回填到items
    translated_count = 0
    for item in items:
        title = item.get('title', '')
        if title in translations:
            item['title_cn'] = translations[title]
            translated_count += 1

    logger.info(f"翻译完成: {translated_count}/{len(to_translate)} 条")
    return items
