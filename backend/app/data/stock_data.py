"""
多市场行情数据 — A股/港股/美股
A股行情: 新浪hq.sinajs.cn  K线: 新浪CN_MarketData
港股行情: 新浪hq.sinajs.cn  K线: 腾讯ifzq.gtimg.cn
美股行情: 新浪hq.sinajs.cn  K线: 新浪US_MinKService
搜索: 东财searchapi (type=14 全市场)
"""
import requests
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
_SINA_HEADERS = {**_HEADERS, "Referer": "https://finance.sina.com.cn/"}

# 东财搜索API
_SEARCH_URL = "https://searchapi.eastmoney.com/api/suggest/get"
_EM_TOKEN = "D43BF722C8E33BDC906FB84D85E326E8"

# 新浪行情API
_SINA_HQ_URL = "https://hq.sinajs.cn/list="
# 新浪A股K线API
_SINA_KLINE_URL = "https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData"
# 腾讯K线API (港股用)
_QQ_KLINE_URL = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
# 新浪美股K线API
_SINA_US_KLINE_URL = "https://stock.finance.sina.com.cn/usstock/api/json_v2.php/US_MinKService.getDailyK"


# ══════════════════════════════════════════
# 市场识别
# ══════════════════════════════════════════

def detect_market(code: str, market_hint: str = "") -> str:
    """识别股票市场: 'A' / 'HK' / 'US'"""
    if market_hint.upper() in ("HK", "US", "A"):
        return market_hint.upper()
    code = code.strip()
    # 港股: 5位数字 00700, 09988
    if code.isdigit() and len(code) == 5:
        return "HK"
    # A股: 6位数字 600519, 000001, 300750
    if code.isdigit() and len(code) == 6:
        return "A"
    # 美股: 字母开头 AAPL, TSLA, NVDA
    if code.isalpha():
        return "US"
    return "A"  # 默认A股


def _code_to_sina(code: str, market: str = "A") -> str:
    """股票代码 → 新浪行情格式"""
    code = code.strip()
    if market == "HK":
        return f"hk{code}"
    elif market == "US":
        return f"gb_{code.lower()}"
    else:  # A股
        if code.startswith(("6", "9")):
            return f"sh{code}"
        else:
            return f"sz{code}"


# ══════════════════════════════════════════
# 股票搜索 (东财 — 全市场)
# ══════════════════════════════════════════

def search_stocks(query: str, limit: int = 20) -> list[dict]:
    """
    股票模糊搜索 — 东财搜索建议API
    支持A股/港股/美股，按代码前缀或名称子串匹配
    返回 [{code, name, market}]
    """
    if not query or len(query.strip()) < 1:
        return []

    q = query.strip()
    try:
        resp = requests.get(_SEARCH_URL, params={
            "input": q,
            "type": "14",
            "token": _EM_TOKEN,
            "count": str(limit),
        }, headers=_HEADERS, timeout=5)
        data = resp.json()

        items = data.get("QuotationCodeTable", {}).get("Data", [])
        results = []
        for item in items:
            code = item.get("Code", "")
            name = item.get("Name", "")
            classify = item.get("Classify", "")

            # 根据Classify判断市场
            if classify == "HKStock":
                market = "HK"
            elif classify == "USStock":
                market = "US"
            elif classify == "AStock":
                market = "A" if code.startswith(("6", "9", "0", "3")) else "A"
                if code.startswith(("8", "4")):
                    market = "BJ"
            else:
                # 根据代码格式推断
                if code.isdigit() and len(code) == 5:
                    market = "HK"
                elif code.isalpha():
                    market = "US"
                elif code.startswith(("6", "9")):
                    market = "SH"
                elif code.startswith(("0", "3")):
                    market = "SZ"
                else:
                    market = ""

            results.append({"code": code, "name": name, "market": market})

        logger.info(f"搜索 '{q}' → {len(results)} 条")
        return results

    except Exception as e:
        logger.error(f"搜索失败 '{q}': {e}")
        return []


# ══════════════════════════════════════════
# 实时行情 (新浪 — A股/港股/美股)
# ══════════════════════════════════════════

