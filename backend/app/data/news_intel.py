"""
全球新闻情报层 v2 — 12源聚合 + 智能去重 + AI影响评估

数据源（全部免费，已验证可用）：
━━ 国内权威财经 ━━
1. 财联社全球快讯 (stock_info_global_cls)     — 实时快讯，最快速度
2. 东方财富全球快讯 (stock_info_global_em)     — 200条滚动，覆盖面最广
3. 同花顺全球快讯 (stock_info_global_ths)      — 带链接
4. 富途全球快讯 (stock_info_global_futu)       — 港美股视角
5. 新浪全球快讯 (stock_info_global_sina)       — 综合
6. 央视新闻 (news_cctv)                       — 政策/宏观权威
7. 财新新闻 (stock_news_main_cx)              — 深度财经
8. 东方财富个股新闻 (stock_news_em)            — 个股关联
9. 百度经济日历 (news_economic_baidu)          — 全球宏观经济数据

━━ 国际权威媒体（RSS） ━━
10. Bloomberg (via RSSHub)                      — 全球顶级财经
11. CNBC Top News                              — 美股/全球
12. MarketWatch                                — 市场动态
13. FXStreet                                   — 外汇/大宗/宏观
14. SeekingAlpha                               — 美股深度分析

分层策略：
- 第一层：多源采集 + 智能去重（免费）
- 第二层：关键词过滤（免费，毫秒级）→ 筛出可能影响A股的新闻
- 第三层：AI影响评估（付费，仅对过滤后的新闻）→ 判断利好/利空
"""
import akshare as ak
import logging
import re
import hashlib
import urllib.request
from datetime import datetime
from difflib import SequenceMatcher
from concurrent.futures import ThreadPoolExecutor, as_completed
from app.data.translator import translate_news_items
from app.data.cn_news import fetch_wallstreetcn, fetch_wallstreetcn_articles, fetch_cls as fetch_cls_api, fetch_cn_financial_news

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════
# 关键词库
# ══════════════════════════════════════════

KEYWORDS_HIGH = [
    # 央行政策
    '降息', '加息', '降准', 'MLF', 'LPR', '美联储', 'Fed', '利率决议',
    'QE', '缩表', '逆回购', '国债', '货币政策', 'interest rate', 'FOMC',
    # 地缘/贸易
    '制裁', '关税', 'tariff', '贸易战', 'trade war', '冲突', '战争', '封锁', '禁运',
    '台海', '南海', '朝鲜', '伊朗', 'Iran', '俄乌', 'Russia', 'Ukraine',
    # 经济数据
    'GDP', 'CPI', 'PPI', 'PMI', '非农', 'nonfarm', '失业率', 'unemployment',
    '社融', 'M2', '进出口', '贸易顺差', '贸易逆差', 'inflation',
    # 市场冲击
    '暴跌', '熔断', '崩盘', 'circuit breaker', '黑天鹅', 'black swan',
    '退市', 'ST', '立案', '处罚', '暴雷', 'default', 'crash',
    # 大公司/科技
    'Apple', '苹果', 'NVIDIA', '英伟达', 'Tesla', '特斯拉',
    'Microsoft', 'Google', 'Meta', 'OpenAI', 'DeepSeek',
    '台积电', 'TSMC', 'ASML', 'Samsung', '三星',
    # 大宗商品
    'oil', '原油', 'gold', '黄金', 'copper', '铜', 'lithium', '锂',
]

KEYWORDS_SECTOR = {
    'AI': ['人工智能', '大模型', 'GPT', '算力', 'GPU', '英伟达', 'NVIDIA', 'ChatGPT', 'DeepSeek', 'AI agent'],
    '芯片': ['半导体', '芯片', '台积电', 'ASML', '光刻机', 'EDA', '封装', 'semiconductor', 'chip'],
    '新能源': ['光伏', '锂电', '储能', '新能源', '碳中和', '风电', 'solar', 'lithium'],
    '消费': ['白酒', '茅台', '消费', '零售', '餐饮', 'retail', 'consumer'],
    '医药': ['医药', '创新药', '疫苗', '集采', 'FDA', '医疗器械', 'pharma', 'biotech'],
    '地产': ['房地产', '楼市', '恒大', '碧桂园', '万科', '保交楼', 'real estate'],
    '金融': ['银行', '券商', '保险', '信托', '基金', 'bank', 'insurance'],
    '汽车': ['新能源车', '智能驾驶', '自动驾驶', '特斯拉', '比亚迪', 'EV', 'autonomous'],
    '军工': ['军工', '国防', '导弹', '航空母舰', '歼20', 'defense', 'military'],
    '稀土': ['稀土', '锗', '镓', '钨', '钼', 'rare earth'],
    '石油': ['原油', '石油', 'OPEC', 'oil', 'crude', 'petroleum'],
}


