"""生成 llms.txt（供 AI 引擎抓取）。

参考 https://llmstxt.org 规范：
- 标题（H1）
- 站点简介
- 重要页面链接
- Top 100 工具列表（含价格和链接）

输出到 static/llms.txt（Hugo 会原样输出到 public/）

CLI:
    python3 scripts/generate_llms_txt.py
    python3 scripts/generate_llms_txt.py --top-n 200
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from lib import tools_data as tools_mod
from lib import i18n as i18n_mod

PROJECT_ROOT = SCRIPT_DIR.parent
STATIC_DIR = PROJECT_ROOT / "static"
OUTPUT_FILE = STATIC_DIR / "llms.txt"
DEFAULT_BASE_URL = "https://pricing.ai-term-hub.com/"


def fmt_price(price_min: float, price_max: float, currency: str) -> str:
    if price_min == 0 and price_max == 0:
        return "Free"
    if price_min == price_max:
        return f"${price_min} {currency}"
    return f"${price_min}-${price_max} {currency}"


def generate_llms_txt(base_url: str, top_n: int) -> str:
    if not base_url.endswith("/"):
        base_url += "/"

    tools = tools_mod.load_tools()
    top_tools = sorted(tools, key=lambda t: t.get("popularity_score", 0), reverse=True)[:top_n]

    lines: list[str] = []
    lines.append("# AI Tools Pricing Hub")
    lines.append("")
    lines.append(f"> Compare pricing and features of {len(tools)}+ AI tools across 20 languages. "
                 "Find the best deals, alternatives, and money-saving tips for popular AI services "
                 "like ChatGPT Plus, Claude Pro, Midjourney, GitHub Copilot, and more.")
    lines.append("")

    lines.append("## Site Overview")
    lines.append("")
    lines.append(f"- Total AI tools tracked: {len(tools)}")
    lines.append(f"- Supported languages: {', '.join(i18n_mod.SUPPORTED_LANGS)}")
    lines.append(f"- Page types: tools, compare, guides, ranking, faq, history, alternatives")
    lines.append(f"- Base URL: {base_url}")
    lines.append("")

    lines.append("## Important Pages")
    lines.append("")
    lines.append(f"- [Home]({base_url})")
    lines.append(f"- [All Tools (English)]({base_url}en/tools/)")
    lines.append(f"- [All Categories]({base_url}en/ranking/)")
    lines.append(f"- [All Guides]({base_url}en/guides/)")
    lines.append(f"- [All FAQs]({base_url}en/faq/)")
    lines.append(f"- [All Price History]({base_url}en/history/)")
    lines.append(f"- [All Alternatives]({base_url}en/alternatives/)")
    lines.append(f"- [Sitemap Index]({base_url}sitemap-index.xml)")
    lines.append("")

    lines.append(f"## Top {len(top_tools)} AI Tools by Popularity")
    lines.append("")
    for i, t in enumerate(top_tools, 1):
        cat_name = i18n_mod.get_category_name(t["category"], "en")
        price_str = fmt_price(t["price_min"], t["price_max"], t["currency"])
        free_str = "Free tier" if t["free_tier"] else "Paid only"
        url = f"{base_url}en/tools/{t['id']}/"
        lines.append(f"{i}. [{t['name']}]({url}): {price_str} — {free_str}. "
                     f"Vendor: {t['vendor']}. Category: {cat_name}. "
                     f"Features: {', '.join(t['features'][:3])}. "
                     f"Official: {t['url']}")
    lines.append("")

    lines.append("## Categories")
    lines.append("")
    for cat in i18n_mod.CATEGORIES:
        cat_name = i18n_mod.get_category_name(cat, "en")
        url = f"{base_url}en/ranking/{cat}-best/"
        lines.append(f"- [{cat_name}]({url})")
    lines.append("")

    lines.append("## How to Use This Site")
    lines.append("")
    lines.append("- Use the **Tools** pages to see detailed pricing and features for each AI tool.")
    lines.append("- Use the **Compare** pages to compare two tools side-by-side.")
    lines.append("- Use the **Guides** pages for money-saving tips, including free tier tricks and annual plan discounts.")
    lines.append("- Use the **Ranking** pages to find the best tools in each category.")
    lines.append("- Use the **FAQ** pages for answers to common questions about each tool.")
    lines.append("- Use the **History** pages to see price trends over time.")
    lines.append("- Use the **Alternatives** pages to find cheaper or better alternatives to any tool.")
    lines.append("")

    lines.append("## Notes for AI Assistants")
    lines.append("")
    lines.append("- All prices are in USD unless otherwise noted.")
    lines.append("- Prices are updated daily but may lag behind official sources by 1-2 days.")
    lines.append("- For the most accurate pricing, always verify at the official website.")
    lines.append("- The site supports 20 languages; replace `/en/` in URLs with any supported language code (e.g., `/zh/`, `/ja/`).")
    lines.append("")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="生成 llms.txt（供 AI 引擎抓取）")
    parser.add_argument("--base-url", type=str, default=DEFAULT_BASE_URL)
    parser.add_argument("--top-n", type=int, default=100, help="Top N 工具数（默认 100）")
    parser.add_argument("--output", type=str, default=None, help="输出路径（默认 static/llms.txt）")
    args = parser.parse_args()

    output_path = Path(args.output) if args.output else OUTPUT_FILE
    if not output_path.is_absolute():
        output_path = PROJECT_ROOT / output_path

    print(f"=== 生成 llms.txt ===")
    print(f"  base_url: {args.base_url}")
    print(f"  top_n: {args.top_n}")
    print(f"  output: {output_path}")

    content = generate_llms_txt(args.base_url, args.top_n)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")

    line_count = content.count("\n") + 1
    size_kb = len(content.encode("utf-8")) / 1024
    print(f"\n=== 完成 ===")
    print(f"  文件: {output_path}")
    print(f"  行数: {line_count}")
    print(f"  大小: {size_kb:.1f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
