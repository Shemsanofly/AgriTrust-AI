"""An existing database from an older version gains new nullable columns at startup."""

from sqlalchemy import create_engine, inspect, text

from app import models  # noqa: F401  (register tables)
from app.db import add_missing_columns


def test_old_database_gets_new_columns_without_losing_data(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with engine.begin() as conn:
        # "crop" as an older version created it: no acreage column.
        conn.execute(text("CREATE TABLE crop (id INTEGER PRIMARY KEY, farm_id INTEGER, crop_type VARCHAR, variety VARCHAR, planting_date DATE, expected_harvest_date DATE, growth_stage VARCHAR)"))
        conn.execute(text("INSERT INTO crop (farm_id, crop_type, planting_date, growth_stage) VALUES (1, 'maize', '2026-01-01', 'initial')"))

    added = add_missing_columns(engine)

    assert "crop.acreage" in added
    assert "acreage" in {c["name"] for c in inspect(engine).get_columns("crop")}
    with engine.connect() as conn:
        assert conn.execute(text("SELECT crop_type, acreage FROM crop")).one() == ("maize", None)
    assert add_missing_columns(engine) == []  # second run: nothing to do
