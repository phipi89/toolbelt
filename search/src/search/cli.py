import argparse
import fnmatch
import os
import subprocess
import sys
import threading
from datetime import datetime, timezone
from math import exp
from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.shortcuts import CompleteStyle
from prompt_toolkit.styles import Style

from . import mdfind


_IGNORED_SEARCH_DIRS = {
    ".cache",
    ".git",
    ".hg",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".svn",
    ".tox",
    ".venv",
    "__pycache__",
    "dist-packages",
    "node_modules",
    "old",
    "site-packages",
    "venv",
}


def _env_int(name, default):
    return int(os.environ.get(name, str(default)))


def _env_float(name, default):
    return float(os.environ.get(name, str(default)))


def _format_relative_time(timestamp, now=None):
    if timestamp is None:
        return "unknown"
    now = now or datetime.now(timezone.utc)
    delta_seconds = max(0, int((now - timestamp).total_seconds()))
    if delta_seconds < 60:
        return "just now"
    if delta_seconds < 3600:
        minutes = delta_seconds // 60
        unit = "minute" if minutes == 1 else "minutes"
        return f"{minutes} {unit} ago"
    if delta_seconds < 86400:
        hours = delta_seconds // 3600
        unit = "hour" if hours == 1 else "hours"
        return f"{hours} {unit} ago"
    days = delta_seconds // 86400
    unit = "day" if days == 1 else "days"
    return f"{days} {unit} ago"


def _format_index_status(meta):
    timestamp = meta.get("freshest_item_at")
    if timestamp is None:
        return "freshest item: unknown"
    local_timestamp = timestamp.astimezone()
    when = local_timestamp.strftime("%Y-%m-%d %H:%M")
    age = _format_relative_time(timestamp)
    return f"freshest item: {age}" # skiping when


def _index_summary(entries, meta):
    return (
        f"Indexed {len(entries)} items "
        f"(source={meta['source']}, recent_days={meta['recent_days']}, "
        f"total_matches={meta['total_matches']}, {_format_index_status(meta)})"
    )


def _index_stats(entries, meta):
    return [
        "", # padding line
        f"indexed items: {len(entries)}",
        f"source:        {meta['source']}",
        f"recent days:   {meta['recent_days']}",
        f"total matches: {meta['total_matches']}",
        _format_index_status(meta),
    ]


def print_title(entries, meta):
    title = r"""
                   _____
                  /     \______
                 |  .-""-.     |
                 | / sea  \    |
                 | \  rch /    |
                 |  '-..;\     |
                 |_______\\____|
                          \\
""".strip("\n").splitlines()
    stats = _index_stats(entries, meta)
    gap = "        "
    print()
    for i in range(max(len(title), len(stats))):
        left = title[i] if i < len(title) else ""
        right = stats[i - 1] if 0 < i <= len(stats) else ""
        print(f"{left:<36}{gap}{right}")
    print()


def _tokens(query):
    return [part for part in query.lower().split() if part]


def _is_subsequence(needle, haystack):
    i = 0
    for ch in haystack:
        if i < len(needle) and needle[i] == ch:
            i += 1
    return i == len(needle)


def text_score(path, query):
    parts = _tokens(query)
    if not parts:
        return 0.0

    path_l = path.lower()
    name = path_l.rsplit("/", 1)[-1]
    components = set(path_l.split("/"))
    score = 0.0

    for token in parts:
        if token in components:
            score += 120.0
        elif token in name:
            score += 85.0
        elif token in path_l:
            score += 55.0
        elif _is_subsequence(token, path_l):
            score += 25.0
        else:
            return -1.0

    score += max(0.0, 20.0 - (len(path) / 40.0))
    return score


def recency_score(last_used, now):
    if not last_used:
        return 0.0
    if last_used.tzinfo is None:
        last_used = last_used.replace(tzinfo=timezone.utc)
    age_days = max(0.0, (now - last_used).total_seconds() / 86400.0)
    return 100.0 * exp(-age_days / 30.0)


