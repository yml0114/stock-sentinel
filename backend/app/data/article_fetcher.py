"""
文章正文抓取 — trafilatura 为核心引擎

策略链：
1. 华尔街见闻专用API（wallstreetcn文章）
2. trafilatura 全文提取（所有站点通用，业内最强）
3. 直接HTML抓取 + trafilatura（网络降级）

trafilatura 优势：
- 业界最强的文章正文提取，自动去除导航/广告/侧栏
- 无需维护 HTML parser，自动适配各站点结构
- 比 BeautifulSoup/readability 准确率高 30%+
"""
import re
import json
import html as html_module
import logging
import urllib.request
import urllib.parse

import trafilatura

logger = logging.getLogger(__name__)

_UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
_HEADERS = {
    'User-Agent': _UA,
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
}


# ── 噪音清理 ──

_NAV_NOISE = {
    # 中文
    '商城', '订阅', '数据', '我闻', '机构订阅', '会议', '应用下载', '帮助',
    '首页', '经济', '金融', '公司', '政经', '世界', '观点', '博客', '图片', '视频',
    '周刊', '数据通', '商圈', '企业数据库', '沪深股市', '港股', '更多',
    '科技', '地产', '汽车', '消费', '能源', '健康', '环科', '民生', 'ESG',
    '财新一线', '私房课', '运动家', '企业用户', '电邮',
    '金融我闻', '地缘图志', '数字说', '比较', '中国改革', '专题', '讣闻',
    '财新名家', '名家/新秀', '正文',
    '观点频道', '政经频道', '金融频道', '公司频道', '世界频道', '科技频道',
    '发表评论', '分享到微信朋友圈', '新浪转发',
    '网上有害信息举报专区', '责任编辑',
    'Promotion', 'mini+', 'English',
    '图片编辑', '美术编辑', '视觉编辑',
    '分享到新浪微博', '分享到微信',
    # 英文
    'skip navigation', 'markets', 'business', 'investing', 'tech',
    'politics', 'video', 'watchlist', 'investing club', 'pro',
    'livestream', 'key points', 'skip nav', 'menu',
    'sign in', 'subscribe', 'log in', 'newsletter',
    'home', 'world', 'opinion', 'sports', 'style', 'food',
    'travel', 'magazine', 'real estate', 'weather',
    'entertainment', 'health', 'science', 'education',
    'more', 'search', 'share', 'print', 'email',
    'choose cnbc.com as your preferred source',
}

_STOP_MARKERS = [
    '相关报道', '推荐阅读', '上一篇', '下一篇',
    '相关阅读', '延伸阅读', '猜你喜欢', '热门推荐',
    '图片编辑：', '美术编辑：', '视觉编辑：',
    '分享到', '发表评论', '我要纠错',
    '财新网主编精选版电邮', '财新网新闻版电邮',
    '版权所有', '本文来源', '本文仅代表',
    '图片推荐', '视听推荐', '编辑推荐',
    '版面编辑：', '责任编辑：',
    'Recommend entering Caixin Database',  # 财新广告
    '推荐进入财新数据库',
    'subscribe now', 'start your free trial',
    'sign in to continue', 'get unlimited access',
    'already a subscriber', 'download the app',
]

# 去重用标点集（用 set 比 re 替换快）
_PUNCT = set('，。、；：""\u2018\u2019\u201c\u201d（）《》【】！？~·…——,.:;-!?()[]{}\"\' \t\r\n')


