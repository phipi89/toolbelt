import datetime as dt
import os
import subprocess
from pathlib import Path

_ATTR_SEPARATOR = "   kMDItemLastUsedDate = "
_IGNORED_DIRECTORIES = {"node_modules", "__pycache__", "build", "dist"}


def _excluded(path, root):
    try:
        parts = Path(path).relative_to(root).parts
    except ValueError:
        return True
    return (
        bool(parts and parts[0] == "Library")
        or any(part.startswith(".") for part in parts)
        or any(part in _IGNORED_DIRECTORIES for part in parts)
    )


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
        path, value = record.rsplit(_ATTR_SEPARATOR, 1)
        try:
            last_used = dt.datetime.fromisoformat(value.strip())
        except ValueError:
            continue
        out.append({"path": path, "last_used": last_used})
    out.sort(key=lambda item: item["last_used"], reverse=True)
    return out


def _spotlight_items(root, days=360, limit=None):
    seconds = days * 24 * 60 * 60
    cutoff = f"$time.now(-{seconds})"
    query = f"kMDItemLastUsedDate > {cutoff}"
    cmd = [
        "mdfind",
        "-0",
        "-onlyin",
        str(root),
    ]
    cmd.extend(["-attr", "kMDItemLastUsedDate"])
    cmd.append(query)
    items = [
        item
        for item in _parse_mdfind_output(_run(cmd))
        if not _excluded(item["path"], root)
    ]
    if limit is None:
        return items
    return items[:limit]


def _with_limit(items, limit):
    if limit is None:
        return items
    return items[:limit]


def _expand_neighbors(items, root, limit=None):
    """Add siblings and the immediate contents of their subdirectories."""
    merged = {item["path"]: item for item in items}
    directories = {os.path.dirname(path) for path in merged}
    scanned = set()
    for depth in range(2):
        children = set()
        for directory in sorted(directories):
            if (
                directory in scanned
                or _excluded(directory, root)
                or os.path.islink(directory)
            ):
                continue
            scanned.add(directory)
            try:
                with os.scandir(directory) as entries:
                    for entry in entries:
                        if _excluded(entry.path, root):
                            continue
                        if entry.path not in merged:
                            if limit is not None and len(merged) >= limit:
                                return list(merged.values())
                            merged[entry.path] = {"path": entry.path, "last_used": None}
                        if depth == 0 and entry.is_dir(follow_symlinks=False):
                            children.add(entry.path)
            except OSError:
                continue
        directories = children
    return list(merged.values())


def _scan_fallback(root, recent_days=360, limit=None):
    cutoff = dt.datetime.now(dt.UTC).timestamp() - (recent_days * 86400)
    out = []
    for dirpath, dirnames, filenames in os.walk(root, topdown=True):
        dirnames[:] = [
            name for name in dirnames if not _excluded(Path(dirpath) / name, root)
        ]
        for name in dirnames:
            _append_entry(Path(dirpath) / name, out, cutoff)
        for name in filenames:
            path = Path(dirpath) / name
            if not _excluded(path, root):
                _append_entry(path, out, cutoff)
    out.sort(key=lambda item: item["last_used"], reverse=True)
    return _with_limit(out, limit)


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
            "last_used": dt.datetime.fromtimestamp(ts, tz=dt.UTC),
        }
    )
    return True


def get_home_indexed_items(
    limit=None, root=None, recent_days=360, with_meta=False, compute_total=False
):
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

    seed_count = len(items)
    if source == "spotlight":
        selected = _expand_neighbors(_with_limit(items, limit), home, limit=limit)
        source = "spotlight + neighbors"
    else:
        selected = _with_limit(items, limit)
    if with_meta:
        return selected, {
            "source": source,
            "recent_days": recent_days,
            "total_matches": total_matches,
            "limit": limit,
            "returned": len(selected),
            "seed_count": seed_count,
            "neighbor_count": sum(item["last_used"] is None for item in selected),
            "freshest_item_at": items[0]["last_used"] if items else None,
        }
    return selected


def main():
    for item in get_home_indexed_items(limit=20):
        print(f"{item['last_used']!s:<25} {item['path']}")


if __name__ == "__main__":
    main()
