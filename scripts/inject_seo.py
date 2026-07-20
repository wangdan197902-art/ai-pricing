#!/usr/bin/env python3
"""注入 WebSite JSON-LD 到首页并优化首页大小。

解决的问题：
1. WebSite 类型 JSON-LD 缺失（因 Hugo 0.140.0 多语种 bug，
   /page/2/index.html 被复制到 /index.html，但 .IsHome=false 导致 WebSite schema 丢失）
2. 首页过大（2.6MB+），影响 Google 爬虫抓取效率

CLI:
    python3 scripts/inject_seo.py publish-{lang} --lang {lang}
    python3 scripts/inject_seo.py publish-en --lang en
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# 站点标题（每个语种）— 与 generate_static_html.py 中 SITE_TITLES 保持一致
SITE_TITLES = {
    "en": "AI Tools Pricing", "zh": "AI工具价格对比",
    "es": "Precios de Herramientas IA", "fr": "Prix des Outils IA",
    "de": "KI-Tools Preise", "ja": "AIツール価格比較",
    "ko": "AI도구 가격비교", "pt": "Preços de Ferramentas IA",
    "ru": "Цены на ИИ-инструменты", "it": "Prezzi Strumenti IA",
    "ar": "أسعار أدوات الذكاء الاصطناعي", "nl": "AI-tools Prijzen",
    "pl": "Ceny Narzędzi AI", "tr": "AI Araçları Fiyatları",
    "vi": "Giá Công cụ AI", "id": "Harga Alat AI",
    "sv": "AI-verktyg Priser", "no": "AI-verktøy Priser",
    "da": "AI-værktøjer Priser",
    # 5 个扩展语种
    "cs": "Ceny AI Nástrojů", "el": "Τιμές Εργαλείων AI",
    "fi": "AI-työkalujen Hinnat", "hu": "AI Eszközök Árai",
    "ro": "Prețuri Instrumente AI",
}

# 站点描述（每个语种）
SITE_DESCRIPTIONS = {
    "en": "Compare AI tools pricing, features and find the best deals. 1000+ AI tools across 20 languages.",
    "zh": "对比AI工具价格、功能,寻找最佳优惠。1000+ AI工具，支持20种语言。",
    "es": "Compara precios y características de herramientas IA y encuentra las mejores ofertas. Más de 1000 herramientas IA en 20 idiomas.",
    "fr": "Comparez les prix et fonctionnalités des outils IA et trouvez les meilleures offres. Plus de 1000 outils IA en 20 langues.",
    "de": "Vergleichen Sie Preise und Funktionen von KI-Tools und finden Sie die besten Angebote. Über 1000 KI-Tools in 20 Sprachen.",
    "ja": "AIツールの価格と機能を比較し、最良の取引を見つけましょう。20言語で1000以上のAIツール。",
    "ko": "AI 도구의 가격과 기능을 비교하고 최고의 거래를 찾으세요. 20개 언어로 1000개 이상의 AI 도구.",
    "pt": "Compare preços e recursos de ferramentas de IA e encontre as melhores ofertas. Mais de 1000 ferramentas de IA em 20 idiomas.",
    "ru": "Сравнивайте цены и функции ИИ-инструментов и находите лучшие предложения. Более 1000 ИИ-инструментов на 20 языках.",
    "it": "Confronta prezzi e funzionalità degli strumenti IA e trova le migliori offerte. Oltre 1000 strumenti IA in 20 lingue.",
    "ar": "قارن أسعار وميزات أدوات الذكاء الاصطناعي وابحث عن أفضل الصفقات. أكثر من 1000 أداة ذكاء اصطناعي في 20 لغة.",
    "nl": "Vergelijk prijzen en functies van AI-tools en vind de beste deals. Meer dan 1000 AI-tools in 20 talen.",
    "pl": "Porównuj ceny i funkcje narzędzi AI i znajdź najlepsze oferty. Ponad 1000 narzędzi AI w 20 językach.",
    "tr": "AI araçlarının fiyatlarını ve özelliklerini karşılaştırın ve en iyi fırsatları bulun. 20 dilde 1000'den fazla AI aracı.",
    "vi": "So sánh giá và tính năng của công cụ AI và tìm ưu đãi tốt nhất. Hơn 1000 công cụ AI trong 20 ngôn ngữ.",
    "id": "Bandingkan harga dan fitur alat AI dan temukan penawaran terbaik. Lebih dari 1000 alat AI dalam 20 bahasa.",
    "sv": "Jämför priser och funktioner för AI-verktyg och hitta de bästa erbjudandena. Över 1000 AI-verktyg på 20 språk.",
    "no": "Sammenlign priser og funksjoner for AI-verktøy og finn de beste tilbudene. Over 1000 AI-verktøy på 20 språk.",
    "da": "Sammenlign priser og funktioner for AI-værktøjer og find de bedste tilbud. Over 1000 AI-værktøjer på 20 sprog.",
    "cs": "Porovnejte ceny a funkce AI nástrojů a najděte nejlepší nabídky. Více než 1000 AI nástrojů ve 20 jazycích.",
    "el": "Συγκρίνετε τιμές και χαρακτηριστικά εργαλείων AI και βρείτε τις καλύτερες προσφορές. Πάνω από 1000 εργαλεία AI σε 20 γλώσσες.",
    "fi": "Vertaile AI-työkalujen hintoja ja ominaisuuksia ja löydä parhaat tarjoukset. Yli 1000 AI-työkalua 20 kielellä.",
    "hu": "Hasonlítsa össze az AI eszközök árait és funkcióit, és találja meg a legjobb ajánlatokat. Több mint 1000 AI eszköz 20 nyelven.",
    "ro": "Comparați prețurile și funcțiile instrumentelor AI și găsiți cele mai bune oferte. Peste 1000 instrumente AI în 20 de limbi.",
}

# Hugo LanguageCode 映射（与 generate_static_html.py 保持一致）
LANG_CODE_MAP = {
    "en": "en-us", "zh": "zh-cn", "es": "es-es", "fr": "fr-fr",
    "de": "de-de", "ja": "ja-jp", "ko": "ko-kr", "pt": "pt-pt",
    "ru": "ru-ru", "it": "it-it", "ar": "ar-sa", "nl": "nl-nl",
    "pl": "pl-pl", "tr": "tr-tr", "vi": "vi-vn", "th": "th-th",
    "id": "id-id", "sv": "sv-se", "no": "nb-no", "da": "da-dk",
    "cs": "cs-cz", "el": "el-gr", "fi": "fi-fi", "hu": "hu-hu", "ro": "ro-ro",
}


def get_site_title(lang: str) -> str:
    return SITE_TITLES.get(lang, SITE_TITLES["en"])


def get_site_description(lang: str) -> str:
    return SITE_DESCRIPTIONS.get(lang, SITE_DESCRIPTIONS["en"])


def get_lang_code(lang: str) -> str:
    return LANG_CODE_MAP.get(lang, lang)


def get_site_url(lang: str, domain: str = "ai-term-hub.com") -> str:
    """获取单语种子站的根 URL。"""
    return f"https://pricing-{lang}.{domain}/"


def build_website_jsonld(lang: str) -> dict:
    """构建 WebSite 类型 JSON-LD。"""
    site_title = get_site_title(lang)
    site_url = get_site_url(lang)
    site_desc = get_site_description(lang)
    lang_code = get_lang_code(lang)

    return {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": site_title,
        "url": site_url,
        "description": site_desc,
        "inLanguage": lang_code,
        "potentialAction": {
            "@type": "SearchAction",
            "target": {
                "@type": "EntryPoint",
                "urlTemplate": f"{site_url}search/?q={{search_term_string}}",
            },
            "query-input": "required name=search_term_string",
        },
    }


def has_website_jsonld(html: str) -> bool:
    """检查 HTML 中是否已有 WebSite 类型 JSON-LD。"""
    # 匹配 <script type="application/ld+json">...</script> 中的 "@type": "WebSite"
    pattern = r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>.*?"@type"\s*:\s*"WebSite".*?</script>'
    return bool(re.search(pattern, html, re.DOTALL))


def inject_website_jsonld(html: str, lang: str) -> str:
    """注入 WebSite JSON-LD 到 HTML 的 </head> 之前。"""
    if has_website_jsonld(html):
        return html

    jsonld = build_website_jsonld(lang)
    jsonld_str = json.dumps(jsonld, ensure_ascii=False, indent=2)
    script_tag = f'<script type="application/ld+json">\n{jsonld_str}\n</script>'

    # 在 </head> 之前注入
    if "</head>" in html:
        return html.replace("</head>", f"    {script_tag}\n</head>", 1)
    # 如果没有 </head>，在 <body> 之前注入
    if "<body" in html:
        return re.sub(r"(<body[^>]*>)", f"{script_tag}\n\\1", html, count=1)
    # 最后兜底：追加到末尾
    return html + "\n" + script_tag


def fix_title(html: str, lang: str) -> str:
    """修复 <title> 标签，确保显示正确的站点标题。

    处理两种异常情况：
    1. title 中包含 "AI Terms Dictionary"（从 terms 项目复制的旧模板遗留）
    2. title 格式为 "短词 | 站点名"，其中短词是 Hugo 0.140.0 多语种 bug 导致的
       错误页面标题（如 "Ens"、"Des" 等），应替换为纯站点名
    """
    site_title = get_site_title(lang)
    # 匹配 <title>...</title>
    title_pattern = r"<title>(.*?)</title>"
    match = re.search(title_pattern, html, re.DOTALL)
    if not match:
        return html

    current_title = match.group(1).strip()

    # 情况1：title 包含 "AI Terms Dictionary"（旧模板遗留）
    if "AI Terms Dictionary" in current_title:
        new_title = site_title
        return html.replace(match.group(0), f"<title>{new_title}</title>", 1)

    # 情况2：title 格式为 "前缀 | 站点名"，前缀是错误的页面标题
    # 这种情况通常是 Hugo 0.140.0 多语种 bug 导致 .Title 返回了错误的短词
    if "|" in current_title:
        parts = current_title.split("|", 1)
        prefix = parts[0].strip()
        suffix = parts[1].strip()
        # 如果后缀是正确的站点名，且前缀不是站点名本身，则用纯站点名
        if suffix == site_title and prefix != site_title:
            new_title = site_title
            return html.replace(match.group(0), f"<title>{new_title}</title>", 1)

    return html


def optimize_homepage_size(html: str, max_tool_cards: int = 20) -> str:
    """优化首页大小，限制工具卡片数量。

    策略：保留前 max_tool_cards 个 <article> 标签，移除其余的。
    这能显著减少首页大小（从 2.6MB 降到 ~200KB）。

    注意：首页可能有多种类名的 article 标签：
    - <article class="tool-card"> （带引号）
    - <article class=tool-card> （无引号，Hugo 压缩输出）
    - <article class="card generic-card"> （通用卡片）
    需要匹配所有 article 标签。
    """
    # 匹配所有 <article ...>...</article>（不限定 class）
    card_pattern = r'<article\b[^>]*>.*?</article>'
    cards = re.findall(card_pattern, html, re.DOTALL)
    if len(cards) <= max_tool_cards:
        return html

    # 保留前 max_tool_cards 个，移除其余的
    removed_count = len(cards) - max_tool_cards

    # 找到所有卡片的起始和结束位置
    matches = list(re.finditer(card_pattern, html, re.DOTALL))
    if not matches:
        return html

    # 构建新的 HTML：保留前 max_tool_cards 个卡片
    result_parts = []
    last_end = 0
    for i, match in enumerate(matches):
        # 添加卡片之前的内容
        result_parts.append(html[last_end:match.start()])
        if i < max_tool_cards:
            # 保留这个卡片
            result_parts.append(match.group(0))
        # else: 跳过这个卡片
        last_end = match.end()

    # 添加最后一段内容
    result_parts.append(html[last_end:])

    optimized = "".join(result_parts)

    # 在工具网格后添加"查看更多"提示（如果移除了卡片）
    if removed_count > 0:
        # 找到 tool-grid 的结束位置，添加查看更多链接
        more_link = f'\n        <div class="home-section-footer"><a href="/tools/" class="btn btn-secondary">View all tools →</a></div>'
        # 在第一个 </div>（tool-grid 结束）后插入
        optimized = re.sub(
            r'(<div class="tool-grid">.*?</div>)',
            f'\\1{more_link}',
            optimized,
            count=1,
            flags=re.DOTALL,
        )

    return optimized


def minify_html(html: str) -> str:
    """简单压缩 HTML：移除 HTML 注释和多余空白。"""
    # 移除 HTML 注释（但保留条件注释）
    html = re.sub(r"<!--(?!\[if).*?-->", "", html, flags=re.DOTALL)
    # 压缩连续空白行为单个换行
    html = re.sub(r"\n\s*\n\s*\n+", "\n\n", html)
    # 移除行首行尾多余空白（保留 <pre> 内容）
    # 注意：不压缩 <pre>、<script>、<style> 内的内容
    return html


def process_homepage(html_path: Path, lang: str, max_tool_cards: int = 20) -> dict:
    """处理单个首页文件。返回统计信息。"""
    original_size = html_path.stat().st_size
    html = html_path.read_text(encoding="utf-8")

    # 1. 修复 title（如果包含 AI Terms Dictionary）
    html = fix_title(html, lang)

    # 2. 注入 WebSite JSON-LD（如果缺失）
    jsonld_injected = not has_website_jsonld(html)
    html = inject_website_jsonld(html, lang)

    # 3. 优化首页大小（限制工具卡片数量）
    html = optimize_homepage_size(html, max_tool_cards=max_tool_cards)

    # 4. 简单压缩 HTML
    html = minify_html(html)

    # 写回文件
    html_path.write_text(html, encoding="utf-8")
    new_size = html_path.stat().st_size

    return {
        "file": str(html_path),
        "original_size": original_size,
        "new_size": new_size,
        "jsonld_injected": jsonld_injected,
        "size_reduction": original_size - new_size,
        "size_reduction_pct": (1 - new_size / original_size) * 100 if original_size > 0 else 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="注入 WebSite JSON-LD 并优化首页大小")
    parser.add_argument("publish_dir", help="发布目录（如 publish-en）")
    parser.add_argument("--lang", required=True, help="语种代码（如 en、zh）")
    parser.add_argument("--max-tool-cards", type=int, default=20,
                        help="首页最大工具卡片数（默认 20）")
    args = parser.parse_args()

    publish_dir = Path(args.publish_dir)
    if not publish_dir.exists():
        print(f"[ERROR] 发布目录不存在: {publish_dir}")
        return 1

    index_path = publish_dir / "index.html"
    if not index_path.exists():
        print(f"[ERROR] 首页文件不存在: {index_path}")
        return 1

    print(f"=== 处理首页: {index_path} ===")
    print(f"  语种: {args.lang}")
    print(f"  站点标题: {get_site_title(args.lang)}")
    print(f"  最大工具卡片数: {args.max_tool_cards}")

    result = process_homepage(index_path, args.lang, max_tool_cards=args.max_tool_cards)

    print(f"\n=== 处理结果 ===")
    print(f"  文件: {result['file']}")
    print(f"  原始大小: {result['original_size']:,} 字节 ({result['original_size'] / 1024:.1f} KB)")
    print(f"  新大小: {result['new_size']:,} 字节 ({result['new_size'] / 1024:.1f} KB)")
    print(f"  减少大小: {result['size_reduction']:,} 字节 ({result['size_reduction_pct']:.1f}%)")
    print(f"  WebSite JSON-LD 注入: {'✅ 是' if result['jsonld_injected'] else '⏭️ 已存在，跳过'}")

    if result['new_size'] > 1024 * 1024:
        print(f"  ⚠️ 警告: 首页仍大于 1MB")
    elif result['new_size'] > 500 * 1024:
        print(f"  ℹ️ 提示: 首页在 500KB-1MB 之间")
    else:
        print(f"  ✅ 首页大小理想（< 500KB）")

    return 0


if __name__ == "__main__":
    sys.exit(main())
