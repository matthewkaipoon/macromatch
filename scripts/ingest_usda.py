"""CLI entry point: python scripts/ingest_usda.py --snapshot ..."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from macromatch.ingest import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
