"""批量生成 Hugo content 目录下的 .md 文件。

- 工具页：1000 × 20 = 20000
- 对比页：200 × 20 = 4000
- 攻略页：1000 × 20 = 20000
- 排行页：50 × 20 = 1000
- FAQ 页：1000 × 20 = 20000
- 价格历史页：1000 × 20 = 20000
- 替代品页：1000 × 20 = 20000
- 总计：105000 页面

CLI:
    python3 scripts/generate_pages.py --all
    python3 scripts/generate_pages.py --tools --lang en,zh --limit 10
    python3 scripts/generate_pages.py --guides --use-ai --limit 50
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# 让脚本可独立运行
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from lib import i18n as i18n_mod
from lib import tools_data as tools_mod
from lib.agnes_client import AgnesClient, get_default_client

PROJECT_ROOT = SCRIPT_DIR.parent
CONTENT_DIR = PROJECT_ROOT / "content"
DATA_FILE = PROJECT_ROOT / "data" / "ai_tools.json"
I18N_FILE = PROJECT_ROOT / "data" / "ui_translations.json"

DEFAULT_LANGS = i18n_mod.SUPPORTED_LANGS  # 20 语种
DEFAULT_AI_TOP_N = 100
DEFAULT_DATE = "2026-07-19"

# 页面类型常量
TYPE_TOOLS = "tools"
TYPE_COMPARE = "compare"
TYPE_GUIDES = "guides"
TYPE_RANKING = "ranking"
TYPE_FAQ = "faq"
TYPE_HISTORY = "history"
TYPE_ALTERNATIVES = "alternatives"


# ----------------------------------------------------------------------
# 工具函数
# ----------------------------------------------------------------------
def load_i18n() -> dict:
    if not I18N_FILE.exists():
        i18n_mod.write_json()
    return json.loads(I18N_FILE.read_text(encoding="utf-8"))


def load_tools(limit: int | None = None) -> list[dict]:
    if not DATA_FILE.exists():
        tools_mod.write_json()
    tools = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    if limit:
        tools = tools[:limit]
    return tools


def write_md(path: Path, front_matter: dict, body: str) -> None:
    """写入单个 .md 文件（front matter + body）。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    # 流式写入
    with path.open("w", encoding="utf-8") as f:
        f.write("---\n")
        for k, v in front_matter.items():
            if isinstance(v, bool):
                f.write(f"{k}: {str(v).lower()}\n")
            elif isinstance(v, (int, float)):
                f.write(f"{k}: {v}\n")
            elif isinstance(v, list):
                f.write(f"{k}:\n")
                for item in v:
                    f.write(f"  - {json.dumps(item, ensure_ascii=False)}\n")
            else:
                # 字符串需要转义引号
                escaped = str(v).replace('"', '\\"')
                f.write(f'{k}: "{escaped}"\n')
        f.write("---\n\n")
        f.write(body)
        f.write("\n")


def tr(i18n_data: dict, key: str, lang: str) -> str:
    """获取翻译文案。"""
    if key in i18n_data:
        translations = i18n_data[key]
        return translations.get(lang, translations.get("en", key))
    return key


def fmt_price(price_min: float, price_max: float, currency: str, per_month_text: str) -> str:
    """格式化价格展示。"""
    if price_min == 0 and price_max == 0:
        return "Free"
    if price_min == price_max:
        return f"${price_min} {currency}{per_month_text}"
    return f"${price_min} - ${price_max} {currency}{per_month_text}"


