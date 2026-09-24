#!/usr/bin/env node
/**
 * kb_walk.cjs — 递归遍历点睛焱究所知识库某文件夹，输出所有"文件类"条目的 JSON。
 * 用法: node kb_walk.cjs <folder_id> [--cache] [--force]
 *
 *   --cache     结果持久化到 scripts/ima/cache/<folder_id>.json
 *   --force     忽略缓存，强制从 API 重新拉取（与 --cache 配合）
 *   (无参数)    输出 stdout 一个 JSON 数组 [{path,title,media_id,kind}]
 *
 * 关键点(踩过的坑):
 *  - 子文件夹的 media_type === 99，其 id 在 `media_id` 字段(不是 folder_id)，递归时用它下钻。
 *  - 分页用 data.is_end 判断结束(不是 has_more)，游标字段 data.next_cursor，limit ≤ 50。
 *  - 必须 export IMA_SKILL_VERSION 否则 API 返回 -200 强制更新。
 */
const { execFileSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const SKILL = process.env.IMA_SKILL_DIR || '/Users/harryji/.claude/skills/ima-skill';
const KB = process.env.IMA_KB_ID || 'fgp_0fLfUt99hoCcbsW1OPPXIrezZEstzWpniCHhNR8=';
process.env.IMA_SKILL_VERSION = process.env.IMA_SKILL_VERSION || '1.1.10';

// Parse args: folder_id is the one that doesn't start with --
const args = process.argv.slice(2);
const USE_CACHE = args.includes('--cache');
const FORCE = args.includes('--force');
const root = args.find(a => !a.startsWith('--'));
if (!root) { console.error('用法: node kb_walk.cjs <folder_id> [--cache] [--force]'); process.exit(1); }

const HERE = __dirname;
const CACHE_DIR = path.join(HERE, 'cache');

function api(apiPath, body) {
  const out = execFileSync('node', [path.join(SKILL, 'ima_api.cjs'), apiPath, JSON.stringify(body)], {
    encoding: 'utf8', maxBuffer: 1 << 26, env: process.env,
  });
  return JSON.parse(out);
}

// 同步 sleep（毫秒）：用于请求间隔防频率超限、以及 200001 限流退避重试
function sleepMs(ms) {
  execFileSync('sleep', [String(ms / 1000)]);
}

function listFolder(folderId) {
  let items = [], cursor = '';
  for (let guard = 0; guard < 30; guard++) {
    let r;
    // 200001 频率限流 → 退避重试（5/15/25/35s），不轻易放弃子文件夹
    for (let attempt = 0; attempt < 4; attempt++) {
      r = api('openapi/wiki/v1/get_knowledge_list', {
        knowledge_base_id: KB, folder_id: folderId, cursor, limit: 50,
      });
      if (r.code === 0) break;
      if (r.code === 200001) {
        const wait = 5 + attempt * 10;
        process.stderr.write(`(频率限流 ${folderId}，等 ${wait}s 重试 ${attempt + 1}/4)\n`);
        sleepMs(wait * 1000);
        continue;
      }
      break; // 其他错误不重试
    }
    if (!r || r.code !== 0) {
      throw new Error(`IMA ${r && r.code}: ${(r && r.msg) || 'unknown error'} (${folderId})`);
    }
    items.push(...(r.data.knowledge_list || []));
    if (r.data.is_end || !r.data.next_cursor) break;
    cursor = r.data.next_cursor;
    sleepMs(300); // 请求间隔 0.3s，避免递归遍历时密集触发频率限制
  }
  return items;
}

const isFolder = (it) => it.media_type === 99;
const isNote   = (it) => (it.media_id || '').startsWith('note_');

function doWalk(folderId) {
  const results = [];
  function walk(fid, prefix) {
    for (const it of listFolder(fid)) {
      if (isFolder(it)) {
        walk(it.media_id, prefix + it.title + '/');
      } else {
        results.push({ path: prefix, title: it.title, media_id: it.media_id, kind: isNote(it) ? 'note' : 'file' });
      }
    }
  }
  walk(folderId, '');
  return results;
}

// --cache 模式：优先读缓存
if (USE_CACHE) {
  const cacheFile = path.join(CACHE_DIR, `${root}.json`);
  if (!FORCE && fs.existsSync(cacheFile)) {
    try {
      const cached = JSON.parse(fs.readFileSync(cacheFile, 'utf8'));
      const ageH = (Date.now() - new Date(cached.cached_at).getTime()) / 3600000;
      if (ageH < 24) {
        process.stderr.write(`(cache ${ageH.toFixed(1)}h old, ${cached.file_count} files)\n`);
        process.stdout.write(JSON.stringify(cached.files, null, 0));
        process.exit(0);
      }
    } catch (e) { /* stale cache, refetch */ }
  }

  // Fetch from API
  process.stderr.write(`>> 遍历远端 ${root} ...\n`);
  let results;
  try {
    results = doWalk(root);
  } catch (error) {
    if (!FORCE && fs.existsSync(cacheFile)) {
      try {
        const cached = JSON.parse(fs.readFileSync(cacheFile, 'utf8'));
        process.stderr.write(`(API 失败，回退缓存: ${cached.file_count} files；${error.message})\n`);
        process.stdout.write(JSON.stringify(cached.files, null, 0));
        process.exit(0);
      } catch (cacheError) {
        // 继续走统一失败出口。
      }
    }
    process.stderr.write(`${error.message}\n`);
    process.stdout.write('[]');
    process.exit(1);
  }
  if (results.length === 0) {
    // API failed → try stale cache as fallback
    if (!FORCE && fs.existsSync(cacheFile)) {
      try {
        const cached = JSON.parse(fs.readFileSync(cacheFile, 'utf8'));
        process.stderr.write(`(API 失败，回退缓存: ${cached.file_count} files)\n`);
        process.stdout.write(JSON.stringify(cached.files, null, 0));
        process.exit(0);
      } catch (e) {}
    }
    process.stderr.write('API 失败且无可用缓存\n');
    process.stdout.write('[]');
    process.exit(1);
  }

  // Save to cache
  fs.mkdirSync(CACHE_DIR, { recursive: true });
  const meta = {
    folder_id: root,
    file_count: results.length,
    cached_at: new Date().toISOString(),
    files: results,
  };
  fs.writeFileSync(cacheFile, JSON.stringify(meta, null, 2), 'utf8');
  process.stderr.write(`(已缓存 ${results.length} files -> ${cacheFile})\n`);
  process.stdout.write(JSON.stringify(results, null, 0));
} else {
  // 纯遍历模式（向后兼容）
  const results = doWalk(root);
  process.stdout.write(JSON.stringify(results, null, 0));
}
