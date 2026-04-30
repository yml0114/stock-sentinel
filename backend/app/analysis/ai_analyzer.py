"""
AI 分析引擎 — OpenAI SDK 调用
仅在事件触发时调用，控制成本
v2: 新增个股画像综合研判
"""
import logging
from openai import OpenAI

import config
from app.data.research_intel import format_profile_for_ai

logger = logging.getLogger(__name__)

# ── 事件分析 Prompt ──
SYSTEM_PROMPT = """你是一位专业的A股投资分析助手。你的任务是对股票异动事件进行简明分析。

分析要求：
1. 用2-3句话总结事件的核心含义
2. 判断短期影响方向（利好/利空/中性）
3. 如果是全球新闻，评估对A股的具体影响板块
4. 给出简要的操作建议

注意：
- 不要给出具体的买卖价格
- 强调风险，不做承诺
- 保持客观中立
- 控制在200字以内
"""

# ── 个股画像分析 Prompt ──
PROFILE_SYSTEM_PROMPT = """你是一位专业的A股投资分析师，擅长综合多维度数据进行个股研判。

你的分析框架：
1. 技术面：价格vs主力成本、趋势方向
2. 基本面：一致预期EPS/PE、盈利能力
3. 资金面：机构参与度、持仓变化、北向资金
4. 消息面：最新研报评级、行业政策
5. 估值面：当前PE vs 一致预期PE、目标价空间

输出要求：
- 综合评分：0-100分（50为中性）
- 多空理由：各2-3条
- 策略建议：短线/中线视角
- 风险提示：1-2条
- 控制在300字以内
- 强调仅供参考，不构成投资建议
"""

# AI 调用计数器
ai_call_count: int = 0


def get_client() -> OpenAI:
    """获取 OpenAI 客户端"""
    return OpenAI(
        api_key=config.AI_API_KEY,
        base_url=config.AI_API_URL,
        timeout=30,
    )


def _call_ai(system: str, user: str, max_tokens: int = 500) -> str:
    """通用AI调用封装"""
    global ai_call_count

    if not config.AI_API_KEY:
        return "（AI分析未配置：缺少 API_KEY）"

    try:
        client = get_client()
        response = client.chat.completions.create(
            model=config.AI_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=max_tokens,
            temperature=0.3,
        )
        ai_call_count += 1
        msg = response.choices[0].message
        # 思考模型(如mimo-v2.5-pro)回复在reasoning_content
        content = (msg.content or '').strip()
        if not content:
            reasoning = getattr(msg, 'reasoning_content', '') or ''
            content = reasoning.strip()
        return content if content else '（AI分析返回为空）'
    except Exception as e:
        logger.error(f"AI 调用失败: {e}")
        return f"（AI分析失败: {str(e)[:200]}）"


def analyze_event(event: dict, quote: dict = None) -> str:
    """
    分析单个事件（同步调用，由 scheduler 在线程中执行）
    ~500 tokens input → ~200 tokens output
    """
    prompt = f"事件类型: {event.get('event_type', '')}\n"
    prompt += f"事件标题: {event.get('title', '')}\n"
    prompt += f"事件详情: {event.get('detail', '')}\n"

    if quote:
        prompt += f"\n当前行情:\n"
        prompt += f"  股票: {quote.get('stock_name', '')}({quote.get('stock_code', '')})\n"
        prompt += f"  现价: {quote.get('price', 0):.2f}\n"
        prompt += f"  涨跌幅: {quote.get('change_pct', 0):+.2f}%\n"
        prompt += f"  成交额: {quote.get('amount', 0):.0f}\n"

    result = _call_ai(SYSTEM_PROMPT, prompt, max_tokens=500)
    logger.info(f"🤖 AI事件分析完成: {event.get('title', '')[:50]}...")
    return result


def analyze_news(news_item: dict) -> str:
    """
    分析全球新闻对A股的影响（同步调用）
    """
    prompt = "以下是全球新闻，请评估其对A股市场的影响：\n\n"
    prompt += f"来源: {news_item.get('source', '')}\n"
    prompt += f"标题: {news_item.get('title', '')}\n"
    prompt += f"内容: {news_item.get('content', '')[:500]}\n"
    prompt += f"时间: {news_item.get('time', '')}\n"

    if news_item.get("matched_keywords"):
        prompt += f"关键词: {', '.join(news_item['matched_keywords'])}\n"
    if news_item.get("related_sectors"):
        prompt += f"关联板块: {', '.join(news_item['related_sectors'])}\n"

    prompt += "\n请简要评估此新闻对A股的影响方向和影响板块，控制在200字以内。"

    result = _call_ai(SYSTEM_PROMPT, prompt, max_tokens=500)
    logger.info(f"🤖 AI新闻分析完成: {news_item.get('title', '')[:50]}...")
    return result


def analyze_profile(profile: dict) -> str:
    """
    个股画像综合研判 — 整合研报+评级+机构+千股千评+行情
    ~1000 tokens input → ~300 tokens output
    """
    # 用 research_intel 的格式化函数生成输入
    profile_text = format_profile_for_ai(profile)

    # 补充当前价格和目标价信息
    current_price = profile.get("currentPrice", 0)
    target_price = profile.get("targetPrice")
    if current_price and target_price:
        upside = (target_price - current_price) / current_price * 100
        profile_text += f"📈 价格分析:\n"
        profile_text += f"  当前价: ¥{current_price:.2f}\n"
        profile_text += f"  目标价: ¥{target_price:.0f}\n"
        profile_text += f"  潜在空间: {upside:+.1f}%\n\n"

    result = _call_ai(PROFILE_SYSTEM_PROMPT, profile_text, max_tokens=800)
    logger.info(f"🤖 AI画像分析完成: {profile.get('code', '')}")
    return result


def get_ai_call_count() -> int:
    """获取 AI 调用次数"""
    return ai_call_count


def reset_ai_call_count():
    """重置 AI 调用计数"""
    global ai_call_count
    ai_call_count = 0