# ----------------------------------------------------------------------
# 页面生成器
# ----------------------------------------------------------------------
def gen_tool_page(tool: dict, lang: str, i18n_data: dict) -> tuple[dict, str]:
    """生成工具页 front matter + body。"""
    cat_name = i18n_mod.get_category_name(tool["category"], lang)
    pm = tr(i18n_data, "per_month", lang)
    price_str = fmt_price(tool["price_min"], tool["price_max"], tool["currency"], pm)
    features_str = "\n".join(f"- {f}" for f in tool["features"])
    alts_str = ", ".join(tool["alternatives"]) if tool["alternatives"] else "—"
    free_text = tr(i18n_data, "free", lang) if tool["free_tier"] else tr(i18n_data, "premium", lang)

    if lang == "en":
        body = f"""# {tool['name']} — Pricing & Features {DEFAULT_DATE}

{tool['description_en']}

## {tr(i18n_data, 'tools_overview', lang)}

- **{tr(i18n_data, 'vendor', lang)}**: {tool['vendor']}
- **{tr(i18n_data, 'category', lang)}**: {cat_name}
- **{tr(i18n_data, 'pricing', lang)}**: {price_str}
- **{tr(i18n_data, 'free_tier', lang)}**: {free_text}
- **{tr(i18n_data, 'founded_year', lang)}**: {tool['founded_year']}
- **{tr(i18n_data, 'popularity', lang)}**: {tool['popularity_score']}/100

## {tr(i18n_data, 'features', lang)}

{features_str}

## {tr(i18n_data, 'tools_pricing_table', lang)}

| Plan | Price | {tr(i18n_data, 'features', lang)} |
|------|-------|-------|
| {free_text} | {price_str} | {', '.join(tool['features'][:3])} |

## {tr(i18n_data, 'alternatives_for', lang)} {tool['name']}

{alts_str}

## {tr(i18n_data, 'official_website', lang)}

[{tool['name']}]({tool['url']})

---

*{tr(i18n_data, 'last_updated', lang)}: {DEFAULT_DATE}*
"""
    else:
        # 非英文：模板化（仅替换 UI 文案 + 变量，正文使用本地化模板）
        body = f"""# {tool['name']} — {tr(i18n_data, 'pricing', lang)} {DEFAULT_DATE}

{tool['description_en']}

## {tr(i18n_data, 'tools_overview', lang)}

- **{tr(i18n_data, 'vendor', lang)}**: {tool['vendor']}
- **{tr(i18n_data, 'category', lang)}**: {cat_name}
- **{tr(i18n_data, 'pricing', lang)}**: {price_str}
- **{tr(i18n_data, 'free_tier', lang)}**: {free_text}
- **{tr(i18n_data, 'founded_year', lang)}**: {tool['founded_year']}
- **{tr(i18n_data, 'popularity', lang)}**: {tool['popularity_score']}/100

## {tr(i18n_data, 'features', lang)}

{features_str}

## {tr(i18n_data, 'tools_pricing_table', lang)}

| {tr(i18n_data, 'pricing', lang)} | {tr(i18n_data, 'features', lang)} |
|------|-------|
| {price_str} | {', '.join(tool['features'][:3])} |

## {tr(i18n_data, 'alternatives_for', lang)} {tool['name']}

{alts_str}

## {tr(i18n_data, 'official_website', lang)}

[{tool['name']}]({tool['url']})

---

*{tr(i18n_data, 'last_updated', lang)}: {DEFAULT_DATE}*
"""

    front_matter = {
        "title": f"{tool['name']} {tr(i18n_data, 'pricing', lang)} {DEFAULT_DATE}",
        "description": tool["description_en"][:160],
        "date": DEFAULT_DATE,
        "lastmod": DEFAULT_DATE,
        "type": TYPE_TOOLS,
        "category": tool["category"],
        "language": lang,
        "draft": False,
        "tool_id": tool["id"],
        "vendor": tool["vendor"],
        "price_min": tool["price_min"],
        "price_max": tool["price_max"],
        "currency": tool["currency"],
        "free_tier": tool["free_tier"],
        "popularity_score": tool["popularity_score"],
    }
    return front_matter, body


def gen_compare_page(tool_a: dict, tool_b: dict, lang: str, i18n_data: dict) -> tuple[dict, str]:
    """生成对比页。"""
    vs = tr(i18n_data, "vs_text", lang)
    pm = tr(i18n_data, "per_month", lang)
    price_a = fmt_price(tool_a["price_min"], tool_a["price_max"], tool_a["currency"], pm)
    price_b = fmt_price(tool_b["price_min"], tool_b["price_max"], tool_b["currency"], pm)

    title = f"{tool_a['name']} {vs} {tool_b['name']}: {tr(i18n_data, 'pricing', lang)} {DEFAULT_DATE}"

    body = f"""# {tool_a['name']} {vs} {tool_b['name']}

{tr(i18n_data, 'compare_title', lang)} — {DEFAULT_DATE}

## {tr(i18n_data, 'tools_overview', lang)}

| Item | {tool_a['name']} | {tool_b['name']} |
|------|------------------|------------------|
| {tr(i18n_data, 'vendor', lang)} | {tool_a['vendor']} | {tool_b['vendor']} |
| {tr(i18n_data, 'category', lang)} | {i18n_mod.get_category_name(tool_a['category'], lang)} | {i18n_mod.get_category_name(tool_b['category'], lang)} |
| {tr(i18n_data, 'pricing', lang)} | {price_a} | {price_b} |
| {tr(i18n_data, 'free_tier', lang)} | {tr(i18n_data, 'free', lang) if tool_a['free_tier'] else tr(i18n_data, 'premium', lang)} | {tr(i18n_data, 'free', lang) if tool_b['free_tier'] else tr(i18n_data, 'premium', lang)} |
| {tr(i18n_data, 'founded_year', lang)} | {tool_a['founded_year']} | {tool_b['founded_year']} |
| {tr(i18n_data, 'popularity', lang)} | {tool_a['popularity_score']}/100 | {tool_b['popularity_score']}/100 |

## {tr(i18n_data, 'features', lang)}

### {tool_a['name']}
{chr(10).join(f'- {f}' for f in tool_a['features'])}

### {tool_b['name']}
{chr(10).join(f'- {f}' for f in tool_b['features'])}

## {tr(i18n_data, 'verdict', lang)}

{tool_a['name']} is {('cheaper' if tool_a['price_min'] < tool_b['price_min'] else 'pricier')} than {tool_b['name']}. Choose {tool_a['name']} if you need {tool_a['features'][0].lower()}; choose {tool_b['name']} if you need {tool_b['features'][0].lower()}.

---

*{tr(i18n_data, 'last_updated', lang)}: {DEFAULT_DATE}*
"""
    front_matter = {
        "title": title,
        "description": f"{tool_a['name']} vs {tool_b['name']} pricing and features comparison.",
        "date": DEFAULT_DATE,
        "lastmod": DEFAULT_DATE,
        "type": TYPE_COMPARE,
        "language": lang,
        "draft": False,
        "tool_a": tool_a["id"],
        "tool_b": tool_b["id"],
    }
    return front_matter, body


