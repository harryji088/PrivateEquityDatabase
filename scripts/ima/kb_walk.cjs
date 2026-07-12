#!/usr/bin/env node
/**
 * kb_walk.cjs — 递归遍历点睛焱究所知识库某文件夹，输出所有"文件类"条目的 JSON。
 * 用法: node kb_walk.cjs <folder_id>
 * 输出: stdout 一个 JSON 数组 [{path,title,media_id,kind}]，kind ∈ {file,note}
 *
 * 关键点(踩过的坑):
 *  - 子文件夹的 media_type === 99，其 id 在 `media_id` 字段(不是 folder_id)，递归时用它下钻。
 *  - 分页用 data.is_end 判断结束(不是 has_more)，游标字段 data.next_cursor，limit ≤ 50。
 *  - 必须 export IMA_SKILL_VERSION 否则 API 返回 -200 强制更新。
 */
const { execFileSync } = require('child_process');
const path = require('path');

const SKILL = process.env.IMA_SKILL_DIR || '/Users/harryji/.claude/skills/ima-skill';
const KB = process.env.IMA_KB_ID || 'fgp_0fLfUt99hoCcbsW1OPPXIrezZEstzWpniCHhNR8=';
process.env.IMA_SKILL_VERSION = process.env.IMA_SKILL_VERSION || '1.1.7';

function api(apiPath, body) {
  const out = execFileSync('node', [path.join(SKILL, 'ima_api.cjs'), apiPath, JSON.stringify(body)], {
    encoding: 'utf8', maxBuffer: 1 << 26, env: process.env,
  });
  return JSON.parse(out);
}

function listFolder(folderId) {
  let items = [], cursor = '';
  for (let guard = 0; guard < 30; guard++) {
    const r = api('openapi/wiki/v1/get_knowledge_list', {
      knowledge_base_id: KB, folder_id: folderId, cursor, limit: 50,
    });
    if (r.code !== 0) { console.error('ERR', folderId, r.code, r.msg); break; }
    items.push(...(r.data.knowledge_list || []));
    if (r.data.is_end || !r.data.next_cursor) break;
    cursor = r.data.next_cursor;
  }
  return items;
}

const isFolder = (it) => it.media_type === 99;          // 子文件夹标志
const isNote   = (it) => (it.media_id || '').startsWith('note_');

const results = [];
function walk(folderId, prefix) {
  for (const it of listFolder(folderId)) {
    if (isFolder(it)) {
      walk(it.media_id, prefix + it.title + '/');       // 子文件夹 id 在 media_id
    } else {
      results.push({ path: prefix, title: it.title, media_id: it.media_id, kind: isNote(it) ? 'note' : 'file' });
    }
  }
}

const root = process.argv[2];
if (!root) { console.error('用法: node kb_walk.cjs <folder_id>'); process.exit(1); }
walk(root, '');
process.stdout.write(JSON.stringify(results, null, 0));