def _clean_text(text: str) -> str:
    """通用文本清理：去噪音行 + 截断尾部 + HTML实体解码"""
    if not text:
        return ''

    # HTML 实体解码（&amp; → &，&lt; → <，&#x2019; → '，等）
    text = html_module.unescape(text)

    # 去除残留的HTML标签
    text = re.sub(r'<[^>]+>', '', text)

    # 去除连续多余空白
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)

    lines = text.split('\n')
    cleaned = []
    for line in lines:
        s = line.strip()
        if not s:
            if cleaned and cleaned[-1].strip():
                cleaned.append('')
            continue
        if len(s) < 2:
            continue
        # 精确匹配导航噪音
        if s in _NAV_NOISE or s.lower() in _NAV_NOISE:
            continue
        # 纯符号行
        if s in ('+', '-', '|', '/', '·', '…', '>>>'):
            continue
        # 面包屑导航（如 "观点 > 财新名家 > 名家/新秀 > 易峘 > 正文"）
        if re.match(r'^[\u4e00-\u9fff\w]+(\s*>\s*[\u4e00-\u9fff\w]+){2,}\s*$', s):
            continue
        # 纯频道列表行（短中文词用空格分隔，如 "金融我闻 地缘图志 数字说"）
        if len(s) < 60 and not re.search(r'[，。！？；：]', s) and re.match(r'^[\u4e00-\u9fff\w\s/·+]+$', s):
            if len(s.split()) >= 3:
                continue
        # 纯英文短行噪音（导航/菜单/广告）
        if len(s) < 50 and re.match(r'^[A-Za-z\s\-–—·/]+$'  , s) and not re.search(r'[.!?]', s):
            continue
        # 版权/免责声明行
        if re.match(r'^(Copyright|©|All rights reserved|Disclaimer|免责|风险提示|投资有风险)', s, re.IGNORECASE):
            continue
        # 推荐/广告行
        if re.match(r'^(推荐阅读|猜你喜欢|热门推荐|您可能感兴趣|相关推荐|点击进入|了解更多|立即查看)', s):
            continue
        # 纯日期时间行（如 "2026-04-30 15:30"）
        if re.match(r'^\d{4}[-/]\d{2}[-/]\d{2}[\sT]\d{2}:\d{2}(:\d{2})?$', s):
            continue
        # 编辑/记者署名行（短，且在正文前面）
        if len(s) < 30 and re.match(r'^(记者|编辑|作者|来源|文/|图/|摄影/)', s):
            continue
        cleaned.append(line)

    # 段落级去重（财新等付费墙预览内容经常重复段落）
    seen = set()
    deduped = []
    for line in cleaned:
        s = line.strip()
        if not s:
            deduped.append(line)
            continue
        # 规范化：删空白+删标点 → 取前40字符做key
        norm = ''.join(ch for ch in s if ch not in _PUNCT)
        key = norm[:40]
        if key in seen:
            continue
        seen.add(key)
        deduped.append(line)
    cleaned = deduped

    # 找正文开始（第一条超过40字的行）
    body_start = 0
    for i, line in enumerate(cleaned):
        if len(line.strip()) > 40:
            body_start = i
            break

    # 截断尾部噪音
    result = []
    for line in cleaned[body_start:]:
        s = line.strip()
        if any(marker in s for marker in _STOP_MARKERS):
            break
        result.append(line)

    return '\n'.join(result).strip()


def _clean_title(title: str) -> str:
    """清理标题：去除站点后缀"""
    if not title:
        return ''
    # 去掉 "_频道_站点名" 类后缀（如 "_观点频道_财新网"）
    title = re.sub(r'_[\u4e00-\u9fff\w]+频道_[\u4e00-\u9fff\w]+网?$', '', title)
    title = re.sub(r'_[\u4e00-\u9fff\w]+网$', '', title)
    title = re.sub(r'\s*[-–—|]\s*(财新网|华尔街见闻|新浪财经|澎湃新闻|界面新闻|36氪)\s*$', '', title)
    return title.strip()


# ── 华尔街见闻专用 ──

