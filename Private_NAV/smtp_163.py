"""通过 163 邮箱 SMTP 发送纯文本邮件及附件的独立模块。

使用前在项目根目录的 .env 中设置 MAIL_USER、MAIL_PASSWORD；其中
MAIL_PASSWORD 必须是 163 邮箱的客户端授权密码，而不是网页登录密码。
"""

from __future__ import annotations

import argparse
import mimetypes
import os
import smtplib
import ssl
import sys
from email.message import EmailMessage
from pathlib import Path
from typing import Iterable, List, Optional, Sequence


DEFAULT_SMTP_HOST = "smtp.163.com"
DEFAULT_SMTP_PORT = 465


def load_dotenv(env_file: Path) -> None:
    """加载简单的 KEY=VALUE 格式 .env 文件，已存在的环境变量优先。"""
    if not env_file.is_file():
        return

    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].lstrip()

        key, separator, value = line.partition("=")
        key = key.strip()
        if not separator or not key or key in os.environ:
            continue

        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        os.environ[key] = value


def find_project_env() -> Optional[Path]:
    """从本文件向上寻找项目的 .env；不读取 .env.example。"""
    for directory in Path(__file__).resolve().parents:
        candidate = directory / ".env"
        if candidate.is_file():
            return candidate
    return None


def configure_environment(env_file: Optional[Path] = None) -> None:
    """按需加载 .env，且不覆盖已显式导出的环境变量。"""
    target = env_file or find_project_env()
    if target is not None:
        load_dotenv(target)


def _require_setting(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError("缺少环境变量 {}".format(name))
    return value


def _split_addresses(addresses: Iterable[str]) -> List[str]:
    result: List[str] = []
    for address in addresses:
        result.extend(item.strip() for item in address.split(",") if item.strip())
    if not result:
        raise ValueError("至少需要一个收件人")
    return result


def build_message(
    sender: str,
    to: Sequence[str],
    cc: Sequence[str],
    subject: str,
    body: str,
    attachments: Sequence[Path] = (),
) -> EmailMessage:
    """构造 MIME 邮件；密送收件人应仅在发送时传入，不能放进头部。"""
    message = EmailMessage()
    message["From"] = sender
    message["To"] = ", ".join(to)
    if cc:
        message["Cc"] = ", ".join(cc)
    message["Subject"] = subject
    message.set_content(body)

    for attachment in attachments:
        if not attachment.is_file():
            raise FileNotFoundError("附件不存在: {}".format(attachment))
        mime_type, _ = mimetypes.guess_type(str(attachment))
        maintype, subtype = (mime_type or "application/octet-stream").split("/", 1)
        message.add_attachment(
            attachment.read_bytes(),
            maintype=maintype,
            subtype=subtype,
            filename=attachment.name,
        )
    return message


def send_via_163(
    message: EmailMessage,
    recipients: Sequence[str],
    sender: Optional[str] = None,
) -> None:
    """通过 SSL SMTP 将已构造的邮件发出。"""
    user = _require_setting("MAIL_USER")
    password = _require_setting("MAIL_PASSWORD")
    host = os.environ.get("MAIL_HOST", DEFAULT_SMTP_HOST).strip() or DEFAULT_SMTP_HOST
    port = int(os.environ.get("MAIL_PORT", str(DEFAULT_SMTP_PORT)))

    try:
        with smtplib.SMTP_SSL(host, port, context=ssl.create_default_context(), timeout=20) as smtp:
            smtp.login(user, password)
            smtp.send_message(message, from_addr=sender or user, to_addrs=list(recipients))
    except smtplib.SMTPAuthenticationError as exc:
        raise RuntimeError("SMTP 认证失败：请确认使用的是客户端授权密码，并已开启 SMTP 服务") from exc


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="用 163 邮箱 SMTP 发送邮件")
    parser.add_argument("--to", action="append", required=True, help="收件人；可重复或用逗号分隔")
    parser.add_argument("--cc", action="append", default=[], help="抄送人；可重复或用逗号分隔")
    parser.add_argument("--bcc", action="append", default=[], help="密送人；可重复或用逗号分隔")
    parser.add_argument("--subject", required=True, help="邮件主题")
    body_group = parser.add_mutually_exclusive_group(required=True)
    body_group.add_argument("--body", help="纯文本正文")
    body_group.add_argument("--body-file", type=Path, help="UTF-8 编码的正文文件")
    parser.add_argument("--attachment", type=Path, action="append", default=[], help="附件路径；可重复")
    parser.add_argument("--env-file", type=Path, help="指定 .env 路径，默认自动寻找项目根目录 .env")
    parser.add_argument("--dry-run", action="store_true", help="只校验并预览，不建立网络连接或发送")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        configure_environment(args.env_file)
        to = _split_addresses(args.to)
        cc = _split_addresses(args.cc) if args.cc else []
        bcc = _split_addresses(args.bcc) if args.bcc else []
        body = args.body if args.body is not None else args.body_file.read_text(encoding="utf-8")
        sender = os.environ.get("MAIL_FROM") or os.environ.get("MAIL_USER") or "unconfigured@163.com"
        message = build_message(sender, to, cc, args.subject, body, args.attachment)
        recipients = to + cc + bcc

        if args.dry_run:
            print("预览成功：收件人 {} 位，抄送 {} 位，密送 {} 位，附件 {} 个；未发送。".format(
                len(to), len(cc), len(bcc), len(args.attachment)
            ))
            return 0

        send_via_163(message, recipients, sender)
        print("邮件已提交至 SMTP 服务器：收件人 {} 位，抄送 {} 位，密送 {} 位。".format(
            len(to), len(cc), len(bcc)
        ))
        return 0
    except (OSError, RuntimeError, ValueError, smtplib.SMTPException) as exc:
        print("发送失败：{}".format(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
