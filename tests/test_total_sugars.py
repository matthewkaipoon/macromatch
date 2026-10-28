"""Sugar-extension transaction tests plus frozen 166-food end-to-end integration."""
from pathlib import Path
import duckdb
import pytest
from macromatch.total_sugars import build_total_sugars, SugarDataError, sugar_report
from macromatch.recommend import recommend

ROOT=Path(__file__).resolve().parents[1]


def base_db(tmp_path, records):
    path=tmp_path/'minimal.duckdb'
    con=duckdb.connect(str(path))
    con.execute('CREATE TABLE stg_foods(food_key VARCHAR,snapshot_id VARCHAR,fdc_id BIGINT,data_type VARCHAR)')
    con.execute('CREATE TABLE stg_food_nutrients(food_key VARCHAR,snapshot_id VARCHAR,fdc_id BIGINT,nutrient_entry_key VARCHAR,nutrient_id BIGINT,nutrient_name VARCHAR,unit_name VARCHAR,amount DOUBLE)')
    con.execute('CREATE TABLE cur_food_catalog(food_key VARCHAR,snapshot_id VARCHAR,fdc_id BIGINT)')
    for fid,dtype,values in records:
        key=f'snap:{fid}'
        con.execute('INSERT INTO stg_foods VALUES (?,?,?,?)',[key,'snap',fid,dtype])
        con.execute('INSERT INTO cur_food_catalog VALUES (?,?,?)',[key,'snap',fid])
        for i,(nid,amt,unit) in enumerate(values):
            con.execute('INSERT INTO stg_food_nutrients VALUES (?,?,?,?,?,?,?,?)',
                        [key,'snap',fid,f'{key}:{i}',nid,'Total Sugars',unit,amt])
    con.close()
    return path


def test_empty_sugars_keeps_null_rows(tmp_path):
    db=base_db(tmp_path,[(1,'Foundation',[])])
    r=build_total_sugars(db)
    assert r['curated_sugar_rows']==1 and r['foods_with_validated_sugars']==0


def test_valid_1063_and_2000_and_untouched_source(tmp_path):
    db=base_db(tmp_path,[(1,'Foundation',[(1063,12.221,'g'),(2000,12.22,'g')]),
                          (2,'SR Legacy',[(2000,3.5,'g')]),(3,'Foundation',[])])
    r=build_total_sugars(db)
    assert r['sugar_source_entries']==3
    assert r['foods_with_validated_sugars']==2
    assert r['foods_with_both_definitions']==1 and r['dual_definition_conflicts']==0
    con=duckdb.connect(str(db),read_only=True)
    try:
        assert con.execute('SELECT total_sugars_g,total_sugars_source_id FROM cur_food_total_sugars WHERE fdc_id=1').fetchone()==(12.221,1063)
        assert con.execute('SELECT COUNT(*) FROM stg_food_nutrients').fetchone()==(3,)
    finally: con.close()


def test_conflicting_dual_values_are_not_validated(tmp_path):
    db=base_db(tmp_path,[(1,'Foundation',[(1063,15.,'g'),(2000,12.,'g')])])
    r=build_total_sugars(db)
    assert r['status_counts']['conflicting_definitions']==1
    assert r['foods_with_validated_sugars']==0


@pytest.mark.parametrize('entries,expected',[
    ([(1063,-1,'g')],'invalid_source_entry'),
    ([(1063,200,'g')],'invalid_source_entry'),
    ([(1063,2,'kg')],'invalid_source_entry'),
    ([(1063,None,'g')],'invalid_source_entry'),
    ([(1063,2,'g'),(1063,3,'g')],'multiple_entries_same_id'),
])
def test_sugar_anomaly_screening(tmp_path,entries,expected):
    db=base_db(tmp_path,[(1,'Foundation',entries)])
    r=build_total_sugars(db)
    assert r['status_counts'][expected]==1
    assert r['foods_with_validated_sugars']==0


def test_explicit_zero_not_missing(tmp_path):
    db=base_db(tmp_path,[(1,'SR Legacy',[(2000,0,'g')])])
    r=build_total_sugars(db)
    assert r['validated_zero_sugars']==1
    assert r['foods_with_validated_sugars']==1


def test_conversion_mg_to_g(tmp_path):
    db=base_db(tmp_path,[(1,'Foundation',[(1063,1250,'mg')])])
    build_total_sugars(db)
    con=duckdb.connect(str(db),read_only=True)
    try: assert con.execute('SELECT total_sugars_g FROM cur_food_total_sugars').fetchone()==(1.25,)
    finally: con.close()


def test_sugar_build_idempotent(tmp_path):
    db=base_db(tmp_path,[(1,'Foundation',[(1063,2,'g')])])
    assert build_total_sugars(db)==build_total_sugars(db)


def test_missing_source_table_rejected(tmp_path):
    db=base_db(tmp_path,[(1,'Foundation',[])])
    con=duckdb.connect(str(db));con.execute('DROP TABLE stg_food_nutrients');con.close()
    with pytest.raises(SugarDataError, match='Run M06'):
        build_total_sugars(db)


def test_real_snapshot_end_to_end(tmp_path):
    """Rebuild M04 through M10 from committed raw JSON; no API/network calls."""
    from macromatch.ingest import build_database
    from macromatch.stage import build_staging
    from macromatch.stage_nutrients import build_nutrient_staging
    from macromatch.standardise import build_standardisation
    from macromatch.quality import build_quality
    from macromatch.classify_foods import build_classification
    from macromatch.curate import build_curation
    snap=ROOT/'data/raw/m04_catalog_v1'
    if not snap.is_dir():
        pytest.skip('Frozen snapshot unavailable outside full repository')
    db=tmp_path/'frozen.duckdb'
    build_database([snap],db)
    build_staging(db)
    build_nutrient_staging(db)
    build_standardisation(db)
    build_quality(db)
    build_classification(db)
    build_curation(db)
    r=build_total_sugars(db)
    assert r['source_foods']==166 and r['sugar_source_entries']==106
    assert r['foods_with_sugar_source_entries']==101
    assert r['foods_with_both_definitions']==5
    assert r['dual_definition_conflicts']==0
    assert r['foods_with_validated_sugars']==101
    out=recommend(db,['increase_protein','increase_calories','lower_sugars'])
    assert out['source_foods']==166
    assert out['primary_count']>0
    assert out['incomplete_count']>0
    assert all(x['score'] is None for x in out['incomplete_results'])
