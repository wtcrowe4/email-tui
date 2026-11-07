# Thunderbird bridge

Gives terminal tools access to mail in a running Thunderbird, with no new OAuth setup. Thunderbird already holds the logins.

```
Claude ── bin/email-bridge-mcp ──┐
Terminal ── bin/email-bridge ────┼── private Unix socket ── helper ── add-on ── Thunderbird
herdr ── bin/email-tui-notifier ─┘                    (native messaging)
```

Thunderbird starts the helper when the add-on loads, and it stops when Thunderbird closes. It opens no network port. The socket is `$XDG_RUNTIME_DIR/email-tui/bridge.sock`, in a `0700` directory with `0600` permissions.

## Commands

```sh
bin/email-bridge status
bin/email-bridge accounts
bin/email-bridge unread
bin/email-bridge search "invoice" --from someone@example.com --since 2026-01-01
bin/email-bridge read 12345
bin/email-bridge draft --to someone@example.com --subject "Hi" --body "Text"
bin/email-bridge watch
```

Message ids stop working when Thunderbird restarts or the message moves, so search again.

## Limits

- Thunderbird must be running.
- Search only covers mail stored locally. Thunderbird's API doesn't offer server search for IMAP.
- Search defaults to the last 90 days. Use `--since` for older mail.
- Each search scans up to 500 messages or 20 seconds, then reports `truncated: true`.
- Attachment names and sizes are visible. Contents are not.
- Bodies are capped at 100,000 characters.

## Safety

Email is written by strangers, so a message can contain instructions aimed at Claude. The limits below hold even if that works:

| Layer | Limit |
|---|---|
| Add-on permissions | No send, delete, move, modify or filter permission, so Thunderbird refuses those calls. `compose.send` is not granted |
| Add-on type | Standard MailExtension. No Experiment API, so no access beyond its permissions |
| Helper | Allowlist of six methods |
| Drafts | Open a window for review. Sending is always the owner's click. No attachments |
| Events | New-mail events carry only a count and an account |

`bridge/tests` fails if a permission is added or a dangerous API is called. Reading can't be blocked this way: anything Claude reads could be repeated in its session, so read only what's needed.

## Install notes

- The host manifest goes in `~/.mozilla/native-messaging-hosts/`. Thunderbird 153 reads that path, even though its profile is in `~/.thunderbird`.
- Thunderbird accepted the unsigned add-on when it was placed in a test profile. The Install From File path has not been tested.
- The manifest stores an absolute path to `bin/email-bridge-host`. Rerun `scripts/install-bridge.py` if the repo moves.
- After changing the add-on, rebuild it and install it again.

## Herdr badge

The plugin sets a `$mail` token on each workspace. Show it by adding the token to a sidebar row in `~/.config/herdr/config.toml`:

```toml
[ui.sidebar.spaces]
rows = [
  ["state_icon", "workspace", "$mail"],
  ["branch", "git_status"],
]
```

The count covers inbox folders only, because Gmail labels would otherwise count one message several times.
