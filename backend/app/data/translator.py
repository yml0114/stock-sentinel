"""
翻译模块 v3 — 用AI模型批量翻译 + 单条翻译兼容
"""
import re
import json
import logging
import requests

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


def _ai_translate(texts: list[str]) -> dict[str, str]:
    """用AI模型批量翻译"""
    result = {}
    if not texts:
        return result

    # 分批，每批15条（避免超时）
    batch_size = 15
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        numbered = "\n".join(f"{j+1}. {t}" for j, t in enumerate(batch))
        prompt = f"翻译为中文，只输出翻译结果，保持编号格式：\n{numbered}"

        try:
            resp = requests.post(
                f"{config.AI_API_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {config.AI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "mimo-v2.5",  # 用非思考模型，避免reasoning消耗所有tokens
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 2000,
                    "temperature": 0.1,
                },
                timeout=30,
            )
            data = resp.json()
            msg = data.get("choices", [{}])[0].get("message", {})
            content = msg.get("content", "")
            # 思考模型可能把结果放在reasoning_content
            if not content or not re.search(r'\d+[.、]', content):
                content = msg.get("reasoning_content", "")

            # 解析编号结果
            logger.info(f"AI返回 content={content[:200]!r}, reasoning={msg.get('reasoning_content','')[:100]!r}")
            for line in content.strip().split("\n"):
                line = line.strip()
                if not line:
                    continue
                m = re.match(r'^(\d+)[.\s、\)）]+(.+)', line)
                if m:
                    idx = int(m.group(1)) - 1
                    translated = m.group(2).strip()
                    # 清理markdown格式
                    translated = re.sub(r'\*\*|__', '', translated)
                    if 0 <= idx < len(batch) and translated and _is_chinese(translated):
                        result[batch[idx]] = translated

            ok = sum(1 for t in batch if t in result)
            logger.info(f"AI翻译批次 {i//batch_size + 1}: {ok}/{len(batch)} 成功")

        except Exception as e:
            logger.error(f"AI翻译批次失败: {e}")

    return result


def translate_to_zh(text: str) -> str:
    """单条翻译（兼容旧接口）"""
    if not text or _is_chinese(text):
        return text
    if text in _cache:
        return _cache[text]
    result = _ai_translate([text])
    if text in result:
        _cache[text] = result[text]
        return result[text]
    return text


def translate_news_items(items: list, source_filter: str = '') -> list:
    """批量翻译新闻标题"""
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

    if not to_translate:
        return items

    logger.info(f"AI翻译: {len(to_translate)}条待翻译")
    translations = _ai_translate(to_translate)

    _cache.update(translations)

    translated_count = 0
    for item in items:
        title = item.get('title', '')
        if title in translations:
            item['title_cn'] = translations[title]
            translated_count += 1

    logger.info(f"翻译完成: {translated_count}/{len(to_translate)} 条")
    return items
