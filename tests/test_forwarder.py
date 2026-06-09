from gmail_forwarder.forwarder import (
    build_search_tokens,
    normalize_subject_filter,
    quote_imap_search_value,
)


def test_build_search_tokens_includes_date_subject_and_sender_filters():
    assert build_search_tokens(
        since="01-Jan-2026",
        before="01-Feb-2026",
        subject="Payment confirmation",
        sender="billing@example.com",
    ) == [
        "ALL",
        "SINCE",
        "01-Jan-2026",
        "BEFORE",
        "01-Feb-2026",
        "FROM",
        '"billing@example.com"',
        "SUBJECT",
        '"Payment confirmation"',
    ]


def test_quote_imap_search_value_escapes_quotes_and_backslashes():
    assert quote_imap_search_value(r'a\b "quoted"') == r'"a\\b \"quoted\""'


def test_normalize_subject_filter_accepts_plain_subject():
    assert normalize_subject_filter("Payment confirmation") == "Payment confirmation"


def test_normalize_subject_filter_extracts_legacy_subject_syntax():
    assert normalize_subject_filter('SUBJECT "Payment confirmation"') == "Payment confirmation"
