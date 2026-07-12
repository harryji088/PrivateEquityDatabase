# scripts/ima — 点睛焱究所知识库下载工具

从点睛焱究所 IMA 知识库(`fgp_0fLfUt99hoCcbsW1OPPXIrezZEstzWpniCHhNR8=`)遍历、比对、下载文件到本地
`点睛焱究所/` 目录。进度与清单见项目根 `点睛.md`。

## 前置条件

- **IMA skill**: `~/.claude/skills/ima-skill/ima_api.cjs`(副本在 `~/.workbuddy/skills-marketplace/skills/ima-skills/`)
- **凭证**: `~/.config/ima/client_id` 与 `~/.config/ima/api_key`(脚本自动读取，勿提交到 git)
- **node** + **curl**
- 环境变量 `IMA_SKILL_VERSION=1.1.7`(脚本已内置默认值，缺了会被 API 以 `-200 强制更新` 拒绝)

可选覆盖：`IMA_SKILL_DIR`、`IMA_KB_ID`。

## 用法

```bash
# 遍历某文件夹，输出全部文件清单(JSON)
node scripts/ima/kb_walk.cjs <folder_id>

# 下载某文件夹缺失文件到目标目录(相对项目根)。第3参可限制数量。
scripts/ima/kb_download.sh <folder_id> "点睛焱究所/<模块目录>" [N]
```

### 各模块 folder_id

| 模块 | folder_id |
|------|-----------|
| 1. 尽调报告 | `folder_7352341586014294` |
| 2. CTA和股票策略周报 | `folder_7352341644738452` |
| 3. 管理人与策略主题研究 | `folder_7352341971893409` |
| 4. 周度业绩排名 | `folder_7352341879618812`(子夹:周度`folder_7354341090423503` / 季度半年`folder_7354341044286731`) |
| 5. 管理人观点速递 | `folder_7352342089331773` |
| 6. 重点管理人官方介绍材料 | `folder_7353058740684809` |
| 7. 他山之石 | `folder_7352342164831219` |
| 8. 管理人直通车 | `folder_7361226648602134` |
| 9. 基协备案 | `folder_7479537394794106` |

### 示例

```bash
# 下模块2缺失的 CTA/股票策略周报
scripts/ima/kb_download.sh folder_7352341644738452 "点睛焱究所/2. CTA和股票策略周报（纯原创）"

# 只下 5 篇试跑
scripts/ima/kb_download.sh folder_7352341586014294 "点睛焱究所/1. 尽调报告（纯原创）" 5
```

## 已知坑(都已在脚本里处理)

- **子文件夹**: `media_type === 99`，其 id 在 `media_id` 字段(非 `folder_id`)，递归用它下钻。
- **分页**: 用 `data.is_end` 判断结束(不是 has_more)，游标 `data.next_cursor`，limit ≤ 50。
- **比对**: 远端阿尔法周报标题「周报 _」比本地「周报_」多一个空格 → 必须**去空格归一化**再比，否则误判缺失。
- **末行**: TSV 清单最后一行常无换行符，`while read` 会漏读 → 用 `sed '$a\'` 补。
- **下载**: `get_media_info` 返回的 `data.url_info.url` 已带签名，纯 `curl -sL` 即可，无需附加 headers。签名URL有时效，跨天需重新遍历。
- **笔记**: `media_type=11`(media_id `note_` 开头)无下载链接；且他人创建的笔记 notes API 报 `210005 not author`，无法导出，只能在 IMA 客户端手动复制。
