# Try Rail first

Goal: use [Rail](https://github.com/vitosans/rail) for a week before writing a TUI here.

Rail v0.10.1 is installed in `~/.local/bin` on the Omarchy laptop, with its checksum and attestation verified. It has no accounts yet. Its daemon stores tokens in the system keyring, and `gnome-keyring` is running here. Confirm with `rail doctor` after setup.

## 1. Create your Google login (about 15 to 30 minutes)

Start with the personal Gmail account, in Google Cloud Console.

1. Create a project and enable the **Gmail API**.
2. In **Google Auth Platform**, set the app name and your address, with audience **External**.
3. Under **Branding**, use this repository's URL for the homepage and privacy policy if needed, and leave the logo out.
4. Under **Audience**, choose **Publish app**. It must say **In production**. In Testing, your login expires every 7 days.
5. Under **Clients**, create a **Desktop app** client and click **Download JSON**. Google only shows the secret there.

Google will warn that the app is unverified when you sign in. That's expected for your own client.

## 2. Sign in and sync

Limit the first sync so it doesn't take hours. Follow [Rail's configuration docs](https://github.com/vitosans/rail/blob/main/docs/configuration.md) for `history_days`.

```sh
rail setup
rail doctor
rail sync
rail
```

Press `?` for keys, or `:` for the command palette. Delete the downloaded client JSON once the account works.

## 3. Outlook

Rail reaches Outlook through Microsoft Graph, and its docs list personal accounts as an option. This hasn't been tested with a personal account here. Follow the [Microsoft section of Rail's account docs](https://github.com/vitosans/rail/blob/main/docs/accounts.md).

Azure registration may ask for a subscription or a credit card. If it hits a wall, stop. The Thunderbird bridge already reaches this account.

## 4. Be careful

Rail's Gmail permission can send and modify mail. It has no read-only mode, so be deliberate with send, trash and bulk actions.

## 5. Judge it after a week

Write down what you hit in `docs/RAIL-NOTES.md`, which git ignores so it stays private:

- What you used every day
- What's missing compared with Gmail
- Whether it was fast and comfortable inside herdr
- Anything that felt unsafe

Then choose: use Rail as is, send features upstream, or build a TUI on the bridge.
