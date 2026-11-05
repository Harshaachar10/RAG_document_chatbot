"""Clear runtime state so the identity pipeline reseeds on next API start."""
from __future__ import annotations

from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1] / "data" / "runtime"


def main() -> None:
    RUNTIME.mkdir(parents=True, exist_ok=True)
    for name in ("state.json", "state.previous.json"):
        path = RUNTIME / name
        if path.exists():
            path.unlink()
            print(f"removed {path}")
    print("Runtime cleared. Restart the API to rebuild from backend/data/*.csv")


if __name__ == "__main__":
    main()
