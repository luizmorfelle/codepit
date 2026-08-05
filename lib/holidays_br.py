"""Brazilian national holidays, computed locally (no network, no dependencies)."""
from datetime import date, timedelta


def easter(year):
    """Easter Sunday (Anonymous Gregorian / Meeus algorithm)."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    ell = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * ell) // 451
    month = (h + ell - 7 * m + 114) // 31
    day = ((h + ell - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def holidays(year):
    """Map of {date: (name, kind)}; kind = 'holiday' | 'optional'. On a collision (a movable
    holiday landing on a fixed one, e.g. Good Friday on April 21st) the names are merged."""
    es = easter(year)
    entries = [
        (date(year, 1, 1), "New Year's Day", "holiday"),
        (date(year, 4, 21), "Tiradentes Day", "holiday"),
        (date(year, 5, 1), "Labour Day", "holiday"),
        (date(year, 9, 7), "Independence Day", "holiday"),
        (date(year, 10, 12), "Our Lady of Aparecida", "holiday"),
        (date(year, 11, 2), "All Souls' Day", "holiday"),
        (date(year, 11, 15), "Republic Day", "holiday"),
        (date(year, 12, 25), "Christmas Day", "holiday"),
        (es - timedelta(days=2), "Good Friday", "holiday"),
        (es - timedelta(days=47), "Carnival", "optional"),
        (es + timedelta(days=60), "Corpus Christi", "optional"),
    ]
    # Black Consciousness Day: a national holiday from 2024 on (Law 14.759/2023).
    if year >= 2024:
        entries.append((date(year, 11, 20), "Black Consciousness Day", "holiday"))
    result = {}
    for d, name, kind in entries:
        if d in result:
            prev_name, prev_kind = result[d]
            name = f"{prev_name} / {name}"
            kind = "holiday" if "holiday" in (prev_kind, kind) else "optional"
        result[d] = (name, kind)
    return result


def holiday_for(d):
    """(name, kind) if the date is a national holiday, else None."""
    return holidays(d.year).get(d)
