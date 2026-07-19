"""项目校验脚本。

校验项：
- 检查 hugo.toml 配置完整性（20 语种）
- 检查 20 语种目录是否齐全
- 检查 content/ 文件数量是否达到 10 万+
- 检查 layouts/ 模板完整性
- 检查 data/ai_tools.json 格式
- 检查 i18n/ui_translations.json 完整性
- 检查 scripts/ 脚本完整性
- 输出统计报告

CLI:
    python3 scripts/validate_project.py
    python3 scripts/validate_project.py --strict  # 严格模式，任何 ❌ 都返回非 0
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from lib import i18n as i18n_mod

PROJECT_ROOT = SCRIPT_DIR.parent
HUGO_TOML = PROJECT_ROOT / "hugo.toml"
CONTENT_DIR = PROJECT_ROOT / "content"
LAYOUTS_DIR = PROJECT_ROOT / "layouts"
DATA_DIR = PROJECT_ROOT / "data"
I18N_DIR = PROJECT_ROOT / "i18n"
SCRIPTS_DIR = SCRIPT_DIR
LIB_DIR = SCRIPTS_DIR / "lib"

EXPECTED_LANGS = i18n_mod.SUPPORTED_LANGS
EXPECTED_PAGE_TYPES = ["tools", "compare", "guides", "ranking", "faq", "history", "alternatives"]
EXPECTED_LAYOUTS = [
    "index.html", "404.html", "robots.txt",
    "_default/baseof.html", "_default/list.html", "_default/single.html",
    "partials/header.html", "partials/footer.html", "partials/seo.html",
    "partials/structured-data.html", "partials/tool-card.html",
    "partials/language-switcher.html", "partials/search-box.html",
    "search/list.html",
]
EXPECTED_SCRIPTS = [
    "lib/agnes_client.py", "lib/i18n.py", "lib/tools_data.py",
    "generate_pages.py", "fetch_prices.py", "translate_content.py",
    "generate_sitemap.py", "generate_llms_txt.py",
    "validate_project.py", "build.sh",
]

MIN_TOOLS_COUNT = 1000
MIN_TOTAL_PAGES = 100_000


class Report:
    def __init__(self) -> None:
        self.passed: list[str] = []
        self.warnings: list[str] = []
        self.failed: list[str] = []

    def ok(self, msg: str) -> None:
        self.passed.append(msg)
        print(f"  ✅ {msg}")

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)
        print(f"  ⚠️  {msg}")

    def err(self, msg: str) -> None:
        self.failed.append(msg)
        print(f"  ❌ {msg}")


def check_hugo_toml(r: Report) -> None:
    print("\n[1] 检查 hugo.toml 配置完整性")
    if not HUGO_TOML.exists():
        r.err(f"hugo.toml 不存在: {HUGO_TOML}")
        return
    content = HUGO_TOML.read_text(encoding="utf-8")
    if "baseURL" not in content:
        r.err("hugo.toml 缺少 baseURL 配置")
    else:
        r.ok("hugo.toml 包含 baseURL")
    if "DefaultContentLanguage" not in content:
        r.err("hugo.toml 缺少 DefaultContentLanguage")
    else:
        r.ok("hugo.toml 包含 DefaultContentLanguage")
    # 检查 20 语种
    for lang in EXPECTED_LANGS:
        pattern = rf"\[languages\.{lang}\]"
        if not re.search(pattern, content):
            r.err(f"hugo.toml 缺少语种配置: {lang}")
        else:
            pass  # 单条不打 ✅ 避免刷屏
    # 汇总
    found = sum(1 for lang in EXPECTED_LANGS if re.search(rf"\[languages\.{lang}\]", content))
    if found == len(EXPECTED_LANGS):
        r.ok(f"hugo.toml 配置了全部 {found} 语种")
    else:
        r.err(f"hugo.toml 仅配置 {found}/{len(EXPECTED_LANGS)} 语种")


def check_layouts(r: Report) -> None:
    print("\n[2] 检查 layouts/ 模板完整性")
    if not LAYOUTS_DIR.exists():
        r.err(f"layouts/ 目录不存在: {LAYOUTS_DIR}")
        return
    for rel in EXPECTED_LAYOUTS:
        path = LAYOUTS_DIR / rel
        if path.exists():
            r.ok(f"layouts/{rel}")
        else:
            r.err(f"layouts/{rel} 缺失")


def check_scripts(r: Report) -> None:
    print("\n[3] 检查 scripts/ 脚本完整性")
    for rel in EXPECTED_SCRIPTS:
        path = PROJECT_ROOT / "scripts" / rel
        if path.exists():
            r.ok(f"scripts/{rel}")
        else:
            r.err(f"scripts/{rel} 缺失")


def check_ai_tools_json(r: Report) -> None:
    print("\n[4] 检查 data/ai_tools.json 格式")
    path = DATA_DIR / "ai_tools.json"
    if not path.exists():
        r.err(f"data/ai_tools.json 不存在")
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        r.err(f"data/ai_tools.json JSON 解析失败: {exc}")
        return
    if not isinstance(data, list):
        r.err("data/ai_tools.json 不是数组")
        return
    if len(data) < MIN_TOOLS_COUNT:
        r.warn(f"工具数 {len(data)} < 期望 {MIN_TOOLS_COUNT}")
    else:
        r.ok(f"工具数 {len(data)} ≥ {MIN_TOOLS_COUNT}")
    # 检查必填字段
    required = ["id", "name", "category", "vendor", "url", "pricing_model",
                "price_min", "price_max", "currency", "free_tier",
                "description_en", "features", "alternatives",
                "founded_year", "popularity_score"]
    missing_count = 0
    seen_ids: set[str] = set()
    dup_ids: list[str] = []
    for i, t in enumerate(data):
        for k in required:
            if k not in t:
                missing_count += 1
                if missing_count <= 3:
                    r.err(f"工具 #{i} ({t.get('id', '?')}) 缺少字段: {k}")
        if t.get("id") in seen_ids:
            dup_ids.append(t.get("id", "?"))
        seen_ids.add(t.get("id", ""))
    if missing_count == 0:
        r.ok(f"所有 {len(data)} 个工具字段完整")
    else:
        r.err(f"共有 {missing_count} 处字段缺失")
    if dup_ids:
        r.err(f"工具 ID 重复: {dup_ids[:5]}")
    else:
        r.ok("工具 ID 无重复")


def check_i18n_json(r: Report) -> None:
    print("\n[5] 检查 data/ui_translations.json 完整性")
    path = DATA_DIR / "ui_translations.json"
    if not path.exists():
        r.err(f"data/ui_translations.json 不存在")
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        r.err(f"data/ui_translations.json JSON 解析失败: {exc}")
        return
    if "LANG_MAP" not in data:
        r.err("缺少 LANG_MAP 字段")
        return
    if len(data["LANG_MAP"]) != len(EXPECTED_LANGS):
        r.err(f"LANG_MAP 语种数 {len(data['LANG_MAP'])} ≠ 期望 {len(EXPECTED_LANGS)}")
    else:
        r.ok(f"LANG_MAP 包含全部 {len(EXPECTED_LANGS)} 语种")
    # 检查每个 key 都有 20 种语言
    bad_keys: list[str] = []
    for k, v in data.items():
        if k in ("LANG_MAP", "__categories__"):
            continue
        if not isinstance(v, dict):
            bad_keys.append(k)
            continue
        for lang in EXPECTED_LANGS:
            if lang not in v:
                bad_keys.append(f"{k}[{lang}]")
    if bad_keys:
        r.err(f"翻译缺失 ({len(bad_keys)} 处): {bad_keys[:5]}")
    else:
        ui_keys = [k for k in data.keys() if k not in ("LANG_MAP", "__categories__")]
        r.ok(f"UI keys {len(ui_keys)} 个，全部 20 语种完整")


def check_content_pages(r: Report) -> None:
    print("\n[6] 检查 content/ 目录与文件数量")
    if not CONTENT_DIR.exists():
        r.err("content/ 目录不存在")
        return

    # 语种目录
    found_langs: list[str] = []
    for lang in EXPECTED_LANGS:
        lang_dir = CONTENT_DIR / lang
        if lang_dir.exists():
            found_langs.append(lang)
    if len(found_langs) == len(EXPECTED_LANGS):
        r.ok(f"全部 {len(EXPECTED_LANGS)} 语种目录存在")
    else:
        missing = set(EXPECTED_LANGS) - set(found_langs)
        r.err(f"缺少语种目录: {missing}")
        r.warn(f"仅有 {len(found_langs)}/{len(EXPECTED_LANGS)} 语种目录")

    # 每个语种下的页面类型
    page_type_counts: dict[str, dict[str, int]] = {}
    for lang in found_langs:
        page_type_counts[lang] = {}
        for ptype in EXPECTED_PAGE_TYPES:
            ptype_dir = CONTENT_DIR / lang / ptype
            if ptype_dir.exists():
                count = sum(1 for _ in ptype_dir.rglob("*.md"))
                page_type_counts[lang][ptype] = count

    # 统计总文件数
    total = 0
    for lang, counts in page_type_counts.items():
        for ptype, n in counts.items():
            total += n
    print(f"  总 .md 文件数: {total}")
    if total >= MIN_TOTAL_PAGES:
        r.ok(f"总文件数 {total} ≥ {MIN_TOTAL_PAGES}")
    elif total > 0:
        r.warn(f"总文件数 {total} < 期望 {MIN_TOTAL_PAGES}（需运行 generate_pages.py --all）")
    else:
        r.err("content/ 下无 .md 文件（请先运行 generate_pages.py）")

    # 每种页面类型分布
    if page_type_counts:
        for ptype in EXPECTED_PAGE_TYPES:
            total_ptype = sum(c.get(ptype, 0) for c in page_type_counts.values())
            if total_ptype > 0:
                r.ok(f"  {ptype}: {total_ptype} 文件")
            else:
                r.warn(f"  {ptype}: 0 文件")


def check_static_assets(r: Report) -> None:
    print("\n[7] 检查 static/ 资源")
    static_dir = PROJECT_ROOT / "static"
    if not static_dir.exists():
        r.warn("static/ 目录不存在（可能尚未生成 llms.txt 等）")
        return
    if (static_dir / "llms.txt").exists():
        r.ok("static/llms.txt 存在")
    else:
        r.warn("static/llms.txt 不存在（运行 generate_llms_txt.py）")


def main() -> int:
    parser = argparse.ArgumentParser(description="项目校验")
    parser.add_argument("--strict", action="store_true", help="严格模式，任何 ❌ 都返回非 0")
    args = parser.parse_args()

    print("=" * 60)
    print(f"AI Tools Pricing Hub — 项目校验报告")
    print(f"项目根目录: {PROJECT_ROOT}")
    print(f"校验时间: {__import__('datetime').datetime.now().isoformat()}")
    print("=" * 60)

    r = Report()
    check_hugo_toml(r)
    check_layouts(r)
    check_scripts(r)
    check_ai_tools_json(r)
    check_i18n_json(r)
    check_content_pages(r)
    check_static_assets(r)

    print("\n" + "=" * 60)
    print("=== 汇总 ===")
    print(f"  ✅ 通过: {len(r.passed)}")
    print(f"  ⚠️  警告: {len(r.warnings)}")
    print(f"  ❌ 失败: {len(r.failed)}")
    print("=" * 60)

    if r.failed:
        print("\n失败项:")
        for msg in r.failed:
            print(f"  ❌ {msg}")

    if args.strict and r.failed:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
