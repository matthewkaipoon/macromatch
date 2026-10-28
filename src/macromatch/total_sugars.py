"""Additive offline sugar processing for M07/M08/M10. Does not modify old tables."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[2]
MODELS = (
    'sql/intermediate/03_standardise_total_sugars.sql',
    'sql/quality/04_total_sugars_quality.sql',
    'sql/curated/05_food_sugars.sql',
)


class SugarDataError(RuntimeError):
    pass


def _tables(con):
    return {name for (name,) in con.execute('SHOW TABLES').fetchall()}


def sugar_report(con) -> dict:
    required = {'int_total_sugars_entries', 'int_total_sugars_quality', 'cur_food_total_sugars'}
    if not required.issubset(_tables(con)):
        raise SugarDataError('Missing sugar extension tables; run sugar build first')
    n, unique = con.execute('SELECT COUNT(*), COUNT(DISTINCT food_key) FROM cur_food_total_sugars').fetchone()
    entries = con.execute('SELECT COUNT(*) FROM int_total_sugars_entries').fetchone()[0]
    status = dict(con.execute('SELECT quality_status, COUNT(*) FROM int_total_sugars_quality GROUP BY quality_status ORDER BY quality_status').fetchall())
    a = con.execute('''
        SELECT COUNT(*) FILTER (WHERE count_1063+count_2000>0),
               COUNT(*) FILTER (WHERE count_1063>0 AND count_2000>0),
               COUNT(*) FILTER (WHERE dual_id_review_flag),
               COUNT(*) FILTER (WHERE explicit_zero_sugars)
        FROM int_total_sugars_quality
    ''').fetchone()
    return {
        'sugar_source_entries': entries,
        'curated_sugar_rows': n,
        'unique_sugar_food_keys': unique,
        'foods_with_sugar_source_entries': a[0],
        'foods_with_both_definitions': a[1],
        'dual_definition_conflicts': a[2],
        'validated_zero_sugars': a[3],
        'foods_with_validated_sugars': status.get('valid', 0),
        'status_counts': status,
    }


def build_total_sugars(db_path: Path) -> dict:
    db_path = Path(db_path)
    if not db_path.is_file():
        raise SugarDataError('DuckDB database not found')
    con = duckdb.connect(str(db_path))
    begun = False
    try:
        needed = {'stg_foods', 'stg_food_nutrients', 'cur_food_catalog'}
        if not needed.issubset(_tables(con)):
            raise SugarDataError('Run M06 and M10 first: ' + ', '.join(sorted(needed-_tables(con))))
        expected, unique = con.execute('SELECT COUNT(*), COUNT(DISTINCT food_key) FROM stg_foods').fetchone()
        if not expected or unique != expected:
            raise SugarDataError('Missing or duplicate upstream food keys')
        con.execute('BEGIN TRANSACTION')
        begun = True
        for relative in MODELS:
            con.execute((ROOT / relative).read_text(encoding='utf-8'))
        out = sugar_report(con)
        if out['curated_sugar_rows'] != expected or out['unique_sugar_food_keys'] != expected:
            raise SugarDataError('Sugar profile lost or duplicated source foods')
        source_entries = con.execute('SELECT COUNT(*) FROM stg_food_nutrients WHERE nutrient_id IN (1063,2000)').fetchone()[0]
        if source_entries != out['sugar_source_entries']:
            raise SugarDataError('Sugar source-entry reconciliation failed')
        unlinked = con.execute('''
            SELECT COUNT(*) FROM stg_foods f
            LEFT JOIN cur_food_total_sugars s ON s.food_key=f.food_key
            WHERE s.food_key IS NULL
        ''').fetchone()[0]
        bad = con.execute('''
            SELECT COUNT(*) FROM cur_food_total_sugars
            WHERE (total_sugars_status='valid' AND total_sugars_g IS NULL)
               OR (total_sugars_status<>'valid' AND total_sugars_g IS NOT NULL)
               OR (total_sugars_g IS NOT NULL AND (total_sugars_g<0 OR total_sugars_g>100 OR NOT isfinite(total_sugars_g)))
        ''').fetchone()[0]
        if unlinked or bad:
            raise SugarDataError('Sugar provenance, validity, or coverage invariant failed')
        con.execute('COMMIT')
        begun = False
        return {'database': str(db_path), 'source_foods': expected, **out}
    except Exception:
        if begun:
            con.execute('ROLLBACK')
        raise
    finally:
        con.close()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='M11 prerequisite: offline, non-destructive total sugars extension')
    parser.add_argument('--db', type=Path, default=Path('data/processed/macromatch.duckdb'))
    parser.add_argument('--report', action='store_true', help='Read only existing extension tables')
    args = parser.parse_args(argv)
    try:
        if args.report:
            if not args.db.is_file():
                raise SugarDataError('DuckDB database not found')
            con = duckdb.connect(str(args.db), read_only=True)
            try:
                result = {'database': str(args.db), **sugar_report(con)}
            finally:
                con.close()
        else:
            result = build_total_sugars(args.db)
        print(json.dumps(result, indent=2))
        return 0
    except (SugarDataError, FileNotFoundError, OSError, duckdb.Error) as exc:
        print(f'Sugar extension failed: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
