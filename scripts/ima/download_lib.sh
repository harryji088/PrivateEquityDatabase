#!/usr/bin/env bash

ima_download_one() {
  local media_id="$1" title="$2" target="$3" temp_dir="$4"
  local response api_code api_msg url tmp magic

  response=$(node "$IMA_SKILL_DIR/ima_api.cjs" \
    "openapi/wiki/v1/get_media_info" \
    "{\"media_id\":\"$media_id\"}") || {
      echo "下载链接请求失败: $title" >&2
      return 1
    }
  api_code=$(printf '%s' "$response" | node -e \
    'const d=JSON.parse(require("fs").readFileSync(0,"utf8"));process.stdout.write(String(d.code ?? ""))')
  api_msg=$(printf '%s' "$response" | node -e \
    'const d=JSON.parse(require("fs").readFileSync(0,"utf8"));process.stdout.write(String(d.msg ?? ""))')
  if [ "$api_code" != "0" ]; then
    echo "IMA 返回错误 ${api_code}：${api_msg}（${title}）" >&2
    return 1
  fi
  url=$(printf '%s' "$response" | node -e \
    'const d=JSON.parse(require("fs").readFileSync(0,"utf8"));process.stdout.write(d.data?.url_info?.url || "")')
  if [ -z "$url" ]; then
    echo "IMA 未返回下载链接: $title" >&2
    return 1
  fi

  mkdir -p "$(dirname "$target")"
  tmp="$temp_dir/download.part"
  rm -f "$tmp"
  if ! curl -sL --fail --max-time 300 -o "$tmp" "$url"; then
    echo "文件下载失败: $title" >&2
    return 1
  fi

  case "${title##*.}" in
    pdf|PDF)
      magic=$(head -c 4 "$tmp")
      [ "$magic" = "%PDF" ] || { echo "PDF 签名校验失败: $title" >&2; return 1; }
      ;;
    xlsx|XLSX|docx|DOCX|pptx|PPTX)
      magic=$(head -c 2 "$tmp")
      [ "$magic" = "PK" ] || { echo "Office ZIP 签名校验失败: $title" >&2; return 1; }
      ;;
    *)
      [ -s "$tmp" ] || { echo "下载文件为空: $title" >&2; return 1; }
      ;;
  esac

  mv "$tmp" "$target"
  echo "OK: $title"
}
