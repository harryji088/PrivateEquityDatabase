#!/usr/bin/env bash
# 模块 4 专用：只进入指定周文件夹，并按策略路由到 2026 的四个固定目录。
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
source "$HERE/modules.sh"
source "$HERE/download_lib.sh"

export IMA_SKILL_VERSION="${IMA_SKILL_VERSION:-1.1.10}"
export IMA_SKILL_DIR="${IMA_SKILL_DIR:-/Users/harryji/.claude/skills/ima-skill}"

WEEK=""
APPLY=false
FROM_CACHE=false
while [ "$#" -gt 0 ]; do
  case "$1" in
    --week) [ "$#" -ge 2 ] || exit 2; WEEK="$2"; shift 2 ;;
    --apply) APPLY=true; shift ;;
    --from-cache) FROM_CACHE=true; shift ;;
    -h|--help)
      echo "用法: scripts/ima/kb_download_m4.sh --week MMDD-MMDD [--from-cache] [--apply]"
      exit 0 ;;
    *) echo "未知参数: $1" >&2; exit 2 ;;
  esac
done
[[ "$WEEK" =~ ^[0-9]{4}-[0-9]{4}$ ]] || { echo "--week 格式必须为 MMDD-MMDD" >&2; exit 2; }

ima_resolve_module 4
DEST="$ROOT/$IMA_LOCAL_DIR"
[ -d "$DEST" ] || { echo "规范模块目录不存在: $DEST" >&2; exit 2; }
for strategy in 量化股票 CTA 主观多头 宏观; do
  [ -d "$DEST/周度业绩/2026/$strategy" ] || {
    echo "策略目录不存在，拒绝自动创建: $DEST/周度业绩/2026/$strategy" >&2
    exit 2
  }
done

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
if $FROM_CACHE; then
  node "$HERE/kb_m4_shallow.cjs" --cache > "$TMP/weeks.json"
else
  node "$HERE/kb_m4_shallow.cjs" --cache --force > "$TMP/weeks.json"
fi

week_folder_id=$(node -e '
  const rows=require(process.argv[1]);
  const row=rows.find(x => x.title === process.argv[2]);
  if (!row) process.exit(2);
  process.stdout.write(row.media_id);
' "$TMP/weeks.json" "$WEEK") || { echo "远端未找到周文件夹: $WEEK" >&2; exit 2; }

week_cache="$HERE/cache/${week_folder_id}.json"
if $FROM_CACHE && [ -f "$week_cache" ]; then
  node -e 'const d=require(process.argv[1]);process.stdout.write(JSON.stringify(d.files))' \
    "$week_cache" > "$TMP/remote.json"
else
  node "$HERE/kb_walk.cjs" --cache --force "$week_folder_id" > "$TMP/remote.json"
fi

node -e '
  const fs=require("fs");
  const rows=JSON.parse(fs.readFileSync(process.argv[1],"utf8"));
  const week=process.argv[2];
  const seen=new Set();
  const out=[];
  for (const x of rows) {
    if (x.kind === "note") throw new Error(`周文件夹出现笔记: ${x.title}`);
    if (!x.title.toLowerCase().endsWith(".xlsx")) throw new Error(`周文件不是 xlsx: ${x.title}`);
    let strategy="";
    if (x.title.includes("量化股票")) strategy="量化股票";
    else if (x.title.includes("量化+主观CTA")) strategy="CTA";
    else if (x.title.includes("主观多头")) strategy="主观多头";
    else if (x.title.includes("宏观")) strategy="宏观";
    else throw new Error(`无法识别策略: ${x.title}`);
    if (seen.has(strategy)) throw new Error(`同周策略重复: ${strategy}`);
    if (!x.title.includes(week)) throw new Error(`文件名与周不一致: ${x.title}`);
    seen.add(strategy);
    out.push({...x, strategy, rel_path:`周度业绩/2026/${strategy}/${x.title}`});
  }
  if (out.length < 3 || out.length > 4) throw new Error(`周文件数量异常: ${out.length}`);
  process.stdout.write(JSON.stringify(out));
' "$TMP/remote.json" "$WEEK" > "$TMP/plan.json"

planned=$(node -e 'const d=require(process.argv[1]);process.stdout.write(String(d.length))' "$TMP/plan.json")
echo "[M4 $WEEK] 远端 $planned 个策略文件"
node -e '
  const d=require(process.argv[1]);
  for (const x of d) process.stdout.write(`- ${x.rel_path}\n`);
' "$TMP/plan.json"

existing=0
while IFS= read -r rel_path; do
  if [ -e "$DEST/$rel_path" ]; then existing=$((existing + 1)); fi
done < <(node -e 'for(const x of require(process.argv[1])) console.log(x.rel_path)' "$TMP/plan.json")
if [ "$existing" -eq "$planned" ]; then
  echo "本周文件已全部存在，无需下载。"
  exit 0
fi
if [ "$existing" -gt 0 ]; then
  echo "本周仅部分文件存在（${existing}/${planned}），拒绝自动补写；请先人工核对。" >&2
  exit 3
fi
if ! $APPLY; then
  echo "DRY-RUN：未下载。确认后追加 --apply。"
  exit 0
fi

node -e '
  for(const x of require(process.argv[1])) {
    process.stdout.write(`${x.rel_path}\t${x.media_id}\t${x.title}\n`);
  }
' "$TMP/plan.json" > "$TMP/download.tsv"

i=0
while IFS=$'\t' read -r rel_path media_id title; do
  [ -n "$rel_path" ] || continue
  target="$DEST/$rel_path"
  [ ! -e "$target" ] || { echo "目标已存在，停止避免覆盖: $target" >&2; exit 1; }
  ima_download_one "$media_id" "$title" "$target" "$TMP"
  i=$((i + 1))
done < "$TMP/download.tsv"
echo "完成：M4 $WEEK 下载 $i 个文件。"
