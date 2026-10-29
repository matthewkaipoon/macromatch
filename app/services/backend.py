"""Thin UI adapter. Import and reuse M11/M12 services; never reimplement their logic."""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from macromatch.discovery import (  # noqa: E402
    DiscoveryError, catalog_overview, filter_options, get_food, search_foods,
)
from macromatch.recommend import recommend  # noqa: E402
from macromatch.compare import FoodSelection, compare_foods  # noqa: E402


def database_path() -> Path:
    """Local-only file. This path is gitignored and is never created by Streamlit."""
    return ROOT / "data" / "processed" / "macromatch.duckdb"


def recommend_preview(db_path: Path, goal: str, *, top: int = 5) -> dict:
    return recommend(db_path, [goal], top=top, incomplete_top=3)


def compare_preview(db_path: Path, first_id: int, first_g: float,
                    second_id: int, second_g: float) -> dict:
    return compare_foods(db_path, [FoodSelection(str(first_id), first_g),
                                   FoodSelection(str(second_id), second_g)])
