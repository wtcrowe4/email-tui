# Gmail in herdr: research and design

Status: DRAFT. Researched 2026-11-06. Nothing here touched real Gmail, Google Cloud or any credential.

Update: the project now covers Outlook too, and runs on Omarchy rather than WSL. Rail also supports Microsoft accounts through Graph, which this document doesn't reflect, and its WSL keyring notes don't apply on Omarchy. The plugin now gets its unread count from the Thunderbird bridge (`docs/BRIDGE.md`) rather than Rail.

**Verdict: do not build a new Gmail client. Build a thin herdr plugin around Rail, and send missing features upstream as PRs.** Section 7 holds the full-client design in case the owner overrides this. No spike was built, because Step 3 was conditional on Step 1 justifying a new TUI.

How facts are marked: *est* = my estimate. *unverified* = from memory or one weak source. Rail was assessed from its docs and source only; it was not compiled or run.

## 1. Premise test

The starting condition was "if there isn't a good Gmail TUI". As of today there is a serious one, though it is very young.

| Tool | Gmail route | Activity (GitHub, 2026-11-06) | Assessment |
|---|---|---|---|
| **Rail** (vitosans/rail) Rust, MIT/Apache | Gmail REST API, `gmail.modify` | Created 2026-10-11, 118 stars, ~890 commits, 2 main authors, v0.10.1 on 11-03 (44 downloads) | Closest fit: SQLite store, daemon, threads, labels, snooze, 10s undo send, drafts, attachments, multi-account, unified inbox, MCP, no OAuth client shipped. 155k lines in 26 days, so likely heavily AI-written (*est*). Pre-1.0. |
| **GizTUI** (ajramos/giztui) Go, MIT | REST API | 7 stars, pushed 11-03, v1.28.1 | Broad: threads, labels, search, Gmail filter sync (`settings.basic`), multi-account, AI extras. Token sits in `~/.config/giztui/token.json`. Very small user base. |
| **himalaya + himalaya-tui** Rust | REST API or IMAP | CLI 7.6k stars, 11-06; TUI 88 stars, 11-02 | Solid CLI, generic mail model. TUI is newer; no Gmail-specific features advertised. |
| **aerc** Go | IMAP/notmuch/JMAP, no Gmail API | 0.22.0, commits 2026-10 | Good client, Gmail labels only through IMAP folders. No settings. |
| **neomutt** C | IMAP | 3.9k stars, release 2026-06 | Good for mutt people. Painful Gmail OAuth setup. Not Gmail-native. |
| **meli** Rust | IMAP/JMAP/notmuch | 896 stars, active | Not Gmail-native. |
| **lieer + notmuch** | REST API sync to notmuch | 655 stars, 10-16 | Reliable label sync, but is a toolkit, not a TUI. |
| **tidemail** Go, MIT | IMAP + app password | 87 stars, active | Gmail OAuth listed but README points at app passwords. Not Gmail-native. |
| **herdr-google-gmail** (Tomatio13) | fzf + gogcli | 3 stars, idle since 2026-07-22 | The one Gmail plugin in the marketplace. Inbox preview and trash only. Weak prior art. |
| Long tail | Mixed | 59 repos match "gmail tui": gmail-tui 31 stars, epist 19 (idle since March), gogmail 7, rest 0-5 | Crowded with small, often AI-made projects. |

