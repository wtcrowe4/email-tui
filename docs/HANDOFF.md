# Handoff

Where work stopped on 2026-11-23, so a fresh session can pick up.

## State

- This repo: `main` is pushed. It has the always-on `$mail` badge on the Email space, priority alerts that close after about 5 seconds, and `bin/herdr-autopanes`, which restarts beeper-tui and Rail in the panes herdr restores.
- Rail: a local build from source in `~/src/rail`, branch `omarchy-local`, on top of v0.10.3. It adds `theme = "Omarchy"`, which follows the live Omarchy theme. The installed binary is `~/.local/bin/rail`; the previous release is kept as `~/.local/bin/rail-0.10.1`. Local only: the upstream repo belongs to someone else.
- beeper-tui: `~/src/beeper-tui`, a local work branch (one local commit: image viewer, unread navigation, herdr `$texts` badge, read receipts only while the pane has focus). Local only: the upstream repo belongs to someone else.
- Waiting on the owner: whether to create personal forks of Rail and beeper-tui to push those branches to.

## Next 3 steps

1. beeper-tui: a one-line footer showing the keys for the current view.
2. beeper-tui: a key that jumps to the next unread chat, priority chats first.
3. Hyprland: one key that toggles between the Email and Messages herdr spaces.

Later, in ranked order: quick-reply popup, unread count per network in the badge, more Rail styling, snooze, search, inline images, Rail's unread count as the Email badge, and opening PDF and image attachments in local viewers.

## Rules

See `CLAUDE.md`. In short: never send mail or messages, change no real mail without the owner's go, commit as the no-reply address with the hooks on, add no AI attribution, and nothing goes live without the owner's go.