# ══════════════════════════════════════════
# 去重引擎
# ══════════════════════════════════════════

# 源优先级：数字越小越优先（彭博=1, 财新=2, 其他=9）
SOURCE_PRIORITY = {
    'Bloomberg': 1,
    '财新': 2,
    '华尔街见闻': 3,
    '央视新闻': 3,
    '财联社': 4,
    '财联社API': 4,
    '东方财富': 5,
    '同花顺': 5,
    '富途': 5,
    '新浪财经': 5,
    'CNBC': 6,
    'MarketWatch': 6,
    'FXStreet': 6,
    'SeekingAlpha': 6,
}


class NewsDeduplicator:
    """智能去重 — 标题相似度 + 内容指纹 + 源优先级（彭博/财新优先保留）

    改进策略：
    - 多层相似度检测：SequenceMatcher + 最长公共子串比率 + 字符集交集
    - 同一来源更严格的去重阈值
    - 更好的标题清洗：去除来源前缀、常见填充词
    """

    def __init__(self, similarity_threshold: float = 0.60):
        self._seen_hashes: dict = {}         # 精确哈希 → source_name
        self._seen_titles: list = []         # (title_clean, source_name, time_str)
        self._threshold = similarity_threshold
        # 同源去重使用更低阈值（同一来源的标题更可能重复）
        self._same_source_threshold = 0.45

    def _get_priority(self, source: str) -> int:
        return SOURCE_PRIORITY.get(source, 9)

    def _lcs_ratio(self, s1: str, s2: str) -> float:
        """最长公共子串比率（比SequenceMatcher更适合检测部分重叠的标题）"""
        if not s1 or not s2:
            return 0.0
        # 优化：如果长度差异太大，直接跳过
        if len(s1) > len(s2) * 3 or len(s2) > len(s1) * 3:
            return 0.0
        m, n = len(s1), len(s2)
        # 滚动数组优化
        prev = [0] * (n + 1)
        max_len = 0
        for i in range(1, m + 1):
            curr = [0] * (n + 1)
            for j in range(1, n + 1):
                if s1[i-1] == s2[j-1]:
                    curr[j] = prev[j-1] + 1
                    max_len = max(max_len, curr[j])
            prev = curr
        return max_len * 2 / (m + n) if (m + n) > 0 else 0.0

    def _char_set_ratio(self, s1: str, s2: str) -> float:
        """字符集交集比率（快速判断两个标题是否谈论同一件事）"""
        if not s1 or not s2:
            return 0.0
        set1 = set(s1.replace(' ', ''))
        set2 = set(s2.replace(' ', ''))
        if not set1 or not set2:
            return 0.0
        intersection = len(set1 & set2)
        return intersection * 2 / (len(set1) + len(set2))

    def _is_similar(self, t1: str, t2: str, same_source: bool = False) -> bool:
        """综合判断两个标题是否相似（多策略融合）"""
        threshold = self._same_source_threshold if same_source else self._threshold

        # 策略1: SequenceMatcher（经典编辑距离相似度）
        seq_ratio = SequenceMatcher(None, t1, t2).ratio()
        if seq_ratio >= threshold:
            return True

        # 策略2: 最长公共子串比率（适合检测"XX宣布YY" vs "XX：YY"这类变体）
        lcs_ratio = self._lcs_ratio(t1, t2)
        # LCS阈值比SequenceMatcher略高（LCS更容易产生假阳性）
        lcs_threshold = threshold + 0.10
        if lcs_ratio >= lcs_threshold:
            return True

        # 策略3: 字符集交集（快速检测"同一件事"，最宽松）
        # 只有当标题较长时才使用（短标题字符集太小，容易误判）
        if len(t1) > 10 and len(t2) > 10:
            char_ratio = self._char_set_ratio(t1, t2)
            char_threshold = threshold + 0.15
            if char_ratio >= char_threshold:
                # 字符集匹配时，再验证SequenceMatcher至少达到较低阈值
                if seq_ratio >= (threshold - 0.15):
                    return True

        return False

    def is_duplicate(self, title: str, content: str = "", source: str = "", time: str = "") -> bool:
        """判断是否重复新闻，高优先级源可替换低优先级的重复条目"""
        if not title or len(title.strip()) < 5:
            return True

        my_priority = self._get_priority(source)
        title_clean = self._clean_title(title)

        # 标题太短清洗后可能为空
        if len(title_clean) < 3:
            return True

        # 1. 精确哈希去重
        text_hash = hashlib.md5(title.strip().encode()).hexdigest()
        if text_hash in self._seen_hashes:
            existing_src = self._seen_hashes[text_hash]
            if my_priority < self._get_priority(existing_src):
                self._seen_hashes[text_hash] = source
            return True

        # 2. 标题相似度去重（同一件事不同媒体报道）
        for i, (seen_title, seen_src, _) in enumerate(self._seen_titles):
            is_same_src = self._normalize_source(source) == self._normalize_source(seen_src)
            if self._is_similar(title_clean, seen_title, same_source=is_same_src):
                # 高优先级源 → 替换这条记录（保留更好的来源）
                if my_priority < self._get_priority(seen_src):
                    self._seen_titles[i] = (title_clean, source, time)
                return True

        # 3. 通过，记录
        self._seen_hashes[text_hash] = source
        self._seen_titles.append((title_clean, source, time))
        # 保持列表大小（避免内存增长）
        if len(self._seen_titles) > 3000:
            self._seen_titles = self._seen_titles[-1500:]
            self._seen_hashes = {k: v for k, v in list(self._seen_hashes.items())[-1500:]}

        return False

    def _normalize_source(self, source: str) -> str:
        """归一化来源名称（合并同一实体的不同名称）"""
        source_map = {
            '财联社API': '财联社',
            'Bloomberg (via 华尔街见闻)': 'Bloomberg',
            'CNBC (via 华尔街见闻)': 'CNBC',
            'WSJ (via 华尔街见闻)': 'WSJ',
            'FT (via 华尔街见闻)': 'Financial Times',
            'Reuters (via 华尔街见闻)': 'Reuters',
        }
        return source_map.get(source, source)

    def _clean_title(self, title: str) -> str:
        """清洗标题，去除噪音字符和来源前缀"""
        # 去除方括号标签及其内容（如"【财联社】""[快讯]"）
        title = re.sub(r'[【\[（\(][A-Za-z\u4e00-\u9fff]{1,10}[】\]）\)]', '', title)
        # 去除来源冒号前缀（如"财联社：""快讯："）
        title = re.sub(r'^[A-Za-z\u4e00-\u9fff]{1,10}[：:\s]+', '', title)
        # 去除特殊标点（保留中文和字母数字）
        title = re.sub(r'[^\w\s\u4e00-\u9fff]', '', title)
        # 去除常见填充词
        fillers = ['快讯', '突发', '重磅', '最新', '独家', '更新', '早报', '晚报', '午间']
        for f in fillers:
            title = title.replace(f, '')
        title = re.sub(r'\s+', ' ', title).strip()
        return title.lower()

    @property
    def stats(self) -> dict:
        return {
            "seen_hashes": len(self._seen_hashes),
            "seen_titles": len(self._seen_titles),
        }


