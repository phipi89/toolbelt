import pathlib
import subprocess

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.document import Document
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.shortcuts import CompleteStyle
from prompt_toolkit.styles import Style


def interactive(items):
    items = list(items)
    completer = WordCompleter(items, ignore_case=True, match_middle=True)
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
    def _(event):
        b = event.app.current_buffer
        accept_best_completion(b)
        event.app.exit(result=("PARENT", b.text))

    result = session.prompt("> ")
    return ("OPEN", result)


def main():
    items = []
    for base in (pathlib.Path("/"), pathlib.Path.home()):
        app_dir = base / "Applications"
        items += list(app_dir.glob("*.app"))
        items += list(app_dir.glob("*/*.app"))

    apps = {p.stem: p for p in items}

    action, selection = interactive(apps.keys())
    if selection not in apps:
        raise SystemExit(f"Not found: {selection}")

    path = apps[selection]
    target = path.parent if action == "PARENT" else path
    subprocess.run(["open", target.as_posix()])


if __name__ == "__main__":
    main()
