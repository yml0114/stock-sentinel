"""
文章正文抓取 — 从URL提取可读正文

策略链（按优先级，前一个失败自动尝试下一个）：
1. 直接抓取 + HTML解析提取正文
2. Google Cache 兜底
3. 12ft.io / archive.today 绕过付费墙
"""
import re
import logging
import urllib.request
import urllib.parse
from html.parser import HTMLParser

logger = logging.getLogger(__name__)

_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
}


# ── HTML正文提取器 ──

class _TextExtractor(HTMLParser):
    """从HTML提取正文文本，跳过script/style/nav等"""
    SKIP_TAGS = {'script', 'style', 'nav', 'header', 'footer', 'aside',
                 'noscript', 'iframe', 'svg', 'form', 'button', 'input',
                 'select', 'textarea', 'label'}
    BLOCK_TAGS = {'p', 'div', 'br', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
                  'li', 'blockquote', 'tr', 'section', 'article', 'figcaption'}

    def __init__(self):
        super().__init__()
        self._text_parts = []
        self._skip_depth = 0
        self._title = ''
        self._in_title_tag = False
        # 正文区域检测
        self._in_body = False
        self._body_depth = 0
        self._body_text = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        attrs_dict = dict(attrs)

        if tag in self.SKIP_TAGS:
            self._skip_depth += 1
            return

        if tag == 'title':
            self._in_title_tag = True

        # 检测正文区域
        cls = attrs_dict.get('class', '').lower()
        id_val = attrs_dict.get('id', '').lower()

        # 各站点正文区域的class/id模式
        body_patterns = [
            'article-body', 'article-content', 'article-text',
            'story-body', 'story-content', 'post-content',
            'entry-content', 'content-body', 'news-content',
            'article_body', 'caixin_content',  # 财新
            'text_detail',  # 财新备用
            'article-detail',  # 中文站点通用
            'detail-content',
        ]
        if tag == 'article' or any(p in cls or p in id_val for p in body_patterns):
            self._in_body = True
            self._body_depth += 1

        if tag in self.BLOCK_TAGS:
            text = '\n'
            self._text_parts.append(text)
            if self._in_body:
                self._body_text.append(text)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in self.SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
        if tag == 'title':
            self._in_title_tag = False
        if self._body_depth > 0:
            self._body_depth = max(0, self._body_depth - 1)
            if self._body_depth == 0:
                self._in_body = False
        if tag in self.BLOCK_TAGS:
            self._text_parts.append('\n')
            if self._in_body:
                self._body_text.append('\n')

    def handle_data(self, data):
        if self._skip_depth > 0:
            return
        if self._in_title_tag:
            self._title += data.strip()
        self._text_parts.append(data)
        if self._in_body:
            self._body_text.append(data)

    def get_text(self) -> str:
        raw = ''.join(self._text_parts)
        return _clean_lines(raw)

    def get_body_text(self) -> str:
        """仅正文区域的文本（如果有）"""
        if not self._body_text:
            return ''
        raw = ''.join(self._body_text)
        return _clean_lines(raw)

    def get_title(self) -> str:
        return self._title.strip()


def _clean_lines(text: str) -> str:
    """清理文本：去除多余空行"""
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    return '\n'.join(lines)


# ── 导航噪音过滤 ──

