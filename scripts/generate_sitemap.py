"""生成 sitemap.xml 和 sitemap-index.xml。

- 遍历 content/ 所有 .md 文件
- 每个语种一个 sitemap-{lang}.xml
- 主 sitemap-index.xml 引用所有子 sitemap
- 标准格式：loc/lastmod/changefreq/priority

输出到 public/sitemap-index.xml 和 public/sitemap-{lang}.xml
（若 public/ 不存在则输出到 static/）

CLI:
    python3 scripts/generate_sitemap.py
    python3 scripts/generate_sitemap.py --base-url https://pricing.ai-term-hub.com/
    python3 scripts/generate_sitemap.py --output public/
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from lib import i18n as i18n_mod

PROJECT_ROOT = SCRIPT_DIR.parent
CONTENT_DIR = PROJECT_ROOT / "content"
DEFAULT_BASE_URL = "https://pricing.ai-term-hub.com/"

FRONT_MATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
LASTMOD_RE = re.compile(r'^lastmod:\s*["\']?(\d{4}-\d{2}-\d{2})', re.MULTILINE)
DATE_RE = re.compile(r'^date:\s*["\']?(\d{4}-\d{2}-\d{2})', re.MULTILINE)
TYPE_RE = re.compile(r'^type:\s*["\']?(\w+)', re.MULTILINE)


def parse_md_meta(path: Path) -> dict:
    """从 .md front matter 提取 lastmod / date / type。"""
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    m = FRONT_MATTER_RE.match(content)
    if not m:
        return {}
    fm = m.group(1)
    meta: dict = {}
    lm = LASTMOD_RE.search(fm)
    if lm:
        meta["lastmod"] = lm.group(1)
    dt = DATE_RE.search(fm)
    if dt:
        meta["date"] = dt.group(1)
    tp = TYPE_RE.search(fm)
    if tp:
        meta["type"] = tp.group(1)
    return meta


def md_path_to_url(md_path: Path, lang: str, base_url: str) -> str:
    """将 content/{lang}/tools/foo.md → {base_url}/{lang}/tools/foo/"""
    rel = md_path.relative_to(CONTENT_DIR / lang)
    # 去除 .md 扩展名
    url_path = str(rel).replace("\\", "/").replace(".md", "")
    # _index.md → 该目录
    if url_path.endswith("/_index"):
        url_path = url_path[:-len("/_index")]
    # 标准化 base_url
    if not base_url.endswith("/"):
        base_url += "/"
    # 英文为默认语种，可选是否带 /en/ 前缀（这里保留 /en/ 以匹配 Hugo 配置）
    return f"{base_url}{lang}/{url_path}/" if url_path else f"{base_url}{lang}/"


def get_changefreq_priority(meta: dict) -> tuple[str, float]:
    """根据页面类型返回 changefreq 和 priority。"""
    ptype = meta.get("type", "")
    table = {
        "tools": ("weekly", 0.9),
        "compare": ("monthly", 0.7),
        "guides": ("monthly", 0.8),
        "ranking": ("weekly", 0.8),
        "faq": ("monthly", 0.6),
        "history": ("weekly", 0.6),
        "alternatives": ("monthly", 0.6),
    }
    return table.get(ptype, ("monthly", 0.5))


def generate_sitemap_for_lang(lang: str, base_url: str) -> tuple[Path, int]:
    """为单个语种生成 sitemap-{lang}.xml。返回 (path, url_count)。"""
    lang_dir = CONTENT_DIR / lang
    if not lang_dir.exists():
        return (lang_dir, 0)

    md_files = sorted(lang_dir.rglob("*.md"))
    if not md_files:
        return (lang_dir, 0)

    today = datetime.now().strftime("%Y-%m-%d")
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    count = 0
    for md_path in md_files:
        meta = parse_md_meta(md_path)
        url = md_path_to_url(md_path, lang, base_url)
        lastmod = meta.get("lastmod") or meta.get("date") or today
        changefreq, priority = get_changefreq_priority(meta)
        lines.append("  <url>")
        lines.append(f"    <loc>{escape(url)}</loc>")
        lines.append(f"    <lastmod>{lastmod}</lastmod>")
        lines.append(f"    <changefreq>{changefreq}</changefreq>")
        lines.append(f"    <priority>{priority}</priority>")
        lines.append("  </url>")
        count += 1
    lines.append("</urlset>")
    return (lang_dir, count)


def write_sitemaps(output_dir: Path, base_url: str) -> tuple[int, int]:
    """生成所有语种的 sitemap 和 sitemap-index。

    返回 (子 sitemap 数量, 总 URL 数量)。
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")

    sub_sitemaps: list[tuple[str, int]] = []
    total_urls = 0

    for lang in i18n_mod.SUPPORTED_LANGS:
        _, count = generate_sitemap_for_lang(lang, base_url)
        if count == 0:
            continue
        # 写入子 sitemap
        sitemap_path = output_dir / f"sitemap-{lang}.xml"
        lang_dir = CONTENT_DIR / lang
        md_files = sorted(lang_dir.rglob("*.md"))
        lines = ['<?xml version="1.0" encoding="UTF-8"?>',
                 '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
        for md_path in md_files:
            meta = parse_md_meta(md_path)
            url = md_path_to_url(md_path, lang, base_url)
            lastmod = meta.get("lastmod") or meta.get("date") or today
            changefreq, priority = get_changefreq_priority(meta)
            lines.append("  <url>")
            lines.append(f"    <loc>{escape(url)}</loc>")
            lines.append(f"    <lastmod>{lastmod}</lastmod>")
            lines.append(f"    <changefreq>{changefreq}</changefreq>")
            lines.append(f"    <priority>{priority}</priority>")
            lines.append("  </url>")
        lines.append("</urlset>")
        sitemap_path.write_text("\n".join(lines), encoding="utf-8")
        sub_sitemaps.append((lang, count))
        total_urls += count
        print(f"  sitemap-{lang}.xml: {count} URLs", flush=True)

    # 写入 sitemap-index.xml
    if not base_url.endswith("/"):
        base_url += "/"
    index_lines = ['<?xml version="1.0" encoding="UTF-8"?>',
                   '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for lang, count in sub_sitemaps:
        index_lines.append("  <sitemap>")
        index_lines.append(f"    <loc>{escape(base_url)}sitemap-{lang}.xml</loc>")
        index_lines.append(f"    <lastmod>{today}</lastmod>")
        index_lines.append("  </sitemap>")
    index_lines.append("</sitemapindex>")
    (output_dir / "sitemap-index.xml").write_text("\n".join(index_lines), encoding="utf-8")

    return len(sub_sitemaps), total_urls


def main() -> int:
    parser = argparse.ArgumentParser(description="生成 sitemap.xml 和 sitemap-index.xml")
    parser.add_argument("--base-url", type=str, default=DEFAULT_BASE_URL,
                        help="站点 base URL（默认 https://pricing.ai-term-hub.com/）")
    parser.add_argument("--output", type=str, default="public",
                        help="输出目录（默认 public/）")
    args = parser.parse_args()

    output_dir = PROJECT_ROOT / args.output
    if not output_dir.is_absolute():
        output_dir = PROJECT_ROOT / args.output

    print(f"=== 生成 sitemap ===")
    print(f"  base_url: {args.base_url}")
    print(f"  output: {output_dir}")
    print(f"  content: {CONTENT_DIR}")

    if not CONTENT_DIR.exists():
        print(f"[ERROR] content/ 目录不存在，请先运行 generate_pages.py")
        return 1

    sub_count, total_urls = write_sitemaps(output_dir, args.base_url)

    print(f"\n=== 完成 ===")
    print(f"  子 sitemap 数: {sub_count}")
    print(f"  总 URL 数: {total_urls}")
    print(f"  sitemap-index: {output_dir / 'sitemap-index.xml'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