def highlight_text(text, query):
    parts = _tokens(query)
    if not parts:
        return text

    lower = text.lower()
    marks = [False] * len(text)
    for token in parts:
        start = 0
        while token and start < len(lower):
            idx = lower.find(token, start)
            if idx < 0:
                break
            for i in range(idx, min(idx + len(token), len(marks))):
                marks[i] = True
            start = idx + len(token)

    out = []
    segment = ""
    active = None
    for i, ch in enumerate(text):
        mark = marks[i]
        if active is None:
            active = mark
            segment = ch
            continue
        if mark == active:
            segment += ch
            continue
        out.append(("class:match" if active else "", segment))
        segment = ch
        active = mark
    if segment:
        out.append(("class:match" if active else "", segment))
    return FormattedText(out)


def display_path(path, base_path):
    if base_path and path.startswith(base_path):
        rel = path[len(base_path) :].lstrip("/")
        return rel or "."
    return path


def _starts_path_mode(query):
    return query.startswith("/") or query.startswith("~/")


def _path_completion_entries(query):
    expanded = os.path.expanduser(query)
    has_trailing_sep = expanded.endswith(os.sep)
    directory = expanded if has_trailing_sep else os.path.dirname(expanded)
    prefix = "" if has_trailing_sep else os.path.basename(expanded)
    if not directory:
        directory = os.sep if expanded.startswith(os.sep) else "."

    try:
        names = os.listdir(directory)
    except OSError:
        return []

    matches = []
    prefix_l = prefix.lower()
    home = str(Path.home())
    for name in names:
        if name.startswith(".") and not prefix.startswith("."):
            continue
        if prefix and not name.lower().startswith(prefix_l):
            continue
        path = os.path.join(directory, name)
        is_dir = os.path.isdir(path)
        completion_path = path + os.sep if is_dir else path
        if query.startswith("~") and completion_path.startswith(home):
            completion_path = "~" + completion_path[len(home) :]
        matches.append((not is_dir, name.lower(), completion_path))
    matches.sort()
    return [path for _, _, path in matches]


def _quoted_find_pattern(query):
    if not query.startswith('"') or len(query) < 2 or not query.endswith('"'):
        return None
    pattern = query[1:-1].strip()
    return pattern or None


def _is_ignored_search_dir(name):
    if name in _IGNORED_SEARCH_DIRS:
        return True
    return name.startswith("python") and any(ch.isdigit() for ch in name)


def _is_ignored_search_path(path):
    return any(_is_ignored_search_dir(part) for part in Path(path).parts)


def _entry_recency(entry, fallback):
    last_used = entry.get("last_used")
    if last_used is None:
        return -fallback
    return last_used.timestamp()


def _mtime(path):
    try:
        return os.path.getmtime(path)
    except OSError:
        return 0


def _indexed_search_roots(entries, max_roots=2000):
    home = str(Path.home())
    roots = []
    seen = set()
    recent_entries = sorted(
        enumerate(entries),
        key=lambda item: _entry_recency(item[1], item[0]),
        reverse=True,
    )
    for _, entry in recent_entries:
        path = entry["path"]
        if _is_ignored_search_path(path):
            continue
        root = path if os.path.isdir(path) else os.path.dirname(path)
        if not root or root == home or not os.path.isdir(root):
            continue
        real_root = os.path.realpath(root)
        if real_root in seen:
            continue
        if any(os.path.commonpath([existing, real_root]) == existing for existing in seen):
            continue
        seen.add(real_root)
        roots.append(root)
        if len(roots) >= max_roots:
            break
    return roots


def _iter_find_completion_entries(
    query, entries, max_results, progress=None, should_cancel=None
):
    pattern = _quoted_find_pattern(query)
    if not pattern:
        return

    seen = set()
    found = 0
    pattern_l = pattern.lower()
    for root in _indexed_search_roots(entries):
        if should_cancel and should_cancel():
            return
        for dirpath, dirnames, filenames in os.walk(root):
            if should_cancel and should_cancel():
                return
            dirnames[:] = [
                name
                for name in dirnames
                if not _is_ignored_search_dir(name)
                and not (name.startswith(".") and not pattern.startswith("."))
            ]
            dirnames.sort(
                key=lambda name: _mtime(os.path.join(dirpath, name)), reverse=True
            )
            filenames.sort(
                key=lambda name: _mtime(os.path.join(dirpath, name)), reverse=True
            )
            if progress:
                progress(dirpath)
            for name in [*dirnames, *filenames]:
                if should_cancel and should_cancel():
                    return
                if not fnmatch.fnmatch(name.lower(), pattern_l):
                    continue
                path = os.path.join(dirpath, name)
                real_path = os.path.realpath(path)
                if real_path in seen:
                    continue
                seen.add(real_path)
                found += 1
                yield path
                if found >= max_results:
                    return


