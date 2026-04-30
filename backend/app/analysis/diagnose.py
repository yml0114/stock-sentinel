"""
AI 诊断引擎 — 综合技术指标+K线形态+消息面，调用DeepSeek生成专业分析报告
"""
import logging
import requests
from typing import Optional

import config
from app.analysis.indicators import generate_signals

logger = logging.getLogger(__name__)


def _build_prompt(stock_code: str, stock_name: str, market: str,
                  kline_data: list[dict], signals: dict, news: list[dict] = None) -> str:
    """构建AI分析prompt"""

    # 最近5天K线摘要
    recent = kline_data[-5:] if len(kline_data) >= 5 else kline_data
    kline_summary = ""
    for d in recent:
        kline_summary += (
            f"  {d['date']}: 开{d['open']:.2f} 收{d['close']:.2f} "
            f"高{d['high']:.2f} 低{d['low']:.2f} 量{d['volume']:.0f}\n"
        )

    # 技术信号
    signal_text = "\n".join(f"  - [{s['source']}] {s['text']}" for s in signals.get("signals", []))
    if not signal_text:
        signal_text = "  无明显技术信号"

    # K线形态
    pattern_text = "\n".join(f"  - {p}" for p in signals.get("patterns", []))
    if not pattern_text:
        pattern_text = "  无明显K线形态"

    # 指标快照
    latest = signals.get("latest", {})
    indicator_text = (
        f"  RSI(14)={latest.get('rsi', 0):.1f} | "
        f"MACD DIF={latest.get('macd_dif', 0):.3f} DEA={latest.get('macd_dea', 0):.3f} | "
        f"KDJ({latest.get('kdj_k', 0):.0f},{latest.get('kdj_d', 0):.0f},{latest.get('kdj_j', 0):.0f}) | "
        f"BOLL上={latest.get('boll_upper', 0):.2f} 中={latest.get('boll_mid', 0):.2f} 下={latest.get('boll_lower', 0):.2f}"
    )

    # 新闻摘要
    news_text = ""
    if news:
        news_text = "\n".join(f"  - {n.get('title', '')}" for n in news[:5])
        news_text = f"\n最近相关新闻:\n{news_text}"

    market_cn = {"A": "A股", "HK": "港股", "US": "美股"}.get(market, "A股")

    prompt = f"""你是一位专业的{market_cn}分析师，请对以下股票进行综合技术分析。

股票: {stock_name}({stock_code})
市场: {market_cn}
综合技术评分: {signals.get('score', 50)}/100 ({signals.get('summary', '中性')})

最近5日K线:
{kline_summary}
技术指标快照:
{indicator_text}

技术信号:
{signal_text}

K线形态:
{pattern_text}
{news_text}

请从以下维度进行分析，给出简洁专业的研判:
1. 【趋势判断】当前处于什么趋势？(上升/下降/震荡)
2. 【关键价位】近期支撑位和压力位
3. 【技术面评分】技术指标综合判断
4. 【风险提示】需要注意的风险点
5. 【操作建议】短期操作建议(观望/轻仓/加仓/减仓)

要求: 直接给出结论，不要啰嗦，每个维度2-3句话。"""

    return prompt


def diagnose_stock(stock_code: str, stock_name: str, market: str,
                   kline_data: list[dict], news: list[dict] = None) -> dict:
    """
    AI综合诊断 — 技术指标 + K线形态 + DeepSeek分析
    返回: {signals, ai_analysis, score, summary}
    """
    # 1. 计算技术指标和信号
    signals = generate_signals(kline_data)

    # 2. 调用AI生成分析报告
    ai_analysis = ""
    try:
        prompt = _build_prompt(stock_code, stock_name, market, kline_data, signals, news)

        resp = requests.post(
            f"{config.AI_API_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {config.AI_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": config.AI_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 1500,
                "temperature": 0.3,
            },
            timeout=30,
        )
        data = resp.json()
        ai_analysis = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        # 思考模型(如mimo-v2.5-pro)回复在reasoning_content
        if not ai_analysis:
            ai_analysis = data.get("choices", [{}])[0].get("message", {}).get("reasoning_content", "")
        logger.info(f"AI诊断 {stock_code} 完成，{len(ai_analysis)} 字")
    except Exception as e:
        logger.error(f"AI诊断 {stock_code} 失败: {e}")
        ai_analysis = f"AI分析暂时不可用: {e}"

    return {
        "stock_code": stock_code,
        "stock_name": stock_name,
        "market": market,
        "signals": signals.get("signals", []),
        "patterns": signals.get("patterns", []),
        "score": signals.get("score", 50),
        "summary": signals.get("summary", "中性"),
        "indicators": signals.get("latest", {}),
        "ai_analysis": ai_analysis,
    }
