"""
技术指标引擎 — 纯Python实现，无外部依赖
支持: MA, EMA, RSI, MACD, KDJ, BOLL, VOL分析
输入: K线数据列表 [{date, open, close, high, low, volume}]
输出: 带指标的K线数据 + 信号摘要
"""
import math
from typing import Optional


def _closes(data: list[dict]) -> list[float]:
    return [float(d.get("close", 0)) for d in data]


def _highs(data: list[dict]) -> list[float]:
    return [float(d.get("high", 0)) for d in data]


def _lows(data: list[dict]) -> list[float]:
    return [float(d.get("low", 0)) for d in data]


def _volumes(data: list[dict]) -> list[float]:
    return [float(d.get("volume", 0)) for d in data]


# ── 移动平均 ──

def calc_ma(values: list[float], period: int) -> list[Optional[float]]:
    """简单移动平均"""
    result = []
    for i in range(len(values)):
        if i < period - 1:
            result.append(None)
        else:
            result.append(sum(values[i - period + 1:i + 1]) / period)
    return result


def calc_ema(values: list[float], period: int) -> list[float]:
    """指数移动平均"""
    if not values:
        return []
    k = 2 / (period + 1)
    ema = [values[0]]
    for i in range(1, len(values)):
        ema.append(values[i] * k + ema[-1] * (1 - k))
    return ema


# ── RSI (相对强弱指数) ──

def calc_rsi(closes: list[float], period: int = 14) -> list[Optional[float]]:
    """RSI: >70超买, <30超卖"""
    if len(closes) < period + 1:
        return [None] * len(closes)

    result = [None] * period
    gains, losses = [], []

    for i in range(1, period + 1):
        diff = closes[i] - closes[i - 1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))

    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    for i in range(period, len(closes)):
        if i == period:
            pass  # 已计算
        else:
            diff = closes[i] - closes[i - 1]
            avg_gain = (avg_gain * (period - 1) + max(diff, 0)) / period
            avg_loss = (avg_loss * (period - 1) + max(-diff, 0)) / period

        if avg_loss == 0:
            result.append(100.0)
        else:
            rs = avg_gain / avg_loss
            result.append(round(100 - 100 / (1 + rs), 2))

        if i > period:
            pass  # 已更新

    return result


# ── MACD ──

def calc_macd(closes: list[float], fast: int = 12, slow: int = 26, signal: int = 9) -> dict:
    """
    MACD: {dif, dea, macd_bar}
    DIF = EMA(fast) - EMA(slow)
    DEA = EMA(DIF, signal)
    MACD柱 = 2 * (DIF - DEA)
    """
    ema_fast = calc_ema(closes, fast)
    ema_slow = calc_ema(closes, slow)
    dif = [f - s for f, s in zip(ema_fast, ema_slow)]
    dea = calc_ema(dif, signal)
    macd_bar = [2 * (d - e) for d, e in zip(dif, dea)]

    return {
        "dif": [round(v, 4) for v in dif],
        "dea": [round(v, 4) for v in dea],
        "macd": [round(v, 4) for v in macd_bar],
    }


# ── KDJ (随机指标) ──

def calc_kdj(highs: list[float], lows: list[float], closes: list[float],
             n: int = 9, m1: int = 3, m2: int = 3) -> dict:
    """
    KDJ: K线, D线, J线
    RSV = (C - Ln) / (Hn - Ln) * 100
    K = SMA(RSV, m1), D = SMA(K, m2), J = 3K - 2D
    """
    length = len(closes)
    rsv = []
    for i in range(length):
        if i < n - 1:
            rsv.append(50.0)
            continue
        h = max(highs[i - n + 1:i + 1])
        l = min(lows[i - n + 1:i + 1])
        if h == l:
            rsv.append(50.0)
        else:
            rsv.append((closes[i] - l) / (h - l) * 100)

    k_vals = [50.0]
    d_vals = [50.0]
    for i in range(1, length):
        k = (m1 - 1) / m1 * k_vals[-1] + 1 / m1 * rsv[i]
        d = (m2 - 1) / m2 * d_vals[-1] + 1 / m2 * k
        k_vals.append(round(k, 2))
        d_vals.append(round(d, 2))

    j_vals = [round(3 * k - 2 * d, 2) for k, d in zip(k_vals, d_vals)]

    return {"k": k_vals, "d": d_vals, "j": j_vals}


# ── 布林带 (BOLL) ──

