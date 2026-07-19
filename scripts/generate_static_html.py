#!/usr/bin/env python3
"""直接生成静态 HTML（绕过 Hugo）。

Hugo 0.164.0 在 macOS 上构建 110K 页面有性能瓶颈，
此脚本独立生成所有 HTML，支持 multiprocessing 并行。

页面类型 × 20 语种：
- tools:        /{lang}/tools/{tool_id}/index.html
- compare:      /{lang}/compare/{tool_a}-vs-{tool_b}/index.html
- guides:       /{lang}/guides/{tool_id}/index.html
- ranking:      /{lang}/ranking/{category}/index.html
- faq:          /{lang}/faq/{tool_id}/index.html
- history:      /{lang}/history/{tool_id}/index.html
- alternatives: /{lang}/alternatives/{tool_id}/index.html
- 首页:          /{lang}/index.html
- 列表页:        /{lang}/{type}/index.html
- 404:           /404.html
- robots.txt
- sitemap-{lang}.xml + sitemap-index.xml

CLI:
    python3 scripts/generate_static_html.py
    python3 scripts/generate_static_html.py --workers 8 --limit 10 --types tools
    python3 scripts/generate_static_html.py --types tools,compare --lang en,zh
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from html import escape
from multiprocessing import Pool, cpu_count
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from lib import i18n as i18n_mod

PROJECT_ROOT = SCRIPT_DIR.parent
DATA_DIR = PROJECT_ROOT / "data"
STATIC_DIR = PROJECT_ROOT / "static"
PUBLIC_DIR = PROJECT_ROOT / "public"

BASE_URL = "https://pricing.ai-term-hub.com/"
DEFAULT_DATE = "2026-07-19"
OG_IMAGE = "/images/og-default.svg"

SUPPORTED_LANGS = i18n_mod.SUPPORTED_LANGS  # 20 langs
LANG_MAP = i18n_mod.LANG_MAP

# hugo.toml [languages.xx] languageCode 映射
LANG_CODE_MAP = {
    "en": "en-us", "zh": "zh-cn", "es": "es-es", "fr": "fr-fr",
    "de": "de-de", "ja": "ja-jp", "ko": "ko-kr", "pt": "pt-pt",
    "ru": "ru-ru", "it": "it-it", "ar": "ar-sa", "nl": "nl-nl",
    "pl": "pl-pl", "tr": "tr-tr", "vi": "vi-vn", "th": "th-th",
    "id": "id-id", "sv": "sv-se", "no": "nb-no", "da": "da-dk",
}

# 站点标题（每个语种）— 来自 hugo.toml
SITE_TITLES = {
    "en": "AI Tools Pricing", "zh": "AI工具价格对比",
    "es": "Precios de Herramientas IA", "fr": "Prix des Outils IA",
    "de": "KI-Tools Preise", "ja": "AIツール価格比較",
    "ko": "AI도구 가격비교", "pt": "Preços de Ferramentas IA",
    "ru": "Цены на ИИ-инструменты", "it": "Prezzi Strumenti IA",
    "ar": "أسعار أدوات الذكاء الاصطناعي", "nl": "AI-tools Prijzen",
    "pl": "Ceny Narzędzi AI", "tr": "AI Araçları Fiyatları",
    "vi": "Giá Công cụ AI", "th": "ราคาเครื่องมือ AI",
    "id": "Harga Alat AI", "sv": "AI-verktyg Priser",
    "no": "AI-verktøy Priser", "da": "AI-værktøjer Priser",
}

# 页面类型常量
TYPE_TOOLS = "tools"
TYPE_COMPARE = "compare"
TYPE_GUIDES = "guides"
TYPE_RANKING = "ranking"
TYPE_FAQ = "faq"
TYPE_HISTORY = "history"
TYPE_ALTERNATIVES = "alternatives"

ALL_TYPES = [TYPE_TOOLS, TYPE_COMPARE, TYPE_GUIDES, TYPE_RANKING,
             TYPE_FAQ, TYPE_HISTORY, TYPE_ALTERNATIVES]

TYPE_SECTION = {
    TYPE_TOOLS: "tools",
    TYPE_COMPARE: "compare",
    TYPE_GUIDES: "guides",
    TYPE_RANKING: "ranking",
    TYPE_FAQ: "faq",
    TYPE_HISTORY: "history",
    TYPE_ALTERNATIVES: "alternatives",
}

# sitemap 优先级与更新频率
SITEMAP_PRIORITY = {
    TYPE_TOOLS: "0.9", TYPE_COMPARE: "0.7", TYPE_GUIDES: "0.8",
    TYPE_RANKING: "0.8", TYPE_FAQ: "0.6", TYPE_HISTORY: "0.6",
    TYPE_ALTERNATIVES: "0.6",
}
SITEMAP_CHANGEFREQ = {
    TYPE_TOOLS: "weekly", TYPE_COMPARE: "monthly", TYPE_GUIDES: "monthly",
    TYPE_RANKING: "weekly", TYPE_FAQ: "monthly", TYPE_HISTORY: "weekly",
    TYPE_ALTERNATIVES: "monthly",
}

# ----------------------------------------------------------------------
# Worker 进程全局变量（在 _init_worker 中初始化）
# ----------------------------------------------------------------------
_ALL_TOOLS: list = []
_TOOLS_BY_ID: dict = {}
_COMPARE_PAIRS: list = []  # [(tool_a, tool_b), ...]


# ----------------------------------------------------------------------
# 辅助函数
# ----------------------------------------------------------------------
def tr(key: str, lang: str) -> str:
    """获取 UI 翻译。"""
    return i18n_mod.get_ui_text(key, lang, default=key)


def cat_name(slug: str, lang: str) -> str:
    """获取分类本地化名称。"""
    return i18n_mod.get_category_name(slug, lang)


def fmt_price(price_min: float, price_max: float, currency: str, per_month: str) -> str:
    """格式化价格展示。"""
    if price_min == 0 and price_max == 0:
        return "Free"
    if price_min == price_max:
        return f"${price_min} {currency}{per_month}"
    return f"${price_min} - ${price_max} {currency}{per_month}"


def lang_dir(lang: str) -> str:
    return "rtl" if lang == "ar" else "ltr"


def lang_code(lang: str) -> str:
    return LANG_CODE_MAP.get(lang, lang)


def site_title(lang: str) -> str:
    return SITE_TITLES.get(lang, SITE_TITLES["en"])


# URL 辅助函数
def url_lang_home(lang: str) -> str:
    return f"/{lang}/"


def url_section(lang: str, ptype: str) -> str:
    return f"/{lang}/{TYPE_SECTION[ptype]}/"


def url_tool(lang: str, tool_id: str) -> str:
    return f"/{lang}/tools/{tool_id}/"


def url_compare(lang: str, tool_a_id: str, tool_b_id: str) -> str:
    return f"/{lang}/compare/{tool_a_id}-vs-{tool_b_id}/"


def url_guide(lang: str, tool_id: str) -> str:
    return f"/{lang}/guides/{tool_id}/"


def url_ranking(lang: str, category: str) -> str:
    return f"/{lang}/ranking/{category}/"


def url_faq(lang: str, tool_id: str) -> str:
    return f"/{lang}/faq/{tool_id}/"


def url_history(lang: str, tool_id: str) -> str:
    return f"/{lang}/history/{tool_id}/"


def url_alternatives(lang: str, tool_id: str) -> str:
    return f"/{lang}/alternatives/{tool_id}/"


def abs_url(path: str) -> str:
    """转绝对 URL。"""
    if path.startswith("/"):
        return BASE_URL + path.lstrip("/")
    return BASE_URL + path


def strip_lang_prefix(path: str) -> str:
    """去除 /{lang}/ 前缀，返回不带语种的路径（保留前导 /）。"""
    for lc in SUPPORTED_LANGS:
        prefix = f"/{lc}/"
        if path.startswith(prefix):
            return path[len(prefix) - 1:]
    if path in ("/", ""):
        return "/"
    return path


def write_html(path: Path, html: str) -> None:
    """写入 HTML 文件（自动创建父目录）。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")


# ----------------------------------------------------------------------
# Partials（HTML 片段）
# ----------------------------------------------------------------------
def render_seo(lang: str, title: str, description: str, canonical_path: str,
               keywords: str = "", og_type: str = "website",
               article_section: str = "", published_time: str = "",
               modified_time: str = "", is_home: bool = False) -> str:
    """渲染 SEO meta 标签 + hreflang。"""
    title_full = f"{title} | {site_title(lang)}"
    canonical = abs_url(canonical_path)
    og_image = abs_url(OG_IMAGE)
    lang_cc = lang_code(lang).replace("-", "_")
    kw = keywords or "AI tools, pricing, comparison, plans, deals, save money"

    robots = ("index,follow,max-image-preview:large,max-snippet:-1,max-video-preview:-1"
              if is_home else "index,follow,max-image-preview:large")

    parts = [
        f'<title>{escape(title_full)}</title>',
        f'<meta name="description" content="{escape(description)}">',
        f'<meta name="keywords" content="{escape(kw)}">',
        '<meta name="author" content="AI Pricing Hub">',
        f'<link rel="canonical" href="{canonical}">',
        f'<meta name="robots" content="{robots}">',
        '<meta name="theme-color" content="#0a0a1a">',
        '<meta name="color-scheme" content="dark light">',
        f'<meta property="og:type" content="{og_type}">',
        f'<meta property="og:title" content="{escape(title)}">',
        f'<meta property="og:description" content="{escape(description)}">',
        f'<meta property="og:url" content="{canonical}">',
        f'<meta property="og:site_name" content="{escape(site_title(lang))}">',
        f'<meta property="og:image" content="{og_image}">',
        f'<meta property="og:image:alt" content="{escape(title)}">',
        f'<meta property="og:locale" content="{lang_cc}">',
        '<meta name="twitter:card" content="summary_large_image">',
        f'<meta name="twitter:title" content="{escape(title)}">',
        f'<meta name="twitter:description" content="{escape(description)}">',
        f'<meta name="twitter:image" content="{og_image}">',
        f'<meta name="twitter:image:alt" content="{escape(title)}">',
    ]

    if article_section:
        parts.append(f'<meta property="article:section" content="{escape(article_section)}">')
    if published_time:
        parts.append(f'<meta property="article:published_time" content="{published_time}">')
    if modified_time:
        parts.append(f'<meta property="article:modified_time" content="{modified_time}">')

    # hreflang
    path_no_lang = strip_lang_prefix(canonical_path)
    for lc in SUPPORTED_LANGS:
        if path_no_lang == "/":
            alt_url = abs_url(f"/{lc}/")
        else:
            alt_url = abs_url(f"/{lc}{path_no_lang}")
        parts.append(f'<link rel="alternate" hreflang="{lc}" href="{alt_url}">')
        if lc == "en":
            parts.append(f'<link rel="alternate" hreflang="x-default" href="{alt_url}">')

    return "\n    ".join(parts)


