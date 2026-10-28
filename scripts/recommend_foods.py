"""CLI: python scripts/recommend_foods.py --goal increase_protein [--goal lower_sugars]"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from macromatch.recommend import main  # noqa: E402
if __name__ == '__main__':
    raise SystemExit(main())