def calc_boll(closes: list[float], period: int = 20, std_dev: float = 2.0) -> dict:
    """
    布林带: 中轨=MA(period), 上轨=中轨+2σ, 下轨=中轨-2σ
    """
    ma = calc_ma(closes, period)
    upper = []
    lower = []
    bandwidth = []
    percent = []

    for i in range(len(closes)):
        if ma[i] is None:
            upper.append(None)
            lower.append(None)
            bandwidth.append(None)
            percent.append(None)
            continue

        window = closes[max(0, i - period + 1):i + 1]
        std = (sum((x - ma[i]) ** 2 for x in window) / len(window)) ** 0.5
        u = ma[i] + std_dev * std
        l = ma[i] - std_dev * std
        upper.append(round(u, 2))
        lower.append(round(l, 2))
        bw = (u - l) / ma[i] * 100 if ma[i] != 0 else 0
        bandwidth.append(round(bw, 2))
        pct = (closes[i] - l) / (u - l) * 100 if (u - l) != 0 else 50
        percent.append(round(pct, 2))

    return {"mid": ma, "upper": upper, "lower": lower, "bandwidth": bandwidth, "percent": percent}


# ── 成交量分析 ──

def calc_vol_ma(volumes: list[float], period: int = 5) -> list[Optional[float]]:
    return calc_ma(volumes, period)


# ── K线形态识别 ──

def detect_patterns(data: list[dict]) -> list[str]:
    """识别最近K线形态，返回信号列表"""
    if len(data) < 3:
        return []

    patterns = []
    latest = data[-1]
    prev = data[-2]
    o, c, h, l = latest["open"], latest["close"], latest["high"], latest["low"]
    po, pc = prev["open"], prev["close"]
    body = abs(c - o)
    upper_shadow = h - max(o, c)
    lower_shadow = min(o, c) - l
    total_range = h - l if h != l else 0.01

    # 十字星
    if body < total_range * 0.1 and total_range > 0:
        patterns.append("十字星 — 多空平衡，可能变盘")

    # 锤子线 (下影线长，实体小，在底部)
    if lower_shadow > body * 2 and upper_shadow < body * 0.5 and c > o:
        patterns.append("锤子线 — 底部反转信号")

    # 上吊线 (同锤子但在顶部)
    if lower_shadow > body * 2 and upper_shadow < body * 0.5 and c < o:
        patterns.append("上吊线 — 顶部反转警告")

    # 射击之星
    if upper_shadow > body * 2 and lower_shadow < body * 0.5 and c < o:
        patterns.append("射击之星 — 顶部反转信号")

    # 吞没形态
    if c > o and pc < po and o <= pc and c >= po:
        patterns.append("看涨吞没 — 强烈做多信号")
    if c < o and pc > po and o >= pc and c <= po:
        patterns.append("看跌吞没 — 强烈做空信号")

    # 三连阳/三连阴
    if len(data) >= 3:
        d1, d2, d3 = data[-3], data[-2], data[-1]
        if d1["close"] > d1["open"] and d2["close"] > d2["open"] and d3["close"] > d3["open"]:
            patterns.append("三连阳 — 多头强势")
        if d1["close"] < d1["open"] and d2["close"] < d2["open"] and d3["close"] < d3["open"]:
            patterns.append("三连阴 — 空头强势")

    # 大阳线/大阴线
    if total_range > 0 and body / total_range > 0.7:
        if c > o:
            patterns.append("大阳线 — 多头主导")
        else:
            patterns.append("大阴线 — 空头主导")

    # 缩量反弹/放量下跌
    if len(data) >= 5:
        avg_vol = sum(d["volume"] for d in data[-6:-1]) / 5
        latest_vol = latest["volume"]
        if latest_vol < avg_vol * 0.5 and c > o:
            patterns.append("缩量上涨 — 上攻动能不足")
        if latest_vol > avg_vol * 2 and c < o:
            patterns.append("放量下跌 — 恐慌抛售")

    return patterns


# ── 技术信号汇总 ──