def render_structured_data(lang: str, page_type: str, title: str, description: str,
                           canonical_path: str, breadcrumb_items: list | None = None,
                           product_data: dict | None = None, faq_items: list | None = None,
                           is_home: bool = False, is_node: bool = False) -> str:
    """渲染 JSON-LD 结构化数据。"""
    scripts: list[str] = []
    lang_cc = lang_code(lang)
    site_t = site_title(lang)

    # 1. WebSite schema（仅首页）
    if is_home:
        ws = {
            "@context": "https://schema.org",
            "@type": "WebSite",
            "name": site_t,
            "url": BASE_URL,
            "description": tr("default_description", lang),
            "inLanguage": lang_cc,
            "potentialAction": {
                "@type": "SearchAction",
                "target": {
                    "@type": "EntryPoint",
                    "urlTemplate": f"{BASE_URL}{lang}/search/?q={{search_term_string}}",
                },
                "query-input": "required name=search_term_string",
            },
        }
        scripts.append(json.dumps(ws, ensure_ascii=False))

    # 2. BreadcrumbList（非首页）
    if not is_home and breadcrumb_items:
        items = []
        for i, (name, url) in enumerate(breadcrumb_items, 1):
            items.append({
                "@type": "ListItem",
                "position": i,
                "name": name,
                "item": abs_url(url),
            })
        bl = {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": items,
        }
        scripts.append(json.dumps(bl, ensure_ascii=False))

    # 3. Product schema（工具详情页）
    if page_type == TYPE_TOOLS and product_data:
        p = {
            "@context": "https://schema.org",
            "@type": "Product",
            "name": title,
            "description": description,
            "url": abs_url(canonical_path),
            "inLanguage": lang_cc,
            "category": product_data.get("category", "AI Tool"),
            "brand": {"@type": "Brand", "name": product_data.get("vendor", "")},
            "offers": {
                "@type": "Offer",
                "priceCurrency": product_data.get("currency", "USD"),
                "price": str(product_data.get("price_min", 0)),
                "availability": "https://schema.org/InStock",
                "url": product_data.get("url", abs_url(canonical_path)),
            },
        }
        if product_data.get("price_max", 0) > product_data.get("price_min", 0):
            p["offers"]["maxPrice"] = str(product_data["price_max"])
        if product_data.get("free_tier"):
            p["offers"]["description"] = "Free tier available"
        scripts.append(json.dumps(p, ensure_ascii=False))

    # 4. FAQPage（攻略 / FAQ）
    if faq_items and page_type in (TYPE_GUIDES, TYPE_FAQ):
        qa = []
        for q, a in faq_items:
            qa.append({
                "@type": "Question",
                "name": q,
                "acceptedAnswer": {"@type": "Answer", "text": a},
            })
        fp = {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "inLanguage": lang_cc,
            "mainEntity": qa,
        }
        scripts.append(json.dumps(fp, ensure_ascii=False))

    # 5. Article schema（攻略详情）
    if page_type == TYPE_GUIDES and not is_node:
        art = {
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": title,
            "description": description,
            "url": abs_url(canonical_path),
            "inLanguage": lang_cc,
            "datePublished": f"{DEFAULT_DATE}T00:00:00Z",
            "dateModified": f"{DEFAULT_DATE}T00:00:00Z",
            "author": {"@type": "Organization", "name": "AI Pricing Hub"},
            "publisher": {"@type": "Organization", "name": site_t, "url": BASE_URL},
            "mainEntityOfPage": {"@type": "WebPage", "@id": abs_url(canonical_path)},
        }
        scripts.append(json.dumps(art, ensure_ascii=False))

    if not scripts:
        return ""

    return "\n    ".join(
        f'<script type="application/ld+json">\n{s}\n</script>' for s in scripts
    )


def render_search_box(lang: str) -> str:
    """渲染搜索框。"""
    placeholder = tr("search_placeholder", lang)
    action = f"/{lang}/search/"
    return f'''<div class="search-box" role="search">
        <form action="{action}" method="get" class="search-form" aria-label="Search">
            <label for="search-input" class="sr-only">{escape(placeholder)}</label>
            <input type="search" id="search-input" name="q" class="search-input"
                   placeholder="{escape(placeholder)}" autocomplete="off" aria-label="Search">
            <button type="submit" class="search-submit" aria-label="Search">
                <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                    <circle cx="11" cy="11" r="8"></circle>
                    <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
                </svg>
            </button>
        </form>
    </div>'''


def render_language_switcher(lang: str, current_path: str) -> str:
    """渲染语言切换器。current_path 形如 /en/tools/xyz/"""
    path_no_lang = strip_lang_prefix(current_path)

    items = []
    for lc in SUPPORTED_LANGS:
        if path_no_lang == "/":
            url = f"/{lc}/"
        else:
            url = f"/{lc}{path_no_lang}"
        active = ' class="active" aria-current="true"' if lc == lang else ""
        name = LANG_MAP.get(lc, lc)
        items.append(f'                <li role="none"><a role="menuitem" href="{url}" hreflang="{lc}"{active}>{escape(name)}</a></li>')

    current_name = LANG_MAP.get(lang, lang)
    items_str = "\n".join(items)
    return f'''<div class="language-switcher" aria-label="Language selector">
        <button class="lang-trigger" aria-haspopup="true" aria-expanded="false" aria-label="Switch language">
            <span class="lang-current">{escape(current_name)}</span>
            <span class="caret" aria-hidden="true">▾</span>
        </button>
        <ul class="lang-menu" role="menu">
{items_str}
        </ul>
    </div>'''


def render_header(lang: str, current_section: str = "") -> str:
    """渲染头部导航。"""
    site_t = site_title(lang)
    home = f"/{lang}/"
    nav_items = [
        (TYPE_TOOLS, tr("tools_title", lang)),
        (TYPE_COMPARE, tr("compare_title", lang)),
        (TYPE_GUIDES, tr("guides_title", lang)),
        (TYPE_RANKING, tr("ranking_title", lang)),
        (TYPE_FAQ, tr("faq_title", lang)),
    ]
    nav_html = "\n            ".join(
        f'<a href="{url_section(lang, ptype)}"{" class=\"active\"" if ptype == current_section else ""}>{escape(label)}</a>'
        for ptype, label in nav_items
    )
    search = render_search_box(lang)
    lang_switch = render_language_switcher(lang, home)

    return f'''<header class="site-header" role="banner">
    <div class="container header-inner">
        <a href="{home}" class="logo" aria-label="{escape(site_t)} home">
            <img src="/favicon.svg" alt="{escape(site_t)}" width="32" height="32" loading="eager">
            <span class="logo-text">{escape(site_t)}</span>
        </a>
        <nav class="main-nav" id="main-nav" aria-label="Primary navigation">
            {nav_html}
        </nav>
        <div class="header-actions" data-pagefind-ignore>
            {search}
            {lang_switch}
            <button class="menu-toggle" id="menu-toggle" aria-label="Toggle menu" aria-expanded="false" aria-controls="main-nav">
                <span class="menu-bar"></span>
                <span class="menu-bar"></span>
                <span class="menu-bar"></span>
            </button>
        </div>
    </div>
</header>'''


def render_footer(lang: str) -> str:
    """渲染底部。"""
    site_t = site_title(lang)
    desc = tr("default_description", lang)
    home = f"/{lang}/"

    explore_links = "\n                ".join(
        f'<li><a href="{url_section(lang, ptype)}">{escape(tr(key, lang))}</a></li>'
        for ptype, key in [
            (TYPE_TOOLS, "tools_title"),
            (TYPE_COMPARE, "compare_title"),
            (TYPE_GUIDES, "guides_title"),
            (TYPE_RANKING, "ranking_title"),
            (TYPE_FAQ, "faq_title"),
        ]
    )

    lang_links = "\n                ".join(
        f'<li><a href="/{lc}/" hreflang="{lc}">{escape(LANG_MAP.get(lc, lc))}</a></li>'
        for lc in SUPPORTED_LANGS
    )

    disclaimer = ("Prices and plans shown are for reference only and may change. "
                  "Always verify on the official provider website before purchasing. "
                  "We may earn affiliate commissions from some links.")
    year = DEFAULT_DATE[:4]

    return f'''<footer class="site-footer" role="contentinfo">
    <div class="container">
        <div class="footer-grid">
            <div class="footer-col footer-brand">
                <h4>{escape(site_t)}</h4>
                <p>{escape(desc)}</p>
            </div>
            <div class="footer-col">
                <h4>Explore</h4>
                <ul>
                    {explore_links}
                </ul>
            </div>
            <div class="footer-col">
                <h4>{escape(tr("about", lang))}</h4>
                <ul>
                    <li><a href="{home}">{escape(tr("about", lang))}</a></li>
                    <li><a href="{home}">{escape(tr("contact", lang))}</a></li>
                    <li><a href="{home}">{escape(tr("privacy", lang))}</a></li>
                </ul>
            </div>
            <div class="footer-col">
                <h4>Languages</h4>
                <ul class="footer-langs">
                    {lang_links}
                </ul>
            </div>
        </div>
        <div class="footer-disclaimer">
            <p>{escape(disclaimer)}</p>
        </div>
        <div class="footer-bottom">
            <p>&copy; {year} {escape(site_t)}. All rights reserved.</p>
        </div>
    </div>
</footer>'''


