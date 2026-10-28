"""M12 CLI: python scripts/compare_foods.py --food 170379@100 --food 747447@150"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from macromatch.compare import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