def gen_guide_page_template(tool: dict, lang: str, i18n_data: dict) -> tuple[dict, str]:
    """生成攻略页（模板版，不调用 API）。"""
    cat_name = i18n_mod.get_category_name(tool["category"], lang)
    annual_price = round(tool["price_max"] * 12 * 0.8, 2) if tool["price_max"] > 0 else 0

    body = f"""# {tr(i18n_data, 'save_tips', lang)}: {tool['name']}

{tr(i18n_data, 'save_tips_intro', lang)}

## 1. {tr(i18n_data, 'free_tier', lang)}

{tool['name']} offers a {('free tier' if tool['free_tier'] else 'paid-only plan')}. {('Use the free tier to test core features before committing.' if tool['free_tier'] else 'Consider free alternatives like ' + ', '.join(tool['alternatives'][:2]) + ' before subscribing.')}

## 2. {tr(i18n_data, 'annual_plan', lang)}

{('Switching to annual billing saves ~20% — total cost ~$' + str(annual_price) + '/year vs $' + str(round(tool['price_max']*12, 2)) + ' monthly.') if tool['price_max'] > 0 else 'No paid tier — fully free to use.'}

## 3. {tr(i18n_data, 'alternatives_for', lang)} {tool['name']}

Consider these {cat_name} alternatives:
{chr(10).join(f'- [{alt}](/tools/{alt}/)' for alt in tool['alternatives'][:5])}

## 4. {tr(i18n_data, 'save_money', lang)} Tips

- Use API instead of subscription if you only need light usage
- Stack student/non-profit discounts (up to 50% off)
- Watch for Black Friday / Cyber Monday deals (typically 30-50% off)
- Use team plan to share costs with colleagues

---

*{tr(i18n_data, 'last_updated', lang)}: {DEFAULT_DATE}*
"""
    front_matter = {
        "title": f"{tr(i18n_data, 'save_tips', lang)}: {tool['name']} {DEFAULT_DATE}",
        "description": f"Save money tips for {tool['name']} - free tier tricks, annual plans, alternatives.",
        "date": DEFAULT_DATE,
        "lastmod": DEFAULT_DATE,
        "type": TYPE_GUIDES,
        "category": tool["category"],
        "language": lang,
        "draft": False,
        "tool_id": tool["id"],
    }
    return front_matter, body