def _try_wallstreetcn(url: str) -> dict:
    """华尔街见闻文章 — 通过API获取完整正文"""
    # 匹配 articles/12345 和 livenews/12345
    m = re.search(r'(?:articles|livenews)[/\-](\d+)', url)
    if not m:
        return {}
    article_id = m.group(1)

    # 方法1: 直接抓取页面 + trafilatura
    try:
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            text = trafilatura.extract(
                downloaded,
                include_comments=False,
                include_tables=False,
                output_format='txt',
                favor_recall=True,
            )
            if text and len(text) > 200:
                title = text.split('\n')[0].strip() if '\n' in text else ''
                return {'title': title, 'text': text, 'length': len(text)}
    except Exception as e:
        logger.debug(f"华尔街见闻 trafilatura失败: {e}")

    # 方法2: API获取
    try:
        api_url = f"https://api-one-wscn.awtmt.com/apiv1/content/article/{article_id}?client=pc"
        req = urllib.request.Request(api_url, headers={'User-Agent': _UA})
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read())
        article = data.get('data', {}).get('article', {})
        title = article.get('title', '')
        content_html = article.get('content', '')
        if content_html:
            text = re.sub(r'<[^>]+>', '\n', content_html)
            text = _clean_text(text)
            if len(text) > 100:
                return {'title': title, 'text': text, 'length': len(text)}
    except Exception as e:
        logger.debug(f"华尔街见闻 API失败: {e}")

    # 方法3: 从页面HTML直接提取 og:description 和 article 标签
    try:
        req = urllib.request.Request(url, headers=_HEADERS)
        resp = urllib.request.urlopen(req, timeout=12)
        html = resp.read().decode('utf-8', errors='ignore')
        if html:
            # 提取 og:description
            desc_m = re.search(r'og:description["\s]*content="([^"]+)"', html)
            desc = html_module.unescape(desc_m.group(1)).strip() if desc_m else ''
            # 提取 article 标签内容
            art_m = re.search(r'<article[^>]*>(.*?)</article>', html, re.S)
            if art_m:
                text = re.sub(r'<[^>]+>', '\n', art_m.group(1))
                text = _clean_text(text)
                if len(text) > 50:
                    title_m = re.search(r'<title[^>]*>(.*?)</title>', html, re.S)
                    title = re.sub(r'<[^>]+>', '', title_m.group(1)).strip() if title_m else desc[:60]
                    return {'title': title, 'text': text, 'length': len(text)}
            # 如果只有 og:description（快讯类短文），也返回
            if desc and len(desc) > 30:
                title_m = re.search(r'<title[^>]*>(.*?)</title>', html, re.S)
                title = re.sub(r'<[^>]+>', '', title_m.group(1)).strip() if title_m else desc[:60]
                return {'title': title, 'text': desc, 'length': len(desc)}
    except Exception as e:
        logger.debug(f"华尔街见闻 HTML提取失败: {e}")

    return {}


# ── 通用 trafilatura 抓取 ──

def _try_trafilatura(url: str) -> dict:
    """策略: trafilatura — 业界最强正文提取"""
    try:
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            return {}

        text = trafilatura.extract(
            downloaded,
            include_comments=False,
            include_tables=False,
            output_format='txt',
            favor_recall=True,  # 召回优先，多抓正文
        )
        if not text or len(text) < 100:
            return {}

        # 提取标题
        metadata = trafilatura.extract(
            downloaded,
            include_comments=False,
            output_format='json',
            favor_recall=True,
        )
        title = ''
        if metadata:
            try:
                meta = json.loads(metadata)
                title = meta.get('title', '') or meta.get('sitename', '')
            except (json.JSONDecodeError, AttributeError):
                pass

        if not title:
            title = text.split('\n')[0].strip()[:80]

        return {'title': title, 'text': text, 'length': len(text)}

    except Exception as e:
        logger.debug(f"trafilatura失败: {e}")
        return {}


def _try_direct_html(url: str) -> dict:
    """策略: 直接抓取HTML + trafilatura解析"""
    try:
        req = urllib.request.Request(url, headers=_HEADERS)
        resp = urllib.request.urlopen(req, timeout=12)
        html = resp.read().decode('utf-8', errors='ignore')
        if not html or len(html) < 500:
            return {}

        text = trafilatura.extract(
            html,
            include_comments=False,
            include_tables=False,
            output_format='txt',
            favor_recall=True,
        )
        if not text or len(text) < 100:
            return {}

        title = ''
        meta_html = trafilatura.extract(
            html,
            include_comments=False,
            output_format='json',
            favor_recall=True,
        )
        if meta_html:
            try:
                meta = json.loads(meta_html)
                title = meta.get('title', '')
            except (json.JSONDecodeError, AttributeError):
                pass

        if not title:
            title = text.split('\n')[0].strip()[:80]

        return {'title': title, 'text': text, 'length': len(text)}

    except Exception as e:
        logger.debug(f"直接抓取失败: {e}")
        return {}


# ── 10jqka (同花顺) 专用 ──

