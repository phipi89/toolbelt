"""
A vibe coded cli tool to keep track of my working hours.
Be sure your system backs up `~/.clk_log.json`.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import date, datetime, timedelta

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None

PATH = os.path.expanduser("~/.clk_log.json")
UNDO_MAX = 5


def tzlocal():
    if ZoneInfo is None:
        return None
    try:
        import time

        return ZoneInfo(time.tzname[0]) if time.tzname and time.tzname[0] else None
    except Exception:
        return None


TZ = tzlocal()


def now():
    return datetime.now(TZ)


def dt_to_s(dt):
    return dt.isoformat()


def s_to_dt(s):
    return datetime.fromisoformat(s)


def load():
    if not os.path.exists(PATH):
        return {"sessions": [], "_undo": []}
    with open(PATH, "r", encoding="utf-8") as f:
        db = json.load(f)
    db.setdefault("sessions", [])
    db.setdefault("_undo", [])
    return db


def save(db):
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
        if s.get("end") is None:
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
        "  interval:  <timepoint>--<timepoint>\n"
        "  start/end: clk start [timepoint], clk end [timepoint]\n"
        "  break:     clk break, clk break <timepoint>, clk break <start> <+/-duration>, clk break <start--end>\n"
        "  session:   clk session [DD.MM.YY] <start--end>\n"
        "             clk session [DD.MM.YY] <start--(break_start--break_end)--end>"
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


def split_top_level(text, sep="--"):
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


def parse_interval(expr, ref, fixed_date=None):
    parts = split_top_level(expr, "--")
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ParseError(f"Invalid interval: {expr!r}")
    a = parse_timepoint(parts[0], ref, fixed_date=fixed_date)
    b = parse_timepoint(parts[1], ref, fixed_date=fixed_date)
    if b <= a:
        raise ParseError("Interval end must be after start.")
    return a, b


def parse_session_spec(spec, ref, fixed_date):
    parts = split_top_level(spec, "--")
    if len(parts) < 2:
        raise ParseError("Session range is missing '--'.")
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


def daily_totals(db, days_back=7):
    n = now()
    start_day = n.date() - timedelta(days=days_back - 1)
    totals = {start_day + timedelta(days=i): timedelta(0) for i in range(days_back)}
    for d in list(totals.keys()):
        r0 = datetime.combine(d, datetime.min.time(), tzinfo=n.tzinfo)
        r1 = r0 + timedelta(days=1)
        for sess in db["sessions"]:
            totals[d] += worked_in_range(sess, r0, r1)
    return totals


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
    print(current_state_text(db))
    totals = daily_totals(db, 7 + 1)
    days = sorted(totals.keys())
    wk = sum((totals[d] for d in days[:-1]), timedelta(0))
    print("\nPrevious 8 days:")
    for d in days:
        label = d.strftime("%a %Y-%m-%d")
        print(f"  {label}: {fmt_td(totals[d])}")

    target = timedelta(hours=42 * 0.8)
    print(
        f"  Total (excl. today): {fmt_td(wk)} ({(wk - target).total_seconds() // 60:+n}m)"
    )


def cmd_report(_args):
    db = load()
    print_report(db)
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
    db["sessions"].append({"start": dt_to_s(t0), "end": None, "breaks": []})
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
    t1 = now() if args.when is None else parse_timepoint(args.when, now())
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
        if "--" in raw:
            startp, endp = parse_interval(raw, n)
        else:
            try:
                delta = parse_signed_delta(raw)
            except ParseError:
                t0 = parse_timepoint(raw, n)
                startp, endp = (t0, n) if t0 <= n else (n, t0)
            else:
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
    parts = args.parts
    if len(parts) == 1:
        day = now().date()
        spec = parts[0]
    elif len(parts) == 2:
        day = parse_date_token(parts[0])
        spec = parts[1]
    else:
        raise ParseError("Usage: clk session [DD.MM.YY] <start--end>")

    if current_session(db) and day == now().date():
        print(
            "Already running. End the active session before adding a complete session for today.",
            file=sys.stderr,
        )
        print(current_state_text(db))
        return 1

    s0, s1, brks = parse_session_spec(spec, now(), fixed_date=day)
    db_before = json.loads(json.dumps(db))
    db["sessions"].append(
        {
            "start": dt_to_s(s0),
            "end": dt_to_s(s1),
            "breaks": [{"start": dt_to_s(a), "end": dt_to_s(b)} for a, b in brks],
        }
    )
    push_undo(db_before, db)
    save(db)
    print(f"Session added: {s0.strftime('%Y-%m-%d %H:%M')} → {s1.strftime('%H:%M')}")
    if brks:
        print(f"Breaks: {len(brks)}")
    print(current_state_text(db))
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
    pe.add_argument("when", nargs="?", help="timepoint: HH:MM or signed delta (+/-)")
    pe.set_defaults(fn=cmd_end)

    pb = sub.add_parser(
        "break",
        aliases=["pause"],
        help="toggle break or add break via timepoint/range",
    )
    pb.add_argument(
        "values",
        nargs="*",
        help="none, <timepoint>, <start--end>, or <start> <+/-duration>",
    )
    pb.set_defaults(fn=cmd_break)

    pss = sub.add_parser("session", help="add a complete session range")
    pss.add_argument(
        "parts",
        nargs="+",
        help="session [DD.MM.YY] <start--end> or <start--(break--break)--end>",
    )
    pss.set_defaults(fn=cmd_session)

    pu = sub.add_parser("undo", help="undo last change")
    pu.set_defaults(fn=cmd_undo)

    pr = sub.add_parser("report", help="report (same as running clk with no args)")
    pr.set_defaults(fn=cmd_report)

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
