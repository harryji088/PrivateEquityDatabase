#!/usr/bin/env node

/**
 * 按“远端相对路径 + 文件名”比对远端清单与本地目录。
 * 输出 JSON；目录错误不会被同名文件掩盖。
 */
const fs = require('fs');
const path = require('path');

const [remoteFile, localDir] = process.argv.slice(2);
if (!remoteFile || !localDir) {
  process.stderr.write('用法: node kb_compare.cjs <remote-json> <local-dir>\n');
  process.exit(2);
}
if (!fs.existsSync(localDir) || !fs.statSync(localDir).isDirectory()) {
  process.stderr.write(`本地模块目录不存在，拒绝自动创建: ${localDir}\n`);
  process.exit(2);
}

const raw = JSON.parse(fs.readFileSync(remoteFile, 'utf8'));
const remote = Array.isArray(raw) ? raw : raw.files;
if (!Array.isArray(remote)) {
  throw new Error('远端清单格式错误：需要数组或含 files 数组的缓存对象');
}

const normalize = (value) => value.replace(/\s+/gu, '').toLowerCase();
const localByRel = new Map();
const localByBase = new Map();
let localCount = 0;

function walkLocal(dir, prefix = '') {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (entry.name.startsWith('.')) continue;
    const abs = path.join(dir, entry.name);
    const rel = prefix ? path.posix.join(prefix, entry.name) : entry.name;
    if (entry.isDirectory()) {
      walkLocal(abs, rel);
    } else if (entry.isFile()) {
      localCount += 1;
      localByRel.set(normalize(rel), rel);
      const key = normalize(entry.name);
      if (!localByBase.has(key)) localByBase.set(key, []);
      localByBase.get(key).push(rel);
    }
  }
}
walkLocal(localDir);

function safeRemoteRel(item) {
  const title = String(item.title || '');
  const remotePath = String(item.path || '').replaceAll('\\', '/');
  if (!title || title.includes('/') || title.includes('\\') || title.includes('\0')) {
    throw new Error(`非法远端标题: ${JSON.stringify(title)}`);
  }
  const rel = path.posix.normalize(path.posix.join(remotePath, title));
  if (path.posix.isAbsolute(rel) || rel === '..' || rel.startsWith('../')) {
    throw new Error(`非法远端相对路径: ${JSON.stringify(rel)}`);
  }
  return rel;
}

const seenRemote = new Set();
const missing = [];
const misplaced = [];
for (const item of remote) {
  const relPath = safeRemoteRel(item);
  const relKey = normalize(relPath);
  if (seenRemote.has(relKey)) {
    throw new Error(`远端清单存在重复相对路径: ${relPath}`);
  }
  seenRemote.add(relKey);
  if (localByRel.has(relKey)) continue;

  const record = {
    rel_path: relPath,
    title: item.title,
    media_id: item.media_id || '',
    kind: item.kind || 'file',
  };
  missing.push(record);
  const sameNames = localByBase.get(normalize(item.title)) || [];
  if (sameNames.length) {
    misplaced.push({ ...record, local_candidates: sameNames });
  }
}

process.stdout.write(JSON.stringify({
  remote_count: remote.length,
  local_count: localCount,
  missing_count: missing.length,
  misplaced_count: misplaced.length,
  missing,
  misplaced,
}));
