"""
A vibe coded cli tool to keep track of my working hours.
Be sure your system backs up `~/.toolbelt-local/clk/clk_log.json`.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from statistics import median
import tomllib

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None

UNDO_MAX = 5
PAD_REASONS = ("sickness", "child-sickness")
DEFAULT_CONFIG = {
    "full_week_hours": 42.0,
    "workload": 0.8,
    "holiday_allowance": 25.0,
    "work_day_threshold_hours": 3.0,
    "bar_unit_minutes": 30.0,
}


def tzlocal():
    if ZoneInfo is None:
        return None
    try:
        import time

        return ZoneInfo(time.tzname[0]) if time.tzname and time.tzname[0] else None
    except Exception:
        return None


TZ = tzlocal()


TOOLBELT_LOCAL = Path(
    os.environ.get("TOOLBELT_LOCAL", Path.home() / ".toolbelt-local")
)
CLK_LOCAL_DIR = TOOLBELT_LOCAL / "clk"
OLD_PATH = Path(os.path.expanduser("~/.clk_log.json"))
PATH = str(CLK_LOCAL_DIR / "clk_log.json")
LOCAL_CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "clk" / "config.toml"
OLD_USER_CONFIG_PATH = Path(os.path.expanduser("~/.clk_config.toml"))
USER_CONFIG_PATH = CLK_LOCAL_DIR / "config.toml"


def _read_toml(path):
    if not path.exists():
        return {}
    with path.open("rb") as f:
        return tomllib.load(f)


def _copy_if_missing(old_path, new_path):
    if new_path.exists() or not old_path.exists():
        return
    new_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(old_path, new_path)


def load_config():
    _copy_if_missing(OLD_USER_CONFIG_PATH, USER_CONFIG_PATH)
    config = dict(DEFAULT_CONFIG)
    config.update(_read_toml(LOCAL_CONFIG_PATH))
    config.update(_read_toml(USER_CONFIG_PATH))
    for key in DEFAULT_CONFIG:
        try:
            config[key] = float(config[key])
        except (TypeError, ValueError) as e:
            raise ValueError(f"Invalid config value for {key}: {config[key]!r}") from e
        if config[key] <= 0:
            raise ValueError(f"Config value for {key} must be positive.")
    return config


def weekly_target_hours(config):
    return config["full_week_hours"] * config["workload"]


def work_day_hours(config):
    return config["full_week_hours"] / 5.0


def now():
    return datetime.now(TZ)


def dt_to_s(dt):
    return dt.isoformat()


def s_to_dt(s):
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        fixed = re.sub(r"(T\d{2}:\d{2}:\d{2}):\d{2}([+-]\d{2}:\d{2})$", r"\1\2", s)
        if fixed != s:
            return datetime.fromisoformat(fixed)
        raise


def load():
    _copy_if_missing(OLD_PATH, Path(PATH))
    if not os.path.exists(PATH):
        return {"sessions": [], "_undo": []}
    with open(PATH, "r", encoding="utf-8") as f:
        db = json.load(f)
    db.setdefault("sessions", [])
    db.setdefault("_undo", [])
    return db


def save(db):
    Path(PATH).parent.mkdir(parents=True, exist_ok=True)
    tmp = PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)
    os.replace(tmp, PATH)


def snapshot(db):
    # Store everything except the undo stack itself (prevents recursive growth)
    return {k: v for k, v in db.items() if k != "_undo"}


def push_undo(db_before, db_after):
    db_after.setdefault("_undo", [])
    db_after["_undo"].append(
        json.dumps(snapshot(db_before), separators=(",", ":"), ensure_ascii=False)
    )
    if len(db_after["_undo"]) > UNDO_MAX:
        db_after["_undo"] = db_after["_undo"][-UNDO_MAX:]


def pop_undo(db):
    st = db.get("_undo") or []
    if not st:
        return None
    prev = json.loads(st.pop())
    prev.setdefault("sessions", [])
    prev["_undo"] = st
    return prev


def current_session(db):
    for s in reversed(db["sessions"]):
        if is_work_session(s) and s.get("end") is None:
            return s
    return None


def active_break(sess):
    for b in reversed(sess.get("breaks", [])):
        if b.get("end") is None:
            return b
    return None


def fmt_td(td):
    neg = td.total_seconds() < 0
    s = int(abs(td.total_seconds()))
    h, rem = divmod(s, 3600)
    m, _ = divmod(rem, 60)
    out = f"{h}h{m:02d}m" if h else f"{m}m"
    return "-" + out if neg else out


def clamp_interval(a0, a1, b0, b1):
    s = max(a0, b0)
    e = min(a1, b1)
    return (s, e) if e > s else None


class ParseError(ValueError):
    pass


def parsing_overview():
    return (
        "Formatting options:\n"
        "  timepoint: HH:MM (also HHMM, HHhMM), or signed delta like -34m / +1h32m\n"
        "  interval:  <timepoint>..<timepoint> (also <timepoint>-<timepoint>)\n"
        "  start/end: clk start [timepoint], clk end [timepoint] or clk end <date> <timepoint>\n"
        "  break:     clk break, clk break <timepoint>, clk break <start> <+/-duration>, clk break <start..end>\n"
        "  session:   clk session [DD.MM.YY] <start..end>\n"
        "             clk session [DD.MM.YY] <start..(break_start..break_end)..end>\n"
        "  pad:       clk pad [DD.MM.YY] --pad sickness|child-sickness\n"
        "  holiday:   clk holiday YYYY-MM-DD or YYYY-MM-DD..YYYY-MM-DD"
    )


def parse_signed_delta(token):
    t = token.strip().lower()
    m = re.fullmatch(r"([+-])(?:(\d+)h)?(?:(\d+)m)?", t)
    if not m or (m.group(2) is None and m.group(3) is None):
        raise ParseError(f"Invalid signed delta: {token!r}")
    h = int(m.group(2) or 0)
    mm = int(m.group(3) or 0)
    if h == 0 and mm == 0:
        raise ParseError("Duration must be non-zero.")
    delta = timedelta(hours=h, minutes=mm)
    return -delta if m.group(1) == "-" else delta


def parse_clock_time(token):
    t = token.strip().lower()
    m = re.fullmatch(r"(\d{1,2})(?::|h)?(\d{2})", t)
    if not m:
        raise ParseError(f"Invalid clock time: {token!r}")
    hh = int(m.group(1))
    mm = int(m.group(2))
    if not (0 <= hh <= 23 and 0 <= mm <= 59):
        raise ParseError(f"Invalid clock time: {token!r}")
    return hh, mm


def parse_date_token(token):
    m = re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.(\d{2,4})", token.strip())
    if not m:
        raise ParseError(f"Invalid date: {token!r}")
    d = int(m.group(1))
    mo = int(m.group(2))
    y = int(m.group(3))
    if y < 100:
        y += 2000
    try:
        return date(y, mo, d)
    except ValueError:
        raise ParseError(f"Invalid date: {token!r}")


def try_parse_date_token(token):
    try:
        return parse_date_token(token)
    except ParseError:
        return None


def parse_iso_date(token):
    try:
        return date.fromisoformat(token.strip())
    except ValueError as e:
        raise ParseError(f"Invalid ISO date: {token!r}. Expected YYYY-MM-DD.") from e


def parse_cli_date(token):
    try:
        return parse_iso_date(token)
    except ParseError:
        try:
            return parse_date_token(token)
        except ParseError as e:
            raise ParseError(
                f"Invalid date: {token!r}. Expected YYYY-MM-DD or DD.MM.YYYY."
            ) from e


def parse_holiday_spec(token):
    t = token.strip()
    range_match = re.fullmatch(r"(\d{4}-\d{2}-\d{2})(?:\.\.|->|-)(\d{4}-\d{2}-\d{2})", t)
    if range_match:
        start = parse_iso_date(range_match.group(1))
        end = parse_iso_date(range_match.group(2))
        if end < start:
            raise ParseError("Holiday range end must not be before start.")
        return start, end
    d = parse_iso_date(t)
    return d, d


def dates_between(start_day, end_day):
    d = start_day
    while d <= end_day:
        yield d
        d += timedelta(days=1)


def is_weekday(d):
    return d.weekday() < 5


def parse_timepoint(token, ref, fixed_date=None):
    t = token.strip()
    try:
        return ref + parse_signed_delta(t)
    except ParseError:
        pass
    hh, mm = parse_clock_time(t)
    day = fixed_date or ref.date()
    out = datetime.combine(day, datetime.min.time(), tzinfo=ref.tzinfo).replace(
        hour=hh, minute=mm
    )
    return out


def split_top_level(text, sep="-"):
    parts = []
    buf = []
    depth = 0
    i = 0
    while i < len(text):
        c = text[i]
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth < 0:
                raise ParseError("Unbalanced parenthesis.")
        if depth == 0 and text.startswith(sep, i):
            parts.append("".join(buf).strip())
            buf = []
            i += len(sep)
            continue
        buf.append(c)
        i += 1
    if depth != 0:
        raise ParseError("Unbalanced parenthesis.")
    parts.append("".join(buf).strip())
    return parts


def split_interval_expr(expr):
    if ".." in expr:
        return split_top_level(expr, "..")
    return split_top_level(expr, "-")


def normalize_session_spec(spec):
    return re.sub(
        r"(\d{1,2}(?::|h)?\d{2})\((.*?)\)(\d{1,2}(?::|h)?\d{2})$",
        r"\1..(\2)..\3",
        spec.strip(),
    )


def parse_interval(expr, ref, fixed_date=None):
    parts = split_interval_expr(expr)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ParseError(f"Invalid interval: {expr!r}")
    a = parse_timepoint(parts[0], ref, fixed_date=fixed_date)
    b = parse_timepoint(parts[1], ref, fixed_date=fixed_date)
    if b <= a:
        raise ParseError("Interval end must be after start.")
    return a, b


def parse_session_spec(spec, ref, fixed_date):
    spec = normalize_session_spec(spec)
    parts = split_interval_expr(spec)
    if len(parts) < 2:
        raise ParseError("Session range is missing '-'.")
    start = parse_timepoint(parts[0], ref, fixed_date=fixed_date)
    end = parse_timepoint(parts[-1], ref, fixed_date=fixed_date)
    if end <= start:
        raise ParseError("Session end must be after start.")
    breaks = []
    for part in parts[1:-1]:
        if not (part.startswith("(") and part.endswith(")")):
            raise ParseError(f"Expected break block in parentheses, got: {part!r}")
        b0, b1 = parse_interval(part[1:-1], ref, fixed_date=fixed_date)
        if b0 < start or b1 > end:
            raise ParseError("Break must be within session bounds.")
        breaks.append((b0, b1))
    return start, end, breaks


def session_bounds(sess):
    s0 = s_to_dt(sess["start"])
    s1 = s_to_dt(sess["end"]) if sess.get("end") else None
    return s0, s1


def session_kind(sess):
    if sess.get("kind"):
        return sess["kind"]
    if sess.get("start"):
        return "work"
    return "unknown"


def is_work_session(sess):
    return session_kind(sess) == "work" and bool(sess.get("start"))


def is_holiday_session(sess):
    return session_kind(sess) == "holiday" and bool(sess.get("date"))


def is_pad_session(sess):
    return session_kind(sess) == "pad" and bool(sess.get("date"))


def holiday_dates(db):
    return {sess["date"] for sess in db["sessions"] if is_holiday_session(sess)}


def pad_entries_for_day(db, d):
    iso = d.isoformat()
    return [
        sess for sess in db["sessions"] if is_pad_session(sess) and sess["date"] == iso
    ]


def pad_minutes_for_day(db, d):
    return sum(int(sess.get("minutes", 0)) for sess in pad_entries_for_day(db, d))


def pad_reasons_for_day(db, d):
    return sorted(
        {sess.get("reason", "") for sess in pad_entries_for_day(db, d) if sess.get("reason")}
    )


def break_intervals(sess, up_to):
    out = []
    for b in sess.get("breaks", []):
        b0 = s_to_dt(b["start"])
        b1 = s_to_dt(b["end"]) if b.get("end") else up_to
        if b1 > b0:
            out.append((b0, b1))
    out.sort(key=lambda x: x[0])
    merged = []
    for a, b in out:
        if not merged or a > merged[-1][1]:
            merged.append([a, b])
        else:
            merged[-1][1] = max(merged[-1][1], b)
    return [(a, b) for a, b in merged]


def worked_in_range(sess, r0, r1):
    if not is_work_session(sess):
        return timedelta(0)
    s0, s1 = session_bounds(sess)
    up_to = s1 if s1 else now()
    core = clamp_interval(s0, up_to, r0, r1)
    if not core:
        return timedelta(0)
    c0, c1 = core
    total = c1 - c0
    for b0, b1 in break_intervals(sess, up_to):
        bi = clamp_interval(b0, b1, c0, c1)
        if bi:
            total -= bi[1] - bi[0]
    return max(total, timedelta(0))


def work_total_for_day(db, d):
    n = now()
    r0 = datetime.combine(d, datetime.min.time(), tzinfo=n.tzinfo)
    r1 = r0 + timedelta(days=1)
    total = timedelta(0)
    for sess in db["sessions"]:
        if is_work_session(sess):
            total += worked_in_range(sess, r0, r1)
    return total


def credited_total_for_day(db, d):
    return work_total_for_day(db, d) + timedelta(minutes=pad_minutes_for_day(db, d))


def active_session_on_day(db, d):
    sess = current_session(db)
    if not sess:
        return False
    return s_to_dt(sess["start"]).date() <= d <= now().date()


def overlapping_work_session(db, start, end):
    for sess in db["sessions"]:
        if not is_work_session(sess):
            continue
        s0 = s_to_dt(sess["start"])
        s1 = s_to_dt(sess["end"]) if sess.get("end") else now()
        if clamp_interval(start, end, s0, s1):
            return sess
    return None


def session_interval_text(sess):
    s0 = s_to_dt(sess["start"])
    if sess.get("end"):
        s1 = s_to_dt(sess["end"])
        return f"{s0.strftime('%Y-%m-%d %H:%M')} → {s1.strftime('%H:%M')}"
    return f"{s0.strftime('%Y-%m-%d %H:%M')} → active"


def add_pad_entry(db, d, reason, config):
    target_minutes = int(round(work_day_hours(config) * 60))
    credited_minutes = int(round(credited_total_for_day(db, d).total_seconds() / 60))
    minutes = max(0, target_minutes - credited_minutes)
    if minutes == 0:
        return 0
    db["sessions"].append(
        {
            "kind": "pad",
            "date": d.isoformat(),
            "minutes": minutes,
            "reason": reason,
        }
    )
    return minutes


def daily_totals(db, days_back=7):
    n = now()
    start_day = n.date() - timedelta(days=days_back - 1)
    totals = {start_day + timedelta(days=i): timedelta(0) for i in range(days_back)}
    for d in list(totals.keys()):
        r0 = datetime.combine(d, datetime.min.time(), tzinfo=n.tzinfo)
        r1 = r0 + timedelta(days=1)
        for sess in db["sessions"]:
            if is_work_session(sess):
                totals[d] += worked_in_range(sess, r0, r1)
        totals[d] += timedelta(minutes=pad_minutes_for_day(db, d))
    return totals


def daily_totals_between(db, start_day, end_day):
    n = now()
    totals = {}
    d = start_day
    while d <= end_day:
        totals[d] = timedelta(0)
        d += timedelta(days=1)
    for d in list(totals.keys()):
        r0 = datetime.combine(d, datetime.min.time(), tzinfo=n.tzinfo)
        r1 = r0 + timedelta(days=1)
        for sess in db["sessions"]:
            if is_work_session(sess):
                totals[d] += worked_in_range(sess, r0, r1)
        totals[d] += timedelta(minutes=pad_minutes_for_day(db, d))
    return totals


def history_bounds(db):
    if not db["sessions"]:
        return None
    n = now().date()
    lo = None
    hi = None
    for sess in db["sessions"]:
        if is_holiday_session(sess) or is_pad_session(sess):
            s0 = s1 = parse_iso_date(sess["date"])
        elif is_work_session(sess):
            s0 = s_to_dt(sess["start"]).date()
            s1 = s_to_dt(sess["end"]).date() if sess.get("end") else n
        else:
            continue
        lo = s0 if lo is None or s0 < lo else lo
        hi = s1 if hi is None or s1 > hi else hi
    if lo is None or hi is None:
        return None
    return lo, hi


def median_work_window_minutes(db):
    starts = []
    ends = []
    for sess in db["sessions"]:
        if not is_work_session(sess):
            continue
        if not sess.get("end"):
            continue
        s0 = s_to_dt(sess["start"])
        s1 = s_to_dt(sess["end"])
        start_m = s0.hour * 60 + s0.minute
        end_m = s1.hour * 60 + s1.minute
        if end_m <= start_m:
            continue
        starts.append(start_m)
        ends.append(end_m)
    if not starts or not ends:
        return 9 * 60, 17 * 60
    return float(median(starts)), float(median(ends))


def day_completion_fraction(ts, start_minute, end_minute):
    if end_minute <= start_minute:
        return 1.0
    m = ts.hour * 60 + ts.minute + ts.second / 60.0
    if m <= start_minute:
        return 0.0
    if m >= end_minute:
        return 1.0
    return (m - start_minute) / (end_minute - start_minute)


def weekly_buckets(daily_rows, holidays):
    out = {}
    for row in daily_rows:
        d = row["date"]
        week_start = d - timedelta(days=d.weekday())
        bucket = out.setdefault(
            week_start,
            {
                "week_start": week_start,
                "worked": 0.0,
                "expected": 0.0,
                "cum_day_marks": [],
                "holiday_count": 0,
                "rows": [],
            },
        )
        bucket["worked"] += row["worked"]
        bucket["expected"] += row["expected"]
        bucket["cum_day_marks"].append(bucket["worked"])
        bucket["rows"].append(row)
        if d.isoformat() in holidays:
            bucket["holiday_count"] += 1
    weeks = [out[k] for k in sorted(out.keys())]
    for w in weeks:
        w["delta"] = w["worked"] - w["expected"]
    return weeks


def fmt_hours(hours):
    minutes = int(round(abs(hours) * 60))
    h, m = divmod(minutes, 60)
    if h:
        text = f"{h}h{m:02d}m"
    else:
        text = f"{m}m"
    return "-" + text if hours < 0 else text


def fmt_delta_hours(hours):
    if abs(hours) < 0.5 / 60:
        return "0m"
    sign = "+" if hours > 0 else "-"
    return sign + fmt_hours(abs(hours))


def color_delta(text, hours):
    if not sys.stdout.isatty() or hours == 0:
        return text
    color = "32" if hours > 0 else "31"
    return f"\033[{color}m{text}\033[0m"


def delta_bar(delta_hours, width=25, unit_minutes=30):
    unit_hours = unit_minutes / 60.0
    units = min(width, int(round(abs(delta_hours) / unit_hours)))
    if units == 0:
        return ""
    return ("+" if delta_hours >= 0 else "-") * units


def cumulative_bar(delta_hours, width=6, unit_minutes=30):
    unit_hours = unit_minutes / 60.0
    units = min(width, int(round(abs(delta_hours) / unit_hours)))
    if delta_hours < 0:
        return " " * (width - units) + "-" * units + "│"
    if delta_hours > 0:
        return " " * width + "│" + "+" * units
    return " " * width + "│"


def progress_bar(value, total, width=25, fill="X"):
    if total <= 0:
        filled = 0
    else:
        filled = max(0, min(width, int(round(width * value / total))))
    return "[" + fill * filled + "-" * (width - filled) + "]"


def holiday_bar(used, allowance, width=25):
    if allowance <= 0:
        filled = 0
    else:
        filled = max(0, min(width, int(round(width * used / allowance))))
    remaining = max(0, allowance - used)
    chars = ["X"] * filled + ["-"] * (width - filled)

    if filled > width / 2:
        label = str(int(used) if used == int(used) else used)
        start = max(0, (filled - len(label)) // 2)
    else:
        label = str(int(remaining) if remaining == int(remaining) else remaining)
        remaining_width = width - filled
        start = filled + max(0, (remaining_width - len(label)) // 2)

    if len(label) <= width:
        for offset, char in enumerate(label):
            index = start + offset
            if 0 <= index < width:
                chars[index] = char
    return "[" + "".join(chars) + "]"


def week_label(d, previous):
    month = d.strftime("%b")
    if previous is None or d.year != previous.year:
        return f"{d.year} {month} {d.day:02d}"
    if d.month != previous.month:
        return f"     {month} {d.day:02d}"
    return f"         {d.day:02d}"


def days_in_year(year):
    return (date(year + 1, 1, 1) - date(year, 1, 1)).days


def analysis_data(db, start_day, end_day, config):
    now_ts = now()
    median_start, median_end = median_work_window_minutes(db)
    daily = daily_totals_between(db, start_day, end_day)
    holidays = holiday_dates(db)
    day_hours = work_day_hours(config)
    threshold_hours = config["work_day_threshold_hours"]
    rows = []
    cum_worked = 0.0
    cum_expected = 0.0
    for d in sorted(daily.keys()):
        worked = daily[d].total_seconds() / 3600.0
        if d.isoformat() in holidays:
            expected = 0.0
        elif d == now_ts.date() and active_session_on_day(db, d):
            frac = day_completion_fraction(now_ts, median_start, median_end)
            expected = day_hours * frac
        elif worked > threshold_hours:
            if d == now_ts.date():
                frac = day_completion_fraction(now_ts, median_start, median_end)
                expected = day_hours * frac
            else:
                expected = day_hours
        else:
            expected = 0.0
        cum_worked += worked
        cum_expected += expected
        rows.append(
            {
                "date": d,
                "worked": worked,
                "expected": expected,
                "delta": worked - expected,
                "cum_worked": cum_worked,
                "cum_expected": cum_expected,
                "cum_delta": cum_worked - cum_expected,
                "holiday": d.isoformat() in holidays,
                "pad_reasons": pad_reasons_for_day(db, d),
            }
        )

    weeks = weekly_buckets(rows, holidays)
    total_worked = rows[-1]["cum_worked"] if rows else 0.0
    total_expected = sum(w["expected"] for w in weeks)
    return {
        "rows": rows,
        "weeks": weeks,
        "worked": total_worked,
        "expected": total_expected,
        "delta": total_worked - total_expected,
    }


def print_holiday_progress(db, start_day, end_day, allowance):
    holidays = sorted(parse_iso_date(iso) for iso in holiday_dates(db))
    used = sum(1 for d in holidays if start_day <= d <= end_day)
    n = now().date()
    year_start = date(n.year, 1, 1)
    year_elapsed = (n - year_start).days + 1
    year_total = days_in_year(n.year)
    holiday_pct = 0.0 if allowance <= 0 else used / allowance * 100
    year_pct = year_elapsed / year_total * 100
    print(f"{'Holidays':<8} {holiday_bar(used, allowance)} {holiday_pct:.0f}%")
    print(f"{'Year':<8} {progress_bar(year_elapsed, year_total, fill='=')} {year_pct:.0f}%")


def day_label(row):
    if row["holiday"]:
        return "holiday"
    if row["pad_reasons"]:
        return "pad " + ",".join(row["pad_reasons"])
    if row["expected"] > 0:
        return "work"
    if row["worked"] > 0:
        return "short"
    return "off"


def print_daily_rows(rows, unit_minutes):
    for row in rows:
        if row["worked"] == 0 and row["expected"] == 0 and not row["holiday"]:
            continue
        d = row["date"]
        bar = delta_bar(row["delta"], width=12, unit_minutes=unit_minutes)
        print(
            f"            │ {d.strftime('%a %m-%d')}  "
            f"{fmt_hours(row['worked']):>6} / {fmt_hours(row['expected']):>6}  "
            f"{fmt_delta_hours(row['delta']):>7}  {bar} {day_label(row)}"
        )


def print_text_analysis(
    db, start_day, end_day, data, config, pre_data=None, show_daily=False
):
    weekly_target = weekly_target_hours(config)
    day_hours = work_day_hours(config)
    unit_minutes = config["bar_unit_minutes"]
    print(
        f"Range: {start_day.isoformat()}..{end_day.isoformat()} | "
        f"Target: {fmt_hours(weekly_target)}/week | Day: {fmt_hours(day_hours)}"
    )
    print()
    if pre_data:
        print(
            f"Before {start_day.isoformat()}: "
            f"worked {fmt_hours(pre_data['worked'])} / expected {fmt_hours(pre_data['expected'])} "
            f"({fmt_delta_hours(pre_data['delta'])})"
        )
    print_holiday_progress(db, start_day, end_day, config["holiday_allowance"])
    print("\nWeeks:")
    cumulative_delta = 0.0
    previous_label_day = None
    visible_weeks = [
        w for w in data["weeks"] if not (w["worked"] == 0 and w["expected"] == 0 and w["holiday_count"] == 0)
    ]
    for index, w in enumerate(visible_weeks):
        cumulative_delta += w["delta"]
        label_day = max(w["week_start"], start_day)
        label = week_label(label_day, previous_label_day)
        previous_label_day = label_day
        bar = delta_bar(w["delta"], width=8, unit_minutes=unit_minutes)
        expected_days = int(round(w["expected"] / day_hours)) if day_hours else 0
        day_label_text = "day" if expected_days == 1 else "days"
        final_delta = ""
        if index == len(visible_weeks) - 1:
            final_delta = " " + color_delta(f"({fmt_delta_hours(cumulative_delta)})", cumulative_delta)
        print(
            f"  {label} │ "
            f"{fmt_hours(w['worked']):>6} : {expected_days:g} {day_label_text:<4}  "
            f"{fmt_delta_hours(w['delta']):>7}  "
            f"{bar:<8} {cumulative_bar(cumulative_delta, unit_minutes=unit_minutes)}{final_delta}"
        )
        if show_daily:
            print_daily_rows(w["rows"], unit_minutes)
    print(
        f"\n  {'Total':<11} │ {fmt_hours(data['worked']):>6} : "
        f"{int(round(data['expected'] / day_hours)) if day_hours else 0:g} days"
    )


def current_state_text(db):
    sess = current_session(db)
    if not sess:
        return "State: idle"
    n = now()
    s0 = s_to_dt(sess["start"])
    up_to = n
    br = active_break(sess)
    gross = up_to - s0
    net = worked_in_range(sess, s0, up_to)
    brtxt = "ON BREAK" if br else "working"
    return f"State: {brtxt} | started {s0.strftime('%Y-%m-%d %H:%M')} | gross {fmt_td(gross)} | net {fmt_td(net)}"


def print_report(db):
    config = load_config()
    print(current_state_text(db))
    totals = daily_totals(db, 7 + 1)
    holidays = holiday_dates(db)
    days = sorted(totals.keys())
    wk = sum((totals[d] for d in days[:-1]), timedelta(0))
    print("\nPrevious 8 days:")
    for d in days:
        label = d.strftime("%a %Y-%m-%d")
        suffix = " holiday" if d.isoformat() in holidays else ""
        pad_reasons = pad_reasons_for_day(db, d)
        if pad_reasons:
            suffix += " pad " + ",".join(pad_reasons)
        print(f"  {label}: {fmt_td(totals[d])}{suffix}")

    weekly_target = weekly_target_hours(config)
    holiday_count = sum(1 for d in days[:-1] if d.isoformat() in holidays)
    target = timedelta(hours=max(0.0, weekly_target - holiday_count * work_day_hours(config)))
    print(
        f"  Total (excl. today): {fmt_td(wk)} ({(wk - target).total_seconds() // 60:+n}m)"
    )


def cmd_report(_args):
    db = load()
    print_report(db)
    return 0


def cmd_analyse(args):
    db = load()
    config = load_config()
    bounds = history_bounds(db)
    if bounds is None:
        print("No sessions found. Add work logs first.")
        return 1

    auto_start, auto_end = bounds
    now_ts = now()
    start_day = parse_iso_date(args.start_date) if args.start_date else date(now_ts.year, 1, 1)
    end_day = max(auto_end, now_ts.date())
    if start_day > end_day:
        print("Start date must not be after latest logged day.", file=sys.stderr)
        return 2

    data = analysis_data(db, start_day, end_day, config)
    pre_data = None
    if auto_start < start_day:
        pre_data = analysis_data(db, auto_start, start_day - timedelta(days=1), config)
    print_text_analysis(
        db,
        start_day,
        end_day,
        data,
        config,
        pre_data,
        show_daily=args.daily,
    )
    return 0


def cmd_edit(args):
    subprocess.run(["open", PATH])
    return 0


def cmd_start(args):
    db = load()
    if current_session(db):
        print("Already running. Use: clk end/stop", file=sys.stderr)
        print(current_state_text(db))
        return 1
    db_before = json.loads(json.dumps(db))
    t0 = now() if args.when is None else parse_timepoint(args.when, now())
    db["sessions"].append(
        {"kind": "work", "start": dt_to_s(t0), "end": None, "breaks": []}
    )
    push_undo(db_before, db)
    save(db)
    print(f"Started: {t0.strftime('%Y-%m-%d %H:%M')}")
    print(current_state_text(db))
    return 0


def cmd_end(args):
    db = load()
    sess = current_session(db)
    if not sess:
        print("No active session. Use: clk start", file=sys.stderr)
        print(current_state_text(db))
        return 1
    db_before = json.loads(json.dumps(db))
    n = now()
    parts = args.parts
    if len(parts) > 2:
        raise ParseError("Usage: clk end [timepoint] or clk end <date> <timepoint>")
    if len(parts) == 2:
        if args.yesterday:
            raise ParseError("Use either an explicit date or --yesterday, not both.")
        day = parse_cli_date(parts[0])
        parse_clock_time(parts[1])
        t1 = parse_timepoint(parts[1], n, fixed_date=day)
    elif len(parts) == 1:
        day = n.date() - timedelta(days=1) if args.yesterday else None
        t1 = parse_timepoint(parts[0], n, fixed_date=day)
    elif args.yesterday:
        day = n.date() - timedelta(days=1)
        t1 = datetime.combine(day, n.timetz())
    else:
        t1 = n
    b = active_break(sess)
    if b:
        b["end"] = dt_to_s(t1)
    s0 = s_to_dt(sess["start"])
    if t1 <= s0:
        print("End must be after start.", file=sys.stderr)
        print(current_state_text(db))
        return 1
    sess["end"] = dt_to_s(t1)
    push_undo(db_before, db)
    save(db)
    print(f"Ended:   {t1.strftime('%Y-%m-%d %H:%M')}")
    print(current_state_text(db))
    return 0


def cmd_break(args):
    db = load()
    sess = current_session(db)
    if not sess:
        print("No active session. Use: clk start", file=sys.stderr)
        print(current_state_text(db))
        return 1

    n = now()
    values = args.values or []
    db_before = json.loads(json.dumps(db))
    if len(values) == 0:
        b = active_break(sess)
        if not b:
            t0 = n
            sess.setdefault("breaks", []).append({"start": dt_to_s(t0), "end": None})
            push_undo(db_before, db)
            save(db)
            print(f"Break started: {t0.strftime('%Y-%m-%d %H:%M')}")
            print(current_state_text(db))
            return 0
        t1 = n
        if t1 <= s_to_dt(b["start"]):
            raise ValueError("Break end must be after break start.")
        b["end"] = dt_to_s(t1)
        push_undo(db_before, db)
        save(db)
        print(f"Break ended:   {t1.strftime('%Y-%m-%d %H:%M')}")
        print(current_state_text(db))
        return 0

    if len(values) == 1:
        raw = values[0]
        if (".." in raw or "-" in raw) and not raw.startswith(("-", "+")):
            startp, endp = parse_interval(raw, n)
        else:
            try:
                delta = parse_signed_delta(raw)
            except ParseError:
                t0 = parse_timepoint(raw, n)
                b = active_break(sess)
                if b:
                    if t0 <= s_to_dt(b["start"]):
                        raise ValueError("Break end must be after break start.")
                    b["end"] = dt_to_s(t0)
                    push_undo(db_before, db)
                    save(db)
                    print(f"Break ended:   {t0.strftime('%Y-%m-%d %H:%M')}")
                    print(current_state_text(db))
                    return 0
                if t0 > n:
                    raise ValueError("Break start must not be in the future.")
                sess.setdefault("breaks", []).append({"start": dt_to_s(t0), "end": None})
                push_undo(db_before, db)
                save(db)
                print(f"Break started: {t0.strftime('%Y-%m-%d %H:%M')}")
                print(current_state_text(db))
                return 0
            else:
                b = active_break(sess)
                if b:
                    t0 = n + delta
                    startp, endp = (t0, n) if t0 <= n else (n, t0)
                    b["start"] = dt_to_s(startp)
                    b["end"] = dt_to_s(endp)
                    push_undo(db_before, db)
                    save(db)
                    print(
                        f"Break set:     {startp.strftime('%Y-%m-%d %H:%M')} → {endp.strftime('%H:%M')} (net {fmt_td(endp - startp)})"
                    )
                    print(current_state_text(db))
                    return 0
                t0 = n + delta
                startp, endp = (t0, n) if t0 <= n else (n, t0)
    elif len(values) == 2:
        startp = parse_timepoint(values[0], n)
        dur = parse_signed_delta(values[1])
        endp = startp + dur
        if endp < startp:
            startp, endp = endp, startp
    else:
        raise ParseError("clk break accepts at most two arguments.")

    sess.setdefault("breaks", []).append(
        {"start": dt_to_s(startp), "end": dt_to_s(endp)}
    )
    push_undo(db_before, db)
    save(db)
    print(
        f"Break added:   {startp.strftime('%Y-%m-%d %H:%M')} → {endp.strftime('%H:%M')} (net {fmt_td(endp - startp)})"
    )
    print(current_state_text(db))
    return 0


def cmd_session(args):
    db = load()
    config = load_config()
    parts = args.parts
    if len(parts) == 1:
        explicit_day = try_parse_date_token(parts[0])
        if explicit_day:
            if args.yesterday:
                raise ParseError("Use either an explicit date or --yesterday, not both.")
            if not args.pad:
                raise ParseError("Date-only add requires --pad.")
            db_before = json.loads(json.dumps(db))
            pad_minutes = add_pad_entry(db, explicit_day, args.pad, config)
            if not pad_minutes:
                print(f"Pad skipped:   {explicit_day.isoformat()} already at full work day")
                print(current_state_text(db))
                return 0
            push_undo(db_before, db)
            save(db)
            print(
                f"Pad added:     {explicit_day.isoformat()} {fmt_td(timedelta(minutes=pad_minutes))} ({args.pad})"
            )
            print(current_state_text(db))
            return 0
        day = now().date() - timedelta(days=1) if args.yesterday else now().date()
        spec = parts[0]
    elif len(parts) == 2:
        if args.yesterday:
            raise ParseError("Use either an explicit date or --yesterday, not both.")
        day = parse_date_token(parts[0])
        spec = parts[1]
    else:
        raise ParseError("Usage: clk session [DD.MM.YY] <start..end>")

    s0, s1, brks = parse_session_spec(spec, now(), fixed_date=day)
    overlap = overlapping_work_session(db, s0, s1)
    if overlap:
        print(
            f"Session overlaps existing session: {session_interval_text(overlap)}",
            file=sys.stderr,
        )
        print(current_state_text(db))
        return 1

    db_before = json.loads(json.dumps(db))
    db["sessions"].append(
        {
            "kind": "work",
            "start": dt_to_s(s0),
            "end": dt_to_s(s1),
            "breaks": [{"start": dt_to_s(a), "end": dt_to_s(b)} for a, b in brks],
        }
    )
    pad_minutes = add_pad_entry(db, day, args.pad, config) if args.pad else 0
    push_undo(db_before, db)
    save(db)
    print(f"Session added: {s0.strftime('%Y-%m-%d %H:%M')} → {s1.strftime('%H:%M')}")
    if brks:
        print(f"Breaks: {len(brks)}")
    if args.pad:
        if pad_minutes:
            print(f"Pad added:     {fmt_td(timedelta(minutes=pad_minutes))} ({args.pad})")
        else:
            print(f"Pad skipped:   {day.isoformat()} already at full work day")
    print(current_state_text(db))
    return 0


def cmd_pad(args):
    db = load()
    config = load_config()
    if args.date and args.yesterday:
        raise ParseError("Use either an explicit date or --yesterday, not both.")
    day = parse_date_token(args.date) if args.date else now().date()
    if args.yesterday:
        day = now().date() - timedelta(days=1)

    db_before = json.loads(json.dumps(db))
    minutes = add_pad_entry(db, day, args.pad, config)
    if not minutes:
        print(f"Pad skipped: {day.isoformat()} already at full work day")
        print(current_state_text(db))
        return 0
    push_undo(db_before, db)
    save(db)
    print(f"Pad added:   {day.isoformat()} {fmt_td(timedelta(minutes=minutes))} ({args.pad})")
    print(current_state_text(db))
    return 0


def cmd_holiday(args):
    db = load()
    start_day, end_day = parse_holiday_spec(args.date_or_range)
    existing = holiday_dates(db)
    to_add = []
    skipped_weekend = []
    skipped_duplicate = []

    for d in dates_between(start_day, end_day):
        iso = d.isoformat()
        if not is_weekday(d):
            skipped_weekend.append(iso)
            continue
        if iso in existing:
            skipped_duplicate.append(iso)
            continue
        to_add.append(iso)
        existing.add(iso)

    if not to_add:
        if skipped_weekend:
            print("No holidays added; skipped weekend date(s): " + ", ".join(skipped_weekend))
        elif skipped_duplicate:
            print("No holidays added; already present: " + ", ".join(skipped_duplicate))
        else:
            print("No holidays added.")
        return 0

    db_before = json.loads(json.dumps(db))
    for iso in to_add:
        db["sessions"].append({"kind": "holiday", "date": iso})
    push_undo(db_before, db)
    save(db)

    print("Holiday added: " + ", ".join(to_add))
    if skipped_weekend:
        print("Skipped weekend date(s): " + ", ".join(skipped_weekend))
    if skipped_duplicate:
        print("Skipped duplicate date(s): " + ", ".join(skipped_duplicate))
    return 0


def cmd_undo(_args):
    db = load()
    prev = pop_undo(db)
    if not prev:
        print("Nothing to undo.")
        print(current_state_text(db))
        return 1
    save(prev)
    print("Undone.")
    print(current_state_text(prev))
    return 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in {"start", "end", "stop", "break", "pause"}:
        rest = argv[1:]
        signed_delta = re.compile(r"[+-](?:(\d+)h)?(?:(\d+)m)?")
        if (
            rest
            and "--" not in rest
            and "-h" not in rest
            and "--help" not in rest
            and any(signed_delta.fullmatch(x.lower()) for x in rest)
        ):
            options = [
                x
                for x in rest
                if x.startswith("--") and not signed_delta.fullmatch(x.lower())
            ]
            values = [x for x in rest if x not in options]
            argv = [argv[0], *options, "--", *values]

    p = argparse.ArgumentParser(prog="clk", add_help=True)
    sub = p.add_subparsers(dest="cmd")

    pt = sub.add_parser("edit", help="edit directly the json log file")
    pt.set_defaults(fn=cmd_edit)

    ps = sub.add_parser("start", help="start a session")
    ps.add_argument("when", nargs="?", help="timepoint: HH:MM or signed delta (+/-)")
    ps.set_defaults(fn=cmd_start)

    pe = sub.add_parser(
        "end", aliases=["stop"], help="end the current session (stop alias)"
    )
    pe.add_argument(
        "parts",
        nargs="*",
        metavar="date/timepoint",
        help="[timepoint] or <YYYY-MM-DD|DD.MM.YYYY> <HH:MM>",
    )
    pe.add_argument(
        "--yesterday",
        action="store_true",
        help="interpret clock time as yesterday instead of today",
    )
    pe.set_defaults(fn=cmd_end)

    pb = sub.add_parser(
        "break",
        aliases=["pause"],
        help="toggle break or add break via timepoint/range",
    )
    pb.add_argument(
        "values",
        nargs="*",
        help="none, <timepoint>, <start..end>, or <start> <+/-duration>",
    )
    pb.set_defaults(fn=cmd_break)

    pss = sub.add_parser(
        "session", aliases=["add"], help="add a complete session range"
    )
    pss.add_argument(
        "parts",
        nargs="+",
        help="session [DD.MM.YY] <start..end> or <start..(break..break)..end>",
    )
    pss.add_argument(
        "--yesterday",
        action="store_true",
        help="interpret clock times as yesterday instead of today",
    )
    pss.add_argument(
        "--pad",
        choices=PAD_REASONS,
        help="pad the day to a full work day for the given reason",
    )
    pss.set_defaults(fn=cmd_session)

    pp = sub.add_parser("pad", help="pad a day to a full work day")
    pp.add_argument("date", nargs="?", help="date: DD.MM.YY (defaults to today)")
    pp.add_argument(
        "--yesterday",
        action="store_true",
        help="pad yesterday instead of today",
    )
    pp.add_argument(
        "--pad",
        choices=PAD_REASONS,
        required=True,
        help="pad reason",
    )
    pp.set_defaults(fn=cmd_pad)

    ph = sub.add_parser("holiday", help="mark weekday holiday date(s)")
    ph.add_argument(
        "date_or_range",
        help="YYYY-MM-DD or inclusive YYYY-MM-DD..YYYY-MM-DD (weekdays only)",
    )
    ph.set_defaults(fn=cmd_holiday)

    pu = sub.add_parser("undo", help="undo last change")
    pu.set_defaults(fn=cmd_undo)

    pr = sub.add_parser("report", help="report (same as running clk with no args)")
    pr.set_defaults(fn=cmd_report)

    pa = sub.add_parser(
        "analyse",
        aliases=["analyze", "stats"],
        help="analyse work history",
    )
    pa.add_argument(
        "--start-date",
        help="analysis start date (YYYY-MM-DD). Defaults to Jan 1 of the current year.",
    )
    pa.add_argument(
        "--summary-only",
        action="store_true",
        help="kept for compatibility; analyse is always text-only",
    )
    pa.add_argument(
        "--daily",
        action="store_true",
        help="include daily worked/expected rows under each week",
    )
    pa.set_defaults(fn=cmd_analyse)

    args = p.parse_args(argv)
    if args.cmd is None:
        return cmd_report(args)
    try:
        return args.fn(args)
    except ParseError as e:
        print(str(e), file=sys.stderr)
        print(parsing_overview(), file=sys.stderr)
        db = load()
        print(current_state_text(db))
        return 2
    except ValueError as e:
        print(str(e), file=sys.stderr)
        db = load()
        print(current_state_text(db))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
