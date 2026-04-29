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


def _clean_text(text: str) -> str:
    """通用文本清理：去噪音行 + 截断尾部"""
    if not text:
        return ''

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
        cleaned.append(line)

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
    m = re.search(r'articles[/\-](\d+)', url)
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

    if 'wallstreetcn.com' in url or 'wallstreetcn' in url:
        strategies.append(('华尔街见闻', _try_wallstreetcn))

    if 'caixin.com' in url:
        strategies.append(('财新', _try_caixin))

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
