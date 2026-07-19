#!/bin/bash
# 分批构建脚本：将 20 语种拆分为 4 批，依次构建后合并到 public 目录
# 解决 Hugo 0.164.0 在 macOS 上构建 110K 页面的性能瓶颈
#
# 用法:
#   bash scripts/batch_build.sh
#
# 预计耗时: 40-60 分钟（4 批 × 10-15 分钟/批）

set -e

cd "$(dirname "$0")/.."
PROJECT_ROOT="$(pwd)"
PUBLIC_DIR="${PROJECT_ROOT}/public"
TMP_DIR="${PROJECT_ROOT}/.hugo_batch_tmp"

echo "============================================================"
echo "AI Tools Pricing Hub — 批量构建（4 批 × 5 语种）"
echo "Project root: ${PROJECT_ROOT}"
echo "Time: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "============================================================"

# 清理之前的构建产物
echo ""
echo "[0/6] 清理之前的构建产物..."
rm -rf "${PUBLIC_DIR}" "${TMP_DIR}"
mkdir -p "${TMP_DIR}" "${PUBLIC_DIR}"

# 批次定义：每批 5 个语种
BATCHES=(
    "en zh es fr de"
    "ja ko pt ru it"
    "ar nl pl tr vi"
    "th id sv no da"
)

# 生成批次配置文件的函数
generate_batch_config() {
    local batch_num=$1
    local langs=$2
    local config_file="${TMP_DIR}/hugo_batch_${batch_num}.toml"

    # 复制原始配置
    cp "${PROJECT_ROOT}/hugo.toml" "${config_file}"

    # 删除所有 languages 配置
    # 使用 Python 处理 TOML 更可靠
    python3 << PYEOF
import re

with open("${config_file}", "r", encoding="utf-8") as f:
    content = f.read()

# 找到 [languages] 段落开始位置
langs_match = re.search(r'\[languages\]', content)
if not langs_match:
    print("ERROR: [languages] not found")
    exit(1)

before_langs = content[:langs_match.start()]

# 构建新的 languages 配置
langs_list = "${langs}".split()
new_langs = "[languages]\n"
lang_names = {
    "en": ("English", "en-us", "AI Tools Pricing", "Compare AI tools pricing, features and find the best deals."),
    "zh": ("中文", "zh-cn", "AI工具价格对比", "对比AI工具价格、功能,寻找最佳优惠。"),
    "es": ("Español", "es-es", "Precios de Herramientas IA", ""),
    "fr": ("Français", "fr-fr", "Prix des Outils IA", ""),
    "de": ("Deutsch", "de-de", "KI-Tools Preise", ""),
    "ja": ("日本語", "ja-jp", "AIツール価格比較", ""),
    "ko": ("한국어", "ko-kr", "AI도구 가격비교", ""),
    "pt": ("Português", "pt-pt", "Preços de Ferramentas IA", ""),
    "ru": ("Русский", "ru-ru", "Цены на ИИ-инструменты", ""),
    "it": ("Italiano", "it-it", "Prezzi Strumenti IA", ""),
    "ar": ("العربية", "ar-sa", "أسعار أدوات الذكاء الاصطناعي", ""),
    "nl": ("Nederlands", "nl-nl", "AI-tools Prijzen", ""),
    "pl": ("Polski", "pl-pl", "Ceny Narzędzi AI", ""),
    "tr": ("Türkçe", "tr-tr", "AI Araçları Fiyatları", ""),
    "vi": ("Tiếng Việt", "vi-vn", "Giá Công cụ AI", ""),
    "th": ("ไทย", "th-th", "ราคาเครื่องมือ AI", ""),
    "id": ("Indonesia", "id-id", "Harga Alat AI", ""),
    "sv": ("Svenska", "sv-se", "AI-verktyg Priser", ""),
    "no": ("Norsk", "nb-no", "AI-verktøy Priser", ""),
    "da": ("Dansk", "da-dk", "AI-værktøjer Priser", ""),
}

for i, lang in enumerate(langs_list, 1):
    if lang not in lang_names:
        print(f"WARNING: lang {lang} not in lang_names")
        continue
    name, code, title, desc = lang_names[lang]
    new_langs += f'\n  [languages.{lang}]\n'
    new_langs += f'    languageName = "{name}"\n'
    new_langs += f'    languageCode = "{code}"\n'
    new_langs += f'    weight = {i}\n'
    new_langs += f'    title = "{title}"\n'
    if desc:
        new_langs += f'    [languages.{lang}.params]\n'
        new_langs += f'      description = "{desc}"\n'
    if lang == "ar":
        if f'[languages.{lang}.params]' not in new_langs:
            new_langs += f'    [languages.{lang}.params]\n'
        new_langs += f'      rtl = true\n'

with open("${config_file}", "w", encoding="utf-8") as f:
    f.write(before_langs + new_langs + "\n")

print(f"  生成批次 ${batch_num} 配置: ${langs_list}")
PYEOF
}