# 10jqka 页面噪音关键词
_10JQKA_NOISE = {
    '操盘必读', '个股行情', '个股资金流', '个股研报', '个股公告',
    '股吧', '讨论区', '加入自选', '模拟炒股', '智能诊股',
    '诊股', '诊股助手', '诊股宝', '诊股器', '诊股王',
    '诊股通', '诊股网', '诊股大师', '诊股机器人', '诊股神器',
    '诊股分析', '诊股报告', '诊股结果', '诊股评级',
    '千股千评', '千股千评', '个股点评', '个股诊断',
    '短线', '中线', '长线', '买入', '卖出', '增持', '减持',
    '主力', '游资', '散户', '机构', '北向资金',
    '热点题材', '题材', '龙头', '涨停', '跌停',
    '换手率', '市盈率', '市净率', '成交量', '成交额',
    '五档盘口', '逐笔交易', '分时图', 'K线', '均线',
    'MACD', 'KDJ', 'RSI', 'BOLL', '布林线',
    '新闻', '公告', '研报', '龙虎榜', '大宗交易',
    '分红', '送股', '转增', '配股', '增发', '回购',
    '行业新闻', '行业研报', '行业分析', '行业报告',
    '股票代码', '股票名称', '涨跌幅', '涨跌额', '最新价',
    '开盘价', '收盘价', '最高价', '最低价',
    '成交量', '成交额', '换手率', '市盈率', '市净率',
    '总市值', '流通市值', '振幅', '量比', '委比',
    '市盈率(TTM)', '市盈率(静)', '市盈率(动)',
    '新浪财经', '东方财富', '同花顺', '雪球', '牛股网',
    '金投网', '财富赢家', '中金在线', '第一财经', '证券之星',
    '点击查看详情', '点击查看', '更多>>', '>>更多',
    '相关股票', '相关概念', '相关板块', '相关基金',
    '本文来源', '责任编辑', '文章作者', '作者:',
    '免责声明', '风险提示', '投资有风险', '入市需谨慎',
}

# 10jqka 股票代码行模式: 纯数字+空格+数字+空格+数字
_10JQKA_STOCK_CODE_PATTERN = re.compile(
    r'^[\d\s\.\+\-%]{10,}$'  # 纯数字/空格/百分号行
)


def _clean_10jqka_html(html: str) -> str:
    """预清理10jqka的HTML，移除导航、广告、股票代码列表等噪音元素"""
    # 移除script和style标签及其内容
    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
    # 移除nav/header/footer标签
    html = re.sub(r'<nav[^>]*>.*?</nav>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<header[^>]*>.*?</header>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<footer[^>]*>.*?</footer>', '', html, flags=re.DOTALL | re.IGNORECASE)
    # 移除 class/id 含导航、广告、股票列表关键词的 div/section
    noise_class_ids = [
        'nav', 'header', 'footer', 'sidebar', 'aside', 'recommend',
        'related', 'comment', 'ad-', 'ads-', 'banner', 'toolbar',
        'breadcrumb', 'breadcrumb', 'stockquote', 'stockbar',
        'hqcode', 'hqtable', 'codelist', 'stocklist', 'stockinfo-side',
        'article-recommend', 'article-related', 'article-ad',
        'you_like', 'guess_like', 'hot_list', 'hot_list_',
        'news_list', 'news_list_', 'newsList',
    ]
    for pattern_str in noise_class_ids:
        # 移除包含这些关键词的 div/section/aside 标签
        regex = re.compile(
            r'<(?:div|section|aside)[^>]*(?:class|id)="[^"]*' + re.escape(pattern_str) + r'[^"]*"[^>]*>.*?</(?:div|section|aside)>',
            re.DOTALL | re.IGNORECASE
        )
        html = regex.sub('', html)
    # 移除iframe
    html = re.sub(r'<iframe[^>]*>.*?</iframe>', '', html, flags=re.DOTALL | re.IGNORECASE)
    return html


