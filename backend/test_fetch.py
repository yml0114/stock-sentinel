#!/usr/bin/env python3
"""Test article fetching strategies"""
import sys
sys.path.insert(0, '.')
import logging
logging.basicConfig(level=logging.DEBUG, format='%(name)s %(message)s')

from app.data.article_fetcher import extract_article, _try_trafilatura, _try_direct_html, _try_wallstreetcn, _try_cls, _try_sina_finance, _try_10jqka
import urllib.request
import json

_UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'

# Find real URLs from news_intel
print("=== Checking news sources ===")
from app.data.news_intel import fetch_wallstreetcn_articles, fetch_cn_financial_news
try:
    items = fetch_wallstreetcn_articles(limit=3)
    print(f"WallStreetCN items: {len(items)}")
    for it in items[:3]:
        print(f"  URL: {it.get('url', 'N/A')[:80]}")
        print(f"  Title: {it.get('title', 'N/A')[:60]}")
except Exception as e:
    print(f"WallStreetCN fetch error: {e}")

print()
try:
    items = fetch_cn_financial_news(limit=3)
    print(f"CN Financial items: {len(items)}")
    for it in items[:3]:
        print(f"  URL: {it.get('url', 'N/A')[:80]}")
        print(f"  Source: {it.get('source', 'N/A')}")
except Exception as e:
    print(f"CN Financial fetch error: {e}")

print()
print("=== Testing individual strategies ===")
# Test with a real wallstreetcn URL
test_url = "https://wallstreetcn.com/articles/3749604"
print(f"\nTest URL: {test_url}")

strategies = [
    ("trafilatura", _try_trafilatura),
    ("direct_html", _try_direct_html),
    ("wallstreetcn", _try_wallstreetcn),
]

for name, fn in strategies:
    try:
        result = fn(test_url)
        text = result.get('text', '')
        print(f"  {name}: text_len={len(text)}, title={result.get('title', '')[:40]}")
        if text:
            print(f"    Preview: {text[:80]}...")
        else:
            print(f"    EMPTY RESULT")
    except Exception as e:
        print(f"  {name}: ERROR {type(e).__name__}: {e}")

# Full extract
print(f"\n=== Full extract_article({test_url[:50]}) ===")
result = extract_article(test_url)
print(f"  success={result['success']}, content_len={len(result['content'])}, error={result.get('error','')}")
if result['content']:
    print(f"  Preview: {result['content'][:100]}...")