def render_tool_card(tool: dict, lang: str) -> str:
    """渲染工具卡片。"""
    pm = tr("per_month", lang)
    price_str = fmt_price(tool["price_min"], tool["price_max"], tool["currency"], pm)
    free_tag = f'<span class="price-tag free">{escape(tr("free_tier", lang))}</span>' if tool["free_tier"] else ""
    cat_n = cat_name(tool["category"], lang)
    name = escape(tool["name"])
    desc = escape(tool["description_en"][:140])
    url = url_tool(lang, tool["id"])
    icon_letter = escape(tool["name"][:1]) if tool["name"] else "?"

    return f'''<article class="tool-card" data-pagefind-body>
    <a href="{url}" class="tool-card-link" aria-label="{name} - {escape(tr("view_pricing", lang))}">
        <div class="tool-card-header">
            <span class="tool-icon-placeholder" aria-hidden="true">{icon_letter}</span>
            <div class="tool-card-title">
                <h3>{name}</h3>
                <span class="tool-brand">{escape(tool["vendor"])}</span>
            </div>
        </div>
        <div class="tool-card-body">
            <p class="tool-description">{desc}</p>
            <div class="tool-pricing">
                {free_tag}
                <span class="price-tag price">{escape(price_str)}</span>
            </div>
            <div class="tool-category">
                <span class="category-pill">{escape(cat_n)}</span>
            </div>
        </div>
        <div class="tool-card-footer">
            <span class="btn btn-primary btn-sm view-pricing-btn">
                {escape(tr("view_pricing", lang))} <span aria-hidden="true">→</span>
            </span>
        </div>
    </a>
</article>'''


def render_base(lang: str, title: str, description: str, canonical_path: str,
                main_content: str, page_type: str = "", keywords: str = "",
                breadcrumb_items: list | None = None, product_data: dict | None = None,
                faq_items: list | None = None, is_home: bool = False, is_node: bool = False,
                og_type: str = "website", article_section: str = "",
                published_time: str = "", modified_time: str = "",
                current_section: str = "") -> str:
    """渲染完整 HTML 文档（baseof 等价）。"""
    head_seo = render_seo(
        lang, title, description, canonical_path,
        keywords=keywords, og_type=og_type,
        article_section=article_section,
        published_time=published_time, modified_time=modified_time,
        is_home=is_home,
    )
    structured = render_structured_data(
        lang, page_type, title, description, canonical_path,
        breadcrumb_items=breadcrumb_items, product_data=product_data,
        faq_items=faq_items, is_home=is_home, is_node=is_node,
    )
    header = render_header(lang, current_section=current_section)
    footer = render_footer(lang)
    direction = lang_dir(lang)
    body_class = "rtl" if lang == "ar" else ""
    lang_cc = lang_code(lang)

    structured_block = f"\n    {structured}\n" if structured else ""

    return f'''<!DOCTYPE html>
<html lang="{lang_cc}" dir="{direction}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="generator" content="generate_static_html.py">
    <meta name="base-url" content="{BASE_URL}">
    {head_seo}
{structured_block}
    <link rel="icon" href="/favicon.svg">
    <link rel="stylesheet" href="/css/style.css">
    <link rel="stylesheet" href="/css/search.css">
    <link rel="stylesheet" href="/pagefind/pagefind-ui.css">
</head>
<body class="{body_class}">
    <a href="#main-content" class="skip-link">Skip to content</a>
    {header}
    <main class="container" id="main-content">
        {main_content}
    </main>
    {footer}
    <script src="/js/main.js" defer></script>
    <script src="/pagefind/pagefind-ui.js" defer></script>
</body>
</html>'''


# ----------------------------------------------------------------------
# 页面生成器
# ----------------------------------------------------------------------
def gen_tool_page_html(tool: dict, lang: str) -> str:
    """工具详情页。"""
    pm = tr("per_month", lang)
    price_str = fmt_price(tool["price_min"], tool["price_max"], tool["currency"], pm)
    cat_n = cat_name(tool["category"], lang)
    free_text = tr("free", lang) if tool["free_tier"] else tr("premium", lang)
    features_html = "\n            ".join(f"<li>{escape(f)}</li>" for f in tool["features"])
    alts = tool.get("alternatives", []) or []
    alt_links = []
    for alt_id in alts[:10]:
        alt_tool = _TOOLS_BY_ID.get(alt_id)
        if alt_tool:
            alt_links.append(f'<li><a href="{url_tool(lang, alt_id)}">{escape(alt_tool["name"])}</a></li>')
        else:
            alt_links.append(f'<li>{escape(alt_id)}</li>')
    alt_html = "\n            ".join(alt_links) if alt_links else "<li>—</li>"

    name = tool["name"]
    title = f"{name} {tr('pricing', lang)} {DEFAULT_DATE}"
    description = tool["description_en"][:160]
    canonical = url_tool(lang, tool["id"])
    keywords = f"{name}, {tool['vendor']}, {cat_n}, AI tool pricing, {tool['category']}"

    breadcrumb_items = [
        (site_title(lang), f"/{lang}/"),
        (tr("tools_title", lang), url_section(lang, TYPE_TOOLS)),
        (name, canonical),
    ]

    tool_links = [
        (tr("guides_title", lang), url_guide(lang, tool["id"])),
        (tr("faq_title", lang), url_faq(lang, tool["id"])),
        (tr("history_title", lang), url_history(lang, tool["id"])),
        (tr("alternatives_title", lang), url_alternatives(lang, tool["id"])),
    ]
    tool_links_html = "\n            ".join(
        f'<li><a href="{u}">{escape(label)}</a></li>' for label, u in tool_links
    )

    main_content = f'''<article class="single-detail" data-pagefind-body>
    <nav class="breadcrumb" aria-label="Breadcrumb" data-pagefind-ignore>
        <ol>
            <li><a href="/{lang}/">{escape(site_title(lang))}</a></li>
            <li><a href="{url_section(lang, TYPE_TOOLS)}">{escape(tr("tools_title", lang))}</a></li>
            <li aria-current="page">{escape(name)}</li>
        </ol>
    </nav>
    <header class="single-header">
        <h1>{escape(name)} — {escape(tr("pricing", lang))} {DEFAULT_DATE}</h1>
        <div class="single-meta">
            <span class="meta-price">
                {('<span class="free-tag">' + escape(tr('free_tier', lang)) + '</span>') if tool['free_tier'] else ''}
                <span class="price-range">{escape(price_str)}</span>
            </span>
            <span class="meta-separator" aria-hidden="true">·</span>
            <span class="meta-category">
                <a href="{url_ranking(lang, tool['category'])}">{escape(cat_n)}</a>
            </span>
        </div>
        <div class="single-cta">
            <a href="{escape(tool['url'])}" class="btn btn-primary" target="_blank" rel="noopener nofollow sponsored">
                {escape(tr("official_website", lang))} ↗
            </a>
        </div>
    </header>
    <div class="single-content">
        <p>{escape(tool["description_en"])}</p>

        <h2>{escape(tr("tools_overview", lang))}</h2>
        <ul>
            <li><strong>{escape(tr("vendor", lang))}</strong>: {escape(tool["vendor"])}</li>
            <li><strong>{escape(tr("category", lang))}</strong>: {escape(cat_n)}</li>
            <li><strong>{escape(tr("pricing", lang))}</strong>: {escape(price_str)}</li>
            <li><strong>{escape(tr("free_tier", lang))}</strong>: {escape(free_text)}</li>
            <li><strong>{escape(tr("founded_year", lang))}</strong>: {tool["founded_year"]}</li>
            <li><strong>{escape(tr("popularity", lang))}</strong>: {tool["popularity_score"]}/100</li>
        </ul>

        <h2>{escape(tr("features", lang))}</h2>
        <ul>
            {features_html}
        </ul>

        <h2>{escape(tr("tools_pricing_table", lang))}</h2>
        <table>
            <thead>
                <tr>
                    <th>{escape(tr("pricing", lang))}</th>
                    <th>{escape(tr("features", lang))}</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td>{escape(price_str)}</td>
                    <td>{escape(", ".join(tool["features"][:3]))}</td>
                </tr>
            </tbody>
        </table>

        <h2>{escape(tr("alternatives_for", lang))} {escape(name)}</h2>
        <ul>
            {alt_html}
        </ul>

        <h2>{escape(tr("related_tools", lang))}</h2>
        <ul>
            {tool_links_html}
        </ul>

        <h2>{escape(tr("official_website", lang))}</h2>
        <p><a href="{escape(tool['url'])}" target="_blank" rel="noopener nofollow sponsored">{escape(name)} ↗</a></p>
    </div>
    <section class="single-languages" data-pagefind-ignore>
        <h2>{escape(tr("about", lang))}</h2>
        {render_language_switcher(lang, canonical)}
    </section>
</article>'''

    product_data = {
        "category": cat_n,
        "vendor": tool["vendor"],
        "currency": tool["currency"],
        "price_min": tool["price_min"],
        "price_max": tool["price_max"],
        "free_tier": tool["free_tier"],
        "url": tool["url"],
    }

    return render_base(
        lang, title, description, canonical,
        main_content, page_type=TYPE_TOOLS,
        keywords=keywords, breadcrumb_items=breadcrumb_items,
        product_data=product_data, og_type="article",
        article_section=cat_n, current_section=TYPE_TOOLS,
    )