# 全局去重器实例
_dedup = NewsDeduplicator()


# ══════════════════════════════════════════
# 国内新闻源（AKShare）
# ══════════════════════════════════════════

def fetch_cls_news() -> list[dict]:
    """财联社全球快讯 — 最快的中文财经快讯"""
    try:
        df = ak.stock_info_global_cls()
        results = []
        for _, row in df.iterrows():
            results.append({
                'source': '财联社',
                'source_type': 'domestic',
                'title': str(row.get('标题', '')),
                'content': str(row.get('内容', '')),
                'time': f"{row.get('发布日期', '')} {row.get('发布时间', '')}",
            })
        return results
    except Exception as e:
        logger.error(f"财联社快讯获取失败: {e}")
        return []


def fetch_em_news() -> list[dict]:
    """东方财富全球快讯 — 200条滚动，覆盖面最广"""
    try:
        df = ak.stock_info_global_em()
        results = []
        for _, row in df.iterrows():
            results.append({
                'source': '东方财富',
                'source_type': 'domestic',
                'title': str(row.get('标题', '')),
                'content': str(row.get('摘要', '')),
                'time': str(row.get('发布时间', '')),
                'url': str(row.get('链接', '')),
            })
        return results
    except Exception as e:
        logger.error(f"东方财富快讯获取失败: {e}")
        return []


