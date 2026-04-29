"""
券商研报数据层 — 整合AKShare研报/分析师/机构数据

数据源（全部免费，已验证可用）：
1. stock_research_report_em  — 券商研报（含PDF链接、评级、盈利预测）
2. stock_analyst_rank_em     — 分析师排行（收益率、最新评级）
3. stock_comment_em           — 千股千评（机构参与度、综合得分）
4. stock_institute_hold       — 机构持仓变化
"""
import akshare as ak
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# ── 缓存 ──
_report_cache: dict[str, list] = {}
_comment_cache: dict[str, dict] = {}


def get_stock_reports(stock_code: str, limit: int = 10) -> dict:
    """
    获取个股券商研报（含评级、盈利预测、PDF链接）
    返回: {reports: [...], consensus: {...}}
    """
    cache_key = f"{stock_code}_{limit}"
    if cache_key in _report_cache:
        return _report_cache[cache_key]

    try:
        df = ak.stock_research_report_em(symbol=stock_code)
        if df is None or df.empty:
            return {"reports": [], "consensus": {}}

        reports = []
        ratings = []
        eps_2026_list = []
        eps_2027_list = []
        pe_2026_list = []
        pe_2027_list = []

        for _, row in df.head(limit).iterrows():
            report = {
                "title": str(row.get("报告名称", "")),
                "institution": str(row.get("机构", "")),
                "rating": str(row.get("东财评级", "")),
                "date": str(row.get("日期", "")),
                "pdfUrl": str(row.get("报告PDF链接", "")),
                "industry": str(row.get("行业", "")),
                "eps2026": _safe_float(row.get("2026-盈利预测-收益")),
                "pe2026": _safe_float(row.get("2026-盈利预测-市盈率")),
                "eps2027": _safe_float(row.get("2027-盈利预测-收益")),
                "pe2027": _safe_float(row.get("2027-盈利预测-市盈率")),
            }
            reports.append(report)

            # 统计评级分布
            rating = report["rating"]
            if rating:
                ratings.append(rating)

            # 统计一致预期
            if report["eps2026"]:
                eps_2026_list.append(report["eps2026"])
            if report["eps2027"]:
                eps_2027_list.append(report["eps2027"])
            if report["pe2026"]:
                pe_2026_list.append(report["pe2026"])
            if report["pe2027"]:
                pe_2027_list.append(report["pe2027"])

        # 计算一致预期
        consensus = _calc_consensus(ratings, eps_2026_list, eps_2027_list,
                                     pe_2026_list, pe_2027_list)

        result = {"reports": reports, "consensus": consensus}
        _report_cache[cache_key] = result
        return result

    except Exception as e:
        logger.error(f"获取研报失败 {stock_code}: {e}")
        return {"reports": [], "consensus": {}}


def get_analyst_ranking(stock_code: str = None, limit: int = 10) -> list[dict]:
    """
    获取分析师排行
    如果指定stock_code，返回推荐该股的分析师
    """
    try:
        df = ak.stock_analyst_rank_em()
        if df is None or df.empty:
            return []

        results = []
        for _, row in df.head(limit).iterrows():
            analyst = {
                "name": str(row.get("分析师名称", "")),
                "institution": str(row.get("分析师单位", "")),
                "annualIndex": _safe_float(row.get("年度指数")),
                "returnRate2024": _safe_float(row.get("2024年收益率")),
                "return3m": _safe_float(row.get("3个月收益率")),
                "return6m": _safe_float(row.get("6个月收益率")),
                "return12m": _safe_float(row.get("12个月收益率")),
                "latestStock": str(row.get("2024最新个股评级-股票名称", "")),
                "latestStockCode": str(row.get("2024最新个股评级-股票代码", "")),
                "industry": str(row.get("行业", "")),
            }
            results.append(analyst)

        return results

    except Exception as e:
        logger.error(f"获取分析师排行失败: {e}")
        return []


def get_stock_comment(stock_code: str) -> dict:
    """
    获取个股千股千评数据（机构参与度、综合得分、主力成本）
    """
    if stock_code in _comment_cache:
        return _comment_cache[stock_code]

    try:
        df = ak.stock_comment_em()
        if df is None or df.empty:
            return {}

        row = df[df["代码"] == stock_code]
        if row.empty:
            return {}

        r = row.iloc[0]
        result = {
            "code": stock_code,
            "name": str(r.get("名称", "")),
            "price": _safe_float(r.get("最新价")),
            "changePct": _safe_float(r.get("涨跌幅")),
            "turnover": _safe_float(r.get("换手率")),
            "peRatio": _safe_float(r.get("市盈率")),
            "mainCost": _safe_float(r.get("主力成本")),
            "institutionParticipation": _safe_float(r.get("机构参与度")),
            "compositeScore": _safe_float(r.get("综合得分")),
            "scoreChange": _safe_float(r.get("上升")),
            "currentRank": _safe_float(r.get("目前排名")),
            "attentionIndex": _safe_float(r.get("关注指数")),
        }
        _comment_cache[stock_code] = result
        return result

    except Exception as e:
        logger.error(f"获取千股千评失败 {stock_code}: {e}")
        return {}