def generate_signals(data: list[dict]) -> dict:
    """
    计算所有技术指标并生成信号汇总
    返回: {indicators, signals, patterns, summary}
    """
    if not data:
        return {"indicators": {}, "signals": [], "patterns": [], "summary": "数据不足"}

    closes = _closes(data)
    highs = _highs(data)
    lows = _lows(data)
    volumes = _volumes(data)
    n = len(closes)

    # ── 计算指标 ──
    ma5 = calc_ma(closes, 5)
    ma10 = calc_ma(closes, 10)
    ma20 = calc_ma(closes, 20)
    ma60 = calc_ma(closes, 60)
    rsi = calc_rsi(closes, 14)
    macd = calc_macd(closes)
    kdj = calc_kdj(highs, lows, closes)
    boll = calc_boll(closes)
    vol_ma5 = calc_vol_ma(volumes, 5)
    vol_ma10 = calc_vol_ma(volumes, 10)

    indicators = {
        "ma5": ma5, "ma10": ma10, "ma20": ma20, "ma60": ma60,
        "rsi": rsi,
        "macd": macd,
        "kdj": kdj,
        "boll": boll,
        "vol_ma5": vol_ma5, "vol_ma10": vol_ma10,
    }

    # ── 生成信号 ──
    signals = []
    latest_close = closes[-1]

    # RSI信号
    if rsi[-1] is not None:
        if rsi[-1] > 80:
            signals.append({"type": "danger", "source": "RSI", "text": f"RSI={rsi[-1]:.1f} 严重超买"})
        elif rsi[-1] > 70:
            signals.append({"type": "warning", "source": "RSI", "text": f"RSI={rsi[-1]:.1f} 超买区间"})
        elif rsi[-1] < 20:
            signals.append({"type": "bullish", "source": "RSI", "text": f"RSI={rsi[-1]:.1f} 严重超卖"})
        elif rsi[-1] < 30:
            signals.append({"type": "info", "source": "RSI", "text": f"RSI={rsi[-1]:.1f} 超卖区间"})

    # MACD信号
    if n >= 2:
        dif = macd["dif"][-1]
        dea = macd["dea"][-1]
        prev_dif = macd["dif"][-2]
        prev_dea = macd["dea"][-2]
        if prev_dif <= prev_dea and dif > dea:
            signals.append({"type": "bullish", "source": "MACD", "text": "MACD金叉 — 做多信号"})
        elif prev_dif >= prev_dea and dif < dea:
            signals.append({"type": "danger", "source": "MACD", "text": "MACD死叉 — 做空信号"})
        if dif > 0 and dea > 0 and macd["macd"][-1] > 0:
            signals.append({"type": "info", "source": "MACD", "text": "MACD零轴上方运行 — 多头趋势"})

    # KDJ信号
    k, d, j = kdj["k"][-1], kdj["d"][-1], kdj["j"][-1]
    if k > 80 and d > 80:
        signals.append({"type": "warning", "source": "KDJ", "text": f"KDJ({k:.0f},{d:.0f},{j:.0f}) 超买"})
    elif k < 20 and d < 20:
        signals.append({"type": "info", "source": "KDJ", "text": f"KDJ({k:.0f},{d:.0f},{j:.0f}) 超卖"})
    if n >= 2:
        pk, pd = kdj["k"][-2], kdj["d"][-2]
        if pk <= pd and k > d:
            signals.append({"type": "bullish", "source": "KDJ", "text": "KDJ金叉"})
        elif pk >= pd and k < d:
            signals.append({"type": "danger", "source": "KDJ", "text": "KDJ死叉"})

    # 布林带信号
    if boll["upper"][-1] is not None:
        if latest_close >= boll["upper"][-1]:
            signals.append({"type": "warning", "source": "BOLL", "text": "触及布林上轨 — 短期压力"})
        elif latest_close <= boll["lower"][-1]:
            signals.append({"type": "info", "source": "BOLL", "text": "触及布林下轨 — 短期支撑"})
        bw = boll["bandwidth"][-1]
        if bw is not None and bw < 5:
            signals.append({"type": "info", "source": "BOLL", "text": f"布林带收口({bw:.1f}%) — 变盘在即"})

    # 均线多头/空头排列
    if all(v is not None for v in [ma5[-1], ma10[-1], ma20[-1], ma60[-1]]):
        if ma5[-1] > ma10[-1] > ma20[-1] > ma60[-1]:
            signals.append({"type": "bullish", "source": "MA", "text": "均线多头排列 — 强势上涨"})
        elif ma5[-1] < ma10[-1] < ma20[-1] < ma60[-1]:
            signals.append({"type": "danger", "source": "MA", "text": "均线空头排列 — 弱势下跌"})

    # ── K线形态 ──
    patterns = detect_patterns(data)

    # ── 综合评分 ──
    score = 50  # 基准50分
    for sig in signals:
        if sig["type"] == "bullish":
            score += 8
        elif sig["type"] == "danger":
            score -= 8
        elif sig["type"] == "warning":
            score -= 4
        elif sig["type"] == "info":
            score += 2

    for p in patterns:
        if any(k in p for k in ["看涨", "锤子", "三连阳", "大阳"]):
            score += 5
        elif any(k in p for k in ["看跌", "射击", "三连阴", "大阴", "上吊"]):
            score -= 5

    score = max(0, min(100, score))

    if score >= 75:
        summary = "强势看多"
    elif score >= 60:
        summary = "偏多"
    elif score >= 40:
        summary = "中性震荡"
    elif score >= 25:
        summary = "偏空"
    else:
        summary = "强势看空"

    return {
        "indicators": indicators,
        "signals": signals,
        "patterns": patterns,
        "score": score,
        "summary": summary,
        "latest": {
            "close": latest_close,
            "rsi": rsi[-1] if rsi[-1] is not None else 0,
            "macd_dif": macd["dif"][-1],
            "macd_dea": macd["dea"][-1],
            "kdj_k": k,
            "kdj_d": d,
            "kdj_j": j,
            "boll_upper": boll["upper"][-1],
            "boll_mid": boll["mid"][-1],
            "boll_lower": boll["lower"][-1],
        },
    }
