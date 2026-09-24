#!/usr/bin/env bash
# 安全下载非 M4 模块：固定模块目录、保留远端相对路径、默认仅预览。
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
CACHE_DIR="$HERE/cache"
source "$HERE/modules.sh"
source "$HERE/download_lib.sh"

export IMA_SKILL_VERSION="${IMA_SKILL_VERSION:-1.1.10}"
export IMA_SKILL_DIR="${IMA_SKILL_DIR:-/Users/harryji/.claude/skills/ima-skill}"

usage() {
  cat <<'EOF'
用法:
  scripts/ima/kb_download.sh --module <1-9> [--from-cache] [--limit N] [--apply] [--allow-large]

默认只输出下载计划；只有显式传入 --apply 才会下载。
模块 4 必须使用 kb_download_m4.sh，禁止走通用递归下载。
EOF
}

MODULE=""
LIMIT=100000
FROM_CACHE=false
APPLY=false
ALLOW_LARGE=false
while [ "$#" -gt 0 ]; do
  case "$1" in
    --module)
      [ "$#" -ge 2 ] || { usage >&2; exit 2; }
      MODULE="$2"; shift 2 ;;
    --limit)
      [ "$#" -ge 2 ] || { usage >&2; exit 2; }
      LIMIT="$2"; shift 2 ;;
    --from-cache) FROM_CACHE=true; shift ;;
    --apply) APPLY=true; shift ;;
    --allow-large) ALLOW_LARGE=true; shift ;;
    -h|--help) usage; exit 0 ;;
    *)
      echo "不再接受手工 folder_id 或目标目录参数: $1" >&2
      usage >&2
      exit 2 ;;
  esac
done

[[ "$MODULE" =~ ^[1-9]$ ]] || { echo "--module 必须是 1-9" >&2; exit 2; }
[[ "$LIMIT" =~ ^[0-9]+$ ]] || { echo "--limit 必须是非负整数" >&2; exit 2; }
ima_resolve_module "$MODULE" || { echo "未知模块: $MODULE" >&2; exit 2; }
if [ "$IMA_MODE" != "recursive" ]; then
  echo "模块 4 使用专用浅层流程：scripts/ima/kb_download_m4.sh --week MMDD-MMDD" >&2
  exit 2
fi

DEST="$ROOT/$IMA_LOCAL_DIR"
if [ ! -d "$DEST" ]; then
  echo "规范模块目录不存在，拒绝自动创建: $DEST" >&2
  exit 2
fi

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
CACHE_FILE="$CACHE_DIR/${IMA_FOLDER_ID}.json"

if $FROM_CACHE; then
  [ -f "$CACHE_FILE" ] || { echo "缓存不存在: $CACHE_FILE" >&2; exit 1; }
  node -e 'const d=require(process.argv[1]);process.stdout.write(JSON.stringify(d.files))' \
    "$CACHE_FILE" > "$TMP/remote.json"
else
  node "$HERE/kb_walk.cjs" --cache --force "$IMA_FOLDER_ID" > "$TMP/remote.json"
fi

node "$HERE/kb_compare.cjs" "$TMP/remote.json" "$DEST" > "$TMP/plan.json"
remote_n=$(node -e 'const d=require(process.argv[1]);process.stdout.write(String(d.remote_count))' "$TMP/plan.json")
local_n=$(node -e 'const d=require(process.argv[1]);process.stdout.write(String(d.local_count))' "$TMP/plan.json")
missing_n=$(node -e 'const d=require(process.argv[1]);process.stdout.write(String(d.missing_count))' "$TMP/plan.json")
misplaced_n=$(node -e 'const d=require(process.argv[1]);process.stdout.write(String(d.misplaced_count))' "$TMP/plan.json")

echo "[$IMA_LABEL] 远端 $remote_n | 本地 $local_n | 缺 $missing_n"
if [ "$misplaced_n" -gt 0 ]; then
  echo "发现同名文件位于错误相对目录，拒绝下载：" >&2
  node -e '
    const d=require(process.argv[1]);
    for (const x of d.misplaced) {
      process.stderr.write(`- 应在 ${x.rel_path}\n  实在 ${x.local_candidates.join(", ")}\n`);
    }
  ' "$TMP/plan.json"
  exit 3
fi

node -e '
  const d=require(process.argv[1]);
  for (const x of d.missing) process.stdout.write(`- ${x.rel_path}${x.kind === "note" ? " [笔记-不可下]" : ""}\n`);
' "$TMP/plan.json"

if [ "$missing_n" -eq 0 ]; then
  echo "无需下载。"
  exit 0
fi
if ! $APPLY; then
  echo "DRY-RUN：未下载。确认后追加 --apply。"
  exit 0
fi

file_missing_n=$(node -e '
  const d=require(process.argv[1]);
  process.stdout.write(String(d.missing.filter(x => x.kind !== "note").length));
' "$TMP/plan.json")
if [ "$file_missing_n" -gt 10 ] && ! $ALLOW_LARGE; then
  echo "计划下载 $file_missing_n 个文件，超过安全阈值 10；请先核对，确认后追加 --allow-large。" >&2
  exit 3
fi

node -e '
  const d=require(process.argv[1]);
  for (const x of d.missing) {
    if (x.kind === "note") continue;
    process.stdout.write(`${x.rel_path}\t${x.media_id}\t${x.title}\n`);
  }
' "$TMP/plan.json" > "$TMP/download.tsv"

downloaded=0
while IFS=$'\t' read -r rel_path media_id title; do
  [ -n "$rel_path" ] || continue
  [ "$downloaded" -lt "$LIMIT" ] || break
  target="$DEST/$rel_path"
  [ ! -e "$target" ] || { echo "目标已存在，停止避免覆盖: $target" >&2; exit 1; }
  ima_download_one "$media_id" "$title" "$target" "$TMP"
  downloaded=$((downloaded + 1))
done < "$TMP/download.tsv"

echo "完成：下载 $downloaded 个文件。"