def _try_10jqka(url: str) -> dict:
    """同花顺(10jqka)文章 — 专用抓取+噪音清理"""
    try:
        req = urllib.request.Request(url, headers=_HEADERS)
        resp = urllib.request.urlopen(req, timeout=12)
        html = resp.read().decode('utf-8', errors='ignore')
        if not html or len(html) < 500:
            return {}

        # 预清理HTML噪音
        html = _clean_10jqka_html(html)

        # 用 trafilatura 提取正文（设置只提取文章内容）
        text = trafilatura.extract(
            html,
            include_comments=False,
            include_tables=False,
            output_format='txt',
            favor_recall=False,  # 10jqka HTML很乱，用保守模式减少噪音
        )
        if not text or len(text) < 50:
            # 降级：favor_recall=True
            text = trafilatura.extract(
                html,
                include_comments=False,
                include_tables=False,
                output_format='txt',
                favor_recall=True,
            )
        if not text or len(text) < 50:
            return {}

        # 逐行清理噪音
        lines = text.split('\n')
        cleaned_lines = []
        seen_stock_codes = set()

        for line in lines:
            s = line.strip()
            if not s:
                if cleaned_lines and cleaned_lines[-1].strip():
                    cleaned_lines.append('')
                continue
            # 跳过过短的行（通常不是正文）
            if len(s) < 4:
                continue
            # 跳过纯股票代码/数据行
            if _10JQKA_STOCK_CODE_PATTERN.match(s):
                continue
            # 跳过纯数字行
            if s.isdigit() and len(s) < 20:
                continue
            # 跳过包含噪音关键词的行（增强：部分匹配+忽略大小写）
            skip = False
            for noise_kw in _10JQKA_NOISE:
                if noise_kw in s or noise_kw.lower() in s.lower():
                    skip = True
                    break
            if skip:
                continue
            # 跳过包含网址、域名的行
            if re.search(r'https?://|www\.', s, re.IGNORECASE):
                continue
            # 跳过纯标点/特殊字符行
            if re.match(r'^[=+\-|#*~><。·、，\-—_…\s]+$', s):
                continue
            # 跳过过长且无标点的行（通常是侧边栏列表）
            if len(s) > 80 and not re.search(r'[，。！？；：,.:;!?]', s):
                continue
            # 跳过股票代码列表格式: "代码 名称 涨跌幅"
            if re.match(r'^\d{6}\s+\S+\s+[\+\-]?\d+\.\d+%?$', s):
                continue
            # 跳过纯股票代码行
            if re.match(r'^\d{6}$', s):
                seen_stock_codes.add(s)
                continue
            cleaned_lines.append(line)

        text = '\n'.join(cleaned_lines).strip()

        # 进一步清理：去掉连续出现的股票代码块（3+个连续6位数字）
        text = re.sub(
            r'(?:\d{6}\s*){3,}', '\n', text
        )

        # 截断尾部噪音（同花顺常见尾部：推荐阅读、股票列表等）
        stop_markers = [
            '推荐阅读', '相关阅读', '延伸阅读', '猜你喜欢',
            '热门推荐', '本文来源', '责任编辑', '免责',
            '风险提示', '投资有风险', '分享到', '发表评论',
            '我要纠错', '加入自选', '诊股', '个股行情',
            '您可能感兴趣', '看了又看', '最新文章', '热门文章',
            '文章来源', '本文不代表', '责任编辑',
        ]
        result_lines = []
        # 找正文开始（第一条超过30字的行）
        body_start = 0
        for i, line in enumerate(cleaned_lines):
            if len(line.strip()) > 30:
                body_start = i
                break
        for line in cleaned_lines[body_start:]:
            s = line.strip()
            if any(marker in s for marker in stop_markers):
                break
            result_lines.append(line)
        text = '\n'.join(result_lines).strip()

        if len(text) < 50:
            return {}

        # 提取标题
        title = ''
        # 尝试从HTML中提取title标签
        title_m = re.search(r'<title[^>]*>(.*?)</title>', html, re.DOTALL | re.IGNORECASE)
        if title_m:
            title = re.sub(r'<[^>]+>', '', title_m.group(1)).strip()
            # 清理标题后缀
            for suffix in ['_股票频道_同花顺', '_同花顺', '-同花顺财经', '_同花顺财经',
                           '-10jqka.com.cn', '_10jqka', '_同花顺股票频道']:
                title = title.replace(suffix, '')

        if not title:
            title = text.split('\n')[0].strip()[:80]

        return {'title': title, 'text': text, 'length': len(text)}

    except Exception as e:
        logger.debug(f"10jqka抓取失败: {e}")
        return {}


# ── 财联社专用 ──