def gen_compare_page_html(tool_a: dict, tool_b: dict, lang: str) -> str:
    """对比页。"""
    vs = tr("vs_text", lang)
    pm = tr("per_month", lang)
    price_a = fmt_price(tool_a["price_min"], tool_a["price_max"], tool_a["currency"], pm)
    price_b = fmt_price(tool_b["price_min"], tool_b["price_max"], tool_b["currency"], pm)
    cat_a = cat_name(tool_a["category"], lang)
    cat_b = cat_name(tool_b["category"], lang)
    free_a = tr("free", lang) if tool_a["free_tier"] else tr("premium", lang)
    free_b = tr("free", lang) if tool_b["free_tier"] else tr("premium", lang)

    name_a, name_b = tool_a["name"], tool_b["name"]
    title = f"{name_a} {vs} {name_b}: {tr('pricing', lang)} {DEFAULT_DATE}"
    description = f"{name_a} vs {name_b} pricing and features comparison."
    canonical = url_compare(lang, tool_a["id"], tool_b["id"])
    keywords = f"{name_a}, {name_b}, compare, vs, AI tools pricing"

    breadcrumb_items = [
        (site_title(lang), f"/{lang}/"),
        (tr("compare_title", lang), url_section(lang, TYPE_COMPARE)),
        (f"{name_a} vs {name_b}", canonical),
    ]

    features_a_html = "\n            ".join(f"<li>{escape(f)}</li>" for f in tool_a["features"])
    features_b_html = "\n            ".join(f"<li>{escape(f)}</li>" for f in tool_b["features"])

    cheaper = name_a if tool_a["price_min"] < tool_b["price_min"] else name_b
    verdict_text = (f"{name_a} is {'cheaper' if tool_a['price_min'] < tool_b['price_min'] else 'pricier'} than {name_b}. "
                    f"Choose {name_a} if you need {tool_a['features'][0].lower()}; "
                    f"choose {name_b} if you need {tool_b['features'][0].lower()}.")

    main_content = f'''<article class="single-detail" data-pagefind-body>
    <nav class="breadcrumb" aria-label="Breadcrumb" data-pagefind-ignore>
        <ol>
            <li><a href="/{lang}/">{escape(site_title(lang))}</a></li>
            <li><a href="{url_section(lang, TYPE_COMPARE)}">{escape(tr("compare_title", lang))}</a></li>
            <li aria-current="page">{escape(name_a)} {escape(vs)} {escape(name_b)}</li>
        </ol>
    </nav>
    <header class="single-header">
        <h1>{escape(name_a)} {escape(vs)} {escape(name_b)}</h1>
        <div class="single-meta">
            <span class="meta-category">{escape(tr("compare_title", lang))} — {DEFAULT_DATE}</span>
        </div>
    </header>
    <div class="single-content">
        <h2>{escape(tr("tools_overview", lang))}</h2>
        <table>
            <thead>
                <tr>
                    <th>Item</th>
                    <th>{escape(name_a)}</th>
                    <th>{escape(name_b)}</th>
                </tr>
            </thead>
            <tbody>
                <tr><td>{escape(tr("vendor", lang))}</td><td>{escape(tool_a["vendor"])}</td><td>{escape(tool_b["vendor"])}</td></tr>
                <tr><td>{escape(tr("category", lang))}</td><td>{escape(cat_a)}</td><td>{escape(cat_b)}</td></tr>
                <tr><td>{escape(tr("pricing", lang))}</td><td>{escape(price_a)}</td><td>{escape(price_b)}</td></tr>
                <tr><td>{escape(tr("free_tier", lang))}</td><td>{escape(free_a)}</td><td>{escape(free_b)}</td></tr>
                <tr><td>{escape(tr("founded_year", lang))}</td><td>{tool_a["founded_year"]}</td><td>{tool_b["founded_year"]}</td></tr>
                <tr><td>{escape(tr("popularity", lang))}</td><td>{tool_a["popularity_score"]}/100</td><td>{tool_b["popularity_score"]}/100</td></tr>
            </tbody>
        </table>

        <h2>{escape(tr("features", lang))}</h2>
        <h3>{escape(name_a)}</h3>
        <ul>
            {features_a_html}
        </ul>
        <h3>{escape(name_b)}</h3>
        <ul>
            {features_b_html}
        </ul>

        <h2>{escape(tr("verdict", lang))}</h2>
        <p>{escape(verdict_text)}</p>

        <h2>{escape(tr("official_website", lang))}</h2>
        <ul>
            <li><a href="{escape(tool_a['url'])}" target="_blank" rel="noopener nofollow sponsored">{escape(name_a)} ↗</a></li>
            <li><a href="{escape(tool_b['url'])}" target="_blank" rel="noopener nofollow sponsored">{escape(name_b)} ↗</a></li>
        </ul>
    </div>
    <section class="single-languages" data-pagefind-ignore>
        <h2>{escape(tr("about", lang))}</h2>
        {render_language_switcher(lang, canonical)}
    </section>
</article>'''

    return render_base(
        lang, title, description, canonical,
        main_content, page_type=TYPE_COMPARE,
        keywords=keywords, breadcrumb_items=breadcrumb_items,
        current_section=TYPE_COMPARE,
    )


def gen_guide_page_html(tool: dict, lang: str) -> str:
    """攻略页（模板版）。"""
    cat_n = cat_name(tool["category"], lang)
    annual_price = round(tool["price_max"] * 12 * 0.8, 2) if tool["price_max"] > 0 else 0
    monthly_total = round(tool["price_max"] * 12, 2) if tool["price_max"] > 0 else 0

    name = tool["name"]
    title = f"{tr('save_tips', lang)}: {name} {DEFAULT_DATE}"
    description = f"Save money tips for {name} - free tier tricks, annual plans, alternatives."
    canonical = url_guide(lang, tool["id"])
    keywords = f"{name}, save money, tips, free tier, annual plan, alternatives"

    breadcrumb_items = [
        (site_title(lang), f"/{lang}/"),
        (tr("guides_title", lang), url_section(lang, TYPE_GUIDES)),
        (f"{tr('save_tips', lang)}: {name}", canonical),
    ]

    free_section = (
        f"{name} offers a free tier. Use the free tier to test core features before committing."
        if tool["free_tier"] else
        f"{name} is paid-only. Consider free alternatives like {', '.join(tool['alternatives'][:2])} before subscribing."
    )

    annual_section = (
        f"Switching to annual billing saves ~20% — total cost ~${annual_price}/year vs ${monthly_total} monthly."
        if tool["price_max"] > 0 else
        "No paid tier — fully free to use."
    )

    alt_links = "\n            ".join(
        f'<li><a href="{url_tool(lang, alt_id)}">{escape(alt_id)}</a></li>'
        for alt_id in tool["alternatives"][:5]
    ) or "<li>—</li>"

    faq_items = [
        (f"How to save money with {name}?", free_section),
        (f"Is annual plan worth it for {name}?", annual_section),
        (f"What are alternatives to {name}?", ", ".join(tool["alternatives"][:5])),
    ]

    main_content = f'''<article class="single-detail" data-pagefind-body>
    <nav class="breadcrumb" aria-label="Breadcrumb" data-pagefind-ignore>
        <ol>
            <li><a href="/{lang}/">{escape(site_title(lang))}</a></li>
            <li><a href="{url_section(lang, TYPE_GUIDES)}">{escape(tr("guides_title", lang))}</a></li>
            <li aria-current="page">{escape(tr("save_tips", lang))}: {escape(name)}</li>
        </ol>
    </nav>
    <header class="single-header">
        <h1>{escape(tr("save_tips", lang))}: {escape(name)}</h1>
        <div class="single-meta">
            <span class="meta-category">{escape(cat_n)}</span>
            <span class="meta-separator" aria-hidden="true">·</span>
            <time datetime="{DEFAULT_DATE}">{DEFAULT_DATE}</time>
        </div>
    </header>
    <div class="single-content">
        <p>{escape(tr("save_tips_intro", lang))}</p>

        <h2>1. {escape(tr("free_tier", lang))}</h2>
        <p>{escape(free_section)}</p>

        <h2>2. {escape(tr("annual_plan", lang))}</h2>
        <p>{escape(annual_section)}</p>

        <h2>3. {escape(tr("alternatives_for", lang))} {escape(name)}</h2>
        <p>Consider these {escape(cat_n)} alternatives:</p>
        <ul>
            {alt_links}
        </ul>

        <h2>4. {escape(tr("save_money", lang))} Tips</h2>
        <ul>
            <li>Use API instead of subscription if you only need light usage</li>
            <li>Stack student/non-profit discounts (up to 50% off)</li>
            <li>Watch for Black Friday / Cyber Monday deals (typically 30-50% off)</li>
            <li>Use team plan to share costs with colleagues</li>
        </ul>

        <h2>{escape(tr("verdict", lang))}</h2>
        <p>{escape(name)} is a {escape(cat_n)} tool by {escape(tool["vendor"])}. {escape(annual_section)}</p>
    </div>
    <section class="single-languages" data-pagefind-ignore>
        <h2>{escape(tr("about", lang))}</h2>
        {render_language_switcher(lang, canonical)}
    </section>
</article>'''

    return render_base(
        lang, title, description, canonical,
        main_content, page_type=TYPE_GUIDES,
        keywords=keywords, breadcrumb_items=breadcrumb_items,
        faq_items=faq_items, og_type="article",
        article_section=cat_n, published_time=f"{DEFAULT_DATE}T00:00:00Z",
        modified_time=f"{DEFAULT_DATE}T00:00:00Z", current_section=TYPE_GUIDES,
    )


