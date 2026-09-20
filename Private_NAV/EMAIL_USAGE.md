# 163 邮箱发送

`smtp_163.py` 不依赖第三方库。先在 163 邮箱网页端的「设置 → POP3/SMTP/IMAP」开启 SMTP 服务，并新建客户端授权密码。授权密码不是网页登录密码。

将 `.env.example` 的 5 个变量填入项目根目录 `.env`；也可以创建此目录下的 `.env`，或通过 `--env-file` 指向任意 `.env` 文件。`.env` 已被仓库忽略，不会提交。

先执行一次不发信预览：

```bash
python3 smtp_163.py \
  --to recipient@example.com \
  --subject '净值文件已更新' \
  --body '附件为最新净值数据。' \
  --attachment output/新增净值_YYYYMMDD_HHMMSS.xlsx \
  --dry-run
```

确认无误后删除 `--dry-run` 即可实际发送。多个收件人可重复传入 `--to`，或用逗号分隔；`--cc` 和 `--bcc` 的规则相同。

```bash
python3 smtp_163.py \
  --to first@example.com,second@example.com \
  --cc colleague@example.com \
  --subject '净值文件已更新' \
  --body-file mail_body.txt \
  --attachment output/新增净值_YYYYMMDD_HHMMSS.xlsx
```

常见故障：认证失败通常表示使用了登录密码、授权码失效，或尚未开启 SMTP 服务。网络超时或连接被拒绝时，先检查本地网络是否允许连接 `smtp.163.com:465`。