_NAV_NOISE = [
    # 中文站点导航
    '商城', '订阅', '数据', '我闻', '机构订阅', '会议', '应用下载', '帮助',
    '首页', '经济', '金融', '公司', '政经', '世界', '观点', '博客', '图片', '视频',
    '周刊', '数据通', '商圈', '企业数据库', '沪深股市', '港股', '更多',
    '科技', '地产', '汽车', '消费', '能源', '健康', '环科', '民生', 'ESG',
    '财新一线', '私房课', '运动家', '企业用户', '订阅', '电邮',
    '发表评论', '分享到微信朋友圈', '新浪转发',
    '网上有害信息举报专区', '责任编辑',
    'Promotion', 'mini+', 'English',
    '图片编辑', '美术编辑', '视觉编辑',
    '分享到新浪微博', '分享到微信',
    # 英文站点导航
    'Subscribe', 'Sign In', 'Log In', 'Newsletter', 'Newsletter Sign Up',
    'Already a subscriber', 'Get unlimited access',
    'Terms of Service', 'Privacy Policy', 'Cookie Settings',
    'Contact Us', 'Advertise', 'Careers', 'Sitemap',
    'Advertisement', 'Sponsored Content',
]


def _remove_nav_noise(text: str) -> str:
    """移除导航菜单、页脚等噪音行"""
    lines = text.split('\n')
    # 第一遍：过滤纯导航噪音
    phase1 = []
    for line in lines:
        stripped = line.strip()
        if len(stripped) < 30:
            if any(noise == stripped for noise in _NAV_NOISE):
                continue
            if stripped in ('+', '-', '|', '/', '·', '…'):
                continue
        if len(stripped) < 2:
            continue
        phase1.append(line)

    # 第二遍：找到正文主体（最长的行或连续文本行），然后截断尾部噪音
    stop_markers = [
        '相关报道', '推荐阅读', '上一篇', '下一篇',
        '相关阅读', '延伸阅读', '猜你喜欢', '热门推荐',
        '图片编辑：', '美术编辑：', '视觉编辑：',
        '分享到', '发表评论', '我要纠错',
        '财新网主编精选版电邮', '财新网新闻版电邮',
        '版权所有', '本文来源', '本文仅代表',
        '图片推荐', '视听推荐', '编辑推荐',
        '版面编辑：',
    ]
    # 找到正文开始位置（第一条超过50字的行）
    body_start = 0
    for i, line in enumerate(phase1):
        if len(line.strip()) > 50:
            body_start = i
            break

    # 从正文开始后截断
    cleaned = phase1[:body_start]
    for line in phase1[body_start:]:
        stripped = line.strip()
        if any(marker in stripped for marker in stop_markers):
            break
        cleaned.append(line)
    return '\n'.join(cleaned)


# ── 抓取策略 ──

def _fetch_html(url: str, timeout: int = 10) -> str:
    """下载HTML"""
    req = urllib.request.Request(url, headers=_HEADERS)
    resp = urllib.request.urlopen(req, timeout=timeout)
    return resp.read().decode('utf-8', errors='ignore')


def _try_direct(url: str) -> dict:
    """策略1: 直接抓取"""
    html = _fetch_html(url)
    parser = _TextExtractor()
    parser.feed(html)

    # 优先使用正文区域文本，如果太短则用全文
    body_text = parser.get_body_text()
    full_text = parser.get_text()

    text = body_text if len(body_text) > len(full_text) * 0.3 else full_text
    text = _remove_nav_noise(text)

    return {
        'title': parser.get_title(),
        'text': text,
        'length': len(text),
    }


def _try_google_cache(url: str) -> dict:
    """策略2: Google Cache"""
    cache_url = f"https://webcache.googleusercontent.com/search?q=cache:{urllib.parse.quote(url, safe='')}"
    html = _fetch_html(cache_url, timeout=12)
    parser = _TextExtractor()
    parser.feed(html)
    text = _remove_nav_noise(parser.get_text())
    return {
        'title': parser.get_title(),
        'text': text,
        'length': len(text),
    }


def _try_12ft(url: str) -> dict:
    """策略3: 12ft.io 绕过付费墙"""
    bypass_url = f"https://12ft.io/{url}"
    html = _fetch_html(bypass_url, timeout=15)
    parser = _TextExtractor()
    parser.feed(html)
    text = _remove_nav_noise(parser.get_text())
    return {
        'title': parser.get_title(),
        'text': text,
        'length': len(text),
    }