def gen_ranking_page_html(category: str, tools_in_cat: list, lang: str) -> str:
    """分类排行页。"""
    cat_n = cat_name(category, lang)
    sorted_tools = sorted(tools_in_cat, key=lambda t: t.get("popularity_score", 0), reverse=True)[:10]
    pm = tr("per_month", lang)

    title = f"{tr('ranking_title', lang)}: {cat_n} {DEFAULT_DATE}"
    description = f"Top {cat_n} ranked by popularity, features and value for money."
    canonical = url_ranking(lang, category)
    keywords = f"best {cat_n}, top {cat_n}, {cat_n} ranking, AI tools"

    breadcrumb_items = [
        (site_title(lang), f"/{lang}/"),
        (tr("ranking_title", lang), url_section(lang, TYPE_RANKING)),
        (cat_n, canonical),
    ]

    rows = []
    for i, t in enumerate(sorted_tools, 1):
        price_str = fmt_price(t["price_min"], t["price_max"], t["currency"], pm)
        rows.append(
            f'<tr><td>{i}</td><td><a href="{url_tool(lang, t["id"])}">{escape(t["name"])}</a></td>'
            f'<td>{escape(t["vendor"])}</td><td>{escape(price_str)}</td>'
            f'<td>{t["popularity_score"]}/100</td></tr>'
        )
    rows_html = "\n            ".join(rows)

    main_content = f'''<section class="list-page" data-pagefind-body>
    <nav class="breadcrumb" aria-label="Breadcrumb" data-pagefind-ignore>
        <ol>
            <li><a href="/{lang}/">{escape(site_title(lang))}</a></li>
            <li><a href="{url_section(lang, TYPE_RANKING)}">{escape(tr("ranking_title", lang))}</a></li>
            <li aria-current="page">{escape(cat_n)}</li>
        </ol>
    </nav>
    <header class="list-header">
        <h1>{escape(tr("ranking_title", lang))}: {escape(cat_n)}</h1>
        <p class="list-description">{escape(tr("ranking_intro", lang))}</p>
    </header>
    <div class="list-intro">
        <h2>Top 10 {escape(cat_n)}</h2>
        <table>
            <thead>
                <tr>
                    <th>#</th>
                    <th>{escape(tr("tools_title", lang))}</th>
                    <th>{escape(tr("vendor", lang))}</th>
                    <th>{escape(tr("pricing", lang))}</th>
                    <th>{escape(tr("popularity", lang))}</th>
                </tr>
            </thead>
            <tbody>
                {rows_html}
            </tbody>
        </table>
    </div>
    <section class="single-languages" data-pagefind-ignore>
        <h2>{escape(tr("about", lang))}</h2>
        {render_language_switcher(lang, canonical)}
    </section>
</section>'''

    return render_base(
        lang, title, description, canonical,
        main_content, page_type=TYPE_RANKING,
        keywords=keywords, breadcrumb_items=breadcrumb_items,
        current_section=TYPE_RANKING,
    )


def gen_faq_page_html(tool: dict, lang: str) -> str:
    """FAQ 页。"""
    cat_n = cat_name(tool["category"], lang)
    pm = tr("per_month", lang)
    price_str = fmt_price(tool["price_min"], tool["price_max"], tool["currency"], pm)
    name = tool["name"]

    title = f"{name} FAQ {DEFAULT_DATE}"
    description = f"Frequently asked questions about {name} pricing, features, and usage."
    canonical = url_faq(lang, tool["id"])
    keywords = f"{name} FAQ, {name} questions, {name} pricing"

    breadcrumb_items = [
        (site_title(lang), f"/{lang}/"),
        (tr("faq_title", lang), url_section(lang, TYPE_FAQ)),
        (f"{name} FAQ", canonical),
    ]

    faq_items = [
        (f"How much does {name} cost?",
         f"{name} is priced at {price_str}. "
         f"{'There is a free tier available.' if tool['free_tier'] else 'No free tier is available.'}"),
        ("Is there a free trial?",
         "Yes, the free tier can be used indefinitely with limits." if tool["free_tier"]
         else "Please check the official website for trial availability."),
        (f"What category does {name} belong to?",
         f"{name} is a {cat_n} tool developed by {tool['vendor']}."),
        (f"What are the main features of {name}?",
         ", ".join(tool["features"]) + "."),
        (f"What are popular alternatives to {name}?",
         ", ".join(tool["alternatives"][:5]) + "."),
        (f"When was {name} founded?",
         f"{name} was founded in {tool['founded_year']}."),
        ("Where can I find the official website?",
         f"Visit {tool['url']} for more information."),
    ]

    faq_html = "\n        ".join(
        f'<h2>{escape(q)}</h2>\n        <p>{escape(a)}</p>' for q, a in faq_items
    )

    main_content = f'''<article class="single-detail" data-pagefind-body>
    <nav class="breadcrumb" aria-label="Breadcrumb" data-pagefind-ignore>
        <ol>
            <li><a href="/{lang}/">{escape(site_title(lang))}</a></li>
            <li><a href="{url_section(lang, TYPE_FAQ)}">{escape(tr("faq_title", lang))}</a></li>
            <li aria-current="page">{escape(name)} FAQ</li>
        </ol>
    </nav>
    <header class="single-header">
        <h1>{escape(name)} FAQ — {DEFAULT_DATE}</h1>
        <div class="single-meta">
            <span class="meta-category">{escape(cat_n)}</span>
        </div>
    </header>
    <div class="single-content">
        <p>{escape(tr("faq_intro", lang))}</p>
        {faq_html}
    </div>
    <section class="single-languages" data-pagefind-ignore>
        <h2>{escape(tr("about", lang))}</h2>
        {render_language_switcher(lang, canonical)}
    </section>
</article>'''

    return render_base(
        lang, title, description, canonical,
        main_content, page_type=TYPE_FAQ,
        keywords=keywords, breadcrumb_items=breadcrumb_items,
        faq_items=faq_items, current_section=TYPE_FAQ,
    )


def gen_history_page_html(tool: dict, lang: str) -> str:
    """价格历史页（模拟数据）。"""
    pm = tr("per_month", lang)
    price_str = fmt_price(tool["price_min"], tool["price_max"], tool["currency"], pm)
    name = tool["name"]
    cat_n = cat_name(tool["category"], lang)

    title = f"{name} {tr('history_title', lang)} {DEFAULT_DATE}"
    description = f"Price history and trend for {name}."
    canonical = url_history(lang, tool["id"])
    keywords = f"{name} price history, {name} price trend, {name} pricing"

    breadcrumb_items = [
        (site_title(lang), f"/{lang}/"),
        (tr("history_title", lang), url_section(lang, TYPE_HISTORY)),
        (f"{name} {tr('history_title', lang)}", canonical),
    ]

    base = tool["price_max"] if tool["price_max"] > 0 else 10
    history_rows = []
    months = ["2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-06", DEFAULT_DATE[:7]]
    for i, m in enumerate(months):
        delta = (i - 3) * 0.5
        p = round(base * (1 + delta * 0.01), 2)
        sign = "+" if delta >= 0 else ""
        history_rows.append(
            f'<tr><td>{m}</td><td>${p} {tool["currency"]}{pm}</td><td>{sign}{delta:.1f}%</td></tr>'
        )
    history_html = "\n            ".join(history_rows)

    trend_text = ("stable" if tool["price_max"] < 50 else "increasing slightly")

    main_content = f'''<article class="single-detail" data-pagefind-body>
    <nav class="breadcrumb" aria-label="Breadcrumb" data-pagefind-ignore>
        <ol>
            <li><a href="/{lang}/">{escape(site_title(lang))}</a></li>
            <li><a href="{url_section(lang, TYPE_HISTORY)}">{escape(tr("history_title", lang))}</a></li>
            <li aria-current="page">{escape(name)} {escape(tr("history_title", lang))}</li>
        </ol>
    </nav>
    <header class="single-header">
        <h1>{escape(name)} {escape(tr("history_title", lang))}</h1>
        <div class="single-meta">
            <span class="meta-category">{escape(cat_n)}</span>
        </div>
    </header>
    <div class="single-content">
        <p>{escape(tr("price_trend", lang))} for {escape(name)} — {DEFAULT_DATE}.</p>

        <h2>{escape(tr("history_title", lang))}</h2>
        <table>
            <thead>
                <tr>
                    <th>Date</th>
                    <th>Price</th>
                    <th>Change</th>
                </tr>
            </thead>
            <tbody>
                {history_html}
            </tbody>
        </table>

        <h2>{escape(tr("verdict", lang))}</h2>
        <p>Current price: <strong>{escape(price_str)}</strong></p>
        <p>The price has been {escape(trend_text)} over the past 6 months.</p>

        <h2>{escape(tr("alternatives_for", lang))} {escape(name)}</h2>
        <p>{escape(", ".join(tool["alternatives"][:5]))}</p>
    </div>
    <section class="single-languages" data-pagefind-ignore>
        <h2>{escape(tr("about", lang))}</h2>
        {render_language_switcher(lang, canonical)}
    </section>
</article>'''

    return render_base(
        lang, title, description, canonical,
        main_content, page_type=TYPE_HISTORY,
        keywords=keywords, breadcrumb_items=breadcrumb_items,
        current_section=TYPE_HISTORY,
    )


def gen_alternatives_page_html(tool: dict, lang: str) -> str:
    """替代品页。"""
    pm = tr("per_month", lang)
    cat_n = cat_name(tool["category"], lang)
    name = tool["name"]

    title = f"{tr('alternatives_for', lang)} {name} {DEFAULT_DATE}"
    description = f"Top alternatives to {name} with pricing and features comparison."
    canonical = url_alternatives(lang, tool["id"])
    keywords = f"{name} alternatives, alternatives to {name}, {cat_n} alternatives"

    breadcrumb_items = [
        (site_title(lang), f"/{lang}/"),
        (tr("alternatives_title", lang), url_section(lang, TYPE_ALTERNATIVES)),
        (f"{tr('alternatives_for', lang)} {name}", canonical),
    ]

    alt_tools = []
    for alt_id in tool["alternatives"][:10]:
        alt_tool = _TOOLS_BY_ID.get(alt_id)
        if alt_tool:
            alt_tools.append(alt_tool)

    if not alt_tools:
        body_html = f'<p>No alternatives listed. See all tools in <a href="{url_ranking(lang, tool["category"])}">{escape(cat_n)}</a>.</p>'
    else:
        rows = []
        for alt in alt_tools:
            price_str = fmt_price(alt["price_min"], alt["price_max"], alt["currency"], pm)
            free = tr("free", lang) if alt["free_tier"] else tr("premium", lang)
            rows.append(
                f'<tr><td><a href="{url_tool(lang, alt["id"])}">{escape(alt["name"])}</a></td>'
                f'<td>{escape(alt["vendor"])}</td><td>{escape(price_str)}</td>'
                f'<td>{escape(free)}</td><td>{alt["popularity_score"]}/100</td></tr>'
            )
        rows_html = "\n            ".join(rows)
        tool_price = fmt_price(tool["price_min"], tool["price_max"], tool["currency"], pm)
        body_html = f'''<p>Looking for {escape(name)} alternatives? Here are the top alternatives:</p>
        <table>
            <thead>
                <tr>
                    <th>{escape(tr("tools_title", lang))}</th>
                    <th>{escape(tr("vendor", lang))}</th>
                    <th>{escape(tr("pricing", lang))}</th>
                    <th>{escape(tr("free_tier", lang))}</th>
                    <th>{escape(tr("popularity", lang))}</th>
                </tr>
            </thead>
            <tbody>
                {rows_html}
            </tbody>
        </table>
        <h2>{escape(tr("verdict", lang))}</h2>
        <p>Compare these alternatives with {escape(name)} ({escape(tool_price)}) to find the best fit for your needs.</p>'''

    main_content = f'''<article class="single-detail" data-pagefind-body>
    <nav class="breadcrumb" aria-label="Breadcrumb" data-pagefind-ignore>
        <ol>
            <li><a href="/{lang}/">{escape(site_title(lang))}</a></li>
            <li><a href="{url_section(lang, TYPE_ALTERNATIVES)}">{escape(tr("alternatives_title", lang))}</a></li>
            <li aria-current="page">{escape(tr("alternatives_for", lang))} {escape(name)}</li>
        </ol>
    </nav>
    <header class="single-header">
        <h1>{escape(tr("alternatives_for", lang))} {escape(name)}</h1>
        <div class="single-meta">
            <span class="meta-category">{escape(cat_n)}</span>
        </div>
    </header>
    <div class="single-content">
        {body_html}
    </div>
    <section class="single-languages" data-pagefind-ignore>
        <h2>{escape(tr("about", lang))}</h2>
        {render_language_switcher(lang, canonical)}
    </section>
</article>'''

    return render_base(
        lang, title, description, canonical,
        main_content, page_type=TYPE_ALTERNATIVES,
        keywords=keywords, breadcrumb_items=breadcrumb_items,
        current_section=TYPE_ALTERNATIVES,
    )