def _promote_directory_match(query, ranked_entries):
    if not query.endswith("/"):
        return ranked_entries

    target_name = query[:-1].strip().rsplit("/", 1)[-1].lower()
    if not target_name:
        return ranked_entries

    for i, entry in enumerate(ranked_entries):
        path = entry["path"]
        if not os.path.isdir(path):
            continue
        if os.path.basename(path).lower() != target_name:
            continue
        if i == 0:
            return ranked_entries
        return [entry, *ranked_entries[:i], *ranked_entries[i + 1 :]]

    inferred = {}
    order = {}
    for i, entry in enumerate(ranked_entries):
        path = Path(entry["path"])
        candidates = []
        if path.name.lower() == target_name:
            candidates.append(path)
        candidates.extend(parent for parent in path.parents if parent.name.lower() == target_name)

        for candidate in candidates:
            candidate_str = str(candidate)
            if not os.path.isdir(candidate_str):
                continue
            inferred[candidate_str] = inferred.get(candidate_str, 0) + 1
            order.setdefault(candidate_str, i)

    if not inferred:
        return ranked_entries

    best = sorted(
        inferred,
        key=lambda item: (-inferred[item], order[item], len(item)),
    )[0]
    synthetic = {"path": best, "last_used": None}
    return [synthetic, *ranked_entries]


class RecencyFuzzyCompleter(Completer):
    def __init__(self, entries, max_results=40, default_base=None):
        self.entries = entries
        self._paths = {entry["path"] for entry in entries}
        self._lock = threading.Lock()
        self.max_results = max_results
        self.current_base_path = default_base or ""
        self.current_query = ""
        self.is_searching = False
        self.invalidate_ui = None
        self._find_cache = {}
        self._cancel_search = threading.Event()

    def update_entries(self, entries):
        with self._lock:
            self.entries = entries
            self._paths = {entry["path"] for entry in entries}

    def has_path(self, path):
        with self._lock:
            expanded = os.path.expanduser(path)
            return path in self._paths or os.path.exists(expanded)

    def _entries_snapshot(self):
        with self._lock:
            return list(self.entries)

    def set_search_progress(self, path):
        self.current_base_path = path
        if self.invalidate_ui:
            self.invalidate_ui()

    def cancel_search(self):
        self._cancel_search.set()

    def ranked(self, query):
        score_query = query[:-1] if query.endswith("/") else query
        now = datetime.now(timezone.utc)
        ranked = []
        for entry in self._entries_snapshot():
            tscore = text_score(entry["path"], score_query)
            if tscore < 0:
                continue
            total = tscore + recency_score(entry["last_used"], now)
            ranked.append((total, entry))
        ranked.sort(key=lambda item: item[0], reverse=True)
        ranked_entries = [entry for _, entry in ranked]
        promoted = _promote_directory_match(query, ranked_entries)
        return promoted[: self.max_results]

    def _common_base(self, ranked_entries):
        paths = [entry["path"] for entry in ranked_entries]
        if not paths:
            return self.current_base_path
        try:
            return os.path.commonpath(paths)
        except ValueError:
            return self.current_base_path

    def get_completions(self, document, _complete_event):
        query = document.text_before_cursor.strip()
        if _starts_path_mode(query):
            self.current_query = query
            self.current_base_path = os.path.dirname(os.path.expanduser(query)) or os.sep
            for path in _path_completion_entries(query):
                yield Completion(
                    path,
                    start_position=-len(document.text_before_cursor),
                    display=path,
                )
            return

        if query.startswith('"'):
            self.current_query = query
            self.current_base_path = str(Path.home())
            pattern = _quoted_find_pattern(query)
            if pattern is None:
                return
            if query in self._find_cache:
                paths = self._find_cache[query]
                for path in paths:
                    yield Completion(
                        path,
                        start_position=-len(document.text_before_cursor),
                        display=highlight_text(
                            path,
                            query[1:-1],
                        ),
                    )
            else:
                paths = []
                self.cancel_search()
                self._cancel_search = threading.Event()
                cancel_search = self._cancel_search
                self.is_searching = True
                self.set_search_progress(str(Path.home()))
                entries = self._entries_snapshot()
                try:
                    for path in _iter_find_completion_entries(
                        query,
                        entries,
                        self.max_results,
                        progress=self.set_search_progress,
                        should_cancel=cancel_search.is_set,
                    ):
                        paths.append(path)
                        yield Completion(
                            path,
                            start_position=-len(document.text_before_cursor),
                            display=highlight_text(
                                path,
                                query[1:-1],
                            ),
                        )
                    if not cancel_search.is_set():
                        self._find_cache[query] = paths
                finally:
                    self.is_searching = False
                    if self.invalidate_ui:
                        self.invalidate_ui()
            return

        self.cancel_search()
        self.is_searching = False
        ranked_entries = self.ranked(query)
        self.current_query = query
        self.current_base_path = self._common_base(ranked_entries)

        for entry in ranked_entries:
            path = entry["path"]
            shown = display_path(path, self.current_base_path)
            yield Completion(
                path,
                start_position=-len(document.text_before_cursor),
                display=highlight_text(shown, query),
            )