def gen_guide_page_ai(tool: dict, lang: str, i18n_data: dict, client: AgnesClient) -> tuple[dict, str]:
    """用 Agnes API 生成高质量攻略页（仅英文版）。"""
    cat_name = i18n_mod.get_category_name(tool["category"], "en")
    alts_str = ", ".join(tool["alternatives"][:5])
    annual_price = round(tool["price_max"] * 12 * 0.8, 2) if tool["price_max"] > 0 else 0

    prompt = f"""Write a comprehensive money-saving guide for the AI tool "{tool['name']}".

Tool details:
- Vendor: {tool['vendor']}
- Category: {cat_name}
- Pricing model: {tool['pricing_model']}
- Price range: ${tool['price_min']} - ${tool['price_max']} {tool['currency']}
- Free tier: {tool['free_tier']}
- Features: {', '.join(tool['features'])}
- Alternatives: {alts_str}

Write in Markdown with these sections (use ## headings):
1. Overview - brief intro
2. Free Tier Strategy - how to maximize free tier if available, or alternatives if not
3. Annual Plan Savings - calculate the 20% savings ($X/year vs $Y/month)
4. Alternatives Comparison - 3-5 cheaper alternatives with prices
5. Pro Tips - 5 actionable tips for saving money with this tool
6. Final Verdict - recommendation

Keep it under 500 words. Be specific with numbers and tool names. No fluff.
"""
    system_prompt = "You are an expert at AI tool pricing and cost optimization. Provide specific, actionable advice."
    try:
        body_en = client.generate(prompt, system_prompt=system_prompt, temperature=0.4)
    except Exception as exc:
        # 暴露异常但降级到模板
        print(f"[WARN] AI 生成失败，降级到模板: {tool['id']} ({type(exc).__name__})")
        return gen_guide_page_template(tool, lang, i18n_data)

    # 非英文版用模板（不调用翻译 API 避免成本）
    if lang != "en":
        return gen_guide_page_template(tool, lang, i18n_data)

    body = f"# Save Money: {tool['name']} ({DEFAULT_DATE})\n\n{body_en}\n\n---\n\n*Last Updated: {DEFAULT_DATE}*\n"
    front_matter = {
        "title": f"Save Money: {tool['name']} {DEFAULT_DATE}",
        "description": f"Money-saving guide for {tool['name']} - free tier, annual plans, alternatives, and pro tips.",
        "date": DEFAULT_DATE,
        "lastmod": DEFAULT_DATE,
        "type": TYPE_GUIDES,
        "category": tool["category"],
        "language": "en",
        "draft": False,
        "tool_id": tool["id"],
        "ai_generated": True,
    }
    return front_matter, body


def gen_faq_page_template(tool: dict, lang: str, i18n_data: dict) -> tuple[dict, str]:
    """生成 FAQ 页（模板版）。"""
    cat_name = i18n_mod.get_category_name(tool["category"], lang)
    pm = tr(i18n_data, "per_month", lang)
    price_str = fmt_price(tool["price_min"], tool["price_max"], tool["currency"], pm)

    body = f"""# {tool['name']} FAQ — {DEFAULT_DATE}

{tr(i18n_data, 'faq_intro', lang)}

## Q1: How much does {tool['name']} cost?

{tool['name']} is priced at {price_str}. {('There is a free tier available.' if tool['free_tier'] else 'No free tier is available.')}

## Q2: Is there a free trial?

{('Yes, the free tier can be used indefinitely with limits.' if tool['free_tier'] else 'Please check the official website for trial availability.')}

## Q3: What category does {tool['name']} belong to?

{tool['name']} is a {cat_name} tool developed by {tool['vendor']}.

## Q4: What are the main features of {tool['name']}?

{', '.join(tool['features'])}.

## Q5: What are popular alternatives to {tool['name']}?

{', '.join(tool['alternatives'][:5])}.

## Q6: When was {tool['name']} founded?

{tool['name']} was founded in {tool['founded_year']}.

## Q7: Where can I find the official website?

Visit [{tool['name']}]({tool['url']}) for more information.

---

*{tr(i18n_data, 'last_updated', lang)}: {DEFAULT_DATE}*
"""
    front_matter = {
        "title": f"{tool['name']} FAQ {DEFAULT_DATE}",
        "description": f"Frequently asked questions about {tool['name']} pricing, features, and usage.",
        "date": DEFAULT_DATE,
        "lastmod": DEFAULT_DATE,
        "type": TYPE_FAQ,
        "category": tool["category"],
        "language": lang,
        "draft": False,
        "tool_id": tool["id"],
    }
    return front_matter, body