def gen_home_page_html(lang: str) -> str:
    """首页。"""
    site_t = site_title(lang)
    desc = tr("default_description", lang)
    canonical = f"/{lang}/"

    # Top tools by popularity
    sorted_tools = sorted(_ALL_TOOLS, key=lambda t: t.get("popularity_score", 0), reverse=True)
    top_tools = sorted_tools[:6]
    top_compare = _COMPARE_PAIRS[:4]

    # Category counts
    cat_counts: dict[str, int] = {}
    for t in _ALL_TOOLS:
        cat_counts[t["category"]] = cat_counts.get(t["category"], 0) + 1
    sorted_cats = sorted(cat_counts.items(), key=lambda x: -x[1])[:12]

    tool_cards_html = "\n            ".join(
        render_tool_card(t, lang) for t in top_tools
    )

    cat_cards_html = "\n                ".join(
        f'<a href="{url_ranking(lang, slug)}" class="category-card">'
        f'<span class="category-icon" aria-hidden="true">▶</span>'
        f'<span class="category-name">{escape(cat_name(slug, lang))}</span>'
        f'<span class="category-count">{count} {escape(tr("tools_title", lang))}</span>'
        f'</a>'
        for slug, count in sorted_cats
    )

    compare_cards_html = "\n                ".join(
        f'<article class="compare-card" data-pagefind-body>'
        f'<a href="{url_compare(lang, a["id"], b["id"])}" class="compare-link">'
        f'<h3 class="compare-title">{escape(a["name"])} vs {escape(b["name"])}</h3>'
        f'<p class="compare-desc">Compare {escape(a["name"])} and {escape(b["name"])} pricing and features.</p>'
        f'</a></article>'
        for a, b in top_compare
    ) if top_compare else ""

    popular_tools_links = "\n                ".join(
        f'<a href="{url_tool(lang, t["id"])}">{escape(t["name"])}</a>'
        for t in sorted_tools[:5]
    )

    search_box = render_search_box(lang)
    lang_switch = render_language_switcher(lang, canonical)

    main_content = f'''<div class="home-page" data-pagefind-body>
    <section class="hero">
        <div class="hero-inner">
            <h1 class="hero-title">{escape(site_t)}</h1>
            <p class="hero-subtitle">{escape(desc)}</p>
            <div class="hero-search">
                {search_box}
            </div>
            <div class="hero-quick-links" data-pagefind-ignore>
                <span class="quick-links-label">Popular:</span>
                {popular_tools_links}
            </div>
            <div class="hero-langs" data-pagefind-ignore>
                {lang_switch}
            </div>
        </div>
    </section>
    <section class="home-section home-categories">
        <h2 class="section-title">Browse by Category</h2>
        <div class="category-grid">
                {cat_cards_html}
        </div>
    </section>
    <section class="home-section home-recent">
        <h2 class="section-title">Latest Price Changes</h2>
        <div class="tool-grid">
            {tool_cards_html}
        </div>
        <div class="home-section-footer">
            <a href="{url_section(lang, TYPE_TOOLS)}" class="btn btn-secondary">View all tools →</a>
        </div>
    </section>
    {'<section class="home-section home-compare"><h2 class="section-title">Popular Comparisons</h2><div class="compare-grid">' + compare_cards_html + '</div><div class="home-section-footer"><a href="' + url_section(lang, TYPE_COMPARE) + '" class="btn btn-secondary">View all comparisons →</a></div></section>' if compare_cards_html else ''}
</div>'''

    return render_base(
        lang, site_t, desc, canonical,
        main_content, page_type="",
        is_home=True, current_section="",
    )


def gen_list_page_html(lang: str, section: str) -> str:
    """列表页 /{lang}/{section}/index.html。"""
    canonical = url_section(lang, section)
    sorted_tools = sorted(_ALL_TOOLS, key=lambda t: t.get("popularity_score", 0), reverse=True)

    if section == TYPE_TOOLS:
        title = tr("tools_title", lang)
        desc = tr("default_description", lang)
        # 显示前 100 个工具
        items = sorted_tools[:100]
        items_html = "\n            ".join(render_tool_card(t, lang) for t in items)
        body = f'<div class="tool-grid">\n            {items_html}\n        </div>'
    elif section == TYPE_COMPARE:
        title = tr("compare_title", lang)
        desc = "Compare AI tools side by side."
        pairs = _COMPARE_PAIRS[:50]
        if pairs:
            items_html = "\n            ".join(
                f'<article class="compare-card" data-pagefind-body>'
                f'<a href="{url_compare(lang, a["id"], b["id"])}" class="compare-link">'
                f'<h3 class="compare-title">{escape(a["name"])} vs {escape(b["name"])}</h3>'
                f'<p class="compare-desc">Compare pricing and features.</p>'
                f'</a></article>'
                for a, b in pairs
            )
            body = f'<div class="compare-grid">\n            {items_html}\n        </div>'
        else:
            body = '<div class="empty-state"><p>No comparisons available.</p></div>'
    elif section == TYPE_GUIDES:
        title = tr("guides_title", lang)
        desc = tr("save_tips_intro", lang)
        items = sorted_tools[:50]
        items_html = "\n            ".join(
            f'<article class="card generic-card" data-pagefind-body>'
            f'<a href="{url_guide(lang, t["id"])}" class="card-link">'
            f'<h2 class="card-title">{escape(tr("save_tips", lang))}: {escape(t["name"])}</h2>'
            f'<p class="card-description">Save money tips for {escape(t["name"])}.</p>'
            f'<span class="card-meta"><time datetime="{DEFAULT_DATE}">{DEFAULT_DATE}</time></span>'
            f'</a></article>'
            for t in items
        )
        body = f'<div class="tool-grid">\n            {items_html}\n        </div>'
    elif section == TYPE_RANKING:
        title = tr("ranking_title", lang)
        desc = tr("ranking_intro", lang)
        cat_counts: dict[str, int] = {}
        for t in _ALL_TOOLS:
            cat_counts[t["category"]] = cat_counts.get(t["category"], 0) + 1
        items_html = "\n            ".join(
            f'<article class="card generic-card" data-pagefind-body>'
            f'<a href="{url_ranking(lang, slug)}" class="card-link">'
            f'<h2 class="card-title">{escape(cat_name(slug, lang))}</h2>'
            f'<p class="card-description">{count} {escape(tr("tools_title", lang))}</p>'
            f'</a></article>'
            for slug, count in sorted(cat_counts.items(), key=lambda x: -x[1])
        )
        body = f'<div class="tool-grid">\n            {items_html}\n        </div>'
    elif section == TYPE_FAQ:
        title = tr("faq_title", lang)
        desc = tr("faq_intro", lang)
        items = sorted_tools[:50]
        items_html = "\n            ".join(
            f'<article class="card generic-card" data-pagefind-body>'
            f'<a href="{url_faq(lang, t["id"])}" class="card-link">'
            f'<h2 class="card-title">{escape(t["name"])} FAQ</h2>'
            f'<p class="card-description">Frequently asked questions about {escape(t["name"])}.</p>'
            f'<span class="card-meta"><time datetime="{DEFAULT_DATE}">{DEFAULT_DATE}</time></span>'
            f'</a></article>'
            for t in items
        )
        body = f'<div class="tool-grid">\n            {items_html}\n        </div>'
    elif section == TYPE_HISTORY:
        title = tr("history_title", lang)
        desc = "Price history for AI tools."
        items = sorted_tools[:50]
        items_html = "\n            ".join(
            f'<article class="card generic-card" data-pagefind-body>'
            f'<a href="{url_history(lang, t["id"])}" class="card-link">'
            f'<h2 class="card-title">{escape(t["name"])} {escape(tr("history_title", lang))}</h2>'
            f'<p class="card-description">Price trend for {escape(t["name"])}.</p>'
            f'<span class="card-meta"><time datetime="{DEFAULT_DATE}">{DEFAULT_DATE}</time></span>'
            f'</a></article>'
            for t in items
        )
        body = f'<div class="tool-grid">\n            {items_html}\n        </div>'
    elif section == TYPE_ALTERNATIVES:
        title = tr("alternatives_title", lang)
        desc = "AI tool alternatives."
        items = sorted_tools[:50]
        items_html = "\n            ".join(
            f'<article class="card generic-card" data-pagefind-body>'
            f'<a href="{url_alternatives(lang, t["id"])}" class="card-link">'
            f'<h2 class="card-title">{escape(tr("alternatives_for", lang))} {escape(t["name"])}</h2>'
            f'<p class="card-description">Alternatives to {escape(t["name"])}.</p>'
            f'<span class="card-meta"><time datetime="{DEFAULT_DATE}">{DEFAULT_DATE}</time></span>'
            f'</a></article>'
            for t in items
        )
        body = f'<div class="tool-grid">\n            {items_html}\n        </div>'
    else:
        title = site_title(lang)
        desc = tr("default_description", lang)
        body = '<div class="empty-state"><p>Unknown section.</p></div>'

    breadcrumb_items = [
        (site_title(lang), f"/{lang}/"),
        (title, canonical),
    ]

    main_content = f'''<section class="list-page" data-pagefind-body>
    <nav class="breadcrumb" aria-label="Breadcrumb" data-pagefind-ignore>
        <ol>
            <li><a href="/{lang}/">{escape(site_title(lang))}</a></li>
            <li aria-current="page">{escape(title)}</li>
        </ol>
    </nav>
    <header class="list-header">
        <h1>{escape(title)}</h1>
        <p class="list-description">{escape(desc)}</p>
    </header>
    <div class="list-intro">
        {body}
    </div>
    <section class="single-languages" data-pagefind-ignore>
        <h2>{escape(tr("about", lang))}</h2>
        {render_language_switcher(lang, canonical)}
    </section>
</section>'''

    return render_base(
        lang, title, desc, canonical,
        main_content, page_type="",
        breadcrumb_items=breadcrumb_items, is_node=True,
        current_section=section,
    )


