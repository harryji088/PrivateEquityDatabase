#!/usr/bin/env bash
# kb_download.sh — 从知识库某文件夹下载缺失的文件到本地目录。
#
# 用法:
#   scripts/ima/kb_download.sh <folder_id> "<目标目录>" [数量N] [--from-cache]
#
#   --from-cache  跳过 API walk，直接使用 scripts/ima/cache/<folder_id>.json
#                 缓存不存在时自动降级为 API walk
#
# 行为:
#   1. 获取远端文件清单（API walk 或缓存）
#   2. 与目标目录已有文件按"去空格归一化"比对，得出缺失清单
#   3. 逐个 get_media_info 取签名URL → curl 下载 → 校验 %PDF 魔数(仅.pdf)
#   4. note 类型(media_type=11)跳过(API 无下载链接)
#
# 依赖: node, curl；凭证在 ~/.config/ima/{client_id,api_key}
set -u

SKILL="${IMA_SKILL_DIR:-/Users/harryji/.claude/skills/ima-skill}"
export IMA_SKILL_VERSION="${IMA_SKILL_VERSION:-1.1.10}"
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
CACHE_DIR="$HERE/cache"

FID="${1:?需要 folder_id}"
DEST_IN="${2:?需要目标目录}"

# Parse optional args
N="100000"
FROM_CACHE=false
for a in "${@:3}"; do
  case "$a" in
    --from-cache) FROM_CACHE=true ;;
    ''|*[!0-9]*) ;;  # not a number
    *) N="$a" ;;
  esac
done

# 相对路径按项目根解析
case "$DEST_IN" in
  /*) DEST="$DEST_IN" ;;
  *)  DEST="$ROOT/$DEST_IN" ;;
esac
mkdir -p "$DEST"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# Step 1: 获取远端清单
CACHE_FILE="$CACHE_DIR/${FID}.json"
if $FROM_CACHE; then
  if [ -f "$CACHE_FILE" ]; then
    echo ">> 使用缓存: $CACHE_FILE"
    python3 -c "import json; d=json.load(open('$CACHE_FILE')); print(json.dumps(d['files']))" > "$TMP/remote.json" 2>/dev/null
    if [ ! -s "$TMP/remote.json" ]; then
      echo "缓存解析失败，降级为 API walk"
      FROM_CACHE=false
    fi
  else
    echo "缓存不存在，降级为 API walk"
    FROM_CACHE=false
  fi
fi

if ! $FROM_CACHE; then
  echo ">> 遍历远端 $FID ..."
  node "$HERE/kb_walk.cjs" --cache "$FID" > "$TMP/remote.json" || {
    # API 失败 → 尝试缓存回退
    if [ -f "$CACHE_FILE" ]; then
      echo ">> API 失败，回退缓存..."
      python3 -c "import json; d=json.load(open('$CACHE_FILE')); print(json.dumps(d['files']))" > "$TMP/remote.json" 2>/dev/null
    fi
    [ -s "$TMP/remote.json" ] || { echo "遍历失败且无缓存可用"; exit 1; }
  }
fi

# Step 2: 计算缺失清单(归一化去空格)，输出 title\tmedia_id\tkind
node -e '
const fs=require("fs"),path=require("path");
const dest=process.argv[1];
const norm=s=>s.replace(/\s+/g,"").replace(/\.pdf$/i,"").toLowerCase();
const remote=JSON.parse(fs.readFileSync(process.argv[2],"utf8"));
const local=new Set();
(function w(d){for(const e of fs.readdirSync(d,{withFileTypes:true})){if(e.name.startsWith("."))continue;const p=path.join(d,e.name);if(e.isDirectory())w(p);else local.add(norm(e.name));}})(dest);
const miss=remote.filter(r=>!local.has(norm(r.title)));
process.stderr.write(`远端 ${remote.length} | 本地 ${local.size} | 缺 ${miss.length}\n`);
process.stdout.write(miss.map(r=>r.title+"\t"+r.media_id+"\t"+r.kind+"\n").join(""));
' "$DEST" "$TMP/remote.json" > "$TMP/missing.tsv"

# Step 3: 下载
SKIPPED_COUNT=0
i=0; ok=0; fail=0; skip=0
# sed '$a\' 补末行换行，防止 while read 漏读最后一行
while IFS=$'\t' read -r title media_id kind; do
  [ -z "$title" ] && continue
  i=$((i+1)); [ "$i" -gt "$N" ] && break
  if [ "$kind" = "note" ]; then
    echo "[$i] SKIP(笔记,API不可下): $title"; skip=$((skip+1)); i=$((i-1)); continue
  fi
  target="$DEST/$title"
  [ -f "$target" ] && { echo "[$i] EXISTS: $title"; ok=$((ok+1)); continue; }
  url=$(node "$SKILL/ima_api.cjs" "openapi/wiki/v1/get_media_info" "{\"media_id\":\"$media_id\"}" 2>/dev/null \
        | node -e 'const d=JSON.parse(require("fs").readFileSync(0,"utf8"));process.stdout.write((d.data&&d.data.url_info&&d.data.url_info.url)||"")')
  [ -z "$url" ] && { echo "[$i] FAIL(无URL): $title"; fail=$((fail+1)); continue; }
  tmp="$target.part"
  curl -sL --fail --max-time 300 -o "$tmp" "$url" 2>/dev/null
  case "$title" in
    *.pdf) magic_ok=$([ -s "$tmp" ] && [ "$(head -c 4 "$tmp")" = "%PDF" ] && echo 1 || echo 0) ;;
    *)     magic_ok=$([ -s "$tmp" ] && echo 1 || echo 0) ;;  # 非pdf仅校验非空
  esac
  if [ "$magic_ok" = "1" ]; then
    mv "$tmp" "$target"; echo "[$i] OK($(du -h "$target"|cut -f1)): $title"; ok=$((ok+1))
  else
    rm -f "$tmp"; echo "[$i] FAIL(空/损坏): $title"; fail=$((fail+1))
  fi
done < "$TMP/missing.tsv"

echo "===== 完成: 成功/已存在 $ok, 失败 $fail, 跳过笔记 $skip ====="