def get_institution_hold_change(limit: int = 20) -> list[dict]:
    """
    获取机构持仓变化（增仓/减仓趋势）
    """
    try:
        # 获取最新季度机构持仓
        df = ak.stock_institute_hold(symbol="20241")  # 2024Q1
        if df is None or df.empty:
            return []

        results = []
        for _, row in df.head(limit).iterrows():
            results.append({
                "code": str(row.get("证券代码", "")),
                "name": str(row.get("证券简称", "")),
                "institutionCount": _safe_float(row.get("机构数")),
                "institutionCountChange": _safe_float(row.get("机构数变化")),
                "holdRatio": _safe_float(row.get("持股比例")),
                "holdRatioChange": _safe_float(row.get("持股比例增幅")),
                "floatRatio": _safe_float(row.get("占流通股比例")),
                "floatRatioChange": _safe_float(row.get("占流通股比例增幅")),
            })

        return results

    except Exception as e:
        logger.error(f"获取机构持仓失败: {e}")
        return []


def get_stock_full_profile(stock_code: str, current_price: float = 0) -> dict:
    """
    获取个股完整画像（研报+评级+机构+千股千评）
    用于AI综合研判的输入
    """
    # 研报数据
    report_data = get_stock_reports(stock_code, limit=10)

    # 千股千评
    comment = get_stock_comment(stock_code)

    # 如果有当前价格，用一致预期推算目标价
    consensus = report_data.get("consensus", {})
    target_price = None
    if current_price and consensus.get("avgPE2026") and consensus.get("avgEPS2026"):
        target_price = consensus["avgPE2026"] * consensus["avgEPS2026"]

    return {
        "code": stock_code,
        "reports": report_data.get("reports", []),
        "consensus": consensus,
        "comment": comment,
        "targetPrice": target_price,
        "currentPrice": current_price or comment.get("price", 0),
    }


def format_profile_for_ai(profile: dict) -> str:
    """
    将个股画像格式化为AI分析输入
    """
    text = f"【{profile['code']} 个股画像】\n\n"

    # 一致预期
    c = profile.get("consensus", {})
    if c:
        text += "📊 券商一致预期:\n"
        text += f"  评级分布: {c.get('ratingDistribution', {})}\n"
        if c.get("avgEPS2026"):
            text += f"  2026年EPS预测均值: {c['avgEPS2026']:.2f}元\n"
        if c.get("avgPE2026"):
            text += f"  2026年PE预测均值: {c['avgPE2026']:.1f}x\n"
        if profile.get("targetPrice"):
            text += f"  推算目标价: ¥{profile['targetPrice']:.0f}\n"
        text += f"  覆盖机构数: {c.get('reportCount', 0)}家\n\n"

    # 最新研报
    reports = profile.get("reports", [])[:3]
    if reports:
        text += "📝 最新研报:\n"
        for r in reports:
            text += f"  [{r['institution']}] {r['rating']} — {r['title'][:40]}\n"
        text += "\n"

    # 千股千评
    comment = profile.get("comment", {})
    if comment:
        text += "🏢 机构数据:\n"
        text += f"  机构参与度: {comment.get('institutionParticipation', 0):.1%}\n"
        text += f"  综合得分: {comment.get('compositeScore', 0):.1f}/100\n"
        text += f"  主力成本: ¥{comment.get('mainCost', 0):.2f}\n"
        text += f"  关注指数: {comment.get('attentionIndex', 0):.1f}\n\n"

    return text


# ── 内部工具函数 ──

def _safe_float(val) -> float:
    """安全浮点数转换"""
    try:
        if val is None or str(val).strip() in ("", "-", "nan", "NaN", "None"):
            return 0.0
        return float(val)
    except (ValueError, TypeError):
        return 0.0


def _calc_consensus(ratings, eps_2026, eps_2027, pe_2026, pe_2027) -> dict:
    """计算一致预期"""
    # 评级分布
    rating_dist = {}
    for r in ratings:
        rating_dist[r] = rating_dist.get(r, 0) + 1
    total = len(ratings) or 1
    rating_pct = {k: round(v / total * 100) for k, v in rating_dist.items()}

    return {
        "ratingDistribution": rating_pct,
        "reportCount": len(ratings),
        "avgEPS2026": round(sum(eps_2026) / len(eps_2026), 2) if eps_2026 else None,
        "avgEPS2027": round(sum(eps_2027) / len(eps_2027), 2) if eps_2027 else None,
        "avgPE2026": round(sum(pe_2026) / len(pe_2026), 1) if pe_2026 else None,
        "avgPE2027": round(sum(pe_2027) / len(pe_2027), 1) if pe_2027 else None,
        "buyRatio": rating_pct.get("买入", 0) + rating_pct.get("增持", 0),
    }