def fetch_ths_news() -> list[dict]:
    """同花顺全球快讯"""
    try:
        df = ak.stock_info_global_ths()
        results = []
        for _, row in df.iterrows():
            results.append({
                'source': '同花顺',
                'source_type': 'domestic',
                'title': str(row.get('标题', '')),
                'content': str(row.get('内容', '')),
                'time': str(row.get('发布时间', '')),
                'url': str(row.get('链接', '')),
            })
        return results
    except Exception as e:
        logger.error(f"同花顺快讯获取失败: {e}")
        return []


def fetch_futu_news() -> list[dict]:
    """富途全球快讯 — 港美股视角"""
    try:
        df = ak.stock_info_global_futu()
        results = []
        for _, row in df.iterrows():
            results.append({
                'source': '富途',
                'source_type': 'domestic',
                'title': str(row.get('标题', '')),
                'content': str(row.get('内容', '')),
                'time': str(row.get('发布时间', '')),
                'url': str(row.get('链接', '')),
            })
        return results
    except Exception as e:
        logger.error(f"富途快讯获取失败: {e}")
        return []


def fetch_sina_news() -> list[dict]:
    """新浪财经全球快讯"""
    try:
        df = ak.stock_info_global_sina()
        results = []
        for _, row in df.iterrows():
            content = str(row.get('内容', ''))
            results.append({
                'source': '新浪财经',
                'source_type': 'domestic',
                'title': content[:60] if content else '',
                'content': content,
                'time': str(row.get('时间', '')),
            })
        return results
    except Exception as e:
        logger.error(f"新浪财经快讯获取失败: {e}")
        return []


def fetch_cctv_news() -> list[dict]:
    """央视新闻 — 政策/宏观权威来源"""
    try:
        df = ak.news_cctv()
        results = []
        for _, row in df.iterrows():
            results.append({
                'source': '央视新闻',
                'source_type': 'domestic',
                'title': str(row.get('title', '')),
                'content': str(row.get('content', '')),
                'time': str(row.get('date', '')),
                'priority': 'high',  # 央视新闻默认高优先级
            })
        return results
    except Exception as e:
        logger.error(f"央视新闻获取失败: {e}")
        return []


def fetch_caixin_news() -> list[dict]:
    """财新新闻 — 深度财经
    从 AKShare stock_news_main_cx() 获取，字段有: summary, url, tag
    summary 通常包含完整摘要/引言，直接作为 content 使用
    title 从 summary 前60字截取（接口无独立 title 字段）
    """
    try:
        df = ak.stock_news_main_cx()
        results = []
        for _, row in df.iterrows():
            summary = str(row.get('summary', '')).strip()
            if not summary or len(summary) < 5:
                continue
            # 尝试从 summary 中分离标题（通常第一句是标题）
            # 财新的 summary 格式: "标题。详细内容..." 或 "标题：详细内容..."
            title = ''
            content = summary
            # 按句号、冒号分割，第一段作为标题
            for sep in ['。', '：', ':', '；', '\n']:
                if sep in summary:
                    parts = summary.split(sep, 1)
                    candidate = parts[0].strip()
                    # 标题通常较短（<80字）
                    if 5 < len(candidate) < 80:
                        title = candidate
                        content = summary
                        break
            if not title:
                title = summary[:80].rstrip()
            
            results.append({
                'source': '财新',
                'source_type': 'domestic',
                'title': title,
                'content': content,  # 完整 summary，不截断
                'url': str(row.get('url', '')),
                'tag': str(row.get('tag', '')),
            })
        return results
    except Exception as e:
        logger.error(f"财新新闻获取失败: {e}")
        return []


def fetch_stock_news(stock_code: str) -> list[dict]:
    """个股新闻"""
    try:
        df = ak.stock_news_em(symbol=stock_code)
        results = []
        for _, row in df.head(10).iterrows():
            results.append({
                'source': str(row.get('文章来源', '')),
                'source_type': 'stock',
                'title': str(row.get('新闻标题', '')),
                'content': str(row.get('新闻内容', '')),
                'time': str(row.get('发布时间', '')),
                'url': str(row.get('新闻链接', '')),
                'stock_code': stock_code,
            })
        return results
    except Exception as e:
        logger.error(f"个股新闻获取失败 {stock_code}: {e}")
        return []


