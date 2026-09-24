# scripts/ima — 点睛焱究所知识库下载工具

从点睛焱究所 IMA 知识库(`fgp_0fLfUt99hoCcbsW1OPPXIrezZEstzWpniCHhNR8=`)遍历、比对、下载文件到本地
`点睛焱究所/` 目录。进度与清单见项目根 `点睛.md`。

## 前置条件

- **IMA skill**: `~/.claude/skills/ima-skill/ima_api.cjs`(副本在 `~/.workbuddy/skills-marketplace/skills/ima-skills/`)
- **凭证**: `~/.config/ima/client_id` 与 `~/.config/ima/api_key`(脚本自动读取，勿提交到 git)
- **node** + **curl**
- 环境变量 `IMA_SKILL_VERSION=1.1.10`(脚本已内置默认值，缺了会被 API 以 `-200 强制更新` 拒绝)

可选覆盖：`IMA_SKILL_DIR`、`IMA_KB_ID`。

## 用法

```bash
# 先比对；默认使用缓存，不下载
scripts/ima/kb_sync.sh
scripts/ima/kb_sync.sh --module 6

# 刷新远端清单；M4 自动改走浅层检查
scripts/ima/kb_sync.sh --refresh

# 非 M4：先预览，再显式 apply
scripts/ima/kb_download.sh --module 6 --from-cache
scripts/ima/kb_download.sh --module 6 --from-cache --apply

# M4：指定新周，先预览，再显式 apply
scripts/ima/kb_download_m4.sh --week 0921-0925
scripts/ima/kb_download_m4.sh --week 0921-0925 --apply
```

模块编号、folder_id 与本地规范目录统一维护在 `modules.sh`。下载脚本不再接受手工目录参数，也不会自动创建模块根目录。

## 已知坑(都已在脚本里处理)

- **子文件夹**: `media_type === 99`，其 id 在 `media_id` 字段(非 `folder_id`)，递归用它下钻。
- **分页**: 用 `data.is_end` 判断结束(不是 has_more)，游标 `data.next_cursor`，limit ≤ 50。
- **路径比对**: 以“远端相对路径 + 文件名”比对；只在相同相对目录内做去空格归一化。同名文件位于错误目录时会中止，不再把错位文件当成已存在。
- **下载**: `get_media_info` 返回的 `data.url_info.url` 已带签名，纯 `curl -sL` 即可，无需附加 headers。签名URL有时效，跨天需重新遍历。
- **笔记**: `media_type=11`(media_id `note_` 开头)无下载链接；且他人创建的笔记 notes API 报 `210005 not author`，无法导出，只能在 IMA 客户端手动复制。
- **目录安全**: 模块目录只能来自 `modules.sh`；规范目录不存在会立即失败，绝不 `mkdir -p` 一个近似目录。缺失文件超过 10 个时，`--apply` 还需追加 `--allow-large`。
- **失败即停**: `get_media_info` 的进程错误和业务错误都会显示原始错误码并立即停止，不再吞掉错误后继续消耗配额。
- **文件签名**: PDF 校验 `%PDF`，xlsx/docx/pptx 校验 `PK`。
- **限流（两个接口，各有频率 + 日限额两层，都会耗尽）**:
  - `get_knowledge_list`（遍历清单）:
    - 频率限制 `200001`「请求频率超限」：短时密集请求触发，等约 60s 恢复（`kb_walk.cjs` 已内置 5/15/25/35s 退避重试）。
    - 日限额 `220021`「资料获取次数已达上限，请明天再尝试」：**会耗尽**！全量刷新多模块 / 多子文件夹（尤其模块4历史归档树）极易触发，**跨天才重置**。⇒ **优先用 <24h 缓存，按需只刷必要模块，避免反复 `--force`**。
  - `get_media_info`（取下载链接）: 日限额 `220021`，每日 **30 次**，跨天重置。
