"""Basic environment verification tests for MacroMatch."""

import duckdb

from macromatch import __version__


def test_package_import():
    """MacroMatch package can be imported."""
    assert __version__ == "0.1.0"


def test_duckdb_connection():
    """DuckDB can execute a basic SQL query."""
    connection = duckdb.connect(":memory:")

    try:
        result = connection.execute(
            "SELECT 1 + 1"
        ).fetchone()

        assert result[0] == 2

    finally:
        connection.close()