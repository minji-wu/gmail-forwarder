from __future__ import annotations

import email
from email import policy
from email.header import decode_header
from email.message import EmailMessage
from email.utils import formatdate, make_msgid, parsedate_to_datetime
import html as html_lib
import imaplib
import json
from pathlib import Path
import re
import smtplib
from typing import Iterable, Optional, Sequence, Set, Tuple


GMAIL_IMAP_HOST = "imap.gmail.com"
GMAIL_SMTP_HOST = "smtp.gmail.com"
GMAIL_SMTP_SSL_PORT = 465


def decode_mime_words(value: str | None) -> str:
    if not value:
        return ""
    return "".join(
        chunk.decode(encoding or "utf8") if isinstance(chunk, bytes) else chunk
        for chunk, encoding in decode_header(value)
    )


def quote_imap_search_value(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', r"\"")
    return f'"{escaped}"'


def build_search_tokens(
    since: Optional[str],
    before: Optional[str],
    subject: Optional[str] = None,
    sender: Optional[str] = None,
) -> Sequence[str]:
    tokens = ["ALL"]
    if since:
        tokens.extend(["SINCE", since])
    if before:
        tokens.extend(["BEFORE", before])
    if sender:
        tokens.extend(["FROM", quote_imap_search_value(sender)])
    if subject:
        tokens.extend(["SUBJECT", quote_imap_search_value(subject)])
    return tokens


def normalize_subject_filter(subject: Optional[str]) -> Optional[str]:
    if not subject:
        return None
    match = re.search(r'SUBJECT\s+"([^"]+)"', subject, flags=re.IGNORECASE)
    if match:
        return match.group(1)
    return subject


def select_all_mailbox(mail: imaplib.IMAP4_SSL) -> None:
    candidates = [
        '"[Gmail]/All Mail"',
        "All Mail",
        '"[Google Mail]/All Mail"',
        "INBOX",
    ]
    for mailbox in candidates:
        status, _ = mail.select(mailbox)
        if status == "OK":
            print(f"MAILBOX: {mailbox}")
            return
    raise RuntimeError("Could not select a Gmail mailbox to scan")


def load_state(path: Path) -> Set[str]:
    if not path.exists():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return {str(item) for item in data}
    except Exception:
        pass
    return set()


def save_state(path: Path, forwarded_uids: Set[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(sorted(forwarded_uids), indent=2),
        encoding="utf-8",
    )


def extract_text_body(message: email.message.Message) -> Tuple[str, Optional[str]]:
    plain_part = message.get_body(preferencelist=("plain",))
    html_part = message.get_body(preferencelist=("html",))

    plain_body = plain_part.get_content() if plain_part else ""
    html_body = html_part.get_content() if html_part else None
    return plain_body, html_body


def gather_attachments(message: email.message.Message) -> Iterable[email.message.Message]:
    for part in message.iter_attachments():
        if part.get_content_maintype() == "multipart":
            continue
        yield part


def format_forward_text(
    source_from: str,
    source_subject: str,
    source_date: str,
    plain_body: str,
) -> str:
    lines = [
        "Forwarded message",
        f"From: {source_from or 'Unknown'}",
        f"Date: {source_date or 'Unknown'}",
        f"Subject: {source_subject or 'No Subject'}",
        "",
        plain_body.strip() or "(no text body found)",
    ]
    return "\n".join(lines)


def format_forward_html(
    source_from: str,
    source_subject: str,
    source_date: str,
    html_body: Optional[str],
    plain_body: str,
) -> str:
    escaped_from = html_lib.escape(source_from or "Unknown")
    escaped_subject = html_lib.escape(source_subject or "No Subject")
    escaped_date = html_lib.escape(source_date or "Unknown")
    if html_body:
        body_block = html_body
    else:
        body_block = f"<pre>{html_lib.escape(plain_body.strip() or '(no text body found)')}</pre>"

    return f"""\
<html>
  <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;">
    <div style="padding: 12px 0 16px; border-bottom: 1px solid #e5e7eb; margin-bottom: 16px;">
      <div><strong>Forwarded message</strong></div>
      <div><strong>From:</strong> {escaped_from}</div>
      <div><strong>Date:</strong> {escaped_date}</div>
      <div><strong>Subject:</strong> {escaped_subject}</div>
    </div>
    <div>{body_block}</div>
  </body>
</html>
"""


def build_forward_message(
    source_message: email.message.Message,
    source_user: str,
    destination_email: str,
    source_message_id: str,
) -> EmailMessage:
    source_subject = decode_mime_words(source_message.get("Subject", ""))
    source_from = decode_mime_words(source_message.get("From", ""))
    raw_date = source_message.get("Date", "")
    try:
        source_date = parsedate_to_datetime(raw_date).astimezone().strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        source_date = raw_date

    plain_body, html_body = extract_text_body(source_message)
    message = EmailMessage()
    message["From"] = source_user
    message["To"] = destination_email
    message["Subject"] = f"Fwd: {source_subject}" if source_subject else "Fwd:"
    message["Date"] = formatdate(localtime=True)
    message["Message-ID"] = make_msgid()
    message["X-Forwarded-From"] = source_from
    message["X-Forwarded-Date"] = source_date
    message["X-Forwarded-Subject"] = source_subject
    message["X-Forwarded-Message-ID"] = source_message_id

    message.set_content(format_forward_text(source_from, source_subject, source_date, plain_body))
    message.add_alternative(
        format_forward_html(source_from, source_subject, source_date, html_body, plain_body),
        subtype="html",
    )

    for part in gather_attachments(source_message):
        content_type = part.get_content_type()
        maintype, subtype = content_type.split("/", 1)
        content = part.get_content()
        if isinstance(content, str):
            charset = part.get_content_charset() or "utf-8"
            content = content.encode(charset, errors="replace")

        filename = part.get_filename()
        content_id = part.get("Content-ID")
        disposition = part.get_content_disposition() or "attachment"
        kwargs = {
            "maintype": maintype,
            "subtype": subtype,
            "disposition": disposition,
        }
        if filename:
            kwargs["filename"] = filename
        if content_id:
            kwargs["cid"] = content_id.strip("<>")
        message.add_attachment(content, **kwargs)

    return message


def forward_existing_messages(
    source_user: str,
    source_password: str,
    destination_email: str,
    subject_filter: Optional[str],
    from_filter: Optional[str],
    since: Optional[str],
    before: Optional[str],
    state_file: Path,
    limit: Optional[int] = None,
    dry_run: bool = False,
) -> None:
    forwarded = load_state(state_file)
    subject_filter = normalize_subject_filter(subject_filter)
    search_tokens = build_search_tokens(since, before, subject_filter, from_filter)

    print("CONNECTING: Gmail IMAP")
    mail = imaplib.IMAP4_SSL(GMAIL_IMAP_HOST)
    mail.login(source_user, source_password)
    select_all_mailbox(mail)

    print(
        "SCANNING: "
        f"subject={subject_filter!r} "
        f"from={from_filter!r} "
        f"since={since!r} "
        f"before={before!r}"
    )
    status, data = mail.search(None, *search_tokens)
    if status != "OK":
        raise RuntimeError(f"IMAP search failed: {status}")
    seq_nums = [seq.decode("ascii") for seq in data[0].split() if seq]
    print(f"RESULTS: {len(seq_nums)} message(s) matched before dedupe")

    if not seq_nums:
        mail.logout()
        return

    smtp = None
    try:
        if not dry_run:
            smtp = smtplib.SMTP_SSL(GMAIL_SMTP_HOST, GMAIL_SMTP_SSL_PORT)
            smtp.login(source_user, source_password)

        forwarded_count = 0
        for index, seq in enumerate(seq_nums, start=1):
            status, msg_data = mail.fetch(seq, "(UID RFC822)")
            if status != "OK" or not msg_data or not msg_data[0]:
                print(f"  WARNING: could not fetch message {seq}")
                continue

            response_meta = msg_data[0][0]
            raw_email = msg_data[0][1]
            original = email.message_from_bytes(raw_email, policy=policy.default)
            uid = None
            if isinstance(response_meta, bytes):
                meta_text = response_meta.decode("utf-8", errors="ignore")
            else:
                meta_text = str(response_meta)
            uid_match = re.search(r"\bUID\s+(\d+)\b", meta_text)
            if uid_match:
                uid = uid_match.group(1)
            if not uid:
                uid = seq
            if uid in forwarded:
                print(f"  [{index}/{len(seq_nums)}] Skipping UID {uid} (already forwarded)")
                continue

            subject = decode_mime_words(original.get("Subject", ""))
            raw_date = original.get("Date", "")
            try:
                msg_date = parsedate_to_datetime(raw_date).astimezone().strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                msg_date = raw_date or "Unknown"

            if limit is not None and forwarded_count >= limit:
                break

            source_message_id = original.get("Message-ID", "")
            forward_message = build_forward_message(original, source_user, destination_email, source_message_id)

            action_prefix = "WOULD FORWARD" if dry_run else "Forwarding"
            print(f"  [{index}/{len(seq_nums)}] {action_prefix} UID {uid} | {msg_date} | {subject!r}")

            if not dry_run:
                smtp.send_message(forward_message)
                forwarded.add(uid)
                save_state(state_file, forwarded)
            forwarded_count += 1

        if dry_run:
            print("DRY RUN: no messages were sent")
    finally:
        if smtp is not None:
            smtp.quit()
        mail.logout()
