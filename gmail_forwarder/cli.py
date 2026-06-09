from __future__ import annotations

import argparse
import os
from pathlib import Path

from dotenv import load_dotenv

from gmail_forwarder.forwarder import forward_existing_messages


def parse_args() -> argparse.Namespace:
    load_dotenv(override=False)

    parser = argparse.ArgumentParser(
        description="Search existing Gmail messages and forward matching messages to another inbox."
    )
    parser.add_argument("--subject", default=os.environ.get("FORWARD_SUBJECT"))
    parser.add_argument("--from", dest="from_filter", default=os.environ.get("FORWARD_FROM"))
    parser.add_argument("--since", default=os.environ.get("FORWARD_SINCE"))
    parser.add_argument("--before", default=os.environ.get("FORWARD_BEFORE"))
    parser.add_argument(
        "--limit",
        type=int,
        default=int(os.environ["FORWARD_LIMIT"]) if os.environ.get("FORWARD_LIMIT") else None,
    )
    parser.add_argument("--dry-run", action="store_true", default=os.environ.get("FORWARD_DRY_RUN") == "1")
    parser.add_argument(
        "--state-file",
        default=os.environ.get("FORWARD_STATE_FILE", ".gmail_forwarder_state.json"),
    )
    parser.add_argument("--source-user", default=os.environ.get("FORWARD_SOURCE_USER"))
    parser.add_argument("--source-password", default=os.environ.get("FORWARD_SOURCE_APP_PASSWORD"))
    parser.add_argument("--destination-email", default=os.environ.get("FORWARD_DESTINATION_EMAIL"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if not args.source_user or not args.source_password:
        raise SystemExit(
            "Missing source Gmail credentials. Set FORWARD_SOURCE_USER and "
            "FORWARD_SOURCE_APP_PASSWORD in .env or the shell environment."
        )
    if not args.destination_email:
        raise SystemExit("Missing destination email. Set FORWARD_DESTINATION_EMAIL in .env or the shell environment.")

    forward_existing_messages(
        source_user=args.source_user,
        source_password=args.source_password,
        destination_email=args.destination_email,
        subject_filter=args.subject,
        from_filter=args.from_filter,
        since=args.since,
        before=args.before,
        state_file=Path(args.state_file),
        limit=args.limit,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
