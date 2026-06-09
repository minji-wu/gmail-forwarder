# Gmail Forwarder

Search existing Gmail messages by subject, sender, and date window, then forward matching messages to another inbox.

This is a small local CLI tool. It connects only to Gmail IMAP and SMTP, stores no email contents, and keeps a local state file of forwarded IMAP UIDs so repeated runs do not forward the same messages again.

## What It Does

- Searches a source Gmail mailbox over IMAP.
- Supports subject, sender, since-date, before-date, and limit filters.
- Prints matching messages in dry-run mode.
- Forwards matching messages to a destination inbox over SMTP.
- Preserves the original message body and attachments in the forwarded email.
- Tracks forwarded Gmail UIDs in a local state file.

## Requirements

- Python 3.10 or newer.
- A Gmail account with 2-Step Verification enabled.
- A Gmail app password for the source account.
- IMAP enabled for the source Gmail account.

This tool does not use your normal Google password.

## Gmail App Password Setup

1. Open your Google Account security settings.
2. Enable 2-Step Verification if it is not already enabled.
3. Open App passwords.
4. Create an app password for mail access.
5. Copy the generated 16-character password.
6. Use that value as `FORWARD_SOURCE_APP_PASSWORD`.

If Gmail rejects the password, try removing spaces from the app password before pasting it into `.env`.

## Install

```bash
git clone https://github.com/minji-wu/gmail-forwarder.git
cd gmail-forwarder
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env`:

```env
FORWARD_SOURCE_USER=source@gmail.com
FORWARD_SOURCE_APP_PASSWORD=xxxx xxxx xxxx xxxx
FORWARD_DESTINATION_EMAIL=destination@gmail.com
```

## Dry Run

Always start with `--dry-run`.

```bash
python -m gmail_forwarder.cli \
  --subject "Payment confirmation" \
  --from "billing" \
  --since 01-Jan-2026 \
  --before 01-Feb-2026 \
  --dry-run
```

Dry-run mode prints the messages that would be forwarded but sends nothing.

## Forward Messages

After reviewing dry-run output, run the same command without `--dry-run`:

```bash
python -m gmail_forwarder.cli \
  --subject "Payment confirmation" \
  --from "billing" \
  --since 01-Jan-2026 \
  --before 01-Feb-2026
```

## CLI Options

```text
--subject              Subject substring to search for.
--from                 From header substring to search for.
--since                IMAP lower date bound, for example 01-Jan-2026.
--before               IMAP upper date bound, for example 01-Feb-2026.
--limit                Maximum number of new messages to forward.
--dry-run              Print matches without sending.
--state-file           Local JSON state file. Defaults to .gmail_forwarder_state.json.
--source-user          Source Gmail address. Usually configured in .env.
--source-password      Source Gmail app password. Usually configured in .env.
--destination-email    Destination inbox. Usually configured in .env.
```

Environment variables with matching names can also be set in `.env`; command-line flags override `.env` values.

## Safety Notes

- The tool does not delete, archive, label, or modify source emails.
- The tool does not upload credentials or email contents to any third-party server.
- Credentials are read from `.env` or environment variables.
- `.env` is ignored by Git.
- The state file stores only forwarded IMAP UIDs.

You can revoke the Gmail app password from your Google Account at any time.

## Development

```bash
python -m pytest
```
