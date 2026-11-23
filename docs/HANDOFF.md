# Handoff

Where work stopped on 2026-11-23 (second session), so a fresh session can pick up.

## State

- This repo: `main` is pushed. It has the always-on `$mail` badge on the Email space, priority alerts that close after about 5 seconds, and `bin/herdr-autopanes`, which restarts beeper-tui and Rail in the panes herdr restores.
- Rail: a local build from source in `~/src/rail`, branch `omarchy-local`, on top of v0.10.3. It adds `theme = "Omarchy"`, which follows the live Omarchy theme. The installed binary is `~/.local/bin/rail`; the previous release is kept as `~/.local/bin/rail-0.10.1`. Local only: the upstream repo belongs to someone else.
- beeper-tui: `~/src/beeper-tui`, local work branch, three local commits: image viewer, herdr `$texts` badge and focus-aware read receipts; key hints on the status line (`?` hides them); `u` for the next unread chat (mentions, then pinned, then direct, then groups). Not installed yet: `~/.local/bin/beeper-tui` is the 2026-11-13 binary. Install with `make install-bin` in the checkout after the owner's go. Local only: the upstream repo belongs to someone else.
- Branch `feat/mail-hop` (pushed): `bin/herdr-mail-hop` flips herdr between Email and Messages and raises its window. Not bound yet. Proposed line for `~/.config/hypr/bindings.lua`, after the owner's go and a symlink into `~/.local/bin`: `o.bind("SUPER + ALT + E", "Email / Messages (herdr)", "herdr-mail-hop")`. SUPER+ALT+E is free.
- Waiting on the owner: whether to create personal forks of Rail and beeper-tui to push those branches to.

## Next 3 steps

1. Owner's go: install beeper-tui, bind the hop key, merge `feat/mail-hop`.
2. Quick-reply popup for texts.
3. Unread count per network in the `$texts` badge.

Later, in ranked order: more Rail styling, snooze, search, inline images, Rail's unread count as the Email badge, and opening PDF and image attachments in local viewers.

## Rules

See `CLAUDE.md`. In short: never send mail or messages, change no real mail without the owner's go, commit as the no-reply address with the hooks on, add no AI attribution, and nothing goes live without the owner's go.
