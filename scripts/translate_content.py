"""翻译脚本：调用 Agnes API 将 .md 文件翻译到目标语种。

- 保留 front matter 不翻译（仅修改 lang/title/description 字段）
- 只翻译正文
- 输出到对应语种目录
- 支持并发（max_workers=5）

CLI:
    python3 scripts/translate_content.py \\
        --file content/en/tools/chatgpt-plus.md \\
        --target-langs zh,es,fr,de,ja,ko,pt,ru,it,ar,nl,pl,tr,vi,th,id,sv,no,da

    # 批量翻译某目录所有 .md
    python3 scripts/translate_content.py \\
        --dir content/en/tools \\
        --target-langs zh,ja
"""
from __future__ import annotations

import argparse
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from lib.agnes_client import AgnesClient, get_default_client
from lib import i18n as i18n_mod

PROJECT_ROOT = SCRIPT_DIR.parent
CONTENT_DIR = PROJECT_ROOT / "content"

FRONT_MATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)


def parse_front_matter(content: str) -> tuple[str, str]:
    """分离 front matter 与正文。返回 (front_matter_raw, body)。"""
    m = FRONT_MATTER_RE.match(content)
    if not m:
        return "", content
    return m.group(1), m.group(2)


def update_front_matter_lang(front_matter_raw: str, target_lang: str) -> str:
    """更新 front matter 中的 lang 字段（若不存在则添加）。"""
    lines = front_matter_raw.split("\n")
    has_lang = False
    new_lines = []
    for line in lines:
        if line.startswith("lang:"):
            new_lines.append(f'lang: "{target_lang}"')
            has_lang = True
        else:
            new_lines.append(line)
    if not has_lang:
        new_lines.append(f'lang: "{target_lang}"')
    return "\n".join(new_lines)


def translate_md_file(
    src_path: Path,
    target_lang: str,
    client: AgnesClient,
    src_lang: str = "en",
) -> Path:
    """翻译单个 .md 文件到目标语种。

    返回目标文件路径。
    """
    # 推导目标路径：将 content/{src_lang}/... 替换为 content/{target_lang}/...
    rel = src_path.relative_to(CONTENT_DIR / src_lang)
    dst_path = CONTENT_DIR / target_lang / rel

    # 幂等：目标已存在则跳过
    if dst_path.exists():
        return dst_path

    src_content = src_path.read_text(encoding="utf-8")
    front_matter_raw, body = parse_front_matter(src_content)

    # 翻译正文
    if body.strip():
        translated_body = client.translate(body, target_lang, source_lang=src_lang)
    else:
        translated_body = body

    # 更新 front matter
    new_front_matter = update_front_matter_lang(front_matter_raw, target_lang)

    # 写入目标文件
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    dst_path.write_text(f"---\n{new_front_matter}\n---\n{translated_body}", encoding="utf-8")
    return dst_path


def translate_one(src_path: Path, target_lang: str, client: AgnesClient, src_lang: str) -> tuple[str, str, str]:
    """线程池任务：返回 (src_path, target_lang, dst_path 或 error)。"""
    try:
        dst = translate_md_file(src_path, target_lang, client, src_lang)
        return (str(src_path), target_lang, str(dst))
    except Exception as exc:
        return (str(src_path), target_lang, f"ERROR: {type(exc).__name__}: {exc}")


def collect_md_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    if path.is_dir():
        return sorted(path.rglob("*.md"))
    raise FileNotFoundError(f"路径不存在: {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="翻译 .md 内容到多语种")
    parser.add_argument("--file", type=str, help="单个 .md 文件路径")
    parser.add_argument("--dir", type=str, help="目录路径（递归翻译所有 .md）")
    parser.add_argument("--target-langs", type=str, required=True,
                        help="目标语种代码，逗号分隔（如 zh,es,fr）")
    parser.add_argument("--source-lang", type=str, default="en", help="源语种（默认 en）")
    parser.add_argument("--max-workers", type=int, default=5, help="并发数")
    parser.add_argument("--no-cache", action="store_true", help="禁用 Agnes 缓存")
    args = parser.parse_args()

    if not args.file and not args.dir:
        parser.error("必须指定 --file 或 --dir")

    src_path = Path(args.file) if args.file else Path(args.dir)
    if not src_path.is_absolute():
        src_path = (PROJECT_ROOT / src_path).resolve()

    target_langs = [l.strip() for l in args.target_langs.split(",")]
    for lang in target_langs:
        if lang not in i18n_mod.SUPPORTED_LANGS:
            print(f"[ERROR] 不支持的语种: {lang}。支持: {i18n_mod.SUPPORTED_LANGS}")
            return 1
    if args.source_lang not in i18n_mod.SUPPORTED_LANGS:
        print(f"[ERROR] 不支持的源语种: {args.source_lang}")
        return 1

    md_files = collect_md_files(src_path)
    print(f"=== 配置 ===")
    print(f"  源路径: {src_path}")
    print(f"  源语种: {args.source_lang}")
    print(f"  目标语种: {target_langs} ({len(target_langs)} 种)")
    print(f"  待翻译文件: {len(md_files)}")
    print(f"  总任务数: {len(md_files) * len(target_langs)}")
    print(f"  并发数: {args.max_workers}")

    print("\n=== 初始化 Agnes 客户端 ===")
    try:
        client = AgnesClient(enable_cache=not args.no_cache)
        print(f"  模型: {client.model}, base_url: {client.base_url}")
    except Exception as exc:
        print(f"[ERROR] 初始化失败: {exc}")
        return 1

    # 构建任务列表
    tasks: list[tuple[Path, str]] = []
    for md_file in md_files:
        for lang in target_langs:
            tasks.append((md_file, lang))

    print(f"\n=== 开始翻译 ({len(tasks)} 个任务) ===")
    success = 0
    failed = 0
    skipped = 0
    with ThreadPoolExecutor(max_workers=args.max_workers) as pool:
        futures = [pool.submit(translate_one, src, lang, client, args.source_lang)
                   for src, lang in tasks]
        for i, future in enumerate(as_completed(futures), 1):
            src_str, lang, result = future.result()
            if result.startswith("ERROR:"):
                failed += 1
                print(f"  [{i}/{len(tasks)}] FAIL {src_str} → {lang}: {result}", flush=True)
            else:
                # 检查是否已存在（跳过）
                src_path_obj = Path(src_str)
                rel = src_path_obj.relative_to(CONTENT_DIR / args.source_lang)
                expected_dst = CONTENT_DIR / lang / rel
                if expected_dst.exists() and expected_dst.stat().st_mtime >= src_path_obj.stat().st_mtime:
                    skipped += 1
                else:
                    success += 1
                if i % 20 == 0:
                    print(f"  [{i}/{len(tasks)}] 进度: 成功={success} 跳过={skipped} 失败={failed}", flush=True)

    print(f"\n=== 完成 ===")
    print(f"  成功: {success}")
    print(f"  跳过: {skipped}")
    print(f"  失败: {failed}")
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
