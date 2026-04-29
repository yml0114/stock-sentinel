"""
华尔街见闻 & 财联社 — 全球财经新闻API

核心策略：Bloomberg/FT/WSJ等付费媒体从服务器端无法直接破解（IP级封锁），
但华尔街见闻和财联社已经翻译/搬运了这些内容，API免费且全文可用。
"""
import urllib.request
import json
import re
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

_UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'


def _fetch_json(url: str, timeout: int = 10) -> dict:
    req = urllib.request.Request(url, headers={'User-Agent': _UA})
    resp = urllib.request.urlopen(req, timeout=timeout)
    return json.loads(resp.read())


def _strip_html(text: str) -> str:
    """去除HTML标签"""
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'&amp;', '&', text)
    text = re.sub(r'&lt;', '<', text)
    text = re.sub(r'&gt;', '>', text)
    text = re.sub(r'&#\d+;', '', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


# ── 华尔街见闻 ──

def _detect_original_source(title: str, content: str) -> str:
    """从华尔街见闻内容中提取原始国际来源名"""
    text = (title + ' ' + content).lower()
    source_map = [
        ('bloomberg', 'Bloomberg'), ('彭博', 'Bloomberg'),
        ('financial times', 'Financial Times'), ('金融时报', 'Financial Times'), ('ft', 'Financial Times'),
        ('wall street journal', 'WSJ'), ('华尔街日报', 'WSJ'), ('wsj', 'WSJ'),
        ('reuters', 'Reuters'), ('路透', 'Reuters'),
        ('cnbc', 'CNBC'),
        ('new york times', 'NYT'), ('纽约时报', 'NYT'), ('nyt', 'NYT'),
        ('the information', 'The Information'),
        ('guardian', 'Guardian'), ('卫报', 'Guardian'),
        ('bbc', 'BBC'),
        ('经济学人', 'The Economist'), ('economist', 'The Economist'),
        ('nikkei', '日经'), ('日经', '日经'),
    ]
    for kw, name in source_map:
        if kw in text:
            return name
    return ''


def fetch_wallstreetcn(limit: int = 30) -> list:
    """
    华尔街见闻实时快讯 — 覆盖Bloomberg/FT/WSJ/Reuters等国际源
    API: https://api-one-wscn.awtmt.com/apiv1/content/lives
    
    免费策略：华尔街见闻已翻译/搬运国际权威媒体内容
    每条新闻自动检测原始来源，显示为"Bloomberg (via 华尔街见闻)"
    """
    url = (
        "https://api-one-wscn.awtmt.com/apiv1/content/lives"
        "?channel=global-channel&client=pc"
        f"&limit={limit}&first_page=true"
    )
    try:
        data = _fetch_json(url)
        items = data.get('data', {}).get('items', [])
        results = []
        for item in items:
            title = item.get('title', '').strip()
            content = _strip_html(item.get('content', ''))
            # 华尔街见闻的title有时为空，内容本身就是标题
            if not title and content:
                title = content[:60] + ('...' if len(content) > 60 else '')
            
            ts = item.get('display_time', 0)
            time_str = datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M') if ts else ''

            # 检测原始来源（Bloomberg/FT/WSJ/Reuters等）
            original_source = _detect_original_source(title, content)
            source_type = 'international' if original_source else 'domestic'
            
            # 来源显示：有国际来源时显示"Bloomberg (via 华尔街见闻)"
            display_source = f'{original_source} (via 华尔街见闻)' if original_source else '华尔街见闻'

            results.append({
                'title': title,
                'content': content,
                'source': display_source,
                'source_type': source_type,
                'original_source': original_source,  # 保留原始来源名
                'url': item.get('uri', ''),
                'time': time_str,
            })
        
        intl_count = sum(1 for r in results if r['source_type'] == 'international')
        logger.info(f"华尔街见闻: 获取 {len(results)} 条快讯 (含 {intl_count} 条国际源)")
        return results
    except Exception as e:
        logger.warning(f"华尔街见闻 API 失败: {e}")
        return []


def fetch_wallstreetcn_articles(limit: int = 20) -> list:
    """
    华尔街见闻深度文章 — 有完整正文
    API: https://api-one-wscn.awtmt.com/apiv1/content/articles
    """
    url = (
        "https://api-one-wscn.awtmt.com/apiv1/content/articles"
        "?channel=global-channel&client=pc"
        f"&limit={limit}&first_page=true"
    )
    try:
        data = _fetch_json(url)
        items = data.get('data', {}).get('items', [])
        results = []
        for item in items:
            title = item.get('title', '').strip()
            # 文章摘要
            content = _strip_html(item.get('content_short', '') or item.get('content', ''))
            
            ts = item.get('display_time', 0)
            time_str = datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M') if ts else ''
            
            url_path = item.get('uri', '')
            if url_path and not url_path.startswith('http'):
                url_path = f"https://wallstreetcn.com/articles/{item.get('id', '')}"

            results.append({
                'title': title,
                'content': content,
                'source': '华尔街见闻',
                'source_type': 'domestic',
                'url': url_path,
                'time': time_str,
            })
        
        logger.info(f"华尔街见闻文章: 获取 {len(results)} 篇")
        return results
    except Exception as e:
        logger.warning(f"华尔街见闻文章 API 失败: {e}")
        return []


# ── 财联社 ──

def fetch_cls(limit: int = 30) -> list:
    """
    财联社电报 — 实时快讯 + 深度内容
    API: https://www.cls.cn/nodeapi/updateTelegraphList
    """
    url = (
        "https://www.cls.cn/nodeapi/updateTelegraphList"
        f"?app=CailianpressWeb&os=web&sv=8.4.6"
    )
    try:
        data = _fetch_json(url)
        items = data.get('data', {}).get('roll_data', [])
        results = []
        for item in items[:limit]:
            title = item.get('title', '').strip()
            content = _strip_html(item.get('content', ''))
            
            # 有些快讯 title 为空，content 本身就是全文
            if not title and content:
                title = content[:60] + ('...' if len(content) > 60 else '')
            
            ts = item.get('ctime', 0)
            time_str = datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M') if ts else ''
            
            # 详情URL — 优先用shareurl，其次拼接id
            share_url = item.get('shareurl', '')
            if share_url:
                article_url = share_url
            else:
                item_id = item.get('id', '')
                article_url = f"https://www.cls.cn/detail/{item_id}" if item_id else ''

            # 检测国际源引用
            source_type = 'domestic'
            intl_keywords = ['Bloomberg', '彭博', 'FT', '金融时报', 'WSJ', '华尔街日报',
                           'Reuters', '路透', 'CNBC', 'NYT', '纽约时报']
            for kw in intl_keywords:
                if kw.lower() in content.lower() or kw.lower() in title.lower():
                    source_type = 'international'
                    break

            results.append({
                'title': title,
                'content': content,
                'source': '财联社',
                'source_type': source_type,
                'url': article_url,
                'time': time_str,
            })
        
        logger.info(f"财联社: 获取 {len(results)} 条电报")
        return results
    except Exception as e:
        logger.warning(f"财联社 API 失败: {e}")
        return []


# ── 统一入口 ──

def fetch_cn_financial_news(limit_per_source: int = 30) -> list:
    """
    聚合所有中文财经新闻源
    返回按时间倒序排列的新闻列表
    """
    all_news = []
    
    # 华尔街见闻快讯
    all_news.extend(fetch_wallstreetcn(limit_per_source))
    
    # 华尔街见闻文章
    all_news.extend(fetch_wallstreetcn_articles(limit_per_source // 2))
    
    # 财联社电报
    all_news.extend(fetch_cls(limit_per_source))
    
    # 按时间倒序
    all_news.sort(key=lambda x: x.get('time', ''), reverse=True)
    
    logger.info(f"中文财经聚合: 共 {len(all_news)} 条")
    return all_news
