#!/usr/bin/env python3
"""Build the Thunderbird add-on and register its native messaging host.

Writes dist/email-tui-bridge.xpi and one small JSON manifest that tells Thunderbird
where the host program is. It does not change Thunderbird or read any mail.
"""

import argparse
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXTENSION = ROOT / "bridge" / "extension"
HOST_NAME = "email_tui_bridge"


def build_xpi(output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(EXTENSION.iterdir()):
            archive.write(path, path.name)


def write_host_manifest(directory: Path) -> Path:
    extension_id = json.loads((EXTENSION / "manifest.json").read_text())[
        "browser_specific_settings"
    ]["gecko"]["id"]
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{HOST_NAME}.json"
    path.write_text(
        json.dumps(
            {
                "name": HOST_NAME,
                "description": "Email TUI Bridge host",
                "path": str(ROOT / "bin" / "email-bridge-host"),
                "type": "stdio",
                "allowed_extensions": [extension_id],
            },
            indent=2,
        )
        + "\n"
    )
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xpi", type=Path, default=ROOT / "dist" / "email-tui-bridge.xpi")
    parser.add_argument(
        "--manifest-dir",
        type=Path,
        default=Path.home() / ".mozilla" / "native-messaging-hosts",
    )
    args = parser.parse_args()
    build_xpi(args.xpi)
    print(f"add-on:   {args.xpi}")
    print(f"manifest: {write_host_manifest(args.manifest_dir)}")


if __name__ == "__main__":
    main()