def fetch_economic_calendar() -> list[dict]:
    """百度经济日历 — 全球宏观经济数据"""
    try:
        df = ak.news_economic_baidu()
        results = []
        today = datetime.now().strftime('%Y-%m-%d')
        for _, row in df.iterrows():
            date_str = str(row.get('日期', ''))
            if date_str != today:
                continue
            importance = int(row.get('重要性', 0))
            if importance < 2:
                continue
            results.append({
                'source': '经济日历',
                'source_type': 'macro',
                'title': f"[{row.get('地区', '')}] {row.get('事件', '')}",
                'content': f"公布: {row.get('公布', '-')} | 预期: {row.get('预期', '-')} | 前值: {row.get('前值', '-')}",
                'time': f"{date_str} {row.get('时间', '')}",
                'importance': importance,
            })
        return results
    except Exception as e:
        logger.error(f"经济日历获取失败: {e}")
        return []


# ══════════════════════════════════════════
# 国际新闻源（RSS）
# ══════════════════════════════════════════

RSS_SOURCES = [
    ('Bloomberg', 'https://rsshub.rssforever.com/bloomberg'),
    ('CNBC', 'https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114'),
    ('MarketWatch', 'https://feeds.marketwatch.com/marketwatch/topstories/'),
    ('FXStreet', 'https://www.fxstreet.com/rss/news'),
    ('SeekingAlpha', 'https://seekingalpha.com/market_currents.xml'),
    # 财新 — 通过RSSHub镜像免费获取全文（无需订阅）
    ('财新', 'https://rsshub.rssforever.com/caixin/latest'),
]

# RSS不可达源黑名单（运行时自动维护，避免重复等待超时）
_rss_blacklist: set = set()
_RSS_BLACKLIST_TTL = 300  # 5分钟后重试
_rss_blacklist_time: dict = {}


def fetch_rss_news() -> list[dict]:
    """从国际RSS源并发抓取（并行 + 黑名单自动降级）"""
    results = []
    now = __import__('time').time()
    
    # 清理过期黑名单
    expired = [k for k, t in _rss_blacklist_time.items() if now - t > _RSS_BLACKLIST_TTL]
    for k in expired:
        _rss_blacklist.discard(k)
        _rss_blacklist_time.pop(k, None)
    
    # 过滤黑名单源
    active_sources = [(name, url) for name, url in RSS_SOURCES if name not in _rss_blacklist]
    if not active_sources:
        logger.debug("所有RSS源均在黑名单中，跳过")
        return []
    
    def _fetch_single_rss(name_url):
        name, url = name_url
        items = []
        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'
            })
            resp = urllib.request.urlopen(req, timeout=5)  # 降低到5秒
            data = resp.read().decode('utf-8', errors='ignore')
            
            rss_items = re.findall(r'<item>(.*?)</item>', data, re.DOTALL)
            for item in rss_items[:15]:
                title_m = re.search(r'<title><!\[CDATA\[(.+?)\]\]></title>|<title>([^<]+)</title>', item)
                desc_m = re.search(r'<description><!\[CDATA\[(.+?)\]\]></description>|<description>([^<]+)</description>', item, re.DOTALL)
                link_m = re.search(r'<link>([^<]+)</link>', item)
                date_m = re.search(r'<pubDate>([^<]+)</pubDate>', item)
                
                title = ''
                if title_m:
                    title = html_module.unescape((title_m.group(1) or title_m.group(2) or '')).strip()
                
                if not title or len(title) < 10 or title in ('Top Stories', 'US Top News and Analysis'):
                    continue
                
                desc = ''
                if desc_m:
                    desc = html_module.unescape(re.sub(r'<[^>]+>', '', (desc_m.group(1) or desc_m.group(2) or ''))).strip()
                
                items.append({
                    'source': name,
                    'source_type': 'international',
                    'title': title,
                    'content': desc,
                    'time': (date_m.group(1) if date_m else ''),
                    'url': (link_m.group(1) if link_m else ''),
                })
        except Exception as e:
            # 加入黑名单
            _rss_blacklist.add(name)
            _rss_blacklist_time[name] = now
            logger.warning(f"RSS源 {name} 获取失败(已加入黑名单): {e}")
        return (name, items)
    
    # 并发抓取所有RSS源
    with ThreadPoolExecutor(max_workers=len(active_sources)) as pool:
        futures = {pool.submit(_fetch_single_rss, src): src[0] for src in active_sources}
        for future in as_completed(futures, timeout=12):  # 总超时12秒
            try:
                name, items = future.result(timeout=6)
                results.extend(items)
                logger.debug(f"  RSS {name}: {len(items)}条")
            except Exception:
                pass
    
    return results