def _parse_a_quote(parts: list, stock_code: str) -> dict:
    """解析A股行情 (新浪格式)"""
    name = parts[0]
    open_price = float(parts[1]) if parts[1] else 0
    prev_close = float(parts[2]) if parts[2] else 0
    price = float(parts[3]) if parts[3] else 0
    high = float(parts[4]) if parts[4] else 0
    low = float(parts[5]) if parts[5] else 0
    volume = float(parts[8]) if parts[8] else 0
    amount = float(parts[9]) if parts[9] else 0

    change_amt = price - prev_close if prev_close > 0 else 0
    change_pct = (change_amt / prev_close * 100) if prev_close > 0 else 0
    amplitude = ((high - low) / prev_close * 100) if prev_close > 0 else 0
    turnover = float(parts[32]) if len(parts) > 32 and parts[32] else 0
    pe_ratio = float(parts[39]) if len(parts) > 39 and parts[39] else 0
    market_cap = float(parts[45]) if len(parts) > 45 and parts[45] else 0

    return {
        "stock_code": stock_code, "stock_name": name, "market": "A",
        "price": round(price, 2), "change_pct": round(change_pct, 2),
        "change_amt": round(change_amt, 2), "volume": volume, "amount": amount,
        "turnover": round(turnover, 2), "high": round(high, 2), "low": round(low, 2),
        "open": round(open_price, 2), "prev_close": round(prev_close, 2),
        "amplitude": round(amplitude, 2), "pe_ratio": round(pe_ratio, 2),
        "market_cap": market_cap,
    }


def _parse_hk_quote(parts: list, stock_code: str) -> dict:
    """解析港股行情 (新浪格式)
    格式: 英文名,中文名,昨收,今开,最高,最低,现价,涨跌额,涨跌%,买入,卖出,..."""
    name = parts[1]  # 中文名
    open_price = float(parts[3]) if parts[3] else 0
    prev_close = float(parts[2]) if parts[2] else 0
    price = float(parts[6]) if parts[6] else 0
    high = float(parts[4]) if parts[4] else 0
    low = float(parts[5]) if parts[5] else 0
    change_amt = float(parts[7]) if parts[7] else 0
    change_pct = float(parts[8]) if parts[8] else 0
    volume = float(parts[11]) if len(parts) > 11 and parts[11] else 0  # 成交量
    amount = float(parts[12]) if len(parts) > 12 and parts[12] else 0  # 成交额

    amplitude = ((high - low) / prev_close * 100) if prev_close > 0 else 0

    return {
        "stock_code": stock_code, "stock_name": name, "market": "HK",
        "price": round(price, 3), "change_pct": round(change_pct, 2),
        "change_amt": round(change_amt, 3), "volume": volume, "amount": amount,
        "turnover": 0, "high": round(high, 3), "low": round(low, 3),
        "open": round(open_price, 3), "prev_close": round(prev_close, 3),
        "amplitude": round(amplitude, 2), "pe_ratio": 0, "market_cap": 0,
    }


def _parse_us_quote(parts: list, stock_code: str) -> dict:
    """解析美股行情 (新浪格式)
    格式: 名称,昨收,涨跌额,时间,涨跌%,最高,最低,开盘,52高,52低,成交量,..."""
    name = parts[0]
    prev_close = float(parts[1]) if parts[1] else 0
    change_amt = float(parts[2]) if parts[2] else 0
    change_pct = float(parts[4]) if parts[4] else 0
    high = float(parts[5]) if parts[5] else 0
    low = float(parts[6]) if parts[6] else 0
    open_price = float(parts[7]) if parts[7] else 0
    price = prev_close + change_amt  # 现价 = 昨收 + 涨跌额
    volume = float(parts[10]) if len(parts) > 10 and parts[10] else 0
    amount = float(parts[11]) if len(parts) > 11 and parts[11] else 0
    pe_ratio = float(parts[15]) if len(parts) > 15 and parts[15] else 0
    market_cap = float(parts[30]) if len(parts) > 30 and parts[30] else 0

    amplitude = ((high - low) / prev_close * 100) if prev_close > 0 else 0

    return {
        "stock_code": stock_code, "stock_name": name, "market": "US",
        "price": round(price, 4), "change_pct": round(change_pct, 2),
        "change_amt": round(change_amt, 4), "volume": volume, "amount": amount,
        "turnover": 0, "high": round(high, 4), "low": round(low, 4),
        "open": round(open_price, 4), "prev_close": round(prev_close, 4),
        "amplitude": round(amplitude, 2), "pe_ratio": round(pe_ratio, 2),
        "market_cap": market_cap,
    }


