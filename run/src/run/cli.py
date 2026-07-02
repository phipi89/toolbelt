import json
import pathlib
import subprocess
import time

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.document import Document
from prompt_toolkit.filters import Condition
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.shortcuts import CompleteStyle
from prompt_toolkit.styles import Style

header = r"""
                         .-------.
                         | >RUN_ |
                       __|_______|__
                      |  _________  |
                      `-/.:::::::.\-'
                       `-----------'
"""


def _query_current_space_windows():
    result = subprocess.run(
        ["yabai", "-m", "query", "--windows", "--space"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []
    try:
        windows = json.loads(result.stdout)
    except json.JSONDecodeError:
        return []
    return [win for win in windows if _is_selectable_window(win)][:9]


def _is_selectable_window(win):
    return bool(
        win.get("is-visible")
        and not win.get("is-minimized")
        and not win.get("is-native-fullscreen")
        and win.get("has-ax-reference")
        and win.get("role") == "AXWindow"
        and win.get("subrole") == "AXStandardWindow"
        and win.get("id")
    )


def _window_label(win):
    app = str(win.get("app") or "")
    title = str(win.get("title") or "")
    if title:
        return f"{app:<18} {title}"
    return app


def _focus_window(win):
    space_id = win.get("space")
    window_id = win.get("id")
    if space_id is not None:
        subprocess.run(["yabai", "-m", "space", "--focus", str(space_id)], check=False)
    subprocess.run(["yabai", "-m", "window", str(window_id), "--focus"], check=False)


def interactive(items, windows=None):
    items = list(items)
    windows = list(windows or [])
    show_windows = bool(windows)
    display_dict = {item: f"{item} " for item in items}  # add trailing padding
    completer = WordCompleter(
        items, display_dict=display_dict, ignore_case=True, match_middle=True
    )
    kb = KeyBindings()
    style = Style.from_dict(
        {
            "completion-menu": "bg:#222222 #dddddd",
            "completion-menu.completion.current": "bg:#00afff #000000",
            "completion-menu.meta": "bg:#222222 #888888",
            "scrollbar.background": "bg:#444444",
            "scrollbar.button": "bg:#888888",
        }
    )

    def bottom_toolbar():
        if not show_windows:
            return ""
        return "\n".join(
            f"{index} {_window_label(win)}" for index, win in enumerate(windows, start=1)
        )

    session = PromptSession(
        completer=completer,
        complete_while_typing=True,
        key_bindings=kb,
        complete_style=CompleteStyle.MULTI_COLUMN,
        style=style,
        bottom_toolbar=bottom_toolbar,
    )

    def hide_windows(event):
        nonlocal show_windows
        if show_windows:
            show_windows = False
            event.app.invalidate()

    def accept_best_completion(buf):
        cs = buf.complete_state
        if cs and cs.current_completion:
            buf.apply_completion(cs.current_completion)
            return
        doc = Document(text=buf.text, cursor_position=buf.cursor_position)
        comps = list(completer.get_completions(doc, None))
        if comps:
            buf.apply_completion(comps[0])

    @kb.add("enter")
    def _(event):
        b = event.app.current_buffer
        accept_best_completion(b)
        b.validate_and_handle()

    @kb.add("escape", "enter")
    def _(event):
        b = event.app.current_buffer
        accept_best_completion(b)
        event.app.exit(result=("NEW_WINDOW", b.text))

    @kb.add("escape")
    def _(event):
        hide_windows(event)

    @kb.add("1")
    @kb.add("2")
    @kb.add("3")
    @kb.add("4")
    @kb.add("5")
    @kb.add("6")
    @kb.add("7")
    @kb.add("8")
    @kb.add("9")
    def _(event):
        if show_windows and event.data and event.data.isdigit():
            index = int(event.data) - 1
            if index < len(windows):
                event.app.exit(result=("WINDOW", windows[index]))
                return
            hide_windows(event)
            event.app.current_buffer.insert_text(event.data)
            return

        buf = event.app.current_buffer
        # If the completion menu is active, use the number to select
        if buf.complete_state and buf.complete_state.completions:
            index = int(event.data) - 1
            if index < len(buf.complete_state.completions):
                buf.apply_completion(buf.complete_state.completions[index])
                buf.validate_and_handle()
                return
        # Otherwise, just type the number normally
        if event.data:
            buf.insert_text(event.data)

    @kb.add(Keys.Any, filter=Condition(lambda: show_windows))
    def _(event):
        hide_windows(event)
        if event.data and event.data.isprintable():
            event.app.current_buffer.insert_text(event.data)

    result = session.prompt(" > ")
    if isinstance(result, tuple):
        return result
    return ("OPEN", result)


def main():

    print(header)

    items = []
    for base in (pathlib.Path("/"), pathlib.Path("/System"), pathlib.Path.home()):
        app_dir = base / "Applications"
        items += list(app_dir.glob("*.app"))
        items += list(app_dir.glob("*/*.app"))

    apps = {p.stem: p for p in items}

    exclude_words = ["install", "dienst", "service", "entfernen"]

    def include(word):
        return not any([e in word.lower() for e in exclude_words])

    app_names = [name for name in apps.keys() if include(name)]

    action, selection = interactive(app_names, _query_current_space_windows())
    if action == "WINDOW":
        _focus_window(selection)
        return

    if selection not in apps:
        raise SystemExit(f"Not found: {selection}")

    path = apps[selection]
    if action == "PARENT":
        target = path.parent
        subprocess.run(["open", target.as_posix()])
    else:
        app_name = path.stem
        script_name = "new_window.sh" if action == "NEW_WINDOW" else "manage.sh"
        window_manager = pathlib.Path.home() / "toolbelt" / "display" / script_name
        completed_process = subprocess.run([window_manager.as_posix(), app_name])
        if completed_process.returncode:
            print(f"failed to open {app_name}")
            time.sleep(5)
            subprocess.run(["open", path.as_posix()])


if __name__ == "__main__":
    main()