**Rail's real gaps** (from its docs and source):
- No schedule send, no server settings: filters, vacation, send-as, server signatures. Signature is a local file.
- TUI filter is local only with a fixed operator set (`from: to: subject: has:attachment is:unread is:starred before: after: account:`). `label:`, `category:`, `larger:`, `filename:`, `older_than:` are not understood there. `rail search` also asks the server, but it is a CLI command. README lists search operators as "later".
- No read-only mode: always asks for `gmail.modify`.
- Token default is the OS keyring. On WSL with no working Secret Service the fallback is a 0600 plaintext file. This author's test WSL has no `gnome-keyring` or `secret-tool`; only `org.kde.secretservicecompat` is on the bus, and I did not test it. `rail doctor` would say.
- First sync of a large mailbox "takes hours" (Rail's own doc). Gmail's quota explains it; see Section 3.
- One-maintainer risk, and it has only existed for 26 days.

**Good enough?** On paper, yes for reading, triage, drafting and sending. It is unproven: Try it for a week on a low-stakes account before anyone relies on it. Every gap above can be fixed in Rail, and a full-coverage settings pane could also be a separate small tool (gmailctl, 2.2k stars, already does filters declaratively).

## 2. Distribution reality

- **herdr:** 48.6k stars, Rust, Apache-2.0, created 2026-03-27. GitHub release assets: v0.9.5 384k downloads, v0.9.3 293k. Auto-update and CI inflate that, so it is not a user count. Active users: 50k-200k (*est, low confidence*). the owner runs 0.9.1-preview, behind current.
- **Plugins:** 2,056 repos carry the `herdr-plugin` topic (some are dotfiles or apps, so real plugins are fewer). Marketplace is an unreviewed index: stars, language, last push. No install counts are published.
- **Popularity skew:** top repos are agent and browser tooling (terminal-browser 4.5k, collie 1.6k, reviewr 974, herdr-sidebar 538). Sample from deep in the list: 0-3 stars.
- **Demand signal for mail is weak:** only Gmail plugin has 3 stars. Other "mail" hits are agent-to-agent mailboxes, not email. People install herdr to run coding agents.
- **Expected result for a Gmail plugin:** tens to low hundreds of stars, not a breakout (*est*). Rail got 118 stars in 26 days with no herdr tie, which is a comparable. Star counts in this ecosystem may also be inflated; I cannot tell from public data.

The BYO OAuth setup (Section 4) further narrows this to people willing to do Google Cloud Console steps.

## 3. Gmail API feature inventory

Scopes per Google's scope table: **Restricted** = `mail.google.com`, `gmail.readonly`, `gmail.compose`, `gmail.insert`, `gmail.modify`, `gmail.metadata`, `gmail.settings.basic`, `gmail.settings.sharing`. **Sensitive** = `gmail.send`. **Non-sensitive** = `gmail.labels`. Any client that reads mail needs a restricted scope.

Quota: 6,000 units per user per project per minute. `threads.get` full = 120, `messages.get` full = 60, `threads.list` = 10, `history.list` = 2, send = 100. That is about 50 full threads or 100 full messages a minute, so metadata first and bodies on demand is mandatory.

| Feature | API support | Terminal verdict | Phase |
|---|---|---|---|
| Threads, read/unread, star, archive, trash, spam | `threads.*`, `messages.modify` | Full | 1 |
| Labels, create/edit/colors, nesting by `/` names | `labels.*` | Full | 1 |
| Categories | `CATEGORY_*` labels, `category:` operator | Full. Tabs can be saved searches | 1 |
| Search operators | `q` on list calls (server) | Full online. Offline only a subset via local index | 1 |
| Drafts | `drafts.*` | Full | 1 |
| Send, reply, forward, threading | `messages.send`, `drafts.send`, `threadId` + headers | Full, gated (Section 6) | 2 |
| Attachments | `attachments.get`, multipart send, 25 MB limit | Full. Drive links for large files need Drive scope | 2 |
| HTML and inline images | Raw MIME only | Lossy: text render, kitty graphics in Ghostty, nothing in Windows Terminal | 2 |
| Multiple accounts | Separate tokens | Full | 2 |
| Sync | `history.list` poll. `users.watch` needs Pub/Sub, meaning a server | Poll is fine, no push | 1 |
| Signatures | `sendAs` update, `settings.basic` (*unverified which fields*) | Full | 3 |
| Filters | `settings.filters`, `settings.basic` | Full, create/delete only, no update | 3 |
| Vacation responder | `getVacation`/`updateVacation`, `settings.basic` | Full | 3 |
| Send-as read/edit, IMAP/POP settings | `settings.*`, `settings.basic` | Full | 3 |
| Send-as create, forwarding addresses, auto-forward | `settings.sharing` | **Service account with domain-wide authority only.** Workspace admins | Out for most users |
| Delegates | `settings.delegates` | **Same restriction:** "requires a service account granted domain-wide authority" | Out for most users |
| S/MIME, client-side encryption | `settings.sendAs.smimeInfo`, `settings.cse.*` | Possible, niche, Workspace-tier dependent | 4 |
| Permanent delete | `messages.delete`, needs `mail.google.com` | Avoid. Trash is enough | 4 or never |
| **Snooze** | **Not in the API.** Mimestream and Rail both emulate it: archive now, return locally | Emulated, works only while local daemon runs; does not appear as snoozed in web Gmail | 3 |
| **Schedule send** | **No method in the reference**; `send` is immediate | Emulated locally (machine must be on), or send from Gmail web. Not the same feature | 4 |
| Undo send | No API | Emulated by holding locally ~10s. Rail does this | 2 |
| Contacts autocomplete | People API, separate scope | Local address index from mail is enough at first | 3 |
| Calendar invites | Calendar API, separate scope | Show ICS; RSVP later | 4 |
| Templates, confidential mode, nudges, smart reply, Gemini, Chat, Meet, Priority Inbox configuration, tasks side panel | No Gmail API surface found (*unverified per feature*) | **Cannot be supported** | Never |

So "every single feature" is not achievable. Roughly 80% of daily mail use is reachable (*est*); the settings tier needs extra restricted scopes; delegates and auto-forward need admin-grade service accounts; several web features have no API at all.

## 4. OAuth: the main distribution risk

**Shipping one shared client ID (the "just sign in" experience):**
- Requires restricted-scope verification: privacy policy on a verified domain, Limited Use compliance, brand review, demo, "several weeks" per Google. Annual re-verification.
- Requires a CASA assessment by an authorized lab, repeated every 12 months. Levels are AL1 and AL2, both lab verified; no self-assessment option is listed. Google assigns the level by user count and scopes.
- **Local-only is not a safe exemption.** One Google page ties the assessment to storing or transmitting restricted data on servers; another says apps requesting restricted scopes "must undergo an annual security assessment". Mimestream, a desktop client with no cloud, wrote in 2024 that Google extended the requirement to it, and it paid a lab. An Oct 2026 Google community answer says to get the verification team's ruling in writing.
- **Cost:** Google publishes no price. Third-party figures for the Gmail tier: $1,500-$6,000/yr (2026 lab rates, one OSS project's write-up), $500-$4,500 (another), up to $15k-$75k from a vendor selling the service (treat as an outlier with consulting included). All-in for a solo project, with lab fee, domain and time: **$3k-$10k per year plus weeks of work up front** (*est*).
- **Other risks:** the client ID is public in an OSS repo, so forks and abuse can get it suspended for every user. A missed annual renewal also suspends it. Adding a scope later means re-review, so the settings phase could trigger a new round. Someone has to be the accountable legal party. Skipping verification is not a way out for a shared client: an unverified app is capped at "100 new users in total", ever.

**Bring your own client ID (what Rail and GizTUI do):**
- Each user creates a Google Cloud project, enables Gmail API, sets consent screen, publishes to "In production" unverified, creates a Desktop client. 15-30 minutes in a browser (*est*).
- No CASA, no cost, no annual cycle, and suspension affects only that user. Falls under the personal-use exemption ("fewer than 100 users"). User clicks through the unverified warning.
- Traps: leaving it in "Testing" expires refresh tokens every 7 days. Gmail-scope tokens die on password change and after 6 months unused. Some Workspace admins block unconfigured apps.
- Workspace accounts can use an Internal consent screen: exempt from verification with no warning, but the project must belong to that organization.

**What this means for "lots of downloads":** downloads are possible, activated users are not. Every BYO install hits a Google Cloud Console wall, which limits the audience to developers, which herdr's users are. A shared verified client is the only real differentiator available in this space, and none of the OSS TUIs I checked does it. Paying for that only makes sense as a funded product. Recommendation: BYO only.

## 5. Recommended project: thin herdr plugin

Herdr plugins are a `herdr-plugin.toml` manifest (id, version, `min_herdr_version`, `[[panes]]`, `[[actions]]`, optional `[[build]]`, events), run unsandboxed as the user, install with `herdr plugin install owner/repo`, and list themselves through the `herdr-plugin` topic. Panes support `overlay`, `split`, `tab` and `popup` placement.

The herdr-beeper plugin is the exact template: panes plus an unread `$beeper` sidebar token fed by `herdr workspace report-metadata --token`.

Scope (about one weekend, *est*):
1. Manifest with a `rail` pane (`tab` and `popup`) and toggle action. Detects a missing `rail` and prints setup steps. Does not bundle or install Rail silently.
2. Background unread count to a `$gmail` sidebar token, plus `herdr notification` on new mail. Reads Rail's local store or CLI, and holds no tokens itself. Rail has no documented unread command, so this may need a small upstream PR.
3. Actions: "compose", "search" (opens prefilled), and open-thread-from-link if practical.

Upstream PRs to Rail, each sized independently: Gmail operators in the TUI filter (server fallback), read-only mode, then settings (filters, vacation, signatures). Ask the maintainer first. Separate companion tool if he declines.

The plugin inherits Rail's safety and token handling, and carries a dependency risk: Rail is 26 days old. Mitigation: the plugin only talks to a small interface (`rail` pane command and unread count), so swapping to himalaya-tui or GizTUI later stays cheap.

## 6. Safe defaults (any route)

Read and draft first, with send as a deliberate action.

**OAuth cannot enforce "draft but not send".** `gmail.compose` and `gmail.modify` both permit sending, so the only hard boundary is `gmail.readonly` vs. everything else. The rest is app-level:
- Tiers: `read` (`gmail.readonly`), `write` (`gmail.modify`, a separate consent step). The default is `read`.
- Send is off until enabled per account in config. When on, send takes a review screen with recipients, subject, attachments and a typed or two-key confirm, then a 10s hold. No single-key send, no send from a macro or plugin action.
- No agent or MCP send path by default. Any agent path creates drafts only.
- Remote images off by default. Trash, never permanent delete. Destructive bulk actions show a count and can be undone.

Rail today covers review + undo send, with a per-account `ai_send` policy documented for its coming agent tools; it lacks the `read` tier and send-off-by-default. Those are PR candidates.

## 7. If overriding that verdict: full-client design

Cost honesty: Rail is 155k lines of Rust. A daily-driver core is many weekends; full coverage is months (*est*). It competes directly with an active project that has a head start.

- **Language:** Rust, with ratatui + crossterm. herdr itself is Rust, and top plugins (reviewr, herdr-sidebar, file-viewer) are too. A single static binary suits `[[build]]` download. Rust 1.97 is already on this machine; Go is not installed.
- **Architecture:** `MailBackend` trait (fake fixture, Gmail REST); `Store` (SQLite + FTS5, bundled); sync daemon as a separate process over a Unix socket so TUI, plugin token and CLI share one state; outbox table with idempotency for all writes; UI never blocks on the network.
- **Sync:** initial pass `messages.list` then metadata format only, bodies on open and for the last N days, respecting the 6,000 units/min budget with backoff. Incremental with `history.list` from stored `historyId`, polling 60s; on an expired `historyId`, resync. Labels are many-to-many, so model threads and labels properly and never as folders.
- **Offline:** read everything cached, search via local FTS, queue label changes and drafts. Sends are never queued silently while offline; they wait in Outbox for explicit release. Conflict rule: server wins for labels, local draft kept as a copy.
- **Secrets:** tokens and client secret only in OS keyring (`keyring` crate, Secret Service). WSL often has none, so fallback is a passphrase-encrypted file. Plaintext is refused, unlike the common 0600 token file. Config holds account names and key references only. Redaction layer in the logger for `Authorization`, tokens and auth codes; bodies and subjects never logged. Loopback redirect with PKCE per the desktop flow.
- **Cache at rest:** 0700 dir, 0600 files. Mail DB is plaintext by default as is usual for mail clients; documented; SQLCipher optional. No attachments stored unless opened. `purge` command per account.
- **Tests:** fake backend + fixture threads (invented only), ratatui `TestBackend` snapshots, history replay tests. No test ever needs a Google credential.
- **Phasing:** per Section 3. Phase 1 read-only + labels + search + drafts. Phase 2 send + attachments + multi-account. Phase 3 settings + snooze. Phase 4 long tail.

## 8. Open decisions

1. Accept "thin plugin + upstream PRs", or override and own a full client (Section 7).
2. Try Rail for a week on a low-stakes account first? Needs him to create the OAuth client himself. Needs a call on keyring in WSL.
3. Which Google account owns any test project. A personal account keeps this side project out of company Workspace; Internal consent on the company domain needs org sign-off.
4. Public repo under his name, and a project name. Both undecided; nothing is published.
5. BYO only (recommended), or fund a verified shared client ($3k-$10k/yr *est*).

## Sources

Google: [scopes](https://developers.google.com/workspace/gmail/api/auth/scopes), [REST reference](https://developers.google.com/workspace/gmail/api/reference/rest), [labels](https://developers.google.com/workspace/gmail/api/guides/labels), [quota](https://developers.google.com/workspace/gmail/api/reference/quota), [delegates](https://developers.google.com/workspace/gmail/api/guides/delegate_settings), [OAuth tokens](https://developers.google.com/identity/protocols/oauth2), [restricted verification](https://developers.google.com/identity/protocols/oauth2/production-readiness/restricted-scope-verification), [security assessment](https://support.google.com/cloud/answer/13465431), [verification exemptions](https://support.google.com/cloud/answer/13464323), [unverified apps](https://support.google.com/cloud/answer/7454865), [CASA tiering](https://appdefensealliance.dev/casa/casa-tiering).

Third-party: [Mimestream CASA post](https://mimestream.com/blog/casa-verified), [Mimestream snooze](https://mimestream.com/help/user-guide/snoozing), [gws-axi cost notes](https://raw.githubusercontent.com/JarvusInnovations/gws-axi/HEAD/docs/shared-client-future.md), [truto](https://truto.one/google.md), [openwearables](https://openwearables.io/blog/google-casa-oauth-verification-health-apps), [Google community thread](https://groups.google.com/g/google-apps-script-community/c/-A00Ngimg1A).

Projects: [Rail](https://github.com/vitosans/rail), [GizTUI](https://github.com/ajramos/giztui), [himalaya](https://github.com/pimalaya/himalaya), [himalaya-tui](https://github.com/pimalaya/himalaya-tui), [aerc](https://aerc-mail.org/), [neomutt](https://github.com/neomutt/neomutt), [lieer](https://github.com/gauteh/lieer), [gmailctl](https://github.com/mbrt/gmailctl), [herdr-google-gmail](https://github.com/Tomatio13/herdr-google-gmail), [herdr](https://github.com/herdrdev/herdr), [herdr plugins doc](https://raw.githubusercontent.com/herdrdev/herdr/v0.9.5/docs/next/website/src/content/docs/plugins.mdx), [marketplace doc](https://herdr.dev/docs/preview/marketplace/).