def _start_refresh_thread(refresh_interval, load_entries, completer, stop_refresh):
    if refresh_interval <= 0:
        return

    def refresh_worker():
        while not stop_refresh.wait(refresh_interval):
            try:
                fresh_entries = load_entries()
            except Exception as exc:
                print(f"[index] Refresh failed: {exc}", file=sys.stderr)
                continue
            completer.update_entries(fresh_entries)

    thread = threading.Thread(target=refresh_worker, name="find-refresh", daemon=True)
    thread.start()


def interactive(entries, refresh_interval, load_entries):
    home = str(Path.home())
    completer = RecencyFuzzyCompleter(entries, default_base=home)
    kb = KeyBindings()
    stop_refresh = threading.Event()
    reveal_action = [False]

    style = Style.from_dict(
        {
            "completion-menu": "bg:#222222 #dddddd",
            "completion-menu.completion.current": "bg:#00afff #000000",
            "match": "bold #ffd75f",
            "scrollbar.background": "bg:#444444",
            "scrollbar.button": "bg:#888888",
        }
    )

    def toolbar_text():
        if completer.is_searching:
            return f" ⏳ searching in {completer.current_base_path or home}"
        label = "Search" if completer.current_query.startswith('"') else "Base path"
        return f" {label}: {completer.current_base_path or home}"

    session = PromptSession(
        completer=completer,
        complete_while_typing=True,
        complete_in_thread=True,
        key_bindings=kb,
        complete_style=CompleteStyle.COLUMN,
        style=style,
        bottom_toolbar=toolbar_text,
    )
    completer.invalidate_ui = session.app.invalidate

    def _completions_for_buffer(buffer):
        doc = Document(text=buffer.text, cursor_position=buffer.cursor_position)
        return list(completer.get_completions(doc, None))

    def accept_best(buffer):
        state = buffer.complete_state
        if state and state.current_completion:
            buffer.apply_completion(state.current_completion)
            return True
        completions = _completions_for_buffer(buffer)
        if completions:
            buffer.apply_completion(completions[0])
            return True
        return False

    @kb.add("tab")
    def _(event):
        buffer = event.app.current_buffer
        query = buffer.text.strip()
        if query.startswith('"'):
            state = buffer.complete_state
            if state and state.current_completion:
                completer.cancel_search()
                buffer.apply_completion(state.current_completion)
                event.app.exit(result=buffer.text)
            elif _quoted_find_pattern(query):
                buffer.start_completion(select_first=False)
            return
        if accept_best(buffer):
            buffer.start_completion(select_first=False)

    @kb.add("enter")
    def _(event):
        buffer = event.app.current_buffer
        query = buffer.text.strip()
        reveal = query.endswith("#RevealFile")
        if reveal:
            buffer.text = query[: -len("#RevealFile")].strip()
        if query.startswith('"'):
            state = buffer.complete_state
            if state and state.current_completion:
                completer.cancel_search()
                buffer.apply_completion(state.current_completion)
                if reveal:
                    reveal_action[0] = True
                event.app.exit(result=buffer.text)
                return
            if _quoted_find_pattern(query):
                buffer.start_completion(select_first=False)
                return
        if accept_best(buffer):
            completer.cancel_search()
        if reveal:
            reveal_action[0] = True
        event.app.exit(result=buffer.text)

    def _check_reveal(buffer):
        text = buffer.text.strip()
        if text.endswith("#RevealFile"):
            buffer.text = text[: -len("#RevealFile")].strip()
            if accept_best(buffer):
                completer.cancel_search()
            reveal_action[0] = True
            session.app.exit(result=buffer.text)

    def _setup_reveal_hook():
        session.app.current_buffer.on_text_changed += _check_reveal

    _start_refresh_thread(refresh_interval, load_entries, completer, stop_refresh)

    try:
        result = session.prompt("> ", pre_run=_setup_reveal_hook)
    finally:
        stop_refresh.set()
    return result, completer.has_path(result), reveal_action[0]


