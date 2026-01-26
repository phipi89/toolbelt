import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta

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


def parse_start_arg(arg, base):
    if arg is None:
        return base - timedelta(minutes=1)
    m = re.fullmatch(r"([+-]?\d+)", arg.strip())
    if m:
        mins = int(m.group(1))
        return base + timedelta(minutes=mins)
    a = arg.strip()
    m = re.fullmatch(r"(\d{1,2})(?::|h)?(\d{2})", a)
    if not m:
        raise ValueError(
            f"Unrecognized time format: {arg!r} (use -7, 0705, 07:05, 07h05)"
        )
    hh = int(m.group(1))
    mm = int(m.group(2))
    if not (0 <= hh <= 23 and 0 <= mm <= 59):
        raise ValueError(f"Invalid time: {arg!r}")
    cand = base.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if cand > base + timedelta(minutes=2):
        cand -= timedelta(days=1)
    return cand


def parse_end_arg(arg, base):
    if arg is None:
        return base + timedelta(minutes=1)
    m = re.fullmatch(r"([+-]?\d+)", arg.strip())
    if m:
        mins = int(m.group(1))
        return base + timedelta(minutes=mins)
    raise ValueError(
        "end/stop only supports minute offsets like: clk end or clk end +5 or clk end -2"
    )


def parse_duration(s):
    if s is None:
        return None
    t = s.strip().lower()
    if not t:
        return None
    m = re.fullmatch(r"(?:(\d+)h)?(?:(\d+)m)?", t)
    if not m or (m.group(1) is None and m.group(2) is None):
        raise ValueError("Invalid duration. Examples: 15m, 2h, 1h5m")
    h = int(m.group(1) or 0)
    mm = int(m.group(2) or 0)
    if h == 0 and mm == 0:
        raise ValueError("Duration must be > 0")
    return timedelta(hours=h, minutes=mm)


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
    totals = daily_totals(db, 7)
    days = sorted(totals.keys())
    wk = sum((totals[d] for d in days), timedelta(0))
    print("\nLast 7 days:")
    for d in days:
        label = d.strftime("%a %Y-%m-%d")
        print(f"  {label}: {fmt_td(totals[d])}")
    print(f"  Total: {fmt_td(wk)}")


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
    t0 = parse_start_arg(args.when, now())
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
    t1 = parse_end_arg(args.when, now())
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
    dur = parse_duration(args.duration) if args.duration else None
    db_before = json.loads(json.dumps(db))

    if dur:
        endp = n  # + timedelta(minutes=1)
        startp = endp - dur  # - timedelta(minutes=1)
        sess.setdefault("breaks", []).append(
            {"start": dt_to_s(startp), "end": dt_to_s(endp)}
        )
        push_undo(db_before, db)
        save(db)
        print(
            f"Break added:   {startp.strftime('%Y-%m-%d %H:%M')} → {endp.strftime('%H:%M')} (net {fmt_td(dur)})"
        )
        print(current_state_text(db))
        return 0

    b = active_break(sess)
    if not b:
        t0 = n + timedelta(minutes=1)
        sess.setdefault("breaks", []).append({"start": dt_to_s(t0), "end": None})
        push_undo(db_before, db)
        save(db)
        print(f"Break started: {t0.strftime('%Y-%m-%d %H:%M')}")
        print(current_state_text(db))
        return 0
    else:
        t1 = n - timedelta(minutes=1)
        b["end"] = dt_to_s(t1)
        push_undo(db_before, db)
        save(db)
        print(f"Break ended:   {t1.strftime('%Y-%m-%d %H:%M')}")
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
    ps.add_argument(
        "when", nargs="?", help="(default: 1 min ago) or -7 or 0705/07:05/07h05"
    )
    ps.set_defaults(fn=cmd_start)

    pe = sub.add_parser(
        "end", aliases=["stop"], help="end the current session (stop alias)"
    )
    pe.add_argument("when", nargs="?", help="(default: in 1 min) or +5 or -2")
    pe.set_defaults(fn=cmd_end)

    pb = sub.add_parser(
        "break",
        aliases=["pause"],
        help="toggle break (pause alias); or add break duration ending now",
    )
    pb.add_argument(
        "duration",
        nargs="?",
        help="e.g. 15m, 1h5m (adds a break ending now, with 1-min padding)",
    )
    pb.set_defaults(fn=cmd_break)

    pu = sub.add_parser("undo", help="undo last change")
    pu.set_defaults(fn=cmd_undo)

    pr = sub.add_parser("report", help="report (same as running clk with no args)")
    pr.set_defaults(fn=cmd_report)

    args = p.parse_args(argv)
    if args.cmd is None:
        return cmd_report(args)
    try:
        return args.fn(args)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        db = load()
        print(current_state_text(db))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