def _try_archive(url: str) -> dict:
    """策略4: archive.today"""
    archive_url = f"https://archive.ph/newest/{url}"
    html = _fetch_html(archive_url, timeout=15)
    parser = _TextExtractor()
    parser.feed(html)
    text = _remove_nav_noise(parser.get_text())
    return {
        'title': parser.get_title(),
        'text': text,
        'length': len(text),
    }


def _try_wallstreetcn_article(url: str) -> dict:
    """华尔街见闻文章API — 获取完整正文"""
    import json as _json
    # 从URL提取文章ID
    m = re.search(r'/articles/(\d+)', url)
    if not m:
        m = re.search(r'wallstreetcn\.com/article/(\d+)', url)
    if not m:
        return {}
    
    article_id = m.group(1)
    api_url = f"https://api-one-wscn.awtmt.com/apiv1/content/article/{article_id}?client=pc"
    try:
        req = urllib.request.Request(api_url, headers={'User-Agent': _HEADERS['User-Agent']})
        resp = urllib.request.urlopen(req, timeout=10)
        data = _json.loads(resp.read())
        article = data.get('data', {}).get('article', {})
        title = article.get('title', '')
        content = article.get('content', '')
        # HTML转纯文本
        content = re.sub(r'<[^>]+>', '\n', content)
        content = _clean_lines(content)
        return {'title': title, 'text': content, 'length': len(content)}
    except Exception as e:
        logger.debug(f"华尔街见闻文章API失败: {e}")
        return {}


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

    # 优先：华尔街见闻文章API（专门优化）
    if 'wallstreetcn.com' in url or 'wallstreetcn' in url:
        try:
            wscn_result = _try_wallstreetcn_article(url)
            if wscn_result and len(wscn_result.get('text', '')) > 100:
                result['title'] = wscn_result['title']
                result['content'] = _final_clean(wscn_result['text'], max_chars=10000)
                result['success'] = True
                return result
        except Exception as e:
            logger.debug(f"华尔街见闻API失败: {e}")

    # 按策略链逐个尝试
    strategies = [
        ('直接抓取', _try_direct),
        ('Google Cache', _try_google_cache),
        ('12ft.io', _try_12ft),
        ('Archive', _try_archive),
    ]

    for name, fn in strategies:
        try:
            data = fn(url)
            text = data['text']
            title = data['title']
            if len(text) > 200:
                result['title'] = title
                result['content'] = _final_clean(text, max_chars=10000)
                result['success'] = True
                logger.info(f"✅ [{name}] 成功提取 {len(text)} 字 from {url[:60]}")
                return result
            else:
                logger.debug(f"⚠️ [{name}] 正文太短({len(text)}字): {url[:60]}")
        except Exception as e:
            logger.debug(f"❌ [{name}] 失败: {e}")

    result['error'] = '所有策略均失败（可能是付费墙或网络限制）'
    return result


def _final_clean(text: str, max_chars: int = 10000) -> str:
    """最终清理"""
    # 移除残留的无关文本
    noise_patterns = [
        r'(?i)(subscribe now|start your free trial|sign in to continue).*',
        r'(?i)(This article was|Write to|Corrections & Amplifications).*',
        r'版权所有[：:].*',
        r'责任编辑[：:].*',
        r'来源[：:]\s*(财新网|新华社|央视|人民日报)\s*.*',
    ]
    for pattern in noise_patterns:
        text = re.sub(pattern, '', text)

    # 移除连续空行
    text = re.sub(r'\n{3,}', '\n\n', text)

    if len(text) > max_chars:
        cut = text[:max_chars]
        # 在中文句号或英文句号处截断
        last_period = max(cut.rfind('。'), cut.rfind('. '), cut.rfind('！'), cut.rfind('？'))
        if last_period > max_chars * 0.7:
            text = cut[:last_period + 1]
        else:
            text = cut + '…'

    return text.strip()
