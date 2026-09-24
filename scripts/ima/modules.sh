#!/usr/bin/env bash

# 点睛焱究所模块的唯一映射来源。
# 格式: module_no|folder_id|label|local_dir|mode
IMA_MODULES=(
  "1|folder_7352341586014294|1. 尽调报告（纯原创）|点睛焱究所/1. 尽调报告（纯原创）|recursive"
  "2|folder_7352341644738452|2. CTA和股票策略周报（纯原创）|点睛焱究所/2. CTA和股票策略周报（纯原创）|recursive"
  "3|folder_7352341971893409|3. 管理人与策略主题研究（纯原创）|点睛焱究所/3.管理人与策略主题研究（纯原创）|recursive"
  "4|folder_7352341879618812|4. 周度业绩排名更新及业绩点评|点睛焱究所/4. 周度业绩排名更新及业绩点评|m4-shallow"
  "5|folder_7352342089331773|5. 管理人观点速递（信息整理与提炼）|点睛焱究所/5.管理人观点速递（信息整理与提炼）|recursive"
  "6|folder_7353058740684809|6. 重点管理人官方介绍材料|点睛焱究所/6.重点管理人官方介绍材料|recursive"
  "7|folder_7352342164831219|7. 他山之石（研报精粹优选&路演分享）|点睛焱究所/7. 他山之石（研报精粹优选&路演分享）|recursive"
  "8|folder_7361226648602134|8. 管理人直通车|点睛焱究所/8. 管理人直通车|recursive"
  "9|folder_7479537394794106|9. 基协备案证券私募情况周度更新|点睛焱究所/9. 基协备案证券私募情况周度更新|recursive"
)

ima_resolve_module() {
  local wanted="$1" row
  for row in "${IMA_MODULES[@]}"; do
    IFS='|' read -r IMA_MODULE_NO IMA_FOLDER_ID IMA_LABEL IMA_LOCAL_DIR IMA_MODE <<< "$row"
    if [ "$IMA_MODULE_NO" = "$wanted" ]; then
      export IMA_MODULE_NO IMA_FOLDER_ID IMA_LABEL IMA_LOCAL_DIR IMA_MODE
      return 0
    fi
  done
  return 1
}
