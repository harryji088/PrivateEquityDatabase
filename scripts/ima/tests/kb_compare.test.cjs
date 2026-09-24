const assert = require('node:assert/strict');
const { execFileSync, spawnSync } = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');

const compareScript = path.resolve(__dirname, '..', 'kb_compare.cjs');

function fixture(remote, localFiles) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'ima-compare-'));
  const localDir = path.join(root, 'local');
  fs.mkdirSync(localDir);
  for (const rel of localFiles) {
    const target = path.join(localDir, rel);
    fs.mkdirSync(path.dirname(target), { recursive: true });
    fs.writeFileSync(target, 'fixture');
  }
  const remoteFile = path.join(root, 'remote.json');
  fs.writeFileSync(remoteFile, JSON.stringify(remote));
  return {
    root,
    localDir,
    remoteFile,
    run() {
      return JSON.parse(execFileSync('node', [compareScript, remoteFile, localDir], { encoding: 'utf8' }));
    },
  };
}

test('同一相对路径的文件识别为已存在', (t) => {
  const f = fixture([
    { path: '子目录/', title: '报告.xlsx', media_id: 'x', kind: 'file' },
  ], ['子目录/报告.xlsx']);
  t.after(() => fs.rmSync(f.root, { recursive: true, force: true }));
  const result = f.run();
  assert.equal(result.missing_count, 0);
  assert.equal(result.misplaced_count, 0);
});

test('同名文件位于模块根目录时识别为错位', (t) => {
  const f = fixture([
    { path: '子目录/', title: '报告.xlsx', media_id: 'x', kind: 'file' },
  ], ['报告.xlsx']);
  t.after(() => fs.rmSync(f.root, { recursive: true, force: true }));
  const result = f.run();
  assert.equal(result.missing_count, 1);
  assert.equal(result.misplaced_count, 1);
  assert.deepEqual(result.misplaced[0].local_candidates, ['报告.xlsx']);
});

test('拒绝越界远端路径', (t) => {
  const f = fixture([
    { path: '../../', title: '报告.xlsx', media_id: 'x', kind: 'file' },
  ], []);
  t.after(() => fs.rmSync(f.root, { recursive: true, force: true }));
  const result = spawnSync('node', [compareScript, f.remoteFile, f.localDir], { encoding: 'utf8' });
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /非法远端相对路径/);
});