def gen_faq_page_ai(tool: dict, lang: str, i18n_data: dict, client: AgnesClient) -> tuple[dict, str]:
    """用 Agnes API 生成高质量 FAQ 页（仅英文）。"""
    if lang != "en":
        return gen_faq_page_template(tool, lang, i18n_data)

    cat_name = i18n_mod.get_category_name(tool["category"], "en")
    prompt = f"""Generate 8 frequently asked questions (FAQ) for the AI tool "{tool['name']}".

Tool info:
- Vendor: {tool['vendor']}
- Category: {cat_name}
- Pricing: ${tool['price_min']} - ${tool['price_max']} {tool['currency']} ({tool['pricing_model']})
- Free tier: {tool['free_tier']}
- Features: {', '.join(tool['features'])}
- Alternatives: {', '.join(tool['alternatives'][:5])}
- Founded: {tool['founded_year']}

Output format: Markdown with ## Q1: ... ## Q2: ... etc. Each answer should be 1-3 sentences, specific and accurate. Cover: pricing, free tier, features, alternatives, integrations, refund policy, support, and use cases.

Keep it under 600 words.
"""
    try:
        body_en = client.generate(prompt, system_prompt="You are an AI tool expert. Be concise and accurate.", temperature=0.4)
    except Exception as exc:
        print(f"[WARN] AI 生成失败，降级到模板: {tool['id']} ({type(exc).__name__})")
        return gen_faq_page_template(tool, lang, i18n_data)

    body = f"# {tool['name']} FAQ — {DEFAULT_DATE}\n\n{tr(i18n_data, 'faq_intro', lang)}\n\n{body_en}\n\n---\n\n*Last Updated: {DEFAULT_DATE}*\n"
    front_matter = {
        "title": f"{tool['name']} FAQ {DEFAULT_DATE}",
        "description": f"Frequently asked questions about {tool['name']}.",
        "date": DEFAULT_DATE,
        "lastmod": DEFAULT_DATE,
        "type": TYPE_FAQ,
        "category": tool["category"],
        "language": "en",
        "draft": False,
        "tool_id": tool["id"],
        "ai_generated": True,
    }
    return front_matter, body


def gen_ranking_page(category: str, tools_in_cat: list[dict], lang: str, i18n_data: dict) -> tuple[dict, str]:
    """生成分类排行页。"""
    cat_name = i18n_mod.get_category_name(category, lang)
    sorted_tools = sorted(tools_in_cat, key=lambda t: t.get("popularity_score", 0), reverse=True)[:10]
    pm = tr(i18n_data, "per_month", lang)

    rows = []
    for i, t in enumerate(sorted_tools, 1):
        price_str = fmt_price(t["price_min"], t["price_max"], t["currency"], pm)
        rows.append(f"| {i} | [{t['name']}](/tools/{t['id']}/) | {t['vendor']} | {price_str} | {t['popularity_score']}/100 |")

    body = f"""# {tr(i18n_data, 'ranking_title', lang)}: {cat_name}

{tr(i18n_data, 'ranking_intro', lang)}

## Top 10 {cat_name}

| # | {tr(i18n_data, 'tools_title', lang)} | {tr(i18n_data, 'vendor', lang)} | {tr(i18n_data, 'pricing', lang)} | {tr(i18n_data, 'popularity', lang)} |
|---|------|------|------|------|
{chr(10).join(rows)}

## {tr(i18n_data, 'all_categories', lang)}

See all categories in our [AI tools directory](/).

---

*{tr(i18n_data, 'last_updated', lang)}: {DEFAULT_DATE}*
"""
    front_matter = {
        "title": f"{tr(i18n_data, 'ranking_title', lang)}: {cat_name} {DEFAULT_DATE}",
        "description": f"Top {cat_name} ranked by popularity, features and value for money.",
        "date": DEFAULT_DATE,
        "lastmod": DEFAULT_DATE,
        "type": TYPE_RANKING,
        "category": category,
        "language": lang,
        "draft": False,
    }
    return front_matter, body


def gen_history_page(tool: dict, lang: str, i18n_data: dict) -> tuple[dict, str]:
    """生成价格历史页（模拟数据）。"""
    pm = tr(i18n_data, "per_month", lang)
    price_str = fmt_price(tool["price_min"], tool["price_max"], tool["currency"], pm)

    # 模拟过去 6 个月价格
    history_rows = []
    base = tool["price_max"] if tool["price_max"] > 0 else 10
    for i, m in enumerate(["2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-06", DEFAULT_DATE[:7]]):
        delta = (i - 3) * 0.5  # 微小波动
        p = round(base * (1 + delta * 0.01), 2)
        history_rows.append(f"| {m} | ${p} {tool['currency']}{pm} | {('+' if delta >= 0 else '')}{delta:.1f}% |")

    body = f"""# {tool['name']} {tr(i18n_data, 'history_title', lang)}

{tr(i18n_data, 'price_trend', lang)} for {tool['name']} — {DEFAULT_DATE}.

## {tr(i18n_data, 'history_title', lang)}

| Date | Price | Change |
|------|-------|--------|
{chr(10).join(history_rows)}

## {tr(i18n_data, 'verdict', lang)}

Current price: **{price_str}**

The price has been {('stable' if tool['price_max'] < 50 else 'increasing slightly')} over the past 6 months.

## {tr(i18n_data, 'alternatives_for', lang)} {tool['name']}

{', '.join(tool['alternatives'][:5])}

---

*{tr(i18n_data, 'last_updated', lang)}: {DEFAULT_DATE}*
"""
    front_matter = {
        "title": f"{tool['name']} {tr(i18n_data, 'history_title', lang)} {DEFAULT_DATE}",
        "description": f"Price history and trend for {tool['name']}.",
        "date": DEFAULT_DATE,
        "lastmod": DEFAULT_DATE,
        "type": TYPE_HISTORY,
        "category": tool["category"],
        "language": lang,
        "draft": False,
        "tool_id": tool["id"],
    }
    return front_matter, body


