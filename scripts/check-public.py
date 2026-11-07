#!/usr/bin/env python3
"""Blocks personal data from entering this public repo.

Git hooks run it at commit and push. Install the hooks with --install-hooks.
Personal terms stay in .git/info/public-denylist, one per line, which is never committed.

  check-public.py              check staged files and the commit identity
  check-public.py --all        check every tracked file
  check-public.py --pre-push   check identities in commits being pushed (hook input on stdin)
"""

import fnmatch
import re
import subprocess
import sys
from pathlib import Path

ALLOWED_EMAIL = re.compile(
    r"@(example\.(com|org|net|invalid)|users\.noreply\.github\.com|wtcrowe4\.github\.io)$"
    r"|^noreply@anthropic\.com$",
    re.IGNORECASE,
)
PRIVATE_IDENTITY = re.compile(r"@users\.noreply\.github\.com$", re.IGNORECASE)
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
SECRETS = {
    "GitHub token": r"gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}",
    "Google token or key": r"ya29\.[A-Za-z0-9_-]{20,}|AIza[0-9A-Za-z_-]{30,}|GOCSPX-[A-Za-z0-9_-]{10,}",
    "API key": r"sk-[A-Za-z0-9_-]{20,}|xox[baprs]-[A-Za-z0-9-]{10,}|AKIA[0-9A-Z]{16}",
    "private key": r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    "OAuth field with a value": r"\"(refresh_token|access_token|client_secret)\"\s*:\s*\"[^\"]+\"",
    "home directory path": r"/home/[a-z_][a-z0-9_-]*/|/Users/[A-Za-z0-9_-]+/|[A-Z]:\\Users\\",
    "private network address": r"\b(192\.168|10\.\d{1,3})\.\d{1,3}\.\d{1,3}\b",
}
BLOCKED_FILES = (
    "*.eml", "*.mbox", "*.msf", "*.sqlite", "*.sqlite-*", "*.db", "*.xpi", "*.pem", "*.key",
    ".env", ".env.*", "logins*.json", "key4.db", "prefs.js", "token*.json", "*.token",
    "credentials*.json", "client_secret*.json", "secrets.json", "RAIL-NOTES.md",
)


def git(*args: str) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout


def denylist() -> list[str]:
    path = Path(git("rev-parse", "--git-path", "info/public-denylist").strip())
    if not path.exists():
        return []
    return [line.strip() for line in path.read_text().splitlines() if line.strip()]


def scan(name: str, text: str, denied: list[str]) -> list[str]:
    problems = []
    if any(fnmatch.fnmatch(Path(name).name, pattern) for pattern in BLOCKED_FILES):
        problems.append(f"{name}: this file type must not be committed")
    for number, line in enumerate(text.splitlines(), 1):
        for address in EMAIL.findall(line):
            if not ALLOWED_EMAIL.search(address):
                problems.append(f"{name}:{number}: email address")
        for label, pattern in SECRETS.items():
            if re.search(pattern, line):
                problems.append(f"{name}:{number}: {label}")
        # The public GitHub handle is fine, but not as part of an address.
        lowered = re.sub(r"wtcrowe4(?!@)", "", line.lower())
        if any(term.lower() in lowered for term in denied):
            problems.append(f"{name}:{number}: term from the private denylist")
    return problems


def read_blob(spec: str) -> str | None:
    data = subprocess.run(["git", "show", spec], check=True, capture_output=True).stdout
    return None if b"\0" in data else data.decode("utf-8", "replace")


def check_files(names: list[str], prefix: str) -> list[str]:
    denied = denylist()
    problems = []
    for name in names:
        text = read_blob(f"{prefix}{name}")
        if text is None:
            problems.append(f"{name}: binary files need a manual review")
        else:
            problems += scan(name, text, denied)
    return problems


def check_identity() -> list[str]:
    problems = []
    for variable in ("GIT_AUTHOR_IDENT", "GIT_COMMITTER_IDENT"):
        email = git("var", variable).split("<")[-1].split(">")[0]
        if not PRIVATE_IDENTITY.search(email):
            problems.append(f"{variable}: use your GitHub no-reply address")
    return problems


def check_push(lines: list[str]) -> list[str]:
    problems = []
    for line in lines:
        fields = line.split()
        if len(fields) != 4 or set(fields[1]) == {"0"}:
            continue
        log = git("log", fields[1], "--not", "--remotes", "--format=%h %ae %ce %B%x00")
        for entry in filter(str.strip, log.split("\0")):
            short, author, committer, *_ = entry.split(maxsplit=3)
            if not (PRIVATE_IDENTITY.search(author) and PRIVATE_IDENTITY.search(committer)):
                problems.append(f"commit {short}: author or committer is not a no-reply address")
            problems += scan(f"commit {short} message", entry.split(maxsplit=3)[-1], denylist())
    return problems


def install_hooks() -> None:
    hooks = Path(git("rev-parse", "--git-path", "hooks").strip())
    hooks.mkdir(parents=True, exist_ok=True)
    for name, flag in (("pre-commit", ""), ("pre-push", " --pre-push")):
        path = hooks / name
        path.write_text(f'#!/bin/sh\nexec python3 "$(git rev-parse --show-toplevel)/scripts/check-public.py"{flag}\n')
        path.chmod(0o755)
    print(f"hooks installed in {hooks}")


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else None
    if mode == "--install-hooks":
        install_hooks()
        return
    if mode == "--all":
        problems = check_files(git("ls-files").splitlines(), ":")
    elif mode == "--pre-push":
        problems = check_push(sys.stdin.read().splitlines())
    else:
        staged = git("diff", "--cached", "--name-only", "--diff-filter=ACMR").splitlines()
        problems = check_identity() + check_files(staged, ":")
    if problems:
        # The matched text is left out so it doesn't end up in logs.
        print("Blocked: possible personal data for a public repo:", file=sys.stderr)
        print("\n".join(f"  {problem}" for problem in problems), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
