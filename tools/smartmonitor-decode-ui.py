#!/usr/bin/env python3

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from library.pythoncheck import check_python_version
from library.smartmonitor_ui import decode_ui_file

check_python_version()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Decode vendor SmartMonitor .ui files into plain XML."
    )
    parser.add_argument("input", help="Path to encrypted vendor .ui file")
    parser.add_argument(
        "-o",
        "--output",
        help="Output XML path. Defaults to input path with .xml suffix.",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Print decoded XML to stdout instead of writing a file.",
    )
    args = parser.parse_args()

    input_path = Path(args.input).expanduser()
    if not input_path.is_file():
        raise SystemExit(f"Input file not found: {input_path}")

    xml_bytes = decode_ui_file(input_path)
    if not xml_bytes.lstrip().startswith(b"<?xml"):
        raise SystemExit(
            "Decoded output does not look like XML. The input may not be a SmartMonitor .ui file."
        )

    if args.stdout:
        print(xml_bytes.decode("utf-8"), end="")
        return 0

    output_path = (
        Path(args.output).expanduser()
        if args.output
        else input_path.with_suffix(input_path.suffix + ".xml")
    )
    output_path.write_bytes(xml_bytes)
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