def _try_cls(url: str) -> dict:
    """财联社文章 — 多策略抓取（API + HTML解析）"""
    # 从URL提取文章ID: detail/123456, telegraph/123456, share/article/123456
    m = re.search(r'(?:detail|telegraph|share/article)[/\-](\d+)', url)
    if not m:
        return {}
    
    article_id = m.group(1)
    is_share_url = 'share/article' in url or 'api3.cls.cn' in url
    
    # 方法1: 直接抓取页面HTML解析（最可靠，不依赖API）
    try:
        # 优先用share URL（HTML内容更丰富），否则用detail URL
        fetch_url = url if is_share_url else f"https://www.cls.cn/detail/{article_id}"
        req = urllib.request.Request(fetch_url, headers={
            'User-Agent': _UA,
            'Referer': 'https://www.cls.cn/',
        })
        resp = urllib.request.urlopen(req, timeout=12)
        html = resp.read().decode('utf-8', errors='ignore')
        
        if html and len(html) > 500:
            title = ''
            text = ''
            
            # 提取 og:title / og:description
            title_m = re.search(r'og:title["\s]*content="([^"]+)"', html)
            desc_m = re.search(r'og:description["\s]*content="([^"]+)"', html)
            if title_m:
                title = html_module.unescape(title_m.group(1)).strip()
            if desc_m:
                desc = html_module.unescape(desc_m.group(1)).strip()
            else:
                desc = ''
            
            # 提取 telegraph-content div（快讯正文）
            tc_m = re.search(r'<div[^>]*class="[^"]*telegraph-content[^"]*"[^>]*>(.*?)</div>', html, re.S)
            if tc_m:
                text = re.sub(r'<[^>]+>', '\n', tc_m.group(1))
                text = _clean_text(text)
            
            # 如果telegraph-content太短，尝试提取所有 content div（深度文章）
            if len(text) < 50:
                # 提取 class="content content-XXXXX" 的div（对应当前文章ID）
                content_m = re.search(
                    rf'<div[^>]*class="[^"]*content\s+content-{article_id}[^"]*"[^>]*>(.*?)</div>',
                    html, re.S
                )
                if content_m:
                    text = re.sub(r'<[^>]+>', '\n', content_m.group(1))
                    text = _clean_text(text)
            
            # 如果正文仍然太短，用 og:description
            if len(text) < 50 and desc:
                text = desc
            
            if len(text) > 50:
                if not title:
                    title = text.split('\n')[0].strip()[:80]
                return {'title': _clean_title(title), 'text': text, 'length': len(text)}
            
            # 最后尝试 trafilatura
            trafilatura_text = trafilatura.extract(
                html, include_comments=False, output_format='txt', favor_recall=True
            )
            if trafilatura_text and len(trafilatura_text) > 50:
                if not title:
                    title = trafilatura_text.split('\n')[0].strip()[:80]
                return {'title': _clean_title(title), 'text': trafilatura_text, 'length': len(trafilatura_text)}
    except Exception as e:
        logger.debug(f"财联社HTML解析失败: {e}")
    
    # 方法2: 财联社详情API（可能已失效，作为降级方案）
    try:
        for api_path in ['detail', 'telegraphDetail']:
            api_url = f"https://www.cls.cn/nodeapi/{api_path}?app=CailianpressWeb&os=web&sv=8.4.6&id={article_id}"
            req = urllib.request.Request(api_url, headers={
                'User-Agent': _UA,
                'Referer': f'https://www.cls.cn/detail/{article_id}',
            })
            resp = urllib.request.urlopen(req, timeout=8)
            data = json.loads(resp.read())
            article_data = data.get('data', {})
            if isinstance(article_data, dict):
                content_html = article_data.get('content', '') or article_data.get('brief', '')
                title = article_data.get('title', '') or article_data.get('subject', '')
                if content_html:
                    text = re.sub(r'<[^>]+>', '\n', content_html)
                    text = _clean_text(text)
                    if len(text) > 50:
                        return {'title': _clean_title(title), 'text': text, 'length': len(text)}
    except Exception as e:
        logger.debug(f"财联社API失败: {e}")
    
    return {}


# ── 新浪财经专用 ──