def _load_entries(
    mdfind_module, index_limit, recent_days, with_meta=False, compute_total=False
):
    return mdfind_module.get_home_indexed_items(
        limit=index_limit,
        recent_days=recent_days,
        with_meta=with_meta,
        compute_total=compute_total,
    )


def _config():
    return {
        "index_limit": _env_int("FIND_INDEX_LIMIT", 80000),
        "recent_days": _env_int("FIND_RECENT_DAYS", 730),
        "refresh_interval": _env_float("FIND_REFRESH_SECONDS", 60),
    }


def _open_in_finder(path):
    path = os.path.expanduser(path)
    subprocess.run(["open", path], check=False)


def _reveal_in_finder(path):
    path = os.path.expanduser(path)
    if os.path.isdir(path):
        subprocess.run(["open", path], check=False)
    else:
        subprocess.run(["open", "-R", path], check=False)


def _cd_target(path):
    path = os.path.expanduser(path)
    if os.path.isdir(path):
        return os.path.abspath(path)
    return os.path.abspath(os.path.dirname(path))


def _resize_window():
    script = Path(__file__).resolve().parents[3] / "display" / "move" / "center.sh"
    if script.exists():
        subprocess.run([str(script)], check=False)


def _run_checked(cmd):
    print("$ " + " ".join(cmd), flush=True)
    result = subprocess.run(cmd, check=False)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def _rebuild_spotlight_index(target):
    target = os.path.expanduser(target)
    _run_checked(["sudo", "mdutil", "-i", "off", target])
    _run_checked(["sudo", "mdutil", "-E", target])
    _run_checked(["sudo", "mdutil", "-i", "on", target])
    _run_checked(["mdutil", "-s", target])


def _select_path(args, show_title=True):
    if args.resize_window:
        _resize_window()

    config = _config()
    entries, meta = _load_entries(
        mdfind,
        config["index_limit"],
        config["recent_days"],
        with_meta=True,
        compute_total=False,
    )
    if args.refresh:
        print(_index_summary(entries, meta))
        return None, False

    if show_title:
        print_title(entries, meta)

    selection, found, reveal = interactive(
        entries,
        refresh_interval=config["refresh_interval"],
        load_entries=lambda: _load_entries(
            mdfind,
            config["index_limit"],
            config["recent_days"],
        ),
    )
    if not found:
        raise SystemExit(f"Not found: {selection}")
    return selection, reveal


def main():
    parser = argparse.ArgumentParser(
        description="Interactive recency-biased file finder"
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Refresh the file index and exit without launching the interactive prompt",
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Rebuild the Spotlight index and exit",
    )
    parser.add_argument(
        "--rebuild-target",
        default="/System/Volumes/Data",
        help="Path to rebuild with mdutil when using --rebuild",
    )
    parser.add_argument(
        "--resize_window",
        "--resize-window",
        action="store_true",
        help="Resize and center the search window before starting",
    )
    args = parser.parse_args()

    if args.rebuild:
        _rebuild_spotlight_index(args.rebuild_target)
        return

    selection, reveal = _select_path(args)
    if selection is None:
        return
    if reveal:
        _reveal_in_finder(selection)
    else:
        _open_in_finder(selection)
    print(selection)


def goto_main():
    parser = argparse.ArgumentParser(description="Interactive directory picker for shell cd")
    parser.add_argument("--refresh", action="store_true", help="Refresh the file index and exit")
    parser.add_argument(
        "--resize_window",
        "--resize-window",
        action="store_true",
        help="Resize and center the search window before starting",
    )
    parser.add_argument("--result-file", required=True, help="File to write the selected cd target to")
    args = parser.parse_args()

    selection, _reveal = _select_path(args, show_title=False)
    if selection is None:
        return
    target = _cd_target(selection)
    with open(args.result_file, "w", encoding="utf-8") as f:
        f.write(target)


if __name__ == "__main__":
    main()
