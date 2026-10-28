"""CLI: python scripts/build_total_sugars.py [--report] [--db PATH]."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from macromatch.total_sugars import main  # noqa: E402
if __name__ == '__main__':
    raise SystemExit(main())
