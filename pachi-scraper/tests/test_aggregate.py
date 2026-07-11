from pachi.aggregate import combined_probability, daily_model_summary
from pachi.storage import connect, load_readings, save_readings


def test_combined_probability():
    assert combined_probability({"start": 6800, "bb": 22, "rb": 20}) == round(6800 / 42, 1)
    assert combined_probability({"start": 150, "bb": 0, "rb": 0}) is None
    assert combined_probability({"bb": 10, "rb": 5}) is None


def test_storage_upsert_and_summary(tmp_path):
    db = tmp_path / "test.db"
    conn = connect(db)

    units = [
        {"unit_no": "1001", "metrics": {"bb": 10, "rb": 5, "start": 3000}},
        {"unit_no": "1002", "metrics": {"bb": 20, "rb": 10, "start": 5000}},
    ]
    save_readings(conn, "2026-07-11", "テストホール", "ジャグラー", units)

    # 同じ日・同じ台を再保存すると上書きされる（重複しない）
    units[0]["metrics"]["bb"] = 12
    save_readings(conn, "2026-07-11", "テストホール", "ジャグラー", units)

    readings = load_readings(conn)
    assert len(readings) == 2
    assert readings[0]["bb"] == 12

    summary = daily_model_summary(readings)
    assert len(summary) == 1
    row = summary[0]
    assert row["units"] == 2
    assert row["total_start"] == 8000
    assert row["total_bb"] == 32
    assert row["combined_prob"] == round(8000 / (32 + 15), 1)
