"""CLI: python scripts/check_quality.py --db ..."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from macromatch.quality import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