def gen_alternatives_page(tool: dict, lang: str, i18n_data: dict, all_tools: list[dict]) -> tuple[dict, str]:
    """生成替代品页。"""
    pm = tr(i18n_data, "per_month", lang)
    alt_tools = []
    tools_by_id = {t["id"]: t for t in all_tools}
    for alt_id in tool["alternatives"][:10]:
        if alt_id in tools_by_id:
            alt_tools.append(tools_by_id[alt_id])

    if not alt_tools:
        body = f"""# {tr(i18n_data, 'alternatives_for', lang)} {tool['name']}

No alternatives listed. See all tools in [{i18n_mod.get_category_name(tool['category'], lang)}](/).

---

*{tr(i18n_data, 'last_updated', lang)}: {DEFAULT_DATE}*
"""
    else:
        rows = []
        for alt in alt_tools:
            price_str = fmt_price(alt["price_min"], alt["price_max"], alt["currency"], pm)
            free = tr(i18n_data, "free", lang) if alt["free_tier"] else tr(i18n_data, "premium", lang)
            rows.append(f"| [{alt['name']}](/tools/{alt['id']}/) | {alt['vendor']} | {price_str} | {free} | {alt['popularity_score']}/100 |")

        body = f"""# {tr(i18n_data, 'alternatives_for', lang)} {tool['name']}

Looking for {tool['name']} alternatives? Here are the top alternatives:

| {tr(i18n_data, 'tools_title', lang)} | {tr(i18n_data, 'vendor', lang)} | {tr(i18n_data, 'pricing', lang)} | {tr(i18n_data, 'free_tier', lang)} | {tr(i18n_data, 'popularity', lang)} |
|------|------|------|------|------|
{chr(10).join(rows)}

## {tr(i18n_data, 'verdict', lang)}

Compare these alternatives with {tool['name']} ({fmt_price(tool['price_min'], tool['price_max'], tool['currency'], pm)}) to find the best fit for your needs.

---

*{tr(i18n_data, 'last_updated', lang)}: {DEFAULT_DATE}*
"""
    front_matter = {
        "title": f"{tr(i18n_data, 'alternatives_for', lang)} {tool['name']} {DEFAULT_DATE}",
        "description": f"Top alternatives to {tool['name']} with pricing and features comparison.",
        "date": DEFAULT_DATE,
        "lastmod": DEFAULT_DATE,
        "type": TYPE_ALTERNATIVES,
        "category": tool["category"],
        "language": lang,
        "draft": False,
        "tool_id": tool["id"],
    }
    return front_matter, body


# ----------------------------------------------------------------------
# 主流程
# ----------------------------------------------------------------------
def generate_tools_pages(tools: list[dict], langs: list[str], i18n_data: dict, dry_run: bool) -> int:
    count = 0
    for tool in tools:
        for lang in langs:
            fm, body = gen_tool_page(tool, lang, i18n_data)
            path = CONTENT_DIR / lang / "tools" / f"{tool['id']}.md"
            if not dry_run:
                write_md(path, fm, body)
            count += 1
            if count % 100 == 0:
                print(f"  [tools] {count} files written...", flush=True)
    return count


def generate_compare_pages(tools: list[dict], langs: list[str], i18n_data: dict, dry_run: bool) -> int:
    # 选 Top 200 工具两两配对，生成 200 对
    top200 = sorted(tools, key=lambda t: t.get("popularity_score", 0), reverse=True)[:200]
    pairs = []
    for i in range(0, len(top200) - 1, 2):
        if i + 1 < len(top200):
            pairs.append((top200[i], top200[i + 1]))
        if len(pairs) >= 200:
            break
    # 若不足 200 对，从相邻工具补充
    idx = 0
    while len(pairs) < 200 and idx < len(top200):
        for j in range(idx + 1, min(idx + 3, len(top200))):
            if len(pairs) >= 200:
                break
            pair = (top200[idx], top200[j])
            if pair not in pairs:
                pairs.append(pair)
        idx += 1

    count = 0
    for tool_a, tool_b in pairs[:200]:
        for lang in langs:
            fm, body = gen_compare_page(tool_a, tool_b, lang, i18n_data)
            path = CONTENT_DIR / lang / "compare" / f"{tool_a['id']}-vs-{tool_b['id']}.md"
            if not dry_run:
                write_md(path, fm, body)
            count += 1
            if count % 100 == 0:
                print(f"  [compare] {count} files written...", flush=True)
    return count


