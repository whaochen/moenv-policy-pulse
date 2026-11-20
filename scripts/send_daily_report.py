#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import os
import re
import smtplib
import subprocess
import sys
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
from zoneinfo import ZoneInfo


LINK_RE = re.compile(r"\[([^\]]+)\]\(<([^>]+)>\)")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send the MOENV daily news report by SMTP.")
    parser.add_argument("--vault", type=Path, default=Path("."), help="Obsidian vault folder.")
    parser.add_argument("--timezone", default="Asia/Taipei", help="Timezone for freshness checks.")
    parser.add_argument(
        "--run-update-if-stale",
        action="store_true",
        help="Run the incremental daily report first if latest.json is missing or not from today.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Send even if last_sent.json says this subject was already sent today.",
    )
    return parser.parse_args()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def generated_date(payload: dict, tz: ZoneInfo) -> str:
    generated_at = payload.get("generated_at")
    if not generated_at:
        return ""
    return datetime.fromisoformat(generated_at).astimezone(tz).date().isoformat()


def latest_is_today(vault: Path, tz: ZoneInfo) -> bool:
    latest_json = vault / "資料" / "daily_update_reports" / "latest.json"
    if not latest_json.exists():
        return False
    payload = load_json(latest_json)
    return generated_date(payload, tz) == datetime.now(tz).date().isoformat()


def run_daily_update(vault: Path) -> None:
    script = vault / "scripts" / "moenv_news_indexer.py"
    command = [
        sys.executable,
        str(script),
        "--incremental",
        "--daily-report",
        "--progress-every",
        "5",
        "--use-curl",
    ]
    subprocess.run(command, cwd=vault, check=True)


def markdown_to_html(body: str) -> str:
    escaped_lines: list[str] = []
    for line in body.splitlines():
        parts: list[str] = []
        last = 0
        for match in LINK_RE.finditer(line):
            parts.append(html.escape(line[last : match.start()]))
            parts.append(
                f'<a href="{html.escape(match.group(2), quote=True)}">'
                f"{html.escape(match.group(1))}</a>"
            )
            last = match.end()
        parts.append(html.escape(line[last:]))
        escaped_lines.append("".join(parts))
    return "<html><body><pre style=\"font-family: system-ui, sans-serif; white-space: pre-wrap;\">" + "\n".join(
        escaped_lines
    ) + "</pre></body></html>"


def smtp_config() -> dict:
    username = os.environ.get("SMTP_USERNAME", "").strip()
    password = os.environ.get("SMTP_PASSWORD", "").strip()
    mail_to = os.environ.get("MAIL_TO", "").strip()
    host = (os.environ.get("SMTP_HOST") or "smtp.gmail.com").strip()
    port = int(os.environ.get("SMTP_PORT") or "587")
    mail_from = (os.environ.get("MAIL_FROM") or username).strip()

    missing = [
        name
        for name, value in {
            "SMTP_USERNAME": username,
            "SMTP_PASSWORD": password,
            "MAIL_TO": mail_to,
            "MAIL_FROM": mail_from,
        }.items()
        if not value
    ]
    if missing:
        raise RuntimeError("Missing required mail settings: " + ", ".join(missing))

    return {
        "host": host,
        "port": port,
        "username": username,
        "password": password,
        "from": mail_from,
        "to": mail_to,
    }


def already_sent(vault: Path, payload: dict, mail_to: str, tz: ZoneInfo) -> bool:
    marker = vault / "資料" / "daily_update_reports" / "last_sent.json"
    if not marker.exists():
        return False
    try:
        sent = load_json(marker)
    except json.JSONDecodeError:
        return False
    today = datetime.now(tz).date().isoformat()
    sent_at = sent.get("sent_at", "")
    sent_date = sent_at[:10] if sent_at else ""
    return (
        sent_date == today
        and sent.get("to") == mail_to
        and sent.get("subject") == payload.get("subject")
        and sent.get("body_file") == payload.get("body_file")
    )


def write_sent_marker(vault: Path, payload: dict, mail_to: str, tz: ZoneInfo) -> None:
    marker = vault / "資料" / "daily_update_reports" / "last_sent.json"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(
        json.dumps(
            {
                "sent_at": datetime.now(tz).isoformat(timespec="seconds"),
                "to": mail_to,
                "subject": payload.get("subject", ""),
                "body_file": payload.get("body_file", ""),
                "report_date": payload.get("report_date", ""),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def send_mail(config: dict, subject: str, body: str) -> None:
    message = EmailMessage()
    message["From"] = config["from"]
    message["To"] = config["to"]
    message["Subject"] = subject
    message.set_content(body)
    message.add_alternative(markdown_to_html(body), subtype="html")

    with smtplib.SMTP(config["host"], config["port"], timeout=30) as smtp:
        smtp.starttls()
        smtp.login(config["username"], config["password"])
        smtp.send_message(message)


def main() -> int:
    args = parse_args()
    vault = args.vault.resolve()
    tz = ZoneInfo(args.timezone)

    if args.run_update_if_stale and not latest_is_today(vault, tz):
        run_daily_update(vault)

    report_dir = vault / "資料" / "daily_update_reports"
    latest_json = report_dir / "latest.json"
    if not latest_json.exists():
        raise RuntimeError("Daily report is missing. Run the daily update first.")

    payload = load_json(latest_json)
    if generated_date(payload, tz) != datetime.now(tz).date().isoformat():
        raise RuntimeError("Daily report is stale. Use --run-update-if-stale or run the updater first.")

    body_file = Path(payload.get("body_file", ""))
    if not body_file.is_absolute():
        body_file = vault / body_file
    if not body_file.exists():
        body_file = report_dir / body_file.name
    if not body_file.exists():
        body_file = report_dir / "latest.md"
    body = body_file.read_text(encoding="utf-8")
    config = smtp_config()

    if not args.force and already_sent(vault, payload, config["to"], tz):
        print("Daily report already sent; skipping.")
        return 0

    send_mail(config, payload["subject"], body)
    write_sent_marker(vault, payload, config["to"], tz)
    print(f"Sent daily report to {config['to']}: {payload['subject']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
