"""Fixed team rituals (daily / planning / review). Local, no network."""
from datetime import datetime, timedelta

# weekday(): Monday=0 ... Sunday=6
WEEKDAYS = [0, 1, 2, 3, 4]
EVENTS = [
    {"name": "Daily", "days": WEEKDAYS, "hour": 8, "minute": 30},
    {"name": "Planning", "days": [0], "hour": 8, "minute": 30},
    {"name": "Review", "days": [4], "hour": 16, "minute": 30},
]

WEEKDAY_ABBR = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def next_event(now):
    """Next (datetime, name) >= now, scanning today and up to 7 days ahead. Pure."""
    for offset in range(8):
        day = (now + timedelta(days=offset)).date()
        cands = []
        for ev in EVENTS:
            if day.weekday() in ev["days"]:
                dt = datetime(day.year, day.month, day.day, ev["hour"], ev["minute"])
                if dt >= now:
                    cands.append((dt, ev["name"]))
        if cands:
            cands.sort(key=lambda pair: pair[0])
            return cands[0]
    return None


def next_event_text(now):
    """'Next: <name> in Xh Ymin' (today) or 'Next: <day> HH:MM <name>' (another day). Pure."""
    nxt = next_event(now)
    if not nxt:
        return "Next: —"
    dt, name = nxt
    if dt.date() == now.date():
        return f"Next: {name} {human_delta(dt - now)}"
    return f"Next: {WEEKDAY_ABBR[dt.weekday()]} {dt.strftime('%H:%M')} {name}"


def human_delta(delta):
    """'in Xh Ymin' / 'in Ymin' / 'past'. Pure."""
    secs = int(delta.total_seconds())
    if secs < 0:
        return "past"
    hours, rem = divmod(secs, 3600)
    minutes = rem // 60
    return f"in {hours}h {minutes}min" if hours else f"in {minutes}min"