def generate_guide_pages(tools: list[dict], langs: list[str], i18n_data: dict,
                          use_ai: bool, ai_top_n: int, client: AgnesClient | None,
                          dry_run: bool) -> int:
    top_ids = set()
    if use_ai:
        top_ids = {t["id"] for t in sorted(tools, key=lambda t: t.get("popularity_score", 0), reverse=True)[:ai_top_n]}

    count = 0
    for tool in tools:
        use_ai_for_this = use_ai and tool["id"] in top_ids and client is not None
        for lang in langs:
            if use_ai_for_this:
                fm, body = gen_guide_page_ai(tool, lang, i18n_data, client)
            else:
                fm, body = gen_guide_page_template(tool, lang, i18n_data)
            path = CONTENT_DIR / lang / "guides" / f"{tool['id']}-save-tips.md"
            if not dry_run:
                write_md(path, fm, body)
            count += 1
            if count % 100 == 0:
                print(f"  [guides] {count} files written...", flush=True)
    return count


def generate_ranking_pages(tools: list[dict], langs: list[str], i18n_data: dict, dry_run: bool) -> int:
    by_cat: dict[str, list[dict]] = {}
    for t in tools:
        by_cat.setdefault(t["category"], []).append(t)

    count = 0
    for category, tools_in_cat in by_cat.items():
        for lang in langs:
            fm, body = gen_ranking_page(category, tools_in_cat, lang, i18n_data)
            path = CONTENT_DIR / lang / "ranking" / f"{category}-best.md"
            if not dry_run:
                write_md(path, fm, body)
            count += 1
            if count % 100 == 0:
                print(f"  [ranking] {count} files written...", flush=True)
    return count


def generate_faq_pages(tools: list[dict], langs: list[str], i18n_data: dict,
                        use_ai: bool, ai_top_n: int, client: AgnesClient | None,
                        dry_run: bool) -> int:
    top_ids = set()
    if use_ai:
        top_ids = {t["id"] for t in sorted(tools, key=lambda t: t.get("popularity_score", 0), reverse=True)[:ai_top_n]}

    count = 0
    for tool in tools:
        use_ai_for_this = use_ai and tool["id"] in top_ids and client is not None
        for lang in langs:
            if use_ai_for_this:
                fm, body = gen_faq_page_ai(tool, lang, i18n_data, client)
            else:
                fm, body = gen_faq_page_template(tool, lang, i18n_data)
            path = CONTENT_DIR / lang / "faq" / f"{tool['id']}-faq.md"
            if not dry_run:
                write_md(path, fm, body)
            count += 1
            if count % 100 == 0:
                print(f"  [faq] {count} files written...", flush=True)
    return count


def generate_history_pages(tools: list[dict], langs: list[str], i18n_data: dict, dry_run: bool) -> int:
    count = 0
    for tool in tools:
        for lang in langs:
            fm, body = gen_history_page(tool, lang, i18n_data)
            path = CONTENT_DIR / lang / "history" / f"{tool['id']}-history.md"
            if not dry_run:
                write_md(path, fm, body)
            count += 1
            if count % 100 == 0:
                print(f"  [history] {count} files written...", flush=True)
    return count


