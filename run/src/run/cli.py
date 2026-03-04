import pathlib
import subprocess
import time

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.document import Document
from prompt_toolkit.key_binding import KeyBindings
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


def interactive(items):
    items = list(items)
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
    session = PromptSession(
        completer=completer,
        complete_while_typing=True,
        key_bindings=kb,
        complete_style=CompleteStyle.MULTI_COLUMN,
        style=style,
    )

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

    @kb.add("escape", "enter")  # Cmd+Enter in many macOS terminals
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
        buf = event.app.current_buffer
        # If the completion menu is active, use the number to select
        if buf.complete_state and buf.complete_state.completions:
            index = int(event.data) - 1
            if index < len(buf.complete_state.completions):
                buf.apply_completion(buf.complete_state.completions[index])
                buf.validate_and_handle()
                return
        # Otherwise, just type the number normally
        buf.insert_text(event.data)

    result = session.prompt(" > ")
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

    action, selection = interactive(app_names)
    if selection not in apps:
        raise SystemExit(f"Not found: {selection}")

    path = apps[selection]
    if action == "PARENT":
        target = path.parent
        subprocess.run(["open", target.as_posix()])
    else:
        app_name = path.stem
        window_manager = (
            pathlib.Path.home() / "toolbelt" / "window_management" / "manage_windows.sh"
        )
        completed_process = subprocess.run([window_manager.as_posix(), app_name])
        if completed_process.returncode:
            print(f"failed to open {app_name}")
            time.sleep(5)
            subprocess.run(["open", target.as_posix()])


if __name__ == "__main__":
    main()