# ══════════════════════════════════════════
# 关键词过滤 + 严重度评估
# ══════════════════════════════════════════

def keyword_filter(news: list[dict]) -> list[dict]:
    """
    关键词匹配（免费，零成本）
    返回命中的新闻 + 命中的关键词 + 关联板块 + 严重度
    """
    filtered = []

    for item in news:
        title = item.get('title', '')
        content = item.get('content', '')
        text = (title + ' ' + content).lower()

        # 关键词匹配
        matched_keywords = []
        for kw in KEYWORDS_HIGH:
            if kw.lower() in text:
                matched_keywords.append(kw)

        # 板块关联
        related_sectors = []
        for sector, keywords in KEYWORDS_SECTOR.items():
            for kw in keywords:
                if kw.lower() in text:
                    related_sectors.append(sector)
                    break

        if matched_keywords or related_sectors:
            # 严重度评估
            severity = 'info'
            high_severity_kw = ['暴跌', '熔断', '制裁', '战争', '退市', 'crash', 'default', 'black swan']
            if any(kw in text for kw in high_severity_kw):
                severity = 'high'
            elif len(matched_keywords) >= 2:
                severity = 'high'
            elif matched_keywords or related_sectors:
                severity = 'medium'

            # 国际新闻加权（通常对全球市场影响更大）
            if item.get('source_type') == 'international':
                if severity == 'medium':
                    severity = 'high'

            filtered.append({
                **item,
                'matched_keywords': matched_keywords,
                'related_sectors': list(set(related_sectors)),
                'severity': severity,
            })

    return filtered


# ══════════════════════════════════════════
# 聚合入口
# ══════════════════════════════════════════

# 并发线程池（AKShare源慢，用线程池并行抓取）
_executor = ThreadPoolExecutor(max_workers=6, thread_name_prefix='news')


def fetch_all_news(stock_codes: list[str] = None) -> list[dict]:
    """
    聚合所有新闻源 → 智能去重 → 关键词过滤
    返回过滤后的需要AI评估的新闻列表
    """
    all_news = []

    # ━━ 国际RSS源（一次抓取，按优先级排列）━━
    try:
        all_rss = fetch_rss_news()
        bloomberg = [x for x in all_rss if x.get('source') == 'Bloomberg']
        other_rss = [x for x in all_rss if x.get('source') != 'Bloomberg']
        all_news.extend(bloomberg)   # 彭博优先
        all_news.extend(other_rss)
        logger.debug(f"  国际RSS: {len(bloomberg)} Bloomberg + {len(other_rss)} 其他")
    except Exception as e:
        logger.warning(f"  国际RSS 失败: {e}")

    # ━━ 财新（深度媒体，优先采集）━━
    try:
        caixin_items = fetch_caixin_news()
        all_news.extend(caixin_items)
        logger.debug(f"  ★ 财新: {len(caixin_items)}条")
    except Exception as e:
        logger.warning(f"  ★ 财新 失败: {e}")

    # ━━ 华尔街见闻 + 财联社API（Bloomberg内容的中文搬运，全文可用）━━
    try:
        cn_items = fetch_cn_financial_news(limit_per_source=30)
        all_news.extend(cn_items)
        logger.debug(f"  ★ 华尔街见闻+财联社API: {len(cn_items)}条")
    except Exception as e:
        logger.warning(f"  ★ 华尔街见闻+财联社API 失败: {e}")

    # ━━ 翻译所有含英文的新闻（不限于国际源）━━
    translate_news_items(all_news)

    # ━━ AKShare源并发（第三梯队，总超时20秒）━━
    ak_sources = [
        ("财联社", fetch_cls_news),
        ("东方财富", fetch_em_news),
        ("同花顺", fetch_ths_news),
        ("富途", fetch_futu_news),
        ("新浪财经", fetch_sina_news),
        ("央视新闻", fetch_cctv_news),
        ("经济日历", fetch_economic_calendar),
    ]

    futures = {_executor.submit(fn): name for name, fn in ak_sources}
    for future in as_completed(futures, timeout=20):
        name = futures[future]
        try:
            items = future.result(timeout=15)
            all_news.extend(items)
            logger.debug(f"  {name}: {len(items)}条")
        except Exception as e:
            logger.warning(f"  {name} 失败: {e}")


    # ━━ 个股新闻 ━━
    if stock_codes:
        for code in stock_codes:
            try:
                items = fetch_stock_news(code)
                all_news.extend(items)
            except Exception:
                pass

    # ━━ 智能去重 ━━
    deduped = []
    for item in all_news:
        if not _dedup.is_duplicate(
            item.get('title', ''), item.get('content', ''),
            item.get('source', ''), item.get('time', '')
        ):
            deduped.append(item)

    stats_before = len(all_news)
    stats_after = len(deduped)

    # ━━ 关键词过滤 ━━
    filtered = keyword_filter(deduped)

    logger.info(
        f"📰 新闻采集: {stats_before}条 → 去重后{stats_after}条 → 过滤后{len(filtered)}条需关注"
    )
    return filtered


