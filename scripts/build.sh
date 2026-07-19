#!/bin/bash
# AI Tools Pricing Hub — 构建脚本（本地和 CI 通用）
#
# 用法:
#   bash scripts/build.sh              # 完整构建（含 AI 生成）
#   bash scripts/build.sh --no-ai      # 跳过 AI 生成（仅模板）
#   bash scripts/build.sh --no-hugo    # 跳过 Hugo 构建（仅生成内容）
#   bash scripts/build.sh --limit 100  # 限制工具数（测试用）

set -e

# 切换到项目根目录（脚本上两级）
cd "$(dirname "$0")/.."
PROJECT_ROOT="$(pwd)"

echo "============================================================"
echo "AI Tools Pricing Hub — Build"
echo "Project root: ${PROJECT_ROOT}"
echo "Time: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "============================================================"

# 解析参数
USE_AI="--use-ai"
SKIP_HUGO=0
LIMIT_ARG=""
SKIP_PAGEFIND=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --no-ai)
            USE_AI=""
            shift
            ;;
        --no-hugo)
            SKIP_HUGO=1
            shift
            ;;
        --no-pagefind)
            SKIP_PAGEFIND=1
            shift
            ;;
        --limit)
            LIMIT_ARG="--limit $2"
            shift 2
            ;;
        *)
            echo "Unknown argument: $1"
            exit 1
            ;;
    esac
done

# 检查依赖
echo ""
echo "[0/7] 检查依赖..."
if ! command -v python3 >/dev/null 2>&1; then
    echo "❌ 未找到 python3"
    exit 1
fi
echo "  ✅ python3: $(python3 --version)"

if ! python3 -c "import openai" 2>/dev/null; then
    echo "  ⚠️  openai SDK 未安装，正在安装..."
    pip3 install --quiet 'openai>=1.40.0'
fi
echo "  ✅ openai SDK: $(python3 -c 'import openai; print(openai.__version__)')"

if [ "$SKIP_HUGO" -eq 0 ]; then
    if ! command -v hugo >/dev/null 2>&1; then
        echo "❌ 未找到 hugo，请先安装: https://gohugo.io/installation/"
        exit 1
    fi
    echo "  ✅ hugo: $(hugo version | head -c 80)"
fi

# 步骤 1: 生成工具数据
echo ""
echo "[1/7] 生成工具数据 (data/ai_tools.json)..."
python3 scripts/lib/tools_data.py

# 步骤 2: 生成 UI 翻译
echo ""
echo "[2/7] 生成 UI 翻译 (data/ui_translations.json)..."
python3 scripts/lib/i18n.py

# 步骤 3: 生成页面
echo ""
echo "[3/7] 生成 Hugo 页面 (content/)..."
python3 scripts/generate_pages.py --all $USE_AI $LIMIT_ARG

# 步骤 4: 生成 sitemap
echo ""
echo "[4/7] 生成 sitemap..."
# 先创建 public/ 目录（如果不存在）
mkdir -p public
python3 scripts/generate_sitemap.py --output public/

# 步骤 5: 生成 llms.txt
echo ""
echo "[5/7] 生成 llms.txt..."
python3 scripts/generate_llms_txt.py

# 步骤 6: Hugo 构建
if [ "$SKIP_HUGO" -eq 0 ]; then
    echo ""
    echo "[6/7] Hugo 构建..."
    hugo --minify --baseURL "https://pricing.ai-term-hub.com/"

    # 生成 Pagefind 索引
    if [ "$SKIP_PAGEFIND" -eq 0 ]; then
        if command -v npx >/dev/null 2>&1; then
            echo ""
            echo "[6.5/7] 生成 Pagefind 索引..."
            npx pagefind --site public/ || echo "  ⚠️  Pagefind 索引失败（不影响构建）"
        else
            echo "  ⚠️  未找到 npx，跳过 Pagefind 索引"
        fi
    fi
else
    echo ""
    echo "[6/7] 跳过 Hugo 构建（--no-hugo）"
fi

# 步骤 7: 校验
echo ""
echo "[7/7] 校验项目..."
python3 scripts/validate_project.py || echo "  ⚠️  校验发现警告（非阻塞）"

echo ""
echo "============================================================"
echo "✅ 构建完成！"
echo "============================================================"
echo ""
echo "输出目录:"
echo "  - public/           # Hugo 构建产物"
echo "  - content/          # 生成的 .md 文件"
echo "  - data/ai_tools.json"
echo "  - data/ui_translations.json"
echo "  - static/llms.txt"
echo "  - public/sitemap-index.xml"
echo ""
echo "本地预览:"
echo "  hugo server --bind 0.0.0.0 --port 1313"
echo ""
