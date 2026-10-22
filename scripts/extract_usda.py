"""CLI entry point from repository root: python scripts/extract_usda.py ..."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from macromatch.extract import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