def _try_sina_finance(url: str) -> dict:
    """新浪财经 — 直接抓取 artibody 正文（国内可直连）"""
    try:
        req = urllib.request.Request(url, headers={'User-Agent': _UA, 'Referer': 'https://finance.sina.com.cn/'})
        resp = urllib.request.urlopen(req, timeout=12)
        html = resp.read().decode('utf-8', errors='ignore')
        if not html:
            return {}

        # 提取标题
        title = ''
        title_m = re.search(r'<title>(.*?)</title>', html, re.S)
        if title_m:
            title = re.sub(r'<[^>]+>', '', title_m.group(1)).strip()
            title = re.sub(r'[_\-—|]\s*(新浪财经|新浪网|新浪)\s*$', '', title).strip()

        # 方法1: 直接从 artibody div 提取
        artibody = re.search(r'<div[^>]*id=["\']artibody["\'].*?>(.*?)</div>\s*(?:<div[^>]*class|<script)', html, re.S)
        if artibody:
            text = re.sub(r'<[^>]+>', '\n', artibody.group(1))
            text = _clean_text(text)
            if len(text) > 100:
                return {'title': title, 'text': text, 'length': len(text)}

        # 方法2: 从 article body div 提取
        article = re.search(r'<div[^>]*class=["\'][^"\']*article[^"\']*["\'].*?>(.*?)</div>\s*(?:<div[^>]*class|<script)', html, re.S)
        if article:
            text = re.sub(r'<[^>]+>', '\n', article.group(1))
            text = _clean_text(text)
            if len(text) > 100:
                return {'title': title, 'text': text, 'length': len(text)}

        # 方法3: trafilatura 兜底
        text = trafilatura.extract(html, include_comments=False, output_format='txt', favor_recall=True)
        if text and len(text) > 100:
            if not title:
                title = text.split('\n')[0].strip()[:80]
            return {'title': title, 'text': text, 'length': len(text)}

    except Exception as e:
        logger.debug(f"新浪财经抓取失败: {e}")
    return {}


# ── 财新专用 ──

def _try_caixin(url: str) -> dict:
    """财新 — trafilatura抓取预览内容（付费墙前的部分）"""
    try:
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            return {}
        text = trafilatura.extract(
            downloaded,
            include_comments=False,
            output_format='txt',
            favor_recall=True,
        )
        if text and len(text) > 50:
            title = text.split('\n')[0].strip() if '\n' in text else ''
            return {'title': title, 'text': text, 'length': len(text)}
    except Exception as e:
        logger.debug(f"财新抓取失败: {e}")
    return {}


# ── 主入口 ──

def extract_article(url: str) -> dict:
    """
    从URL提取文章正文
    返回: {"title": "...", "content": "...", "url": "...", "success": True/False}
    """
    result = {
        'url': url,
        'title': '',
        'content': '',
        'success': False,
        'error': '',
    }

    # 根据域名选择最优策略
    strategies = []

    # 从中国服务器完全不可达的站点 — 不浪费42秒尝试
    _SKIP_DOMAINS = ['bloomberg.com', 'reuters.com', 'marketwatch.com',
                     'wsj.com', 'ft.com', 'nytimes.com', 'cnbc.com',
                     'seekingalpha.com', 'fool.com']
    for skip in _SKIP_DOMAINS:
        if skip in url:
            result['error'] = f'该源({skip})从当前服务器不可达，请查看摘要'
            result['success'] = False
            return result

    if 'wallstreetcn.com' in url or 'wallstreetcn' in url:
        strategies.append(('华尔街见闻', _try_wallstreetcn))

    if 'caixin.com' in url:
        strategies.append(('财新', _try_caixin))

    if 'finance.sina.com.cn' in url or 'sina.com.cn' in url:
        strategies.append(('新浪财经', _try_sina_finance))

    if '10jqka.com.cn' in url or '10jqka' in url or 'ths.com' in url:
        strategies.append(('10jqka', _try_10jqka))

    if 'cls.cn' in url:
        strategies.append(('财联社', _try_cls))

    # 通用策略：trafilatura 优先
    strategies.append(('trafilatura', _try_trafilatura))
    strategies.append(('直接抓取', _try_direct_html))

    for name, fn in strategies:
        try:
            data = fn(url)
            text = data.get('text', '')
            title = data.get('title', '')
            if text and len(text) > 100:
                text = _clean_text(text)
                if len(text) > 100:
                    result['title'] = _clean_title(title)
                    result['content'] = text[:10000]  # 上限10K
                    result['success'] = True
                    logger.info(f"✅ [{name}] 成功提取 {len(text)} 字 from {url[:60]}")
                    return result
            else:
                logger.debug(f"⚠️ [{name}] 正文太短({len(text)}字): {url[:60]}")
        except Exception as e:
            logger.debug(f"❌ [{name}] 失败: {e}")

    result['error'] = '所有策略均失败（可能是付费墙或网络限制）'
    return result