def get_batch_quotes(stock_codes: list[str], market_map: dict = None) -> list[dict]:
    """
    批量获取实时行情 — 新浪行情API (A股/港股/美股混合)
    market_map: {code: 'A'|'HK'|'US'} 可选，不传则自动识别
    """
    if not stock_codes:
        return []

    # 构建新浪代码列表
    sina_items = []  # [(sina_code, stock_code, market)]
    for code in stock_codes:
        market = (market_map or {}).get(code) or detect_market(code)
        sina_items.append((_code_to_sina(code, market), code, market))

    sina_codes = ",".join(item[0] for item in sina_items)

    try:
        resp = requests.get(f"{_SINA_HQ_URL}{sina_codes}", headers=_SINA_HEADERS, timeout=8)
        resp.encoding = "gbk"

        results = []
        lines = resp.text.strip().split("\n")
        for i, line in enumerate(lines):
            if '="' not in line or i >= len(sina_items):
                continue

            data_str = line.split('"')[1] if '"' in line else ""
            if not data_str:
                continue

            parts = data_str.split(",")
            _, stock_code, market = sina_items[i]

            try:
                if market == "HK" and len(parts) >= 10:
                    results.append(_parse_hk_quote(parts, stock_code))
                elif market == "US" and len(parts) >= 10:
                    results.append(_parse_us_quote(parts, stock_code))
                elif len(parts) >= 32:
                    results.append(_parse_a_quote(parts, stock_code))
                else:
                    logger.warning(f"数据字段不足 {stock_code} ({market}): {len(parts)} fields")
            except (ValueError, IndexError) as e:
                logger.warning(f"解析行情失败 {stock_code}: {e}")

        logger.debug(f"批量行情 → {len(results)} 条")
        return results

    except Exception as e:
        logger.error(f"批量行情失败: {e}")
        return []


def get_realtime_quote(stock_code: str, market: str = "") -> dict:
    """获取单只股票实时行情"""
    m = market or detect_market(stock_code)
    quotes = get_batch_quotes([stock_code], {stock_code: m})
    if quotes:
        return quotes[0]
    return {
        "stock_code": stock_code, "stock_name": "未知", "market": m,
        "price": 0, "change_pct": 0, "change_amt": 0,
        "volume": 0, "amount": 0, "turnover": 0,
        "high": 0, "low": 0, "open": 0, "prev_close": 0,
        "amplitude": 0, "pe_ratio": 0, "market_cap": 0,
    }


# ══════════════════════════════════════════
# K线历史 (多源: A股新浪 / 港股腾讯 / 美股新浪US)
# ══════════════════════════════════════════

def _get_a_kline(stock_code: str, period: str = "daily", days: int = 120) -> list[dict]:
    """A股K线 — 新浪CN_MarketData"""
    sina_code = _code_to_sina(stock_code, "A")
    scale_map = {
        "1m": "1", "5m": "5", "15m": "15", "30m": "30", "60m": "60",
        "daily": "240", "weekly": "1680", "monthly": "7200"
    }
    scale = scale_map.get(period, "240")
    datalen = min(days, 5) if period.endswith('m') else days

    try:
        resp = requests.get(_SINA_KLINE_URL, params={
            "symbol": sina_code, "scale": scale, "ma": "no", "datalen": str(datalen),
        }, headers=_SINA_HEADERS, timeout=10)
        data = json.loads(resp.text)
        if not data:
            return []

        results = []
        prev_close = 0
        for item in data:
            close = float(item.get("close", 0))
            open_p = float(item.get("open", 0))
            high = float(item.get("high", 0))
            low = float(item.get("low", 0))
            volume = float(item.get("volume", 0))
            date = item.get("day", "")

            change_amt = close - prev_close if prev_close > 0 else 0
            change_pct = (change_amt / prev_close * 100) if prev_close > 0 else 0
            amplitude = ((high - low) / prev_close * 100) if prev_close > 0 else 0

            results.append({
                "date": date, "open": open_p, "close": close,
                "high": high, "low": low, "volume": volume, "amount": 0,
                "amplitude": round(amplitude, 2),
                "changePct": round(change_pct, 2),
                "changeAmt": round(change_amt, 2), "turnover": 0,
            })
            prev_close = close
        return results
    except Exception as e:
        logger.error(f"A股K线失败 {stock_code}: {e}")
        return []


