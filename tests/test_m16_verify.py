"""M16 pure semantic checks; complete offline rebuild is exercised by CI script."""
from __future__ import annotations

import pytest

from scripts.m16_verify import (
    VerificationError, EXPECTED_COUNTS, FINGERPRINT_TABLES,
    assert_expected_counts, assert_same_semantics, semantic_fingerprint,
)


def test_fingerprint_independent_of_row_order():
    cols = ["food_key", "g"]
    a = [("snap:1", 2.5), ("snap:2", 1.0)]
    assert semantic_fingerprint(cols, a) == semantic_fingerprint(cols, list(reversed(a)))


def test_fingerprint_preserves_null_versus_zero():
    assert semantic_fingerprint(["sugar"], [(None,)]) != semantic_fingerprint(["sugar"], [(0,)])


def test_fingerprint_preserves_duplicate_rows():
    assert semantic_fingerprint(["fdc"], [(1,)]) != semantic_fingerprint(["fdc"], [(1,), (1,)])


def test_fingerprint_preserves_column_order():
    assert semantic_fingerprint(["a", "b"], [(1, 2)]) != semantic_fingerprint(["b", "a"], [(1, 2)])


def test_fingerprint_preserves_numeric_differences():
    assert semantic_fingerprint(["protein"], [(2.82,)]) != semantic_fingerprint(["protein"], [(2.83,)])


def test_expected_counts_pass_on_correct_snapshot():
    assert_expected_counts(dict(EXPECTED_COUNTS))


def test_expected_counts_reject_missing_table():
    counts = dict(EXPECTED_COUNTS)
    del counts["cur_food_total_sugars"]
    with pytest.raises(VerificationError, match="cur_food_total_sugars"):
        assert_expected_counts(counts)


def test_expected_counts_reject_source_drift():
    counts = dict(EXPECTED_COUNTS)
    counts["raw_foods"] = 165
    with pytest.raises(VerificationError, match="raw_foods"):
        assert_expected_counts(counts)


def test_comparison_accepts_identical_semantic_summaries():
    a = {"counts": {"raw_foods": 166}, "fingerprints": {"cur_food_catalog": "a"}}
    assert_same_semantics(a, {"counts": {"raw_foods": 166}, "fingerprints": {"cur_food_catalog": "a"}})


def test_comparison_rejects_changed_table_fingerprint():
    with pytest.raises(VerificationError, match="fingerprints"):
        assert_same_semantics({"fingerprints": {"t": "aaa"}}, {"fingerprints": {"t": "bbb"}})


def test_essential_curated_layers_are_fingerprinted():
    assert {"cur_food_catalog", "cur_food_visibility", "cur_recommendation_inputs",
            "cur_food_total_sugars", "int_food_quality"}.issubset(FINGERPRINT_TABLES)


def test_rebuild_uses_existing_m04_to_m11_functions_in_order(monkeypatch, tmp_path):
    """No duplicate build implementation; the orchestrator must call accepted modules."""
    import sys
    from types import ModuleType
    from scripts.m16_verify import _rebuild

    call_order = []
    stages = (
        ("ingest", "build_database", "M04"),
        ("stage", "build_staging", "M05"),
        ("stage_nutrients", "build_nutrient_staging", "M06"),
        ("standardise", "build_standardisation", "M07"),
        ("quality", "build_quality", "M08"),
        ("classify_foods", "build_classification", "M09"),
        ("curate", "build_curation", "M10"),
        ("total_sugars", "build_total_sugars", "M11"),
    )

    for module_name, function_name, marker in stages:
        module = ModuleType("macromatch." + module_name)

        def stub(*args, marker=marker, **kwargs):
            call_order.append(marker)

        setattr(module, function_name, stub)
        monkeypatch.setitem(sys.modules, "macromatch." + module_name, module)

    _rebuild(tmp_path / "fake.duckdb")
    assert call_order == [stage[2] for stage in stages]
