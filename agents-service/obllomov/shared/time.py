import datetime as dt

NOW = lambda : dt.datetime.now(dt.timezone.utc)

def to_utc(datetime: dt.datetime):
    return datetime.astimezone(dt.timezone.utc)
