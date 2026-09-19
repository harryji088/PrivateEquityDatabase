#!/usr/bin/env bash
# kb_sync.sh — 智能同步：缓存优先 walk → 全量比对 → 分批下载
#
# 用法:
#   scripts/ima/kb_sync.sh              仅对比，不下载（dry-run）
#   scripts/ima/kb_sync.sh --download N  下载最多 N 篇缺失文件
#   scripts/ima/kb_sync.sh --refresh     强制刷新所有模块的远端清单
#   scripts/ima/kb_sync.sh --module 6    只看指定模块
#
# 策略:
#   - 优先用本地缓存（<24h），避免消耗 get_knowledge_list 配额
#   - 缓存命中时 0 API 调用即可完成比对
#   - 下载走 get_media_info（独立限额 30次/天）
set -u

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
CACHE_DIR="$HERE/cache"
mkdir -p "$CACHE_DIR"

export IMA_SKILL_VERSION="${IMA_SKILL_VERSION:-1.1.10}"

# 模块定义: folder_id|label|local_dir
MODULES=(
  "folder_7352341586014294|1. 尽调报告（纯原创）|点睛焱究所/1. 尽调报告（纯原创）"
  "folder_7352341644738452|2. CTA和股票策略周报（纯原创）|点睛焱究所/2. CTA和股票策略周报（纯原创）"
  "folder_7352341971893409|3. 管理人与策略主题研究（纯原创）|点睛焱究所/3.管理人与策略主题研究（纯原创）"
  "folder_7352341879618812|4. 周度业绩排名更新及业绩点评|点睛焱究所/4. 周度业绩排名更新及业绩点评"
  "folder_7352342089331773|5. 管理人观点速递（信息整理与提炼）|点睛焱究所/5.管理人观点速递（信息整理与提炼）"
  "folder_7353058740684809|6. 重点管理人官方介绍材料|点睛焱究所/6.重点管理人官方介绍材料"
  "folder_7352342164831219|7. 他山之石（研报精粹优选&路演分享）|点睛焱究所/7. 他山之石（研报精粹优选&路演分享）"
  "folder_7361226648602134|8. 管理人直通车|点睛焱究所/8. 管理人直通车"
  "folder_7479537394794106|9. 基协备案证券私募情况周度更新|点睛焱究所/9. 基协备案证券私募情况周度更新"
)

REFRESH=false
DOWNLOAD=0
TARGET_MOD=""

args=(${@:+"$@"})
for ((idx=0; idx<${#args[@]}; idx++)); do
  a="${args[idx]}"
  case "$a" in
    --refresh) REFRESH=true ;;
    --download)
      idx=$((idx+1))
      nxt="${args[idx]:-0}"
      [[ "$nxt" =~ ^[0-9]+$ ]] && DOWNLOAD="$nxt"
      ;;
    --module)
      idx=$((idx+1))
      TARGET_MOD="${args[idx]:-}"
      ;;
  esac
done

echo "====== 点睛焱究所 智能同步 ======"
echo "模式: refresh=$REFRESH | download=$DOWNLOAD | module=${TARGET_MOD:-全部}"
echo ""

TOTAL_MISSING=0

for def in "${MODULES[@]}"; do
  IFS='|' read -r fid label local_dir <<< "$def"
  [ -n "$TARGET_MOD" ] && [[ "$label" != "$TARGET_MOD"* ]] && continue

  CACHE_FILE="$CACHE_DIR/${fid}.json"
  REMOTE_JSON="$(mktemp)"

  # Get remote list
  if $REFRESH || [ ! -f "$CACHE_FILE" ]; then
    echo "  [$label] 🌐 从 API 拉取..."
    node "$HERE/kb_walk.cjs" --cache "$fid" > "$REMOTE_JSON" 2>/dev/null || true
    if [ ! -s "$REMOTE_JSON" ] || [ "$(cat "$REMOTE_JSON")" = "[]" ]; then
      # API 失败 → 回退缓存
      if [ -f "$CACHE_FILE" ]; then
        python3 -c "import json; d=json.load(open('$CACHE_FILE')); print(json.dumps(d['files']))" > "$REMOTE_JSON" 2>/dev/null
        echo "  [$label] ⚠️ API 失败，使用缓存"
      else
        echo "  [$label] ❌ 无缓存且 API 不可用"
        continue
      fi
    fi
  else
    python3 -c "import json; d=json.load(open('$CACHE_FILE')); print(json.dumps(d['files']))" > "$REMOTE_JSON" 2>/dev/null
    age=$(python3 -c "import json,datetime; d=json.load(open('$CACHE_FILE')); delta=datetime.date.today()-datetime.date.fromisoformat(d['cached_at']); print(delta.days)" 2>/dev/null)
    echo "  [$label] 📦 缓存 (${age}d ago)"
  fi

  # Compare
  result=$(python3 -c "
import json, os, re, sys
def norm(s):
    return re.sub(r'\s+', '', s).lower()
remote = json.load(open('$REMOTE_JSON'))
local_dir = os.path.join('$ROOT', '$local_dir')
local_set = set()
if os.path.isdir(local_dir):
    for root, dirs, files in os.walk(local_dir):
        for f in files:
            if not f.startswith('.'):
                local_set.add(norm(f))
missing = []
for item in remote:
    if norm(item.get('title','')) not in local_set:
        missing.append(item.get('title','') + '\t' + item.get('media_id','') + '\t' + item.get('kind','file'))
print(f'{len(remote)}\t{len(local_set)}\t{len(missing)}')
for m in missing:
    print(m)
" 2>/dev/null)

  remote_n=$(echo "$result" | head -1 | cut -f1)
  local_n=$(echo "$result" | head -1 | cut -f2)
  miss_n=$(echo "$result" | head -1 | cut -f3)

  if [ "$miss_n" = "0" ]; then
    echo "  [$label] ✅ $remote_n = $local_n"
  else
    echo "  [$label] ⚠️ 远端 $remote_n | 本地 $local_n | 缺 $miss_n"
    echo "$result" | tail -n +2 | while IFS=$'\t' read -r title media_id kind; do
      [ -z "$title" ] && continue
      tag=""
      [ "$kind" = "note" ] && tag=" [笔记-不可下]"
      echo "      - $title$tag"
    done
    TOTAL_MISSING=$((TOTAL_MISSING + miss_n))
  fi
  echo ""

  # Cleanup
  rm -f "$REMOTE_JSON"
done

echo "====== 总计缺失: $TOTAL_MISSING 篇 ======"

if [ "$DOWNLOAD" -gt 0 ] && [ "$TOTAL_MISSING" -gt 0 ]; then
  echo ""
  echo "⚠️  批量下载功能请使用 kb_download.sh --from-cache"
  echo "   例: scripts/ima/kb_download.sh folder_7353058740684809 \"点睛焱究所/6.重点管理人官方介绍材料\" $DOWNLOAD --from-cache"
fi
