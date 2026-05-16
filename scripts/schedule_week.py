import sys
from datetime import datetime
from scripts.scheduler_db import enqueue

def schedule_week(topics: list):
    print("Scheduling Week:")
    for i, topic in enumerate(topics):
        topic = topic.strip()
        if not topic:
            continue
            
        video_type = "longform" if i < 3 else "shorts"
        try:
            slot = enqueue(topic, video_type)
            print(f"- '{topic}' ({video_type}) -> {slot.strftime('%A %Y-%m-%d %H:%M')}")
        except ValueError as e:
            print(f"- '{topic}' skipped: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Check if topics are passed as a single comma-separated string
        if "," in sys.argv[1]:
            topics = [t.strip() for t in sys.argv[1].split(",") if t.strip()]
        else:
            topics = [t.strip() for t in sys.argv[1:] if t.strip()]
        schedule_week(topics)
    else:
        print("Usage: python schedule_week.py 'topic1, topic2, topic3'")
