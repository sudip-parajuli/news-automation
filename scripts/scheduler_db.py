import sqlite3
import os
from datetime import datetime, timedelta

def get_db(db_path="output/queue.db"):
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(db_path="output/queue.db"):
    with get_db(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT NOT NULL,
                type TEXT NOT NULL,
                scheduled_for TIMESTAMP NOT NULL,
                status TEXT DEFAULT 'queued',
                video_path TEXT,
                youtube_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

def _get_next_slot(video_type: str, start_from: datetime, db_path: str) -> datetime:
    # long-form: Tue 22:00, Thu 22:00 (UTC)
    # shorts: Mon-Fri 17:00, Sat-Sun 15:00 (UTC)
    candidate = start_from.replace(minute=0, second=0, microsecond=0)
    
    while True:
        valid_slot = False
        weekday = candidate.weekday() # 0 = Mon, 6 = Sun
        hour = candidate.hour
        
        if video_type == "longform":
            if weekday in [1, 3] and hour == 22:
                valid_slot = True
        else: # shorts
            if weekday in [0, 1, 2, 3, 4] and hour == 17:
                valid_slot = True
            elif weekday in [5, 6] and hour == 15:
                valid_slot = True
                
        if valid_slot:
            with get_db(db_path) as conn:
                existing = conn.execute("SELECT 1 FROM queue WHERE scheduled_for = ?", (candidate.strftime("%Y-%m-%d %H:%M:%S"),)).fetchone()
            if not existing:
                return candidate
                
        candidate += timedelta(hours=1)


def enqueue(topic: str, video_type: str, db_path="output/queue.db"):
    init_db(db_path)
    
    with get_db(db_path) as conn:
        # Check duplicate topic in last 14 days
        fourteen_days_ago = (datetime.utcnow() - timedelta(days=14)).strftime("%Y-%m-%d %H:%M:%S")
        dup = conn.execute("""
            SELECT scheduled_for FROM queue 
            WHERE LOWER(topic) = LOWER(?) AND scheduled_for >= ?
            ORDER BY scheduled_for DESC LIMIT 1
        """, (topic, fourteen_days_ago)).fetchone()
        
        if dup:
            days_ago = (datetime.utcnow() - datetime.strptime(dup["scheduled_for"], "%Y-%m-%d %H:%M:%S")).days
            if days_ago < 0: days_ago = 0 # if it's in the future
            raise ValueError(f"Duplicate topic: '{topic}' was posted {days_ago} days ago (or is already queued).")
            
        # Find next slot
        now = datetime.utcnow()
        slot = _get_next_slot(video_type, now, db_path)
        
        # Check 24 hour limit (max 3 videos)
        window_start = (slot - timedelta(hours=12)).strftime("%Y-%m-%d %H:%M:%S")
        window_end = (slot + timedelta(hours=12)).strftime("%Y-%m-%d %H:%M:%S")
        
        count = conn.execute("""
            SELECT COUNT(*) FROM queue 
            WHERE scheduled_for >= ? AND scheduled_for <= ?
        """, (window_start, window_end)).fetchone()[0]
        
        if count >= 3:
            # Shift search forward 24h from the slot to avoid bunching
            slot = _get_next_slot(video_type, slot + timedelta(days=1), db_path)
            
        # 30 min gap is intrinsically handled by our slot rules (which are hours apart),
        # but to be safe:
        conflict = conn.execute("""
            SELECT 1 FROM queue 
            WHERE abs(julianday(scheduled_for) - julianday(?)) * 24 * 60 < 30
        """, (slot.strftime("%Y-%m-%d %H:%M:%S"),)).fetchone()
        
        if conflict:
            slot = _get_next_slot(video_type, slot + timedelta(hours=1), db_path)
            
        conn.execute("""
            INSERT INTO queue (topic, type, scheduled_for, status)
            VALUES (?, ?, ?, 'queued')
        """, (topic, video_type, slot.strftime("%Y-%m-%d %H:%M:%S")))
        
        return slot

def get_next_upload(db_path="output/queue.db"):
    init_db(db_path)
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    with get_db(db_path) as conn:
        rows = conn.execute("""
            SELECT * FROM queue 
            WHERE status = 'queued' AND scheduled_for <= ?
            ORDER BY scheduled_for ASC
        """, (now,)).fetchall()
        return [dict(r) for r in rows]

def mark_status(item_id: int, status: str, video_path: str = None, youtube_id: str = None, db_path="output/queue.db"):
    with get_db(db_path) as conn:
        if video_path and youtube_id:
            conn.execute("UPDATE queue SET status = ?, video_path = ?, youtube_id = ? WHERE id = ?", (status, video_path, youtube_id, item_id))
        elif video_path:
            conn.execute("UPDATE queue SET status = ?, video_path = ? WHERE id = ?", (status, video_path, item_id))
        else:
            conn.execute("UPDATE queue SET status = ? WHERE id = ?", (status, item_id))
