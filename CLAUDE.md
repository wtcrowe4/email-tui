# Gmail in herdr: working plan

Pick up here. Read `docs/DESIGN.md` for the research and `docs/TRY-RAIL.md` for the setup steps.

## Where things stand

- Decision so far: try Rail first. Only build our own client if Rail isn't good enough.
- Nothing is built. Rail hasn't been run yet.
- The test runs on a personal laptop (Ubuntu WSL) with a personal Gmail account. Never use a work account or work credentials here.

## Plan

1. Install Rail v0.10.1 and verify the checksum and attestation.
2. Create a personal Google Cloud project and a Desktop OAuth client. The owner does the browser steps and sign-in.
3. Run `rail setup` and `rail doctor`, then sync with a limited `history_days`.
4. Check where tokens are stored. If there's no keyring, decide whether the private file is acceptable or set up a keyring.
5. Use it for real, including inside a herdr pane. Keep notes in `docs/RAIL-NOTES.md`.
6. Try other Gmail terminal clients only if Rail falls short. GizTUI and himalaya are next, per `docs/DESIGN.md`.
7. Choose one:
   - Use Rail as is.
   - Build a thin herdr plugin (Rail pane, unread count, new-mail alerts) and send missing features upstream.
   - Build a full client, using section 7 of `docs/DESIGN.md`.

## Rules

- This repo is public. Never commit tokens, client secrets, real email content, addresses or mailbox data.
- Don't send, trash or bulk-change real mail without the owner asking for that specific action.
- The owner signs in and handles OAuth. Don't read token files or paste secrets into chat.
- Keep test fixtures fake.

## Open decisions

- Project name and license. There's no license yet.
- Whether a shared verified Google client is ever worth its yearly cost. The default is that each user brings their own client ID.
