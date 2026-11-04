#!/usr/bin/env python3
"""Delete runtime state and restore seeded demo cases. Requires --confirm RESET."""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description="Reset Doctor Intelligence demo runtime state")
    parser.add_argument("--confirm", required=True, help='Must be exactly "RESET"')
    args = parser.parse_args()
    if args.confirm != "RESET":
        print('Refusing to reset: pass --confirm RESET')
        raise SystemExit(2)

    runtime = BACKEND_ROOT / "data" / "runtime"
    if runtime.exists():
        shutil.rmtree(runtime)
    runtime.mkdir(parents=True, exist_ok=True)
    (runtime / ".gitkeep").write_text("", encoding="utf-8")
    print(f"Runtime state cleared at {runtime}")
    print("Restart the backend to reinitialize state.json from seed CSVs.")


if __name__ == "__main__":
    main()
