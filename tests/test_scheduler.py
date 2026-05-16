import pytest
import sqlite3
import os
from datetime import datetime, timedelta
from scripts.scheduler_db import get_db, init_db, enqueue, _get_next_slot, get_next_upload

# Use a temporary file for DB testing since :memory: creates a new DB per connection
TEST_DB = "output/test_queue.db"

@pytest.fixture(autouse=True)
def setup_teardown():
    try:
        if os.path.exists(TEST_DB):
            os.remove(TEST_DB)
    except: pass
    yield
    try:
        if os.path.exists(TEST_DB):
            os.remove(TEST_DB)
    except: pass

def test_init_db():
    init_db(TEST_DB)
    with get_db(TEST_DB) as conn:
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='queue'").fetchall()
        assert len(tables) == 1

def test_slot_assignment_exact_times():
    init_db(TEST_DB)
    
    # We will start from a fixed Monday so we can predict the exact datetime
    # 2026-05-18 is a Monday
    start_time = datetime(2026, 5, 18, 9, 0, 0)
    
    # Next longform should be Mon 10:00 (since we start at 09:00)
    slot1 = _get_next_slot("longform", start_time, TEST_DB)
    assert slot1.hour == 10
    assert slot1.minute == 0
    assert slot1.weekday() == 0 # Monday
    
    # Write it to DB to simulate enqueue
    with get_db(TEST_DB) as conn:
        conn.execute("INSERT INTO queue (topic, type, scheduled_for) VALUES (?, ?, ?)", 
                    ("test1", "longform", slot1.strftime("%Y-%m-%d %H:%M:%S")))
    
    # Next shorts from the same start_time should be Tue 18:00
    slot2 = _get_next_slot("shorts", start_time, TEST_DB)
    assert slot2.hour == 18
    assert slot2.minute == 0
    assert slot2.weekday() == 1 # Tuesday

def test_duplicate_topic_guard():
    init_db(TEST_DB)
    # Clear DB
    with get_db(TEST_DB) as conn:
        conn.execute("DELETE FROM queue")
        
    enqueue("The history of AI", "longform", db_path=TEST_DB)
    
    # Enqueueing same topic should fail
    with pytest.raises(ValueError) as excinfo:
        enqueue("The History of AI", "longform", db_path=TEST_DB)
        
    assert "Duplicate topic" in str(excinfo.value)
    
def test_24_hour_limit_guard():
    init_db(TEST_DB)
    # Clear DB
    with get_db(TEST_DB) as conn:
        conn.execute("DELETE FROM queue")
        
    # We force insert 3 videos into a single 24-hour window
    base_time = datetime(2026, 5, 18, 10, 0, 0)
    with get_db(TEST_DB) as conn:
        conn.execute("INSERT INTO queue (topic, type, scheduled_for) VALUES (?, ?, ?)", ("t1", "longform", (base_time).strftime("%Y-%m-%d %H:%M:%S")))
        conn.execute("INSERT INTO queue (topic, type, scheduled_for) VALUES (?, ?, ?)", ("t2", "longform", (base_time + timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")))
        conn.execute("INSERT INTO queue (topic, type, scheduled_for) VALUES (?, ?, ?)", ("t3", "longform", (base_time + timedelta(hours=4)).strftime("%Y-%m-%d %H:%M:%S")))
        
    # Now when we try to get a slot around base_time, it should skip to the next day due to 24h limit
    # We patch _get_next_slot temporarily to start searching from base_time
    
    import scripts.scheduler_db
    original_now = scripts.scheduler_db.datetime
    
    class MockDatetime:
        @classmethod
        def now(cls):
            return base_time
        @classmethod
        def strptime(cls, *args, **kwargs):
            return datetime.strptime(*args, **kwargs)
            
    scripts.scheduler_db.datetime = MockDatetime
    
    try:
        # Enqueue should find a slot, but NOT on May 18th because there are already 3 there.
        # So it should be shifted to May 19th (Wait, longform doesn't run on Tue, so it should be Wed 10:00 -> May 20th)
        slot = enqueue("t4", "longform", db_path=TEST_DB)
        assert slot.day == 20 # Wed May 20th
        assert slot.hour == 10
    finally:
        scripts.scheduler_db.datetime = original_now
