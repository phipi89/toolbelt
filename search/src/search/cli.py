import argparse
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


def _env_int(name, default):
    return int(os.environ.get(name, str(default)))


def _env_float(name, default):
    return float(os.environ.get(name, str(default)))


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

    def update_entries(self, entries):
        with self._lock:
            self.entries = entries
            self._paths = {entry["path"] for entry in entries}

    def has_path(self, path):
        with self._lock:
            return path in self._paths or os.path.exists(path)

    def _entries_snapshot(self):
        with self._lock:
            return list(self.entries)

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

    style = Style.from_dict(
        {
            "completion-menu": "bg:#222222 #dddddd",
            "completion-menu.completion.current": "bg:#00afff #000000",
            "match": "bold #ffd75f",
            "scrollbar.background": "bg:#444444",
            "scrollbar.button": "bg:#888888",
        }
    )

    session = PromptSession(
        completer=completer,
        complete_while_typing=True,
        key_bindings=kb,
        complete_style=CompleteStyle.COLUMN,
        style=style,
        bottom_toolbar=lambda: f" Base path: {completer.current_base_path or home}",
    )

    def accept_best(buffer):
        state = buffer.complete_state
        if state and state.current_completion:
            buffer.apply_completion(state.current_completion)
            return
        doc = Document(text=buffer.text, cursor_position=buffer.cursor_position)
        completions = list(completer.get_completions(doc, None))
        if completions:
            buffer.apply_completion(completions[0])

    @kb.add("enter")
    def _(event):
        buffer = event.app.current_buffer
        accept_best(buffer)
        event.app.exit(result=buffer.text)

    _start_refresh_thread(refresh_interval, load_entries, completer, stop_refresh)

    try:
        result = session.prompt("> ")
    finally:
        stop_refresh.set()
    return result, completer.has_path(result)


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
        "recent_days": _env_int("FIND_RECENT_DAYS", 360),
        "refresh_interval": _env_float("FIND_REFRESH_SECONDS", 60),
    }


def _open_in_finder(path):
    if os.path.isdir(path):
        subprocess.run(["open", path], check=False)
    else:
        subprocess.run(["open", "-R", path], check=False)


def main():
    parser = argparse.ArgumentParser(
        description="Interactive recency-biased file finder"
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Refresh the file index and exit without launching the interactive prompt",
    )
    args = parser.parse_args()

    config = _config()
    entries, meta = _load_entries(
        mdfind,
        config["index_limit"],
        config["recent_days"],
        with_meta=True,
        compute_total=True,
    )
    print(
        f"Indexed {len(entries)} items "
        f"(source={meta['source']}, recent_days={meta['recent_days']}, total_matches={meta['total_matches']})"
    )
    if args.refresh:
        return

    selection, found = interactive(
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
    _open_in_finder(selection)
    print(selection)


if __name__ == "__main__":
    main()
