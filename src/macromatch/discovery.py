"""M13: read-only food discovery on the M10/M11 curated layer.

No API requests, ranking, nutrient imputation, or data writes. SQL values are
parameter-bound, with a stable sort and explicit default-visibility switch.
"""
from __future__ import annotations

from pathlib import Path
import re

import duckdb

ROOT = Path(__file__).resolve().parents[2]
SQL_FILE = ROOT / "sql" / "discovery" / "01_food_discovery.sql"
REQUIRED_TABLES = frozenset({"cur_food_catalog", "cur_food_total_sugars", "cur_food_visibility"})
MAX_PAGE_SIZE = 50


class DiscoveryError(ValueError):
    """Invalid request or incomplete local curated data."""


def _connect(db_path: Path):
    db_path = Path(db_path)
    if not db_path.is_file():
        raise DiscoveryError("Local DuckDB file is missing. Build M10 and the sugar extension first.")
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        found = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if REQUIRED_TABLES - found:
            raise DiscoveryError("Missing curated tables: " + ", ".join(sorted(REQUIRED_TABLES - found)))
    except Exception:
        con.close()
        raise
    return con


def _sql() -> str:
    return SQL_FILE.read_text(encoding="utf-8").strip().rstrip(";")


def _filters(*, query: str, group: str | None, data_type: str | None,
             preparation: str | None, include_alternates: bool) -> tuple[str, list]:
    if not isinstance(query, str) or len(query) > 120:
        raise DiscoveryError("Search text must contain at most 120 characters")
    terms = re.findall(r"[a-z0-9]+", query.casefold())
    if len(terms) > 10:
        raise DiscoveryError("Search has too many words (maximum 10)")
    conditions: list[str] = []
    args: list = []
    exact_fdc_lookup = len(terms) == 1 and terms[0].isdigit()
    # Explicit ID lookup must still locate approved alternates (M10 promise).
    if not include_alternates and not exact_fdc_lookup:
        conditions.append("is_default_discovery_visible = TRUE")
    if terms:
        if exact_fdc_lookup:
            conditions.append("fdc_id = ?")
            args.append(int(terms[0]))
        else:
            for term in terms:
                conditions.append("contains(coalesce(search_name, ''), ?)")
                args.append(term)
    for col, value in (("proposed_group", group), ("data_type", data_type),
                       ("preparation_state", preparation)):
        if value is not None:
            if not isinstance(value, str) or not value.strip():
                raise DiscoveryError("Filter values must be nonempty strings")
            conditions.append(f"{col} = ?")  # col is hardcoded, never user supplied
            args.append(value)
    return (" WHERE " + " AND ".join(conditions) if conditions else ""), args


def search_foods(db_path: Path, *, query: str = "", group: str | None = None,
                 data_type: str | None = None, preparation: str | None = None,
                 include_alternates: bool = False, limit: int = 20,
                 offset: int = 0) -> dict:
    """Return a stable, filtered page and full match count; no writes."""
    if (isinstance(limit, bool) or not isinstance(limit, int)
            or not 1 <= limit <= MAX_PAGE_SIZE):
        raise DiscoveryError(f"Page size must be between 1 and {MAX_PAGE_SIZE}")
    if isinstance(offset, bool) or not isinstance(offset, int) or not 0 <= offset <= 10000:
        raise DiscoveryError("Offset must be between 0 and 10000")
    if not isinstance(include_alternates, bool):
        raise DiscoveryError("include_alternates must be true or false")
    where, args = _filters(query=query, group=group, data_type=data_type,
                           preparation=preparation, include_alternates=include_alternates)
    base = f"({_sql()}) AS foods"
    con = _connect(db_path)
    try:
        count = con.execute(f"SELECT count(*) FROM {base}{where}", args).fetchone()[0]
        # Name/FDC/source order is deterministic across runs and snapshots.
        cursor = con.execute(f"""
            SELECT * FROM {base}{where}
            ORDER BY lower(coalesce(display_name, '')), fdc_id, snapshot_id, food_key
            LIMIT ? OFFSET ?
        """, [*args, limit, offset])
        fields = [desc[0] for desc in cursor.description]
        items = [dict(zip(fields, row)) for row in cursor.fetchall()]
        return {"total": int(count), "limit": limit, "offset": offset, "foods": items}
    finally:
        con.close()


def get_food(db_path: Path, food_key: str) -> dict | None:
    """Exact food-key lookup: approved alternates are still discoverable explicitly."""
    if not isinstance(food_key, str) or not food_key.strip() or len(food_key) > 200:
        raise DiscoveryError("Provide an exact snapshot-aware food_key")
    con = _connect(db_path)
    try:
        cursor = con.execute(f"SELECT * FROM ({_sql()}) AS foods WHERE food_key = ?", [food_key])
        found = cursor.fetchone()
        if found is None:
            return None
        return dict(zip([d[0] for d in cursor.description], found))
    finally:
        con.close()


def catalog_overview(db_path: Path) -> dict:
    """All figures are measured from the local database, never hardcoded."""
    con = _connect(db_path)
    try:
        row = con.execute(f"""
            SELECT count(*) AS searchable,
                count(*) FILTER (WHERE is_default_discovery_visible) AS default_visible,
                count(*) FILTER (WHERE total_sugars_status = 'valid') AS valid_sugars,
                count(*) FILTER (WHERE total_sugars_status <> 'valid') AS missing_or_invalid_sugars,
                count(*) FILTER (WHERE review_required) AS review_flags
            FROM ({_sql()}) AS foods
        """).fetchone()
        return dict(zip(("searchable", "default_visible", "valid_sugars",
                         "missing_or_invalid_sugars", "review_flags"), row))
    finally:
        con.close()


def filter_options(db_path: Path) -> dict[str, list[str]]:
    con = _connect(db_path)
    try:
        result = {}
        for col, key in (("proposed_group", "groups"), ("data_type", "sources"),
                         ("preparation_state", "preparations")):
            rows = con.execute(f"""
                SELECT DISTINCT {col} FROM ({_sql()}) AS foods
                WHERE {col} IS NOT NULL ORDER BY {col}
            """).fetchall()
            result[key] = [r[0] for r in rows]
        return result
    finally:
        con.close()
