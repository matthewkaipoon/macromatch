"""M06 CLI entry point (run from MacroMatch repository root)."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from macromatch.stage_nutrients import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
