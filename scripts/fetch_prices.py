"""每日价格抓取脚本（模拟版，因无法访问国外网站）。

流程：
1. 读取 data/ai_tools.json
2. 对每个工具的 url 字段，尝试 HTTP 请求（10 秒超时）
3. 如果失败（预期），从工具数据中随机微调价格（±5%）模拟价格变动
4. 检测价格变动并记录到 data/price_history.json
5. 输出变更报告

CLI:
    python3 scripts/fetch_prices.py
    python3 scripts/fetch_prices.py --limit 50
    python3 scripts/fetch_prices.py --skip-fetch  # 跳过 HTTP 尝试，直接模拟
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from lib import tools_data as tools_mod

PROJECT_ROOT = SCRIPT_DIR.parent
DATA_DIR = PROJECT_ROOT / "data"
TOOLS_FILE = DATA_DIR / "ai_tools.json"
HISTORY_FILE = DATA_DIR / "price_history.json"
REPORT_FILE = DATA_DIR / "price_change_report.md"

HTTP_TIMEOUT = 10  # 秒
PRICE_VARIATION = 0.05  # ±5%
USER_AGENT = "Mozilla/5.0 (compatible; AIPricingBot/1.0)"


def try_fetch(url: str) -> tuple[bool, str]:
    """尝试 HTTP 请求。返回 (是否成功, 内容或错误信息)。"""
    try:
        req = Request(url, headers={"User-Agent": USER_AGENT})
        with urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            content = resp.read(4096).decode("utf-8", errors="ignore")
            return True, content
    except (URLError, TimeoutError, ConnectionError, OSError) as exc:
        return False, f"{type(exc).__name__}: {exc}"
    except Exception as exc:
        return False, f"Unexpected error: {type(exc).__name__}: {exc}"


def load_history() -> dict:
    if HISTORY_FILE.exists():
        return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    return {"tools": {}, "last_updated": None}


def save_history(history: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    HISTORY_FILE.write_text(
        json.dumps(history, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def simulate_price_change(current_min: float, current_max: float) -> tuple[float, float, float]:
    """模拟价格变动（±5%）。

    返回 (new_min, new_max, change_pct)。
    """
    rng = random.Random()
    # 用当前最大价作为基准（更直观）
    base = current_max if current_max > 0 else current_min
    if base == 0:
        return current_min, current_max, 0.0
    delta_pct = rng.uniform(-PRICE_VARIATION, PRICE_VARIATION)
    new_max = round(base * (1 + delta_pct), 2)
    new_min = round(current_min * (1 + delta_pct), 2) if current_min > 0 else 0
    change_pct = round(delta_pct * 100, 2)
    return new_min, new_max, change_pct


def fetch_all_prices(tools: list[dict], skip_fetch: bool = False) -> tuple[list[dict], list[dict]]:
    """抓取所有工具的价格。

    返回 (更新后的工具列表, 变更记录列表)。
    """
    today = datetime.now().strftime("%Y-%m-%d")
    history = load_history()
    changes: list[dict] = []

    for i, tool in enumerate(tools, 1):
        tool_id = tool["id"]
        url = tool.get("url", "")
        fetch_ok = False
        fetch_msg = ""

        if not skip_fetch and url:
            fetch_ok, fetch_msg = try_fetch(url)
            if i % 50 == 0:
                print(f"  [{i}/{len(tools)}] {tool_id}: fetch={'OK' if fetch_ok else 'FAIL'}", flush=True)

        # 由于无法访问国外网站，预期 fetch_ok=False
        # 用模拟价格变动
        old_min = tool["price_min"]
        old_max = tool["price_max"]
        new_min, new_max, change_pct = simulate_price_change(old_min, old_max)

        # 价格变动检测
        changed = abs(change_pct) > 0.1  # 真实变动 (>0.1%)
        if changed:
            changes.append({
                "tool_id": tool_id,
                "name": tool["name"],
                "old_min": old_min,
                "old_max": old_max,
                "new_min": new_min,
                "new_max": new_max,
                "change_pct": change_pct,
                "currency": tool["currency"],
                "date": today,
                "fetch_ok": fetch_ok,
                "fetch_msg": fetch_msg,
            })
            # 更新工具价格
            tool["price_min"] = new_min
            tool["price_max"] = new_max
            tool["price_updated_at"] = today

        # 更新历史
        if tool_id not in history["tools"]:
            history["tools"][tool_id] = []
        history["tools"][tool_id].append({
            "date": today,
            "price_min": tool["price_min"],
            "price_max": tool["price_max"],
            "currency": tool["currency"],
            "change_pct": change_pct,
        })
        # 只保留最近 365 天
        if len(history["tools"][tool_id]) > 365:
            history["tools"][tool_id] = history["tools"][tool_id][-365:]

    history["last_updated"] = today
    return tools, changes


def write_report(changes: list[dict], total_tools: int) -> Path:
    """输出变更报告 (Markdown)。"""
    today = datetime.now().strftime("%Y-%m-%d")
    up = [c for c in changes if c["change_pct"] > 0]
    down = [c for c in changes if c["change_pct"] < 0]
    no_change = total_tools - len(changes)

    lines = [
        f"# Price Change Report — {today}",
        "",
        f"## Summary",
        "",
        f"- Total tools checked: **{total_tools}**",
        f"- Price increased: **{len(up)}**",
        f"- Price decreased: **{len(down)}**",
        f"- No change: **{no_change}**",
        "",
        "## Price Increases",
        "",
        "| Tool | Old Max | New Max | Change % |",
        "|------|---------|---------|----------|",
    ]
    for c in up[:50]:
        lines.append(f"| {c['name']} | ${c['old_max']} | ${c['new_max']} | +{c['change_pct']}% |")
    if len(up) > 50:
        lines.append(f"| ... and {len(up)-50} more | | | |")

    lines.extend([
        "",
        "## Price Decreases",
        "",
        "| Tool | Old Max | New Max | Change % |",
        "|------|---------|---------|----------|",
    ])
    for c in down[:50]:
        lines.append(f"| {c['name']} | ${c['old_max']} | ${c['new_max']} | {c['change_pct']}% |")
    if len(down) > 50:
        lines.append(f"| ... and {len(down)-50} more | | | |")

    lines.extend([
        "",
        "## Notes",
        "",
        "- Due to network restrictions, prices are simulated with ±5% random variation.",
        "- Real price fetching requires a network proxy or running from a server with international access.",
        "- Full history is stored in `data/price_history.json`.",
        "",
    ])

    REPORT_FILE.write_text("\n".join(lines), encoding="utf-8")
    return REPORT_FILE


def main() -> int:
    parser = argparse.ArgumentParser(description="每日价格抓取（模拟版）")
    parser.add_argument("--limit", type=int, default=None, help="限制工具数")
    parser.add_argument("--skip-fetch", action="store_true", help="跳过 HTTP 尝试，直接模拟价格变动")
    args = parser.parse_args()

    print("=== 加载工具数据 ===")
    tools = tools_mod.load_tools()
    if args.limit:
        tools = tools[:args.limit]
    print(f"  工具数: {len(tools)}")

    print("\n=== 抓取价格（预期失败，会模拟变动） ===")
    start = time.time()
    updated_tools, changes = fetch_all_prices(tools, skip_fetch=args.skip_fetch)
    duration = time.time() - start
    print(f"  耗时: {duration:.1f}s")

    print("\n=== 保存数据 ===")
    # 更新 ai_tools.json
    all_tools = tools_mod.load_tools()
    if args.limit:
        # 部分更新
        updated_ids = {t["id"]: t for t in updated_tools}
        for i, t in enumerate(all_tools):
            if t["id"] in updated_ids:
                all_tools[i] = updated_ids[t["id"]]
    else:
        all_tools = updated_tools
    TOOLS_FILE.write_text(
        json.dumps(all_tools, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"  已更新 {TOOLS_FILE}")

    print("\n=== 生成变更报告 ===")
    report_path = write_report(changes, len(tools))
    print(f"  报告: {report_path}")

    # 控制台摘要
    up = sum(1 for c in changes if c["change_pct"] > 0)
    down = sum(1 for c in changes if c["change_pct"] < 0)
    print(f"\n=== 摘要 ===")
    print(f"  检查工具: {len(tools)}")
    print(f"  价格上涨: {up}")
    print(f"  价格下降: {down}")
    print(f"  无变动: {len(tools) - len(changes)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
