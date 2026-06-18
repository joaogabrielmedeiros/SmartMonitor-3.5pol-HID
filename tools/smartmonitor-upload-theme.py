#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from library.pythoncheck import check_python_version

check_python_version()


def main():
    try:
        from library.lcd.lcd_comm_rev_a_hid import LcdCommRevAHid
        from library.log import logger
    except ModuleNotFoundError as exc:
        raise SystemExit(
            f"Missing Python dependency: {exc.name}. Install the project requirements before using this tool."
        ) from exc

    parser = argparse.ArgumentParser(description="Upload a SmartMonitor img.dat theme over Linux hidraw/HID")
    parser.add_argument("theme", type=Path, help="Path to img.dat")
    parser.add_argument("--port", default="AUTO", help="hidraw path or AUTO")
    parser.add_argument("--remote-name", default="img.dat", help="Remote filename announced to the monitor")
    parser.add_argument("--skip-reset", action="store_true", help="Do not send the pre-upload reset command")
    args = parser.parse_args()

    if not args.theme.is_file():
        raise SystemExit(f"Theme file not found: {args.theme}")

    lcd = LcdCommRevAHid(com_port=args.port)
    try:
        lcd.openSerial()
        lcd.smartmonitor_upload_theme(
            theme_path=str(args.theme),
            remote_name=args.remote_name,
            send_reset=not args.skip_reset,
        )
        logger.info("SmartMonitor theme upload finished")
    finally:
        lcd.closeSerial()


if __name__ == "__main__":
    main()