# 依次构建每批
TOTAL_BATCHES=${#BATCHES[@]}
for i in "${!BATCHES[@]}"; do
    batch_num=$((i + 1))
    langs="${BATCHES[$i]}"
    batch_public="${TMP_DIR}/public_batch_${batch_num}"

    echo ""
    echo "[$batch_num/$TOTAL_BATCHES] 构建批次 $batch_num: $langs"
    echo "  时间: $(date -u +%H:%M:%S)"

    # 生成批次配置
    generate_batch_config "$batch_num" "$langs"

    # 构建
    echo "  启动 Hugo 构建..."
    time hugo --config "${TMP_DIR}/hugo_batch_${batch_num}.toml" \
         --minify \
         --baseURL "https://pricing.ai-term-hub.com/" \
         --destination "${batch_public}" \
         --logLevel error \
         --noChmod \
         --noTimes \
         --printPathWarnings=false \
         --printUnusedTemplates=false

    # 统计本批 HTML 数
    html_count=$(find "${batch_public}" -name "*.html" 2>/dev/null | wc -l | tr -d ' ')
    echo "  本批 HTML 数: ${html_count}"

    # 合并到主 public 目录
    echo "  合并到 public/..."
    if [ "$batch_num" -eq 1 ]; then
        # 第一批：直接移动
        cp -R "${batch_public}/"* "${PUBLIC_DIR}/"
    else
        # 后续批：合并（保留已有的 index.html、404.html、robots.txt 等）
        # 先合并语种目录
        for lang in $langs; do
            if [ -d "${batch_public}/${lang}" ]; then
                cp -R "${batch_public}/${lang}" "${PUBLIC_DIR}/"
            fi
        done
        # 合并 sitemap（后续覆盖）
        if [ -f "${batch_public}/sitemap.xml" ]; then
            cp "${batch_public}/sitemap.xml" "${TMP_DIR}/sitemap_batch_${batch_num}.xml"
        fi
    fi

    # 清理本批临时目录（保留 sitemap 备份）
    rm -rf "${batch_public}"

    echo "  批次 $batch_num 完成"
done

# 生成统一 sitemap
echo ""
echo "[5/6] 生成统一 sitemap..."
python3 "${PROJECT_ROOT}/scripts/generate_sitemap.py" --output "${PUBLIC_DIR}/" || echo "  ⚠️  sitemap 生成失败（非阻塞）"

# 统计最终 HTML 数
echo ""
echo "[6/6] 最终统计"
final_html=$(find "${PUBLIC_DIR}" -name "*.html" 2>/dev/null | wc -l | tr -d ' ')
echo "  总 HTML 数: ${final_html}"
echo "  预期: ~110,800"

# 清理临时目录
rm -rf "${TMP_DIR}"

echo ""
echo "============================================================"
echo "✅ 批量构建完成！"
echo "  完成时间: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "  总 HTML: ${final_html}"
echo "  输出目录: ${PUBLIC_DIR}"
echo "============================================================"
