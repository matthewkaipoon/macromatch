"""CLI: python scripts/classify_foods.py --db data/processed/macromatch.duckdb"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from macromatch.classify_foods import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
