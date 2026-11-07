# email-tui

Gmail and Outlook from the terminal, especially inside [herdr](https://github.com/herdrdev/herdr). Early and experimental.

It has two parts:

- **Thunderbird bridge:** a small add-on and local helper that give terminal tools and Claude read access to the mail in your running Thunderbird. It can open a compose window, but it can't send, delete, move or change mail. See [docs/BRIDGE.md](docs/BRIDGE.md).
- **herdr plugin:** an unread badge and new-mail toasts from the bridge, plus a pane that opens [Rail](https://github.com/vitosans/rail). See [docs/TRY-RAIL.md](docs/TRY-RAIL.md).

Requires Linux, Python 3.11+, Thunderbird 128+ and herdr 0.8+. It has been tested on Thunderbird 153. There are no other dependencies.

```sh
python3 scripts/install-bridge.py
```

Then in Thunderbird, open Add-ons and Themes, click the gear, choose **Install Add-on From File**, and pick `dist/email-tui-bridge.xpi`. Check the connection:

```sh
bin/email-bridge status
```

The original Gmail research is in [docs/DESIGN.md](docs/DESIGN.md).

MIT licensed. See [LICENSE](LICENSE).
