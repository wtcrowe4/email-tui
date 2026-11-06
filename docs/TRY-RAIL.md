# Try Rail first

Goal: use [Rail](https://github.com/vitosans/rail) for a week before writing any code here. Do this on a personal PC, in Linux or WSL, with a personal Gmail account.

Rail hasn't been run or verified by this project yet. These steps come from its docs for v0.10.1.

## 1. Install

```sh
V=v0.10.1
A=rail-$V-x86_64-unknown-linux-gnu.tar.gz
gh release download "$V" -R vitosans/rail -p "$A" -p SHA256SUMS
sha256sum -c SHA256SUMS --ignore-missing
gh attestation verify "$A" --repo vitosans/rail
tar -xzf "$A"
find . -type f -name rail -exec install -m 755 {} ~/.local/bin/rail \;
rail --version
```

It needs glibc 2.36 or newer. Make sure `~/.local/bin` is on your `PATH`.

## 2. Create your Google login (about 15 to 30 minutes)

Use the personal Google account in Google Cloud Console.

1. Create a project and enable the **Gmail API**.
2. In **Google Auth Platform**, set the app name and your address, with audience **External**.
3. Under **Branding**, use this repository's URL for the homepage and privacy policy if needed, and leave the logo out.
4. Under **Audience**, choose **Publish app**. It must say **In production**. In Testing, your login expires every 7 days.
5. Under **Clients**, create a **Desktop app** client and click **Download JSON**. Google only shows the secret there.

Google will warn that the app is unverified when you sign in. That's expected for your own client.

## 3. Sign in and sync

Limit the first sync so it doesn't take hours. Follow [Rail's configuration docs](https://github.com/vitosans/rail/blob/main/docs/configuration.md) for `history_days`.

```sh
rail setup
rail doctor
rail sync
rail
```

Press `?` for keys, or `:` for the command palette.

Run `rail doctor` and check where tokens are stored. On WSL without a working keyring, Rail may use a private `secrets.json` file. Delete the downloaded client JSON once the account works.

## 4. Be careful

Rail's Gmail permission can send and modify mail. It has no read-only mode, so be deliberate with send, trash and bulk actions.

## 5. Judge it after a week

Write down what you hit in `docs/RAIL-NOTES.md`:

- What you used every day
- What's missing compared with Gmail
- Whether it was fast and comfortable inside herdr
- Anything that felt unsafe

Then choose: use Rail as is, add a thin herdr plugin and send features upstream, or build a full client.
