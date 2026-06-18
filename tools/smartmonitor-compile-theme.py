#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from library.pythoncheck import check_python_version
from library.smartmonitor_compile import compile_theme_file

check_python_version()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compile an experimental SmartMonitor img.dat from a vendor .ui theme."
    )
    parser.add_argument("ui", help="Path to vendor .ui")
    parser.add_argument("-o", "--output", required=True, help="Output img.dat path")
    parser.add_argument("--compare", help="Optional existing img.dat to compare against")
    args = parser.parse_args()

    compiled = compile_theme_file(args.ui)
    output_path = Path(args.output).expanduser()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(compiled)

    print(f"wrote {output_path}")
    print(f"compiled_sha256={sha256_bytes(compiled)}")

    if args.compare:
        compare_path = Path(args.compare).expanduser()
        compare_data = compare_path.read_bytes()
        print(f"compare_sha256={sha256_bytes(compare_data)}")
        print(f"byte_equal={compiled == compare_data}")
        if len(compiled) == len(compare_data):
            diff_count = sum(1 for left, right in zip(compiled, compare_data) if left != right)
            print(f"diff_bytes={diff_count}")
        else:
            print(f"compiled_size={len(compiled)} compare_size={len(compare_data)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
