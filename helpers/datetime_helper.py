from datetime import datetime

def round_to_one_minute(dt: datetime) -> datetime:
    return datetime(
        dt.year,dt.month,dt.day,dt.hour,dt.minute,0,
    )
     