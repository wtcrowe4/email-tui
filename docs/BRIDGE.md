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
| Add-on permissions | Reads and organises mail: folders, move, copy, archive, trash, flags, tags, contacts, signatures and saved drafts. Identities can only have their signature changed, never be created or deleted. No `messages.send` or `compose.send`, so Thunderbird refuses to send |
| Deleting | Trash moves mail to the account's Trash folder. Permanent deletion is never called. Folders can be deleted only when empty, and built-in folders can't be renamed, moved or deleted |
| Add-on type | Standard MailExtension. No Experiment API, so no access beyond its permissions |
| Helper | Allowlist of methods. None of them sends |
| Protected mail | Subjects and bodies (text and HTML) of mail in a Finance folder, or from senders in `~/.config/email-tui/protected.json`, are removed before any client sees them |
| Drafts | Saved to Drafts or opened in a window for review. Sending is always the owner's click |
| Events | New-mail events carry a count, an account and up to three sender display names. Never addresses, subjects or bodies |

`bridge/tests` fails if a send permission is added or a send, permanent-delete or attachment-removal API is called. Reading can't be blocked this way: anything Claude reads could be repeated in its session, so read only what's needed.

## Install notes

- The host manifest goes in `~/.mozilla/native-messaging-hosts/`. Thunderbird 153 reads that path, even though its profile is in `~/.thunderbird`.
- Install From File works on Thunderbird 158 with real accounts.
- The manifest stores an absolute path to `bin/email-bridge-host`. Rerun `scripts/install-bridge.py` if the repo moves.
- After changing the add-on, rebuild it and install it again.

## Herdr badge and alerts

The plugin sets two tokens on one workspace, named by `EMAIL_TUI_WORKSPACE` (default `Messages`), and clears them everywhere else:

- `$mail`: unread inbox mail, as `✉ 5`
- `$career`: unread inbox mail that looks job-related, as `★ 2`

Show them by adding the tokens to a sidebar row in `~/.config/herdr/config.toml`:

```toml
[ui.sidebar.spaces]
rows = [
  ["state_icon", "workspace", "$career", "$mail"],
  ["branch", "git_status"],
]
```

New mail shows a herdr toast with the senders' display names. Career mail also raises a desktop notification that stays until dismissed.

Career mail is flagged mail, LinkedIn messages, invitations and application updates, mail from common recruiting systems, and subjects such as "interview" or "your application". LinkedIn job alerts are left out. The rules in `background.js` are generic on purpose. Rules about specific people or organisations belong in Thunderbird filters, which stay in the local profile.

The counts cover inbox folders only, because Gmail labels would otherwise count one message several times.
