import datetime as dt
import os
import subprocess
from pathlib import Path


_ATTR_SEPARATOR = "   kMDItemLastUsedDate = "


def _run(cmd):
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""
    return result.stdout


def _parse_mdfind_output(raw):
    out = []
    for record in raw.split("\0"):
        if not record or _ATTR_SEPARATOR not in record:
            continue
        path, date_str = record.rsplit(_ATTR_SEPARATOR, 1)
        try:
            last_used = dt.datetime.strptime(date_str.strip(), "%Y-%m-%d %H:%M:%S %z")
        except ValueError:
            continue
        out.append({"path": path, "last_used": last_used})
    out.sort(key=lambda item: item["last_used"], reverse=True)
    return out


def _spotlight_items(root, days=360, limit=None):
    seconds = days * 24 * 60 * 60
    query = f"kMDItemLastUsedDate > $time.now(-{seconds})"
    cmd = [
        "mdfind",
        "-0",
        "-onlyin",
        str(root),
        "-attr",
        "kMDItemLastUsedDate",
        query,
    ]
    items = _parse_mdfind_output(_run(cmd))
    if limit is None:
        return items
    return items[:limit]


def _with_limit(items, limit):
    if limit is None:
        return items
    return items[:limit]


def _scan_fallback(root, recent_days=360, limit=None):
    cutoff = dt.datetime.now(dt.timezone.utc).timestamp() - (recent_days * 86400)
    out = []
    for dirpath, dirnames, filenames in os.walk(root, topdown=True):
        for name in dirnames:
            if _append_entry(Path(dirpath) / name, out, cutoff):
                if limit is not None and len(out) >= limit:
                    out.sort(key=lambda item: item["last_used"], reverse=True)
                    return out
        for name in filenames:
            if _append_entry(Path(dirpath) / name, out, cutoff):
                if limit is not None and len(out) >= limit:
                    out.sort(key=lambda item: item["last_used"], reverse=True)
                    return out
    out.sort(key=lambda item: item["last_used"], reverse=True)
    return out


def _append_entry(path, out, cutoff):
    try:
        st = path.stat()
    except OSError:
        return False
    ts = st.st_atime if st.st_atime > 0 else st.st_mtime
    if ts < cutoff:
        return False
    out.append(
        {
            "path": str(path),
            "last_used": dt.datetime.fromtimestamp(ts, tz=dt.timezone.utc),
        }
    )
    return True


def get_home_indexed_items(limit=None, root=None, recent_days=360, with_meta=False, compute_total=False):
    home = Path(root).expanduser() if root else Path.home()
    spotlight_limit = None if compute_total else limit
    items = _spotlight_items(home, days=recent_days, limit=spotlight_limit)
    source = "spotlight"
    if items:
        total_matches = len(items)
    else:
        source = "fallback"
        fallback_limit = None if compute_total else limit
        items = _scan_fallback(home, recent_days=recent_days, limit=fallback_limit)
        total_matches = len(items)

    selected = _with_limit(items, limit)
    if with_meta:
        return selected, {
            "source": source,
            "recent_days": recent_days,
            "total_matches": total_matches,
            "limit": limit,
            "returned": len(selected),
        }
    return selected


def main():
    for item in get_home_indexed_items(limit=20):
        print(f"{item['last_used']:<25} {item['path']}")


if __name__ == "__main__":
    main()
