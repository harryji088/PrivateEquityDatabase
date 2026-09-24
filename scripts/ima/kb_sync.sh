#!/usr/bin/env bash
# 安全比对入口：M4 只浅层检查，其余模块按完整相对路径比对。
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
CACHE_DIR="$HERE/cache"
source "$HERE/modules.sh"

export IMA_SKILL_VERSION="${IMA_SKILL_VERSION:-1.1.10}"
export IMA_SKILL_DIR="${IMA_SKILL_DIR:-/Users/harryji/.claude/skills/ima-skill}"

REFRESH=false
TARGET_MOD=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --refresh) REFRESH=true; shift ;;
    --module) [ "$#" -ge 2 ] || exit 2; TARGET_MOD="$2"; shift 2 ;;
    --download)
      echo "--download 已移除；请先 dry-run，再用 kb_download.sh --module N --apply。" >&2
      exit 2 ;;
    -h|--help)
      echo "用法: scripts/ima/kb_sync.sh [--refresh] [--module 1-9]"
      exit 0 ;;
    *) echo "未知参数: $1" >&2; exit 2 ;;
  esac
done
[ -z "$TARGET_MOD" ] || [[ "$TARGET_MOD" =~ ^[1-9]$ ]] || { echo "--module 必须是 1-9" >&2; exit 2; }

echo "====== 点睛焱究所安全同步 ======"
echo "模式: refresh=$REFRESH | module=${TARGET_MOD:-全部}"
echo ""

TOTAL_MISSING=0
for row in "${IMA_MODULES[@]}"; do
  IFS='|' read -r module_no fid label local_dir mode <<< "$row"
  [ -z "$TARGET_MOD" ] || [ "$module_no" = "$TARGET_MOD" ] || continue
  local_abs="$ROOT/$local_dir"
  [ -d "$local_abs" ] || { echo "[$label] ❌ 规范目录不存在: $local_abs" >&2; exit 2; }

  if [ "$mode" = "m4-shallow" ]; then
    temp_dir=$(mktemp -d)
    temp_weeks="$temp_dir/weeks.json"
    if $REFRESH; then
      node "$HERE/kb_m4_shallow.cjs" --cache --force > "$temp_weeks"
    else
      node "$HERE/kb_m4_shallow.cjs" --cache > "$temp_weeks"
    fi
    summary=$(node -e '
      const fs=require("fs"),path=require("path");
      const remote=require(process.argv[1]).filter(x=>/^\d{4}-\d{4}$/.test(x.title)).map(x=>x.title).sort();
      const root=process.argv[2], counts=new Map();
      function walk(d){for(const e of fs.readdirSync(d,{withFileTypes:true})){if(e.name.startsWith("."))continue;const p=path.join(d,e.name);if(e.isDirectory())walk(p);else{const m=e.name.match(/(\d{4}-\d{4})/);if(m)counts.set(m[1],(counts.get(m[1])||0)+1);}}}
      walk(root);
      const localWeeks=[...counts.keys()].sort();
      const latest=remote.at(-1)||"", localLatest=localWeeks.at(-1)||"";
      const missing=remote.filter(w=>w>localLatest);
      const latestCount=counts.get(latest)||0;
      const partial=latest===localLatest&&latestCount>0&&latestCount<3?[latest]:[];
      process.stdout.write(JSON.stringify({remote_count:remote.length,latest,local_latest:localLatest,missing,partial}));
    ' "$temp_weeks" "$local_abs")
    rm -rf "$temp_dir"
    latest=$(printf '%s' "$summary" | node -e 'const d=JSON.parse(require("fs").readFileSync(0,"utf8"));process.stdout.write(d.latest)')
    missing_n=$(printf '%s' "$summary" | node -e 'const d=JSON.parse(require("fs").readFileSync(0,"utf8"));process.stdout.write(String(d.missing.length))')
    partial_n=$(printf '%s' "$summary" | node -e 'const d=JSON.parse(require("fs").readFileSync(0,"utf8"));process.stdout.write(String(d.partial.length))')
    if [ "$missing_n" -eq 0 ] && [ "$partial_n" -eq 0 ]; then
      echo "[$label] ✅ 浅层检查，最新周 ${latest}，无缺周"
    else
      echo "[$label] ⚠️ 浅层检查，最新周 ${latest} | 缺周 $missing_n | 不完整周 $partial_n"
      printf '%s' "$summary" | node -e '
        const d=JSON.parse(require("fs").readFileSync(0,"utf8"));
        for(const w of d.missing) console.log(`  - 缺周 ${w}`);
        for(const w of d.partial) console.log(`  - 不完整周 ${w}`);
      '
      TOTAL_MISSING=$((TOTAL_MISSING + missing_n + partial_n))
    fi
    echo ""
    continue
  fi

  temp_dir=$(mktemp -d)
  temp_remote="$temp_dir/remote.json"
  temp_plan="$temp_dir/plan.json"
  cache_file="$CACHE_DIR/${fid}.json"
  if $REFRESH; then
    node "$HERE/kb_walk.cjs" --cache --force "$fid" > "$temp_remote"
  elif [ -f "$cache_file" ]; then
    node -e 'const d=require(process.argv[1]);process.stdout.write(JSON.stringify(d.files))' \
      "$cache_file" > "$temp_remote"
  else
    node "$HERE/kb_walk.cjs" --cache "$fid" > "$temp_remote"
  fi
  node "$HERE/kb_compare.cjs" "$temp_remote" "$local_abs" > "$temp_plan"

  remote_n=$(node -e 'const d=require(process.argv[1]);process.stdout.write(String(d.remote_count))' "$temp_plan")
  local_n=$(node -e 'const d=require(process.argv[1]);process.stdout.write(String(d.local_count))' "$temp_plan")
  missing_n=$(node -e 'const d=require(process.argv[1]);process.stdout.write(String(d.missing_count))' "$temp_plan")
  misplaced_n=$(node -e 'const d=require(process.argv[1]);process.stdout.write(String(d.misplaced_count))' "$temp_plan")
  if [ "$missing_n" -eq 0 ] && [ "$misplaced_n" -eq 0 ]; then
    echo "[$label] ✅ 远端 $remote_n | 本地 $local_n | 缺 0"
  else
    echo "[$label] ⚠️ 远端 $remote_n | 本地 $local_n | 缺 $missing_n | 错位 $misplaced_n"
    node -e '
      const d=require(process.argv[1]);
      for(const x of d.missing) console.log(`  - ${x.rel_path}${x.kind === "note" ? " [笔记-不可下]" : ""}`);
      for(const x of d.misplaced) console.log(`    错位候选: ${x.local_candidates.join(", ")}`);
    ' "$temp_plan"
    TOTAL_MISSING=$((TOTAL_MISSING + missing_n))
  fi
  rm -rf "$temp_dir"
  echo ""
done

echo "====== 总计缺失/不完整: $TOTAL_MISSING 项 ======"