def gen_404_page_html() -> str:
    """404 页面（英文）。"""
    lang = "en"
    canonical = "/404.html"
    main_content = '''<section class="error-page" data-pagefind-ignore>
    <div class="error-content">
        <h1 class="error-code">404</h1>
        <p class="error-message">Oops! The page you are looking for was not found.</p>
        <p class="error-hint">It may have been moved, deleted, or never existed.</p>
        <div class="error-search">
            ''' + render_search_box(lang) + '''
        </div>
        <div class="error-popular">
            <h2>Popular AI Tools</h2>
            <ul class="error-popular-list">
                <li><a href="/en/tools/chatgpt-plus/">ChatGPT Plus</a></li>
                <li><a href="/en/tools/claude-pro/">Claude Pro</a></li>
                <li><a href="/en/tools/gemini-advanced/">Gemini Advanced</a></li>
            </ul>
        </div>
        <div class="error-actions">
            <a href="/en/" class="btn btn-primary">← Back to Home</a>
            <a href="/en/tools/" class="btn btn-secondary">Browse all tools</a>
        </div>
    </div>
</section>'''
    return render_base(
        lang, "404 - Page Not Found",
        "The page you are looking for was not found.",
        canonical, main_content, current_section="",
    )


# ----------------------------------------------------------------------
# robots.txt & sitemap 生成
# ----------------------------------------------------------------------
def gen_robots_txt() -> str:
    return f"""# robots.txt for AI Tools Pricing Hub
# Site: {BASE_URL}

User-agent: *
Allow: /
Disallow: /search/
Disallow: /search?q=
Disallow: /*/search?q=
Disallow: /pagefind/

Crawl-delay: 1

Sitemap: {BASE_URL}sitemap-index.xml
"""


