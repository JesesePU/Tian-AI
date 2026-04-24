"""
Tian AI — Search Module

联网搜索模块。每次对话自动搜索相关上下文，未命中知识库时自动存入。

使用 DuckDuckGo 的 HTML 搜索结果（无需 API Key），
或 Google 自定义搜索（需配置 API Key）。

Multilingual: user-facing labels go through t().

用法：
    from tian_ai.search import web_search
    results = web_search("quantum computing")
"""

import requests
import re
import time
import json
import os
from urllib.parse import quote_plus

from ..multilingual import TranslationProvider


# ── DuckDuckGo HTML search (no API key) ──
_DDG_URL = "https://html.duckduckgo.com/html/"
_USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 14; K) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Mobile Safari/537.36"
)

# ── Google Custom Search (optional, requires setup) ──
_GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
_GOOGLE_CX = os.environ.get("GOOGLE_CX", "")


def web_search(query: str, num_results: int = 5, engine: str = "ddg") -> list:
    """
    联网搜索，返回结构化结果列表。

    Args:
        query: 搜索关键词
        num_results: 返回结果数（最多10）
        engine: "ddg" (DuckDuckGo) 或 "google" (需配置环境变量)

    Returns:
        [{"title": str, "url": str, "snippet": str}, ...]
    """
    if engine == "google" and _GOOGLE_API_KEY and _GOOGLE_CX:
        return _search_google(query, num_results)
    return _search_ddg(query, num_results)


def _search_ddg(query: str, num_results: int) -> list:
    """DuckDuckGo HTML search — pure Python, no external dependencies"""
    tr = TranslationProvider(lang="en")
    
    try:
        resp = requests.post(
            _DDG_URL,
            data={"q": query},
            headers={
                "User-Agent": _USER_AGENT,
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            },
            timeout=15,
        )
        resp.raise_for_status()
    except Exception as e:
        return [{"title": "[Search Error]", "url": "", "snippet": f"{tr.t('搜索失败')}: {str(e)}"}]

    # 从 HTML 中提取搜索结果
    results = []
    html = resp.text

    # DuckDuckGo HTML 版结果结构:
    # <a class="result__a" href="...">title</a>
    # <a class="result__snippet" ...>snippet</a>

    # 提取 result__a (标题+链接)
    title_pattern = re.compile(
        r'<a[^>]*class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>',
        re.DOTALL,
    )
    snippet_pattern = re.compile(
        r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>',
        re.DOTALL,
    )

    titles = title_pattern.findall(html)
    snippets = snippet_pattern.findall(html)

    for i, (url, title_html) in enumerate(titles):
        if i >= num_results:
            break
        # 清理 HTML 标签
        title = re.sub(r"<[^>]+>", "", title_html).strip()
        # DDG 的 URL 是重定向链接，需要提取真实 URL
        # 格式: //duckduckgo.com/l/?uddg=REAL_URL&...
        if "uddg=" in url:
            from urllib.parse import unquote
            url = unquote(url.split("uddg=")[1].split("&")[0])
        elif url.startswith("//"):
            url = "https:" + url
        elif url.startswith("/"):
            url = "https://duckduckgo.com" + url

        snippet = ""
        if i < len(snippets):
            snippet = re.sub(r"<[^>]+>", "", snippets[i]).strip()

        results.append({
            "title": title or f"Result {i + 1}",
            "url": url,
            "snippet": snippet,
        })

    if not results:
        # 备用: 从简化版提取
        alt_pattern = re.compile(r'<h2[^>]*>.*?<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>.*?</h2>', re.DOTALL)
        alt_matches = alt_pattern.findall(html)
        for i, (url, title_html) in enumerate(alt_matches[:num_results]):
            title = re.sub(r"<[^>]+>", "", title_html).strip()
            results.append({
                "title": title,
                "url": url,
                "snippet": "",
            })

    return results


def _search_google(query: str, num_results: int) -> list:
    """Google Custom Search JSON API"""
    tr = TranslationProvider(lang="en")
    
    if not _GOOGLE_API_KEY or not _GOOGLE_CX:
        return [{"title": "[Config Error]", "url": "", "snippet": f"{tr.t('请设置 GOOGLE_API_KEY 和 GOOGLE_CX 环境变量')}"}]
    try:
        resp = requests.get(
            "https://www.googleapis.com/customsearch/v1",
            params={
                "key": _GOOGLE_API_KEY,
                "cx": _GOOGLE_CX,
                "q": query,
                "lr": "lang_zh-CN",
                "num": min(num_results, 10),
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        items = data.get("items", [])
        return [
            {
                "title": item.get("title", ""),
                "url": item.get("link", ""),
                "snippet": item.get("snippet", ""),
            }
            for item in items[:num_results]
        ]
    except Exception as e:
        return [{"title": "[Search Error]", "url": "", "snippet": f"{tr.t('Google搜索失败')}: {str(e)}"}]


def search_and_summarize(query: str, max_results: int = 3) -> str:
    """
    搜索并返回摘要文本（适合注入对话上下文）。

    Returns:
        格式化的搜索摘要字符串
    """
    tr = TranslationProvider(lang="en")
    
    results = web_search(query, num_results=max_results)
    if not results:
        return ""
    # 检查结果是否全是错误/空（支持所有 [Error]、[Search Error] 等格式）
    first_title = results[0].get("title", "")
    if not first_title or first_title.startswith("[") or all(
        not r.get("title") and not r.get("snippet") for r in results
    ):
        return ""

    parts = [f"[{tr.t('搜索结果')}: {query}]"]
    for i, r in enumerate(results, 1):
        title = r.get("title", "")[:80]
        snippet = r.get("snippet", "")[:200]
        url = r.get("url", "")[:100]
        if title or snippet:
            parts.append(f"  {i}. {title}")
            if snippet:
                parts.append(f"     {snippet}")
            if url:
                parts.append(f"     ({url})")

    return "\n".join(parts)