def fetch_all_raw(stock_codes: list[str] = None) -> list[dict]:
    """
    获取所有原始新闻（不去重不过滤），用于前端展示完整新闻流
    """
    all_news = []

    # 国际RSS源（一次抓取，按源拆分）
    try:
        all_rss = fetch_rss_news()
        bloomberg = [x for x in all_rss if x.get('source') == 'Bloomberg']
        other_rss = [x for x in all_rss if x.get('source') != 'Bloomberg']
        all_news.extend(bloomberg)   # 彭博优先放最前面
        all_news.extend(other_rss)
    except Exception:
        pass

    # 财新（深度媒体优先）
    try:
        all_news.extend(fetch_caixin_news())
    except Exception:
        pass

    # 华尔街见闻 + 财联社API（全文内容）
    try:
        all_news.extend(fetch_cn_financial_news(limit_per_source=30))
    except Exception:
        pass

    # 翻译所有含英文的新闻（不限于国际源）
    translate_news_items(all_news)

    # AKShare源并发
    ak_fetchers = [
        fetch_cls_news, fetch_em_news, fetch_ths_news,
        fetch_futu_news, fetch_sina_news, fetch_cctv_news,
        fetch_economic_calendar,
    ]

    futures = {_executor.submit(fn): fn.__name__ for fn in ak_fetchers}
    for future in as_completed(futures, timeout=25):
        try:
            items = future.result(timeout=15)
            all_news.extend(items)
        except Exception:
            pass

    if stock_codes:
        for code in stock_codes:
            try:
                all_news.extend(fetch_stock_news(code))
            except Exception:
                pass

    # ━━ 去重（raw也去重，避免前端显示重复条目）━━
    raw_dedup = NewsDeduplicator(similarity_threshold=0.60)
    deduped_raw = []
    for item in all_news:
        if not raw_dedup.is_duplicate(
            item.get('title', ''), item.get('content', ''),
            item.get('source', ''), item.get('time', '')
        ):
            deduped_raw.append(item)
    logger.info(f"📰 原始新闻流: {len(all_news)}条 → 去重后{len(deduped_raw)}条")

    # 按时间倒序排列（最新在前），而不是按源排
    deduped_raw.sort(key=lambda x: x.get('time', ''), reverse=True)
    return deduped_raw


def format_for_ai(news_item: dict) -> str:
    """格式化新闻为AI分析的输入"""
    source_label = news_item.get('source', '')
    source_type = news_item.get('source_type', '')
    if source_type == 'international':
        source_label += ' [国际]'

    text = f"来源: {source_label}\n"
    text += f"标题: {news_item.get('title', '')}\n"
    text += f"内容: {news_item.get('content', '')[:500]}\n"
    text += f"时间: {news_item.get('time', '')}\n"
    if news_item.get('matched_keywords'):
        text += f"关键词: {', '.join(news_item['matched_keywords'])}\n"
    if news_item.get('related_sectors'):
        text += f"关联板块: {', '.join(news_item['related_sectors'])}\n"
    return text