def _get_hk_kline(stock_code: str, period: str = "daily", days: int = 120) -> list[dict]:
    """港股K线 — 腾讯ifzq (日/周/月)"""
    period_map = {"daily": "day", "weekly": "week", "monthly": "month"}
    qq_period = period_map.get(period, "day")

    # 分钟线港股暂不支持，降级到日线
    if period.endswith('m'):
        qq_period = "day"
        days = min(days, 5)

    try:
        resp = requests.get(_QQ_KLINE_URL, params={
            "param": f"hk{stock_code},{qq_period},,,{days},qfq",
        }, headers=_HEADERS, timeout=10)
        data = resp.json()

        klines = (data.get("data", {}).get(f"hk{stock_code}", {})
                  .get(f"qfq{qq_period}",
                       data.get("data", {}).get(f"hk{stock_code}", {}).get(qq_period, [])))

        if not klines:
            return []

        results = []
        prev_close = 0
        for item in klines:
            # [日期, 开盘, 收盘, 最高, 最低, 成交量]
            date = item[0]
            open_p = float(item[1])
            close = float(item[2])
            high = float(item[3])
            low = float(item[4])
            volume = float(item[5]) if len(item) > 5 else 0

            change_amt = close - prev_close if prev_close > 0 else 0
            change_pct = (change_amt / prev_close * 100) if prev_close > 0 else 0
            amplitude = ((high - low) / prev_close * 100) if prev_close > 0 else 0

            results.append({
                "date": date, "open": open_p, "close": close,
                "high": high, "low": low, "volume": volume, "amount": 0,
                "amplitude": round(amplitude, 2),
                "changePct": round(change_pct, 2),
                "changeAmt": round(change_amt, 2), "turnover": 0,
            })
            prev_close = close
        return results
    except Exception as e:
        logger.error(f"港股K线失败 {stock_code}: {e}")
        return []


def _get_us_kline(stock_code: str, period: str = "daily", days: int = 120) -> list[dict]:
    """美股K线 — 新浪US_MinKService (仅日线)"""
    # 美股暂只支持日线
    try:
        resp = requests.get(_SINA_US_KLINE_URL, params={
            "symbol": stock_code, "datalen": str(days),
        }, headers=_SINA_HEADERS, timeout=10)
        data = json.loads(resp.text)
        if not data:
            return []

        # 只取最后days条
        data = data[-days:]

        results = []
        prev_close = 0
        for item in data:
            date = item.get("d", "")
            open_p = float(item.get("o", 0))
            close = float(item.get("c", 0))
            high = float(item.get("h", 0))
            low = float(item.get("l", 0))
            volume = float(item.get("v", 0))

            change_amt = close - prev_close if prev_close > 0 else 0
            change_pct = (change_amt / prev_close * 100) if prev_close > 0 else 0
            amplitude = ((high - low) / prev_close * 100) if prev_close > 0 else 0

            results.append({
                "date": date, "open": open_p, "close": close,
                "high": high, "low": low, "volume": volume, "amount": 0,
                "amplitude": round(amplitude, 2),
                "changePct": round(change_pct, 2),
                "changeAmt": round(change_amt, 2), "turnover": 0,
            })
            prev_close = close
        return results
    except Exception as e:
        logger.error(f"美股K线失败 {stock_code}: {e}")
        return []


def get_kline_data(stock_code: str, period: str = "daily", days: int = 120, market: str = "") -> list[dict]:
    """
    获取K线历史数据 — 自动选择数据源
    A股 → 新浪 | 港股 → 腾讯 | 美股 → 新浪US
    """
    m = market or detect_market(stock_code)

    if m == "HK":
        return _get_hk_kline(stock_code, period, days)
    elif m == "US":
        return _get_us_kline(stock_code, period, days)
    else:
        return _get_a_kline(stock_code, period, days)


# ══════════════════════════════════════════
# 兼容旧接口 (AKShare)
# ══════════════════════════════════════════

def get_stock_announcements(stock_code: str) -> list[dict]:
    """获取个股公告 (AKShare，可能失败)"""
    try:
        import akshare as ak
        df = ak.stock_notice_report(symbol=stock_code)
        results = []
        for _, row in df.head(10).iterrows():
            results.append({
                "code": stock_code,
                "title": str(row.get("公告标题", row.get("标题", ""))),
                "date": str(row.get("公告日期", row.get("日期", ""))),
                "type": str(row.get("公告类型", row.get("类型", ""))),
                "url": str(row.get("公告链接", row.get("链接", ""))),
            })
        return results
    except Exception:
        return []


def get_northbound_flow() -> dict:
    """获取北向资金流向 (AKShare，可能失败)"""
    try:
        import akshare as ak
        df = ak.stock_hsgt_north_net_flow_in_em(symbol="北上")
        if df.empty:
            return {"date": "", "net_flow": 0}
        latest = df.iloc[-1]
        return {
            "date": str(latest.get("date", latest.get("日期", ""))),
            "net_flow": float(latest.get("value", latest.get("当日净流入", 0)) or 0),
        }
    except Exception:
        return {"date": "", "net_flow": 0}
