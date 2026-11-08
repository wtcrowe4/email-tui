"""Keeps the content of protected mail, such as finance, away from every client.

Rules live outside the repo in ~/.config/email-tui/protected.json (or EMAIL_TUI_PROTECTED):

    {"folders": ["Finance"], "senders": ["bank.example.com"]}

A message is protected when any folder in its path matches, or its sender's domain
is a listed domain or a subdomain of one. Its subject and body (text and HTML) are removed from
read and search results. Senders and dates stay visible so mail can still be sorted.
"""

import json
import os
import re
from pathlib import Path

DEFAULT_FOLDERS = ("Finance",)
HIDDEN = "[protected]"


def config_path() -> Path:
    return Path(os.environ.get("EMAIL_TUI_PROTECTED", Path.home() / ".config/email-tui/protected.json"))


def load_rules() -> tuple[set[str], tuple[str, ...]]:
    folders, senders = set(f.casefold() for f in DEFAULT_FOLDERS), ()
    try:
        data = json.loads(config_path().read_text())
        folders |= {str(f).casefold() for f in data.get("folders", [])}
        senders = tuple(str(s).casefold().lstrip("@.") for s in data.get("senders", []) if s)
    except (OSError, ValueError, AttributeError):
        pass
    return folders, senders


def sender_domain(author: str | None) -> str:
    match = re.search(r"@([A-Za-z0-9.-]+)", author or "")
    return match.group(1).casefold().rstrip(".") if match else ""


def is_protected(message: dict, rules) -> bool:
    folders, senders = rules
    path = str(message.get("folder") or "")
    if any(part.casefold() in folders for part in path.split("/") if part):
        return True
    domain = sender_domain(message.get("from"))
    return bool(domain) and any(domain == s or domain.endswith("." + s) for s in senders)


def redact(method: str, result, rules=None):
    if method not in ("read", "search"):
        return result
    rules = rules or load_rules()
    if method == "read" and isinstance(result, dict) and is_protected(result, rules):
        return {
            **result,
            "subject": HIDDEN,
            "body": "",
            "bodyHtml": "",
            "bodyTruncated": False,
            "attachments": [],
            "protected": True,
        }
    if method == "search" and isinstance(result, dict):
        messages = [
            {**m, "subject": HIDDEN, "protected": True} if is_protected(m, rules) else m
            for m in result.get("messages", [])
        ]
        return {**result, "messages": messages}
    return result