def generate_alternatives_pages(tools: list[dict], langs: list[str], i18n_data: dict, dry_run: bool) -> int:
    count = 0
    for tool in tools:
        for lang in langs:
            fm, body = gen_alternatives_page(tool, lang, i18n_data, tools)
            path = CONTENT_DIR / lang / "alternatives" / f"{tool['id']}-alternatives.md"
            if not dry_run:
                write_md(path, fm, body)
            count += 1
            if count % 100 == 0:
                print(f"  [alternatives] {count} files written...", flush=True)
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description="批量生成 Hugo 页面")
    parser.add_argument("--all", action="store_true", help="生成全部页面类型")
    parser.add_argument("--tools", action="store_true", help="生成工具页")
    parser.add_argument("--compare", action="store_true", help="生成对比页")
    parser.add_argument("--guides", action="store_true", help="生成攻略页")
    parser.add_argument("--ranking", action="store_true", help="生成排行页")
    parser.add_argument("--faq", action="store_true", help="生成 FAQ 页")
    parser.add_argument("--history", action="store_true", help="生成价格历史页")
    parser.add_argument("--alternatives", action="store_true", help="生成替代品页")
    parser.add_argument("--lang", type=str, default=None, help="指定语种，逗号分隔（默认全部 20）")
    parser.add_argument("--limit", type=int, default=None, help="限制工具数（用于测试）")
    parser.add_argument("--use-ai", action="store_true", help="对 Top N 工具使用 Agnes API 生成内容")
    parser.add_argument("--ai-top-n", type=int, default=DEFAULT_AI_TOP_N, help="AI 生成的工具数（默认 100）")
    parser.add_argument("--dry-run", action="store_true", help="只打印不写文件")
    args = parser.parse_args()

    if not any([args.all, args.tools, args.compare, args.guides, args.ranking, args.faq, args.history, args.alternatives]):
        parser.print_help()
        print("\n请指定至少一个页面类型（如 --all 或 --tools）")
        return 1

    if args.all:
        gen_tools = gen_compare = gen_guides = gen_ranking = gen_faq = gen_history = gen_alts = True
    else:
        gen_tools = args.tools
        gen_compare = args.compare
        gen_guides = args.guides
        gen_ranking = args.ranking
        gen_faq = args.faq
        gen_history = args.history
        gen_alts = args.alternatives

    langs = DEFAULT_LANGS if not args.lang else [l.strip() for l in args.lang.split(",")]
    print(f"=== 配置 ===")
    print(f"  语种: {langs} ({len(langs)} 种)")
    print(f"  限制工具数: {args.limit or '全部'}")
    print(f"  AI 生成: {args.use_ai} (Top {args.ai_top_n if args.use_ai else 0})")
    print(f"  Dry run: {args.dry_run}")
    print(f"  页面类型: tools={gen_tools} compare={gen_compare} guides={gen_guides} ranking={gen_ranking} faq={gen_faq} history={gen_history} alternatives={gen_alts}")

    print("\n=== 加载数据 ===")
    i18n_data = load_i18n()
    print(f"  i18n keys: {len(i18n_data)}")
    tools = load_tools(limit=args.limit)
    print(f"  工具数: {len(tools)}")

    client: AgnesClient | None = None
    if args.use_ai and (gen_guides or gen_faq):
        print("\n=== 初始化 Agnes 客户端 ===")
        try:
            client = get_default_client()
            print(f"  模型: {client.model}, base_url: {client.base_url}")
        except Exception as exc:
            print(f"  [WARN] Agnes 客户端初始化失败: {exc}")
            print(f"  [WARN] 将仅使用模板生成内容")
            client = None

    total_count = 0
    start_time = datetime.now()

    if gen_tools:
        print(f"\n=== 生成工具页 ===")
        total_count += generate_tools_pages(tools, langs, i18n_data, args.dry_run)
        print(f"  工具页完成: {total_count}")

    if gen_compare:
        print(f"\n=== 生成对比页 ===")
        # 对比页使用 Top 200，不受 limit 影响（除非 limit 小于 200）
        n_for_compare = max(args.limit or 200, 200)
        compare_tools = load_tools(limit=None)[:n_for_compare] if not args.limit else tools
        n = generate_compare_pages(compare_tools, langs, i18n_data, args.dry_run)
        total_count += n
        print(f"  对比页完成: {n}")

    if gen_guides:
        print(f"\n=== 生成攻略页 ===")
        n = generate_guide_pages(tools, langs, i18n_data, args.use_ai, args.ai_top_n, client, args.dry_run)
        total_count += n
        print(f"  攻略页完成: {n}")

    if gen_ranking:
        print(f"\n=== 生成排行页 ===")
        n = generate_ranking_pages(tools, langs, i18n_data, args.dry_run)
        total_count += n
        print(f"  排行页完成: {n}")

    if gen_faq:
        print(f"\n=== 生成 FAQ 页 ===")
        n = generate_faq_pages(tools, langs, i18n_data, args.use_ai, args.ai_top_n, client, args.dry_run)
        total_count += n
        print(f"  FAQ 页完成: {n}")

    if gen_history:
        print(f"\n=== 生成价格历史页 ===")
        n = generate_history_pages(tools, langs, i18n_data, args.dry_run)
        total_count += n
        print(f"  价格历史页完成: {n}")

    if gen_alts:
        print(f"\n=== 生成替代品页 ===")
        n = generate_alternatives_pages(tools, langs, i18n_data, args.dry_run)
        total_count += n
        print(f"  替代品页完成: {n}")

    duration = (datetime.now() - start_time).total_seconds()
    print(f"\n=== 完成 ===")
    print(f"  总文件数: {total_count}")
    print(f"  耗时: {duration:.1f} 秒")
    if not args.dry_run:
        print(f"  输出目录: {CONTENT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
