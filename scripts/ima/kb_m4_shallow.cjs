#!/usr/bin/env node

/** 只列模块 4“周度业绩”顶层，不递归历史目录。 */
const { execFileSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const SKILL = process.env.IMA_SKILL_DIR || '/Users/harryji/.claude/skills/ima-skill';
const KB = process.env.IMA_KB_ID || 'fgp_0fLfUt99hoCcbsW1OPPXIrezZEstzWpniCHhNR8=';
const WEEKLY_FOLDER = 'folder_7354341090423503';
process.env.IMA_SKILL_VERSION = process.env.IMA_SKILL_VERSION || '1.1.10';

const args = process.argv.slice(2);
const useCache = args.includes('--cache');
const force = args.includes('--force');
const cacheFile = path.join(__dirname, 'cache', `${WEEKLY_FOLDER}.top.json`);

function api(apiPath, body) {
  const out = execFileSync('node', [path.join(SKILL, 'ima_api.cjs'), apiPath, JSON.stringify(body)], {
    encoding: 'utf8', maxBuffer: 1 << 24, env: process.env,
  });
  const response = JSON.parse(out);
  if (response.code !== 0) {
    throw new Error(`IMA ${response.code}: ${response.msg || 'unknown error'}`);
  }
  return response.data;
}

if (useCache && !force && fs.existsSync(cacheFile)) {
  const cached = JSON.parse(fs.readFileSync(cacheFile, 'utf8'));
  const ageMs = Date.now() - new Date(cached.cached_at).getTime();
  if (Number.isFinite(ageMs) && ageMs < 24 * 3600 * 1000) {
    process.stderr.write(`(M4 top cache ${(ageMs / 3600000).toFixed(1)}h old)\n`);
    process.stdout.write(JSON.stringify(cached.folders));
    process.exit(0);
  }
}

const folders = [];
let cursor = '';
for (let guard = 0; guard < 10; guard += 1) {
  const data = api('openapi/wiki/v1/get_knowledge_list', {
    knowledge_base_id: KB,
    folder_id: WEEKLY_FOLDER,
    cursor,
    limit: 50,
  });
  for (const item of data.knowledge_list || []) {
    if (item.media_type === 99) folders.push({ title: item.title, media_id: item.media_id });
  }
  if (data.is_end || !data.next_cursor) break;
  cursor = data.next_cursor;
}

if (useCache) {
  fs.mkdirSync(path.dirname(cacheFile), { recursive: true });
  fs.writeFileSync(cacheFile, JSON.stringify({
    cached_at: new Date().toISOString(),
    folders,
  }, null, 2));
}
process.stdout.write(JSON.stringify(folders));