def gen_sitemaps(tools: list, compare_pairs: list, langs: list) -> tuple[int, int]:
    """生成 sitemap-{lang}.xml 和 sitemap-index.xml。返回 (子 sitemap 数, 总 URL 数)。"""
    from xml.sax.saxutils import escape as xml_escape

    # 计算每个分类的工具
    cat_set: set[str] = set()
    for t in tools:
        cat_set.add(t["category"])
    categories = sorted(cat_set)

    sub_count = 0
    total_urls = 0

    for lang in langs:
        urls: list[tuple[str, str, str]] = []  # (loc, changefreq, priority)
        # 首页
        urls.append((f"{BASE_URL}{lang}/", "daily", "1.0"))
        # 列表页
        for ptype in ALL_TYPES:
            urls.append((f"{BASE_URL}{lang}/{TYPE_SECTION[ptype]}/", "weekly", "0.7"))
        # 工具页
        for t in tools:
            urls.append((abs_url(url_tool(lang, t["id"])),
                         SITEMAP_CHANGEFREQ[TYPE_TOOLS], SITEMAP_PRIORITY[TYPE_TOOLS]))
        # 对比页
        for a, b in compare_pairs:
            urls.append((abs_url(url_compare(lang, a["id"], b["id"])),
                         SITEMAP_CHANGEFREQ[TYPE_COMPARE], SITEMAP_PRIORITY[TYPE_COMPARE]))
        # 攻略页
        for t in tools:
            urls.append((abs_url(url_guide(lang, t["id"])),
                         SITEMAP_CHANGEFREQ[TYPE_GUIDES], SITEMAP_PRIORITY[TYPE_GUIDES]))
        # 排行页
        for cat in categories:
            urls.append((abs_url(url_ranking(lang, cat)),
                         SITEMAP_CHANGEFREQ[TYPE_RANKING], SITEMAP_PRIORITY[TYPE_RANKING]))
        # FAQ 页
        for t in tools:
            urls.append((abs_url(url_faq(lang, t["id"])),
                         SITEMAP_CHANGEFREQ[TYPE_FAQ], SITEMAP_PRIORITY[TYPE_FAQ]))
        # 历史页
        for t in tools:
            urls.append((abs_url(url_history(lang, t["id"])),
                         SITEMAP_CHANGEFREQ[TYPE_HISTORY], SITEMAP_PRIORITY[TYPE_HISTORY]))
        # 替代品页
        for t in tools:
            urls.append((abs_url(url_alternatives(lang, t["id"])),
                         SITEMAP_CHANGEFREQ[TYPE_ALTERNATIVES], SITEMAP_PRIORITY[TYPE_ALTERNATIVES]))

        lines = ['<?xml version="1.0" encoding="UTF-8"?>',
                 '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
        for loc, freq, prio in urls:
            lines.append("  <url>")
            lines.append(f"    <loc>{xml_escape(loc)}</loc>")
            lines.append(f"    <lastmod>{DEFAULT_DATE}</lastmod>")
            lines.append(f"    <changefreq>{freq}</changefreq>")
            lines.append(f"    <priority>{prio}</priority>")
            lines.append("  </url>")
        lines.append("</urlset>")
        sitemap_path = PUBLIC_DIR / f"sitemap-{lang}.xml"
        sitemap_path.write_text("\n".join(lines), encoding="utf-8")
        sub_count += 1
        total_urls += len(urls)

    # sitemap-index.xml
    index_lines = ['<?xml version="1.0" encoding="UTF-8"?>',
                   '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for lang in langs:
        index_lines.append("  <sitemap>")
        index_lines.append(f"    <loc>{xml_escape(BASE_URL)}sitemap-{lang}.xml</loc>")
        index_lines.append(f"    <lastmod>{DEFAULT_DATE}</lastmod>")
        index_lines.append("  </sitemap>")
    index_lines.append("</sitemapindex>")
    (PUBLIC_DIR / "sitemap-index.xml").write_text("\n".join(index_lines), encoding="utf-8")

    return sub_count, total_urls


# ----------------------------------------------------------------------
# Worker 函数
# ----------------------------------------------------------------------
def _init_worker(tools: list, compare_pairs: list) -> None:
    """每个 worker 进程初始化时调用一次。"""
    global _ALL_TOOLS, _TOOLS_BY_ID, _COMPARE_PAIRS
    _ALL_TOOLS = tools
    _TOOLS_BY_ID = {t["id"]: t for t in tools}
    _COMPARE_PAIRS = compare_pairs


def _worker_generate(task: dict) -> tuple[str, str]:
    """生成单个 HTML 文件。返回 (路径 or 标识, 状态)。"""
    ptype = task["type"]
    lang = task["lang"]
    try:
        if ptype == TYPE_TOOLS:
            tool = _TOOLS_BY_ID.get(task["tool_id"])
            if not tool:
                return (task["tool_id"], "missing_tool")
            html = gen_tool_page_html(tool, lang)
            out_path = PUBLIC_DIR / lang / "tools" / tool["id"] / "index.html"
        elif ptype == TYPE_COMPARE:
            tool_a = _TOOLS_BY_ID.get(task["tool_a_id"])
            tool_b = _TOOLS_BY_ID.get(task["tool_b_id"])
            if not tool_a or not tool_b:
                return (f"{task['tool_a_id']}-vs-{task['tool_b_id']}", "missing_tool")
            html = gen_compare_page_html(tool_a, tool_b, lang)
            out_path = PUBLIC_DIR / lang / "compare" / f"{tool_a['id']}-vs-{tool_b['id']}" / "index.html"
        elif ptype == TYPE_GUIDES:
            tool = _TOOLS_BY_ID.get(task["tool_id"])
            if not tool:
                return (task["tool_id"], "missing_tool")
            html = gen_guide_page_html(tool, lang)
            out_path = PUBLIC_DIR / lang / "guides" / tool["id"] / "index.html"
        elif ptype == TYPE_RANKING:
            category = task["category"]
            tools_in_cat = [t for t in _ALL_TOOLS if t["category"] == category]
            if not tools_in_cat:
                return (category, "empty_category")
            html = gen_ranking_page_html(category, tools_in_cat, lang)
            out_path = PUBLIC_DIR / lang / "ranking" / category / "index.html"
        elif ptype == TYPE_FAQ:
            tool = _TOOLS_BY_ID.get(task["tool_id"])
            if not tool:
                return (task["tool_id"], "missing_tool")
            html = gen_faq_page_html(tool, lang)
            out_path = PUBLIC_DIR / lang / "faq" / tool["id"] / "index.html"
        elif ptype == TYPE_HISTORY:
            tool = _TOOLS_BY_ID.get(task["tool_id"])
            if not tool:
                return (task["tool_id"], "missing_tool")
            html = gen_history_page_html(tool, lang)
            out_path = PUBLIC_DIR / lang / "history" / tool["id"] / "index.html"
        elif ptype == TYPE_ALTERNATIVES:
            tool = _TOOLS_BY_ID.get(task["tool_id"])
            if not tool:
                return (task["tool_id"], "missing_tool")
            html = gen_alternatives_page_html(tool, lang)
            out_path = PUBLIC_DIR / lang / "alternatives" / tool["id"] / "index.html"
        elif ptype == "home":
            html = gen_home_page_html(lang)
            out_path = PUBLIC_DIR / lang / "index.html"
        elif ptype == "list":
            section = task["section"]
            html = gen_list_page_html(lang, section)
            out_path = PUBLIC_DIR / lang / section / "index.html"
        else:
            return (str(task), "unknown_type")

        write_html(out_path, html)
        return (str(out_path.relative_to(PROJECT_ROOT)), "ok")
    except Exception as exc:
        return (str(task), f"error: {type(exc).__name__}: {exc}")


# ----------------------------------------------------------------------
# 主流程
# ----------------------------------------------------------------------
def build_compare_pairs(tools: list, max_pairs: int = 200) -> list:
    """构建对比页配对（Top N 工具，相邻配对）。"""
    top = sorted(tools, key=lambda t: t.get("popularity_score", 0), reverse=True)[:max_pairs * 2]
    pairs = []
    for i in range(0, len(top) - 1, 2):
        if i + 1 < len(top):
            pairs.append((top[i], top[i + 1]))
        if len(pairs) >= max_pairs:
            break
    # 不足时从相邻工具补充
    idx = 0
    while len(pairs) < max_pairs and idx < len(top):
        for j in range(idx + 1, min(idx + 3, len(top))):
            if len(pairs) >= max_pairs:
                break
            pair = (top[idx], top[j])
            if pair not in pairs:
                pairs.append(pair)
        idx += 1
    return pairs[:max_pairs]


def build_tasks(tools: list, langs: list, types: list, compare_pairs: list) -> list:
    """构建所有页面生成任务。"""
    tasks: list[dict] = []

    # 单工具任务
    for tool in tools:
        for lang in langs:
            if TYPE_TOOLS in types:
                tasks.append({"type": TYPE_TOOLS, "lang": lang, "tool_id": tool["id"]})
            if TYPE_GUIDES in types:
                tasks.append({"type": TYPE_GUIDES, "lang": lang, "tool_id": tool["id"]})
            if TYPE_FAQ in types:
                tasks.append({"type": TYPE_FAQ, "lang": lang, "tool_id": tool["id"]})
            if TYPE_HISTORY in types:
                tasks.append({"type": TYPE_HISTORY, "lang": lang, "tool_id": tool["id"]})
            if TYPE_ALTERNATIVES in types:
                tasks.append({"type": TYPE_ALTERNATIVES, "lang": lang, "tool_id": tool["id"]})

    # 对比任务
    if TYPE_COMPARE in types:
        for tool_a, tool_b in compare_pairs:
            for lang in langs:
                tasks.append({
                    "type": TYPE_COMPARE, "lang": lang,
                    "tool_a_id": tool_a["id"], "tool_b_id": tool_b["id"],
                })

    # 排行任务
    if TYPE_RANKING in types:
        cat_set = set(t["category"] for t in tools)
        for category in sorted(cat_set):
            for lang in langs:
                tasks.append({"type": TYPE_RANKING, "lang": lang, "category": category})

    # 首页
    for lang in langs:
        tasks.append({"type": "home", "lang": lang})

    # 列表页
    for lang in langs:
        for section in ALL_TYPES:
            if section in types:
                tasks.append({"type": "list", "lang": lang, "section": section})

    return tasks


def copy_static_assets() -> int:
    """复制 static/* 到 public/*。返回复制的文件数。"""
    if not STATIC_DIR.exists():
        return 0
    count = 0
    for src in STATIC_DIR.rglob("*"):
        if src.is_file():
            rel = src.relative_to(STATIC_DIR)
            dst = PUBLIC_DIR / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            count += 1
    return count


def dir_size_mb(path: Path) -> float:
    """计算目录大小（MB）。"""
    total = 0
    for p in path.rglob("*"):
        if p.is_file():
            try:
                total += p.stat().st_size
            except OSError:
                pass
    return total / (1024 * 1024)


def main() -> int:
    parser = argparse.ArgumentParser(description="直接生成静态 HTML（绕过 Hugo）")
    parser.add_argument("--workers", type=int, default=cpu_count(),
                        help=f"并行 worker 数（默认 = CPU 核心数 = {cpu_count()}）")
    parser.add_argument("--limit", type=int, default=None,
                        help="限制工具数（测试用）")
    parser.add_argument("--types", type=str, default=None,
                        help=f"只生成指定类型，逗号分隔（默认全部：{','.join(ALL_TYPES)}）")
    parser.add_argument("--lang", type=str, default=None,
                        help="指定语种，逗号分隔（默认全部 20）")
    parser.add_argument("--compare-pairs", type=int, default=200,
                        help="对比页配对数（默认 200）")
    parser.add_argument("--skip-sitemap", action="store_true",
                        help="跳过 sitemap 生成")
    parser.add_argument("--skip-static", action="store_true",
                        help="跳过静态资源复制")
    args = parser.parse_args()

    # 解析参数
    langs = SUPPORTED_LANGS if not args.lang else [l.strip() for l in args.lang.split(",")]
    types = ALL_TYPES if not args.types else [t.strip() for t in args.types.split(",")]
    invalid_types = [t for t in types if t not in ALL_TYPES]
    if invalid_types:
        print(f"[ERROR] 未知页面类型: {invalid_types}")
        print(f"  支持的类型: {ALL_TYPES}")
        return 1

    workers = max(1, args.workers)

    print("=" * 60)
    print("  静态 HTML 生成器 (绕过 Hugo)")
    print("=" * 60)
    print(f"  项目根目录: {PROJECT_ROOT}")
    print(f"  输出目录:   {PUBLIC_DIR}")
    print(f"  Worker 数:  {workers}")
    print(f"  语种数:     {len(langs)} ({', '.join(langs)})")
    print(f"  页面类型:   {', '.join(types)}")
    print(f"  工具数限制: {args.limit or '全部'}")
    print(f"  对比配对数: {args.compare_pairs}")

    # 加载数据
    print("\n=== 加载数据 ===")
    tools_file = DATA_DIR / "ai_tools.json"
    if not tools_file.exists():
        print(f"[ERROR] 数据文件不存在: {tools_file}")
        return 1
    tools = json.loads(tools_file.read_text(encoding="utf-8"))
    print(f"  工具总数: {len(tools)}")
    if args.limit:
        tools = tools[:args.limit]
        print(f"  限制后:   {len(tools)}")

    # 构建对比配对
    compare_pairs = build_compare_pairs(tools, max_pairs=args.compare_pairs)
    print(f"  对比配对: {len(compare_pairs)}")

    # 准备输出目录
    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)

    # 复制静态资源
    if not args.skip_static:
        print("\n=== 复制静态资源 ===")
        n = copy_static_assets()
        print(f"  复制文件数: {n}")

    # 构建任务
    print("\n=== 构建任务 ===")
    tasks = build_tasks(tools, langs, types, compare_pairs)
    print(f"  任务总数: {len(tasks)}")

    # 并行生成
    print(f"\n=== 并行生成（{workers} workers）===")
    start_time = time.time()
    ok_count = 0
    err_count = 0
    missing_count = 0
    progress_step = max(1, len(tasks) // 20)

    # 使用进程池
    with Pool(processes=workers, initializer=_init_worker,
              initargs=(tools, compare_pairs)) as pool:
        for i, (path_or_id, status) in enumerate(pool.imap_unordered(_worker_generate, tasks, chunksize=20)):
            if status == "ok":
                ok_count += 1
            elif status.startswith("error"):
                err_count += 1
                if err_count <= 10:
                    print(f"  [ERROR] {path_or_id}: {status}")
            else:
                missing_count += 1
            if (i + 1) % progress_step == 0 or (i + 1) == len(tasks):
                elapsed = time.time() - start_time
                pct = (i + 1) / len(tasks) * 100
                rate = (i + 1) / elapsed if elapsed > 0 else 0
                eta = (len(tasks) - i - 1) / rate if rate > 0 else 0
                print(f"  进度: {i + 1}/{len(tasks)} ({pct:.1f}%) | "
                      f"OK={ok_count} ERR={err_count} MISS={missing_count} | "
                      f"{rate:.0f} files/s | ETA {eta:.0f}s")

    duration = time.time() - start_time

    # 生成 404 页面
    print("\n=== 生成 404 页面 ===")
    write_html(PUBLIC_DIR / "404.html", gen_404_page_html())
    print(f"  已写入: public/404.html")

    # 生成 robots.txt
    print("\n=== 生成 robots.txt ===")
    (PUBLIC_DIR / "robots.txt").write_text(gen_robots_txt(), encoding="utf-8")
    print(f"  已写入: public/robots.txt")

    # 生成 sitemap
    if not args.skip_sitemap:
        print("\n=== 生成 sitemap ===")
        sub_count, total_urls = gen_sitemaps(tools, compare_pairs, langs)
        print(f"  子 sitemap 数: {sub_count}")
        print(f"  总 URL 数:     {total_urls}")
        print(f"  sitemap-index: public/sitemap-index.xml")
    else:
        sub_count, total_urls = 0, 0

    # 统计输出
    print("\n" + "=" * 60)
    print("  生成完成")
    print("=" * 60)
    print(f"  总任务数:       {len(tasks)}")
    print(f"  成功:           {ok_count}")
    print(f"  失败:           {err_count}")
    print(f"  跳过(缺失数据): {missing_count}")
    print(f"  耗时:           {duration:.1f} 秒 ({duration / 60:.1f} 分钟)")
    if duration > 0:
        print(f"  生成速率:       {ok_count / duration:.0f} files/s")
    print(f"  + 404 / robots / sitemap ({sub_count} 子 sitemap, {total_urls} URLs)")
    print(f"  输出目录大小:   {dir_size_mb(PUBLIC_DIR):.1f} MB")
    print(f"  输出目录:       {PUBLIC_DIR}")

    if err_count > 0:
        print(f"\n[WARN] 有 {err_count} 个文件生成失败，详见上方错误信息")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
