"""Command line client for the bridge. Prints JSON."""

import argparse
import json
import sys

from .client import BridgeError, call, events


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="email-bridge", description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)
    commands.add_parser("status", help="check the connection to Thunderbird")
    commands.add_parser("accounts", help="list accounts")
    commands.add_parser("unread", help="unread inbox counts per account")
    commands.add_parser("watch", help="print new mail events as they arrive")

    search = commands.add_parser("search", help="search local mail, headers only")
    search.add_argument("text", nargs="?")
    search.add_argument("--from", dest="sender")
    search.add_argument("--subject")
    search.add_argument("--account")
    search.add_argument("--unread", action="store_true")
    search.add_argument("--inbox", action="store_true")
    search.add_argument("--since", help="ISO date. Default is 90 days ago")
    search.add_argument("--until", help="ISO date")
    search.add_argument("--limit", type=int, default=20)

    read = commands.add_parser("read", help="read one message")
    read.add_argument("id", type=int)

    draft = commands.add_parser("draft", help="open a compose window. It does not send")
    draft.add_argument("--to")
    draft.add_argument("--cc")
    draft.add_argument("--subject")
    draft.add_argument("--body")

    generic = commands.add_parser("call", help="call any bridge method with JSON params, such as folders")
    generic.add_argument("method")
    generic.add_argument("params", nargs="?", default="{}", help="JSON object")
    return root


def run(args: argparse.Namespace) -> None:
    if args.command == "watch":
        for event in events():
            print(json.dumps(event), flush=True)
        return
    if args.command == "call":
        params = json.loads(args.params)
        if not isinstance(params, dict):
            sys.exit("email-bridge: params must be a JSON object")
        print(json.dumps(call(args.method, **params), indent=2, ensure_ascii=False))
        return
    if args.command == "search":
        params = {
            "text": args.text,
            "from": args.sender,
            "subject": args.subject,
            "account": args.account,
            "since": args.since,
            "until": args.until,
            "limit": args.limit,
            "unread": args.unread or None,
            "inboxOnly": args.inbox or None,
        }
    elif args.command == "read":
        params = {"id": args.id}
    elif args.command == "draft":
        params = {"to": args.to, "cc": args.cc, "subject": args.subject, "body": args.body}
    else:
        params = {}
    params = {key: value for key, value in params.items() if value is not None}
    print(json.dumps(call(args.command, **params), indent=2, ensure_ascii=False))


def main() -> None:
    try:
        run(parser().parse_args())
    except BridgeError as error:
        sys.exit(f"email-bridge: {error}")
    except KeyboardInterrupt:
        sys.exit(130)
